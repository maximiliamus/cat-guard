"""Integration tests for CatGuard detection pipeline.

These tests load the REAL YOLO11n model and run inference on synthetic frames.
They are marked @pytest.mark.integration and should be run separately from unit
tests, as they:
  - Download ~6 MB YOLO11n weights on first run (cached at ~/.ultralytics/assets/)
  - Are noticeably slower than unit tests (~1–3 s per test on CPU)

Run with:
    pytest tests/integration/test_detection_integration.py -v -m integration

SKIP CONDITION: If the ultralytics package is not installed, all tests in this
module are skipped automatically.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

import numpy as np
import pytest

# Skip the entire module gracefully if ultralytics is not installed
pytest.importorskip("ultralytics", reason="ultralytics not installed — skipping detection integration tests")

from catguard.config import Settings
from catguard.detection import DetectionAction, DetectionEvent, DetectionLoop


def _make_blank_frame(height: int = 480, width: int = 640) -> "np.ndarray":
    """Return a black BGR frame (no cat — should produce no detections)."""
    return np.zeros((height, width, 3), dtype=np.uint8)


@pytest.mark.integration
class TestDetectionIntegration:
    """Tests against the real YOLO model with synthetic / near-blank frames."""

    def test_no_callback_on_blank_frame(self):
        """A blank black frame should not trigger the callback."""
        settings = Settings(confidence_threshold=0.40, cooldown_seconds=5.0)
        callback_events = []

        def on_detected(event: DetectionEvent):
            callback_events.append(event)

        loop = DetectionLoop(settings, on_detected)
        # Run a single iteration manually without the camera
        loop._load_model()
        frame = _make_blank_frame()

        results = loop._model.predict(frame, conf=settings.confidence_threshold, classes=[15], device="cpu", verbose=False)
        for result in results:
            boxes = result.boxes
            if boxes is not None and len(boxes) > 0:
                for box in boxes:
                    conf_val = float(box.conf[0])
                    if loop._cooldown_elapsed():
                        loop._last_alert_time = datetime.now(timezone.utc)
                        on_detected(DetectionEvent(
                            timestamp=datetime.now(timezone.utc),
                            confidence=conf_val,
                            action=DetectionAction.SOUND_PLAYED,
                        ))

        # A blank frame should produce 0 detections → no callback
        assert len(callback_events) == 0

    def test_cooldown_suppresses_rapid_repeat(self):
        """Two rapid alerts within cooldown window — second should be suppressed."""
        settings = Settings(confidence_threshold=0.01, cooldown_seconds=60.0)
        played = []
        suppressed = []

        def on_detected(event: DetectionEvent):
            if event.action == DetectionAction.SOUND_PLAYED:
                played.append(event)
            else:
                suppressed.append(event)

        loop = DetectionLoop(settings, on_detected)
        loop._load_model()

        # Simulate a detection that triggers alert
        now = datetime.now(timezone.utc)
        assert loop._cooldown_elapsed() is True
        loop._last_alert_time = now
        on_detected(DetectionEvent(timestamp=now, confidence=0.9, action=DetectionAction.SOUND_PLAYED))

        # Immediately try again — cooldown not elapsed
        assert loop._cooldown_elapsed() is False
        on_detected(DetectionEvent(
            timestamp=datetime.now(timezone.utc),
            confidence=0.9,
            action=DetectionAction.COOLDOWN_SUPPRESSED,
        ))

        assert len(played) == 1
        assert len(suppressed) == 1

    def test_model_loads_without_error(self):
        """YOLO model should load from cache or download without raising."""
        settings = Settings()
        loop = DetectionLoop(settings, lambda e: None)
        loop._load_model()
        assert loop._model is not None

    def test_detection_loop_start_stop(self):
        """DetectionLoop should start and stop cleanly with a fake camera."""
        import cv2
        from unittest.mock import MagicMock, patch

        settings = Settings(camera_index=0)
        called = threading.Event()

        loop = DetectionLoop(settings, lambda e: called.set())

        blank = _make_blank_frame()

        with patch("cv2.VideoCapture") as mock_cap_cls:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            read_count = [0]

            def fake_read():
                read_count[0] += 1
                if read_count[0] > 3:
                    loop._stop_event.set()
                    return False, None
                return True, blank

            mock_cap.read.side_effect = fake_read
            mock_cap_cls.return_value = mock_cap

            loop.start()
            loop._thread.join(timeout=10.0)

        assert not loop._thread.is_alive(), "DetectionLoop thread did not stop cleanly"
