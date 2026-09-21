"""Video analysis — deterministic measurements + AI interpretation.

Deterministic (FFmpeg/FFprobe):
    duration, frame count, scene changes, cut count, audio presence,
    audio loudness, frame timestamps

AI (vision model):
    content interpretation from frames — what's happening, who's visible,
    location, emotion, text overlay content

The LLM never measures video structure. FFmpeg measures. LLM interprets.

All blocking work (subprocess, whisper) runs via asyncio.to_thread()
so it doesn't block the event loop.
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import analyze_images, complete, CostTier, LLMResponse
from app.schemas.ai_outputs import VisualAnalysis, DraftReviewOutput

logger = logging.getLogger(__name__)

T_Schema = type[BaseModel]


def _parse_llm_json(text: str) -> dict:
    """Extract JSON from LLM response, handling code fences."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    return json.loads(text)

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB


@dataclass
class VideoMeasurements:
    """Deterministic measurements from FFmpeg — not AI-derived."""
    duration: float
    fps: float
    width: int
    height: int
    has_audio: bool
    audio_codec: str | None
    cut_count: int
    scene_change_timestamps: list[float]
    frame_count: int


def _probe_video(video_path: str) -> dict:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", video_path,
        ],
        capture_output=True, text=True,
    )
    return json.loads(result.stdout) if result.stdout else {}


