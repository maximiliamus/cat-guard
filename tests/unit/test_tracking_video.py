from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from catguard.tracking_video import TrackingClipWriter, reserve_tracking_clip_paths


def _frame(height: int = 80, width: int = 120, value: int = 64) -> np.ndarray:
    return np.full((height, width, 3), value, dtype=np.uint8)


def _read_video_frames(path: Path) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(path))
    assert cap.isOpened(), f"Could not open video file: {path}"
    frames: list[np.ndarray] = []
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(frame)
    finally:
        cap.release()
    return frames


class TestReserveTrackingClipPaths:
    def test_reserves_date_folder_and_default_stem(self, tmp_path):
        session_ts = datetime(2026, 3, 31, 12, 34, 56)

        paths = reserve_tracking_clip_paths(tmp_path, session_ts)

        assert paths.final_path == tmp_path / "2026-03-31" / "20260331-123456.avi"
        assert paths.temp_path == tmp_path / "2026-03-31" / "20260331-123456.partial.avi"

    def test_same_second_collision_adds_suffix(self, tmp_path):
        session_ts = datetime(2026, 3, 31, 12, 34, 56)
        existing_dir = tmp_path / "2026-03-31"
        existing_dir.mkdir(parents=True)
        (existing_dir / "20260331-123456.avi").write_bytes(b"existing")

        paths = reserve_tracking_clip_paths(tmp_path, session_ts)

        assert paths.final_path.name == "20260331-123456-01.avi"
        assert paths.temp_path.name == "20260331-123456-01.partial.avi"


class TestTrackingClipWriter:
    def test_zero_frame_finalize_removes_empty_temp_and_returns_none(self, tmp_path):
        paths = reserve_tracking_clip_paths(tmp_path, datetime(2026, 3, 31, 12, 34, 56))
        paths.temp_path.parent.mkdir(parents=True, exist_ok=True)
        paths.temp_path.write_bytes(b"")
        writer = TrackingClipWriter(paths=paths, fps=1)

        result = writer.finalize()

        assert result is None
        assert not paths.temp_path.exists()
        assert not paths.final_path.exists()

    def test_finalize_writes_readable_clip_and_normalises_resize(self, tmp_path):
        paths = reserve_tracking_clip_paths(tmp_path, datetime(2026, 3, 31, 12, 34, 56))
        writer = TrackingClipWriter(paths=paths, fps=4)

        assert writer.write_frame(_frame(80, 120, 32)) is True
        assert writer.write_frame(_frame(120, 80, 128)) is True

        final_path = writer.finalize()

        assert final_path == paths.final_path
        frames = _read_video_frames(final_path)
        assert len(frames) >= 2
        assert frames[0].shape == frames[1].shape

    def test_finalize_preserves_readable_partial_when_rename_fails(self, tmp_path):
        paths = reserve_tracking_clip_paths(tmp_path, datetime(2026, 3, 31, 12, 34, 56))
        writer = TrackingClipWriter(paths=paths, fps=2)
        assert writer.write_frame(_frame()) is True

        with patch("pathlib.Path.replace", side_effect=PermissionError("busy")):
            result = writer.finalize()

        assert result == paths.temp_path
        assert paths.temp_path.exists()
        assert not paths.final_path.exists()
        assert _read_video_frames(paths.temp_path)
