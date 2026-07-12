from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest

from catguard.annotation import EffectivenessTracker
from catguard.config import Settings
from catguard.detection import BoundingBox, DetectionSnapshot


def _frame(h: int = 120, w: int = 180, value: int = 80) -> np.ndarray:
    return np.full((h, w, 3), value, dtype=np.uint8)


def _boxes() -> list[BoundingBox]:
    return [BoundingBox(x1=10, y1=10, x2=70, y2=70, confidence=0.9)]


def _snapshot(frame: np.ndarray, boxes: list[BoundingBox], captured_at: datetime, sequence: int) -> DetectionSnapshot:
    return DetectionSnapshot(
        frame_bgr=frame.copy(),
        boxes=list(boxes),
        captured_at=captured_at,
        sequence=sequence,
    )


def _wait_for_videos(root: Path, count: int, timeout: float = 5.0) -> list[Path]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        videos = sorted(root.rglob("*.avi"))
        if len(videos) >= count:
            return videos
        time.sleep(0.05)
    videos = sorted(root.rglob("*.avi"))
    raise TimeoutError(f"Expected {count} video(s); found {len(videos)} in {root}")


def _read_video(path: Path) -> list[np.ndarray]:
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


def _bottom_edge_pixel(frame: np.ndarray) -> tuple[int, int, int]:
    h, w = frame.shape[:2]
    b, g, r = frame[h - 3, w - 10]
    return int(b), int(g), int(r)


def _is_neutral(frame: np.ndarray) -> bool:
    b, g, r = _bottom_edge_pixel(frame)
    return max(abs(b - g), abs(g - r), abs(b - r)) <= 20 and max(b, g, r) < 100


def _is_red(frame: np.ndarray) -> bool:
    b, g, r = _bottom_edge_pixel(frame)
    return r > 90 and g < 80 and b < 80


def _is_green(frame: np.ndarray) -> bool:
    b, g, r = _bottom_edge_pixel(frame)
    return g > 90 and r < 80 and b < 80


def _make_tracker(settings: Settings, holder: dict[str, DetectionSnapshot]) -> EffectivenessTracker:
    return EffectivenessTracker(
        settings=settings,
        is_window_open=lambda: False,
        on_error=lambda _msg: None,
        detection_snapshot_getter=lambda: holder.get("snapshot"),
    )


@pytest.mark.integration
class TestVideoTrackingIntegration:
    def test_completed_video_mode_session_creates_single_clip_and_no_session_jpegs(self, tmp_path: Path):
        settings = Settings(
            tracking_directory=str(tmp_path),
            tracking_mode="videoclips",
            videoclip_fps=4,
            cooldown_seconds=1.0,
        )
        captured_at = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
        holder = {
            "snapshot": _snapshot(_frame(value=90), _boxes(), captured_at, 1),
        }
        tracker = _make_tracker(settings, holder)

        tracker.on_detection(_frame(), _boxes(), "sound.wav", captured_at=captured_at)
        time.sleep(0.35)
        tracker.on_verification(_frame(value=40), has_cat=False, boxes=[], captured_at=captured_at + timedelta(seconds=1))

        videos = _wait_for_videos(tmp_path, 1)
        assert sorted(tmp_path.rglob("*.jpg")) == []
        frames = _read_video(videos[0])
        assert len(frames) >= 2
        assert _is_neutral(frames[0])
        assert _is_green(frames[-1])

    def test_multi_cycle_video_mode_session_records_remained_then_deterred_in_order(self, tmp_path: Path):
        settings = Settings(
            tracking_directory=str(tmp_path),
            tracking_mode="videoclips",
            videoclip_fps=2,
            cooldown_seconds=1.0,
        )
        captured_at = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
        holder = {
            "snapshot": _snapshot(_frame(value=100), _boxes(), captured_at, 1),
        }
        tracker = _make_tracker(settings, holder)

        tracker.on_detection(_frame(), _boxes(), "sound.wav", captured_at=captured_at)
        tracker.on_verification(_frame(value=110), has_cat=True, boxes=_boxes(), captured_at=captured_at + timedelta(seconds=1))
        holder["snapshot"] = _snapshot(_frame(value=120), _boxes(), captured_at + timedelta(seconds=2), 2)
        time.sleep(0.55)
        tracker.on_detection(_frame(value=130), _boxes(), "sound.wav", captured_at=captured_at + timedelta(seconds=2))
        tracker.on_verification(_frame(value=60), has_cat=False, boxes=[], captured_at=captured_at + timedelta(seconds=3))

        video = _wait_for_videos(tmp_path, 1)[0]
        frames = _read_video(video)
        assert _is_neutral(frames[0])
        assert any(_is_red(frame) for frame in frames[1:-1])
        assert _is_green(frames[-1])

    def test_abandon_preserves_readable_partial_clip(self, tmp_path: Path):
        settings = Settings(
            tracking_directory=str(tmp_path),
            tracking_mode="videoclips",
            videoclip_fps=3,
            cooldown_seconds=1.0,
        )
        captured_at = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
        holder = {
            "snapshot": _snapshot(_frame(value=70), _boxes(), captured_at, 1),
        }
        tracker = _make_tracker(settings, holder)

        tracker.on_detection(_frame(), _boxes(), "sound.wav", captured_at=captured_at)
        time.sleep(0.25)
        tracker.abandon(reason="pause")

        videos = _wait_for_videos(tmp_path, 1)
        assert _read_video(videos[0])

    def test_finalize_completes_within_ten_seconds(self, tmp_path: Path):
        settings = Settings(
            tracking_directory=str(tmp_path),
            tracking_mode="videoclips",
            videoclip_fps=1,
            cooldown_seconds=1.0,
        )
        captured_at = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
        holder = {
            "snapshot": _snapshot(_frame(value=50), _boxes(), captured_at, 1),
        }
        tracker = _make_tracker(settings, holder)

        tracker.on_detection(_frame(), _boxes(), "sound.wav", captured_at=captured_at)
        start = time.perf_counter()
        tracker.on_verification(_frame(value=20), has_cat=False, boxes=[], captured_at=captured_at + timedelta(seconds=1))
        elapsed = time.perf_counter() - start

        assert elapsed < 10.0

    def test_slow_detection_repeats_latest_frame_to_preserve_clip_duration(
        self, tmp_path: Path
    ):
        settings = Settings(
            tracking_directory=str(tmp_path),
            tracking_mode="videoclips",
            videoclip_fps=5,
            cooldown_seconds=1.0,
        )
        captured_at = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
        holder = {
            "snapshot": _snapshot(_frame(value=75), _boxes(), captured_at, 1),
        }
        tracker = _make_tracker(settings, holder)

        tracker.on_detection(_frame(), _boxes(), "sound.wav", captured_at=captured_at)
        time.sleep(0.65)
        tracker.on_verification(
            _frame(value=20),
            has_cat=False,
            boxes=[],
            captured_at=captured_at + timedelta(seconds=1),
        )

        video = _wait_for_videos(tmp_path, 1)[0]
        frames = _read_video(video)
        assert len(frames) >= 5
        assert len(frames) / settings.videoclip_fps >= 0.8