def _measure_video_sync(video_path: str) -> VideoMeasurements:
    """Extract deterministic video properties using FFprobe/FFmpeg (blocking)."""
    probe = _probe_video(video_path)

    video_stream = next(
        (s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {}
    )
    audio_stream = next(
        (s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), None
    )
    fmt = probe.get("format", {})

    duration = float(video_stream.get("duration") or fmt.get("duration") or "0")
    fps_parts = video_stream.get("r_frame_rate", "30/1").split("/")
    fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 and fps_parts[1] != "0" else 30.0
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    frame_count = int(video_stream.get("nb_frames", 0)) or int(duration * fps)

    scene_timestamps = _detect_scene_changes_sync(video_path)

    return VideoMeasurements(
        duration=duration,
        fps=fps,
        width=width,
        height=height,
        has_audio=audio_stream is not None,
        audio_codec=audio_stream.get("codec_name") if audio_stream else None,
        cut_count=len(scene_timestamps),
        scene_change_timestamps=scene_timestamps,
        frame_count=frame_count,
    )


async def measure_video(video_path: str) -> VideoMeasurements:
    return await asyncio.to_thread(_measure_video_sync, video_path)


def _detect_scene_changes_sync(video_path: str, threshold: float = 0.3) -> list[float]:
    """Use FFmpeg scene detection to find cuts/transitions (blocking)."""
    result = subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-vf", f"select='gt(scene,{threshold})',showinfo",
            "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    timestamps = []
    for line in result.stderr.split("\n"):
        if "pts_time:" in line:
            try:
                pts_str = line.split("pts_time:")[1].split()[0]
                timestamps.append(float(pts_str))
            except (IndexError, ValueError):
                continue
    return timestamps


def _extract_hook_frames_sync(video_path: str, duration: float) -> list[tuple[float, bytes]]:
    """Extract frames with heavy weighting on the first 3 seconds (blocking)."""
    hook_times = [0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0]
    hook_times = [t for t in hook_times if t < duration]

    body_count = max(3, min(8, int(duration / 5)))
    body_start = 3.0 if duration > 4.0 else duration * 0.5
    if body_count > 0 and duration > body_start:
        body_interval = (duration - body_start) / (body_count + 1)
        body_times = [body_start + body_interval * (i + 1) for i in range(body_count)]
    else:
        body_times = []

    all_times = hook_times + body_times

    frames = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, t in enumerate(all_times):
            out = f"{tmpdir}/frame_{i:03d}.jpg"
            subprocess.run(
                [
                    "ffmpeg", "-ss", str(t), "-i", video_path,
                    "-frames:v", "1", "-q:v", "2", "-y", out,
                ],
                capture_output=True,
            )
            p = Path(out)
            if p.exists():
                frames.append((t, p.read_bytes()))
    return frames


async def extract_hook_frames(video_path: str, duration: float) -> list[tuple[float, bytes]]:
    return await asyncio.to_thread(_extract_hook_frames_sync, video_path, duration)


def _extract_scene_change_frames_sync(
    video_path: str, scene_timestamps: list[float]
) -> list[tuple[float, bytes]]:
    """Extract a frame at each scene change point (blocking)."""
    frames = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, t in enumerate(scene_timestamps[:12]):
            out = f"{tmpdir}/scene_{i:03d}.jpg"
            subprocess.run(
                [
                    "ffmpeg", "-ss", str(t), "-i", video_path,
                    "-frames:v", "1", "-q:v", "2", "-y", out,
                ],
                capture_output=True,
            )
            p = Path(out)
            if p.exists():
                frames.append((t, p.read_bytes()))
    return frames


async def extract_scene_change_frames(
    video_path: str, scene_timestamps: list[float]
) -> list[tuple[float, bytes]]:
    return await asyncio.to_thread(_extract_scene_change_frames_sync, video_path, scene_timestamps)


async def analyze_visual_features(
    hook_frames: list[tuple[float, bytes]],
    scene_frames: list[tuple[float, bytes]],
    measurements: VideoMeasurements,
) -> dict:
    """Send ALL relevant frames to vision model for content interpretation."""
    all_frames = hook_frames + scene_frames
    if not all_frames:
        return {"error": "No frames to analyze"}

    frame_descriptions = ", ".join(
        f"Frame {i+1} at {t:.1f}s" for i, (t, _) in enumerate(all_frames)
    )

    prompt = f"""You are analyzing {len(all_frames)} frames from a short-form video by fitness/lifestyle creator Kobby Cooper.

Frame timestamps: {frame_descriptions}
Frames 1-{len(hook_frames)} are from the opening (hook). Remaining frames are from scene changes throughout the video.

KNOWN FACTS (measured, do not contradict):
- Duration: {measurements.duration:.1f}s
- Resolution: {measurements.width}x{measurements.height}
- Has audio track: {measurements.has_audio}
- Detected cuts/transitions: {measurements.cut_count}
- Scene change timestamps: {[f'{t:.1f}s' for t in measurements.scene_change_timestamps]}

Analyze ONLY what you can see in the frames:

1. face_visible_first_frame: Is a face visible in Frame 1?
2. face_visible_first_3s: Is a face visible in any frame before 3s?
3. body_visible: Is the creator's body prominently visible?
4. physique_reveal: Is there a physique/muscle reveal moment? Which frame?
5. shirtless: Is the creator shirtless in any frame?
6. location_type: gym / outdoors / home / studio / restaurant / street / beach / other
7. location_name: Specific location if identifiable (e.g. a Barcelona landmark)
8. other_people_visible: Are other people visible in any frame?
9. exercise_performed: What exercise is being performed, if any?
10. camera_angle: Dominant angle — eye-level / low / high / close-up / wide
11. text_overlay: Is there text overlay in any frame?
12. text_overlay_content: What does the text say? (exact text if readable)
13. first_visual_description: Describe Frame 1 in one sentence
14. dominant_emotion: Overall mood — confident / playful / serious / energetic / chill / motivational
15. lighting: natural / gym-artificial / studio / outdoor-bright / mixed / low-light
16. strongest_visual_frame: Which frame number has the most visually impactful content?
17. first_action_frame: Which frame shows the first significant physical action/movement?

Return valid JSON only."""

    frame_bytes = [fb for _, fb in all_frames]
    response = await analyze_images(frame_bytes, prompt)

    try:
        data = _parse_llm_json(response.text)
        validated = VisualAnalysis.model_validate(data)
        return {"validated": validated.model_dump(), "usage": response.usage}
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning("Visual analysis failed validation (%s), returning raw", e)
        return {"raw": response.text, "validation_error": str(e), "usage": response.usage}


async def transcribe_video(video_path: str) -> dict:
    """Transcribe audio from a video using Whisper (runs in thread)."""
    try:
        import whisper_timestamped as whisper
    except ImportError:
        return {
            "full_text": None,
            "segments": [],
            "language": None,
            "has_speech": False,
            "first_spoken_sentence": None,
            "error": "whisper-timestamped not installed",
        }

    from app.services._whisper_cache import get_whisper_model
    model = get_whisper_model()

    result = await asyncio.to_thread(whisper.transcribe, model, video_path)

    segments = [
        {"start": s["start"], "end": s["end"], "text": s["text"]}
        for s in result.get("segments", [])
    ]
    full_text = " ".join(s["text"] for s in segments)
    return {
        "full_text": full_text,
        "segments": segments,
        "language": result.get("language", "en"),
        "has_speech": len(segments) > 0,
        "first_spoken_sentence": segments[0]["text"].strip() if segments else None,
    }


async def analyze_draft(
    video: UploadFile,
    objective: str,
    creator_id: int,
    db: AsyncSession,
) -> dict:
    """Full draft review pipeline: measure → extract → transcribe → analyze → review."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
            total_bytes = 0
            while chunk := await video.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise ValueError(f"File exceeds {MAX_UPLOAD_BYTES // (1024*1024)} MB limit")
                tmp.write(chunk)

        measurements = await measure_video(tmp_path)

        hook_frames = await extract_hook_frames(tmp_path, measurements.duration)
        scene_frames = await extract_scene_change_frames(tmp_path, measurements.scene_change_timestamps)

        transcript = await transcribe_video(tmp_path)
        visual_analysis = await analyze_visual_features(hook_frames, scene_frames, measurements)

        visual_context = visual_analysis.get("validated") or visual_analysis.get("raw", "Not available")
        if isinstance(visual_context, dict):
            visual_context = json.dumps(visual_context, indent=2)

        review_prompt = f"""You are reviewing a draft video for Kobby Cooper before posting.

Intended objective: {objective}

DETERMINISTIC MEASUREMENTS:
- Duration: {measurements.duration:.1f}s
- Has audio: {measurements.has_audio}
- Cuts detected: {measurements.cut_count}
- Scene changes at: {[f'{t:.1f}s' for t in measurements.scene_change_timestamps]}

TRANSCRIPT: {transcript.get('full_text') or 'No speech detected'}

VISUAL ANALYSIS: {visual_context}

HOOK FRAMES ANALYZED: {len(hook_frames)} frames from 0-3s
SCENE FRAMES ANALYZED: {len(scene_frames)} frames from scene changes

Evaluate:
1. Opening strength (1-10): Does Frame 1 at 0.0s grab attention immediately?
2. Hook quality (1-10): Do the first 3 seconds compel the viewer to keep watching?
3. Pacing: Are there dead moments visible between scene changes?
4. First action: When does the first significant movement/action occur?
5. Strongest visual: Which scene is most impactful? Should it appear earlier?
6. Text readability: If text overlay exists, is it readable?
7. CTA / reason to follow: Does the video give a reason to follow Kobby?
8. Objective alignment: Does this serve the intended objective ({objective})?

Return valid JSON with:
- overall_score (1-10)
- opening_score (1-10)
- issues (array of {{timestamp_seconds, description, severity}})
- suggestions (array of {{description, expected_impact}})
- objective_fit (1-10)"""

        review_response = await complete(
            messages=[{"role": "user", "content": review_prompt}],
            tier=CostTier.STRATEGY,
        )

        try:
            review_data = _parse_llm_json(review_response.text)
            validated_review = DraftReviewOutput.model_validate(review_data)
            review_result = {"validated": validated_review.model_dump()}
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning("Draft review failed validation (%s), returning raw", e)
            review_result = {"raw": review_response.text, "validation_error": str(e)}

        return {
            "measurements": {
                "duration": measurements.duration,
                "fps": measurements.fps,
                "resolution": f"{measurements.width}x{measurements.height}",
                "has_audio": measurements.has_audio,
                "cut_count": measurements.cut_count,
                "scene_changes": measurements.scene_change_timestamps,
            },
            "transcript": transcript,
            "visual_analysis": visual_analysis,
            "review": review_result,
            "frames_analyzed": {
                "hook_frames": len(hook_frames),
                "scene_frames": len(scene_frames),
                "total": len(hook_frames) + len(scene_frames),
            },
        }
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
