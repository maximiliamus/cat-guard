from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest

from catguard.annotation import EffectivenessTracker
from catguard.config import Settings
from catguard.detection import BoundingBox, DetectionSnapshot
from catguard.main import shutdown_app


def _frame() -> np.ndarray:
    return np.full((120, 180, 3), 90, dtype=np.uint8)


def _boxes() -> list[BoundingBox]:
    return [BoundingBox(x1=10, y1=10, x2=70, y2=70, confidence=0.9)]


def _snapshot(captured_at: datetime) -> DetectionSnapshot:
    return DetectionSnapshot(
        frame_bgr=_frame(),
        boxes=_boxes(),
        captured_at=captured_at,
        sequence=1,
    )


def _make_tracker(settings: Settings, holder: dict[str, DetectionSnapshot]) -> EffectivenessTracker:
    return EffectivenessTracker(
        settings=settings,
        is_window_open=lambda: False,
        on_error=lambda _msg: None,
        detection_snapshot_getter=lambda: holder.get("snapshot"),
    )


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


@pytest.mark.integration
class TestShutdownAppIntegration:
    def test_shutdown_app_finalizes_active_partial_clip_and_stops_services(self, tmp_path: Path):
        settings = Settings(
            tracking_directory=str(tmp_path),
            tracking_mode="videoclips",
            videoclip_fps=2,
        )
        captured_at = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
        holder = {"snapshot": _snapshot(captured_at)}
        tracker = _make_tracker(settings, holder)
        tracker.on_detection(_frame(), _boxes(), "sound.wav", captured_at=captured_at)

        stop_event = threading.Event()
        time_window_monitor = MagicMock()
        sleep_watcher = MagicMock()
        detection_loop = MagicMock()
        shutdown_audio = MagicMock()
        state: dict[str, bool] = {}

        start = time.perf_counter()
        shutdown_app(
            reason="tray_exit",
            tracker=tracker,
            time_window_monitor=time_window_monitor,
            sleep_watcher=sleep_watcher,
            detection_loop=detection_loop,
            shutdown_audio=shutdown_audio,
            stop_event=stop_event,
            exit_process=False,
            state=state,
        )
        elapsed = time.perf_counter() - start

        assert elapsed < 10.0
        assert stop_event.is_set()
        time_window_monitor.stop.assert_called_once()
        sleep_watcher.stop.assert_called_once()
        detection_loop.stop.assert_called_once()
        shutdown_audio.assert_called_once()

        videos = sorted(tmp_path.rglob("*.avi"))
        assert videos
        assert _read_video(videos[0])

    def test_shutdown_app_is_idempotent_with_shared_state(self, tmp_path: Path):
        settings = Settings(
            tracking_directory=str(tmp_path),
            tracking_mode="videoclips",
            videoclip_fps=1,
        )
        captured_at = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
        holder = {"snapshot": _snapshot(captured_at)}
        tracker = _make_tracker(settings, holder)
        tracker.on_detection(_frame(), _boxes(), "sound.wav", captured_at=captured_at)

        stop_event = threading.Event()
        time_window_monitor = MagicMock()
        sleep_watcher = MagicMock()
        detection_loop = MagicMock()
        shutdown_audio = MagicMock()
        state: dict[str, bool] = {}

        shutdown_app(
            reason="tray_exit",
            tracker=tracker,
            time_window_monitor=time_window_monitor,
            sleep_watcher=sleep_watcher,
            detection_loop=detection_loop,
            shutdown_audio=shutdown_audio,
            stop_event=stop_event,
            exit_process=False,
            state=state,
        )
        shutdown_app(
            reason="tray_exit",
            tracker=tracker,
            time_window_monitor=time_window_monitor,
            sleep_watcher=sleep_watcher,
            detection_loop=detection_loop,
            shutdown_audio=shutdown_audio,
            stop_event=stop_event,
            exit_process=False,
            state=state,
        )

        time_window_monitor.stop.assert_called_once()
        sleep_watcher.stop.assert_called_once()
        detection_loop.stop.assert_called_once()
        shutdown_audio.assert_called_once()
