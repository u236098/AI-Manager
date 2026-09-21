"""Video analysis — deterministic measurements via FFmpeg.

Deterministic (FFmpeg/FFprobe):
    duration, frame count, scene changes, cut count, audio presence,
    audio loudness, frame timestamps

All blocking work (subprocess, whisper) runs via asyncio.to_thread()
so it doesn't block the event loop.
"""
from __future__ import annotations
import asyncio
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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
