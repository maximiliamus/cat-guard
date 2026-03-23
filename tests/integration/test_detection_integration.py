"""Integration tests for CatGuard detection pipeline.

These tests load the REAL YOLO11n ONNX model and run inference on synthetic frames.
They are marked @pytest.mark.integration and should be run separately from unit
tests, as they:
  - Require yolo11n.onnx to be present in the project root
  - Are noticeably slower than unit tests (~1–3 s per test on CPU)

Run with:
    pytest tests/integration/test_detection_integration.py -v -m integration

SKIP CONDITION: If the onnxruntime package is not installed, all tests in this
module are skipped automatically.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Skip the entire module gracefully if onnxruntime is not installed
pytest.importorskip("onnxruntime", reason="onnxruntime not installed — skipping detection integration tests")

from catguard.config import Settings
from catguard.detection import (
    CAT_CLASS_ID,
    _INPUT_SIZE,
    _postprocess,
    _preprocess_frame,
    BoundingBox,
    DetectionAction,
    DetectionEvent,
    DetectionLoop,
)


def _make_blank_frame(height: int = 480, width: int = 640) -> "np.ndarray":
    """Return a black BGR frame (no cat — should produce no detections)."""
    return np.zeros((height, width, 3), dtype=np.uint8)


@pytest.mark.integration
class TestDetectionIntegration:
    """Tests against the real ONNX model with synthetic / near-blank frames."""

    def test_no_callback_on_blank_frame(self):
        """A blank black frame should not trigger the callback."""
        settings = Settings(confidence_threshold=0.40, cooldown_seconds=5.0)
        callback_events = []

        def on_detected(event: DetectionEvent):
            callback_events.append(event)

        loop = DetectionLoop(settings, on_detected)
        loop._load_model()
        frame = _make_blank_frame()

        blob = _preprocess_frame(frame, _INPUT_SIZE)
        raw = loop._model.run(None, {loop._model_input_name: blob})[0]
        boxes = _postprocess(raw, settings.confidence_threshold, CAT_CLASS_ID, frame.shape)

        for box in boxes:
            if loop._cooldown_elapsed():
                loop._last_alert_time = datetime.now(timezone.utc)
                on_detected(DetectionEvent(
                    timestamp=datetime.now(timezone.utc),
                    confidence=box.confidence,
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
        """ONNX model should load without raising."""
        settings = Settings()
        loop = DetectionLoop(settings, lambda e: None)
        loop._load_model()
        assert loop._model is not None
        assert loop._model_input_name is not None

    def test_detection_loop_start_stop(self):
        """DetectionLoop should start and stop cleanly with a fake camera."""
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


@pytest.mark.integration
class TestVerificationCallbackIntegration:
    """Integration coverage for the live verification-frame callback contract."""

    def _run_with_frames(self, loop: DetectionLoop, frames, boxes_per_frame):
        from unittest.mock import MagicMock, patch

        call_count = [0]

        def fake_read():
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(frames):
                return True, frames[idx]
            loop._stop_event.set()
            return False, None

        with patch("cv2.VideoCapture") as mock_cap_cls:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = fake_read
            mock_cap_cls.return_value = mock_cap
            loop._model = MagicMock()
            loop._model.run.return_value = [np.zeros((1, 84, 8400), dtype=np.float32)]
            with patch.object(loop, "_load_model"):
                with patch("catguard.detection._preprocess_frame", return_value=np.zeros((1, 3, 640, 640), dtype=np.float32)):
                    with patch("catguard.detection._postprocess", side_effect=boxes_per_frame):
                        loop._run()

    def test_verification_callback_receives_live_frame_and_boxes(self):
        from datetime import timedelta

        received = []
        loop = DetectionLoop(Settings(cooldown_seconds=1.0), MagicMock())
        loop.set_verification_callback(
            lambda frame_bgr, has_cat, boxes: received.append((frame_bgr, has_cat, boxes))
        )
        loop._verification_pending = True
        loop._last_alert_time = datetime.now(timezone.utc) - timedelta(seconds=60)

        verification_frame = _make_blank_frame()
        verification_boxes = [BoundingBox(10, 10, 40, 40, 0.8)]
        self._run_with_frames(loop, [verification_frame], [[*verification_boxes]])

        assert len(received) == 1
        frame_bgr, has_cat, boxes = received[0]
        assert frame_bgr.shape == verification_frame.shape
        assert has_cat is True
        assert boxes == verification_boxes

    def test_verification_callback_frame_survives_loop_advance(self):
        from datetime import timedelta

        received_frames = []
        loop = DetectionLoop(Settings(cooldown_seconds=1.0), MagicMock())

        def capture(frame_bgr, has_cat, boxes):
            received_frames.append(frame_bgr)
            assert loop._verification_pending is False

        loop.set_verification_callback(capture)
        loop._verification_pending = True
        loop._last_alert_time = datetime.now(timezone.utc) - timedelta(seconds=60)

        first_frame = _make_blank_frame()
        second_frame = np.full_like(first_frame, 255)
        self._run_with_frames(loop, [first_frame, second_frame], [[], []])
        first_frame[:] = 127

        assert len(received_frames) == 1
        assert received_frames[0] is not first_frame
        assert int(received_frames[0][0, 0, 0]) == 0
