"""Tests for video frame extraction logic (no FFmpeg binary needed)."""
from __future__ import annotations
from unittest.mock import patch, MagicMock
from pathlib import Path
from app.services.video_analyzer import (
    _extract_hook_frames_sync,
    _extract_scene_change_frames_sync,
    VideoMeasurements,
)


def test_hook_frame_timestamps_short_video():
    """For a 5s video, hook frames should cover 0-3s heavily."""
    with patch("app.services.video_analyzer.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0)

        with patch("app.services.video_analyzer.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.read_bytes.return_value = b"fake_frame"
            mock_path.return_value = mock_path_instance

            frames = _extract_hook_frames_sync("/fake/video.mp4", 5.0)

    hook_times = [t for t, _ in frames if t <= 3.0]
    assert len(hook_times) >= 5, "Should have at least 5 hook frames in first 3 seconds"
    assert frames[0][0] == 0.0, "First frame must be at t=0.0"


def test_hook_frame_timestamps_very_short_video():
    """For a 2s video, most hook times should be trimmed."""
    with patch("app.services.video_analyzer.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0)

        with patch("app.services.video_analyzer.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.read_bytes.return_value = b"fake_frame"
            mock_path.return_value = mock_path_instance

            frames = _extract_hook_frames_sync("/fake/video.mp4", 2.0)

    all_times = [t for t, _ in frames]
    assert all(t < 2.0 for t in all_times), "All frame times must be within video duration"


def test_scene_change_frames_limit():
    """Should extract at most 12 scene change frames."""
    timestamps = [float(i) for i in range(20)]

    with patch("app.services.video_analyzer.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0)
        with patch("app.services.video_analyzer.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.read_bytes.return_value = b"fake"
            mock_path.return_value = mock_path_instance

            frames = _extract_scene_change_frames_sync("/fake/video.mp4", timestamps)

    assert len(frames) <= 12


def test_video_measurements_dataclass():
    m = VideoMeasurements(
        duration=30.0, fps=30.0, width=1080, height=1920,
        has_audio=True, audio_codec="aac",
        cut_count=5, scene_change_timestamps=[2.0, 5.0, 10.0, 15.0, 22.0],
        frame_count=900,
    )
    assert m.duration == 30.0
    assert m.has_audio is True
    assert len(m.scene_change_timestamps) == 5
