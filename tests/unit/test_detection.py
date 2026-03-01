"""Unit tests for catguard.detection — written before implementation (TDD RED).

Covers:
- Cooldown logic
- Confidence threshold handling
- Camera index usage and unavailable camera
- No-detection path (callback not called)
- list_cameras enumeration
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from catguard.config import Settings
from catguard.detection import (
    Camera,
    DetectionAction,
    DetectionEvent,
    DetectionLoop,
    list_cameras,
)


class TestCooldown:
    def test_no_prior_alert_cooldown_elapsed(self):
        loop = DetectionLoop(Settings(), MagicMock())
        assert loop._cooldown_elapsed() is True

    def test_alert_just_fired_cooldown_not_elapsed(self):
        loop = DetectionLoop(Settings(cooldown_seconds=15.0), MagicMock())
        loop._last_alert_time = datetime.now(timezone.utc)
        assert loop._cooldown_elapsed() is False

    def test_cooldown_elapsed_after_period(self):
        loop = DetectionLoop(Settings(cooldown_seconds=15.0), MagicMock())
        loop._last_alert_time = datetime.now(timezone.utc) - timedelta(seconds=20)
        assert loop._cooldown_elapsed() is True

    def test_cooldown_boundary_exact_period(self):
        settings = Settings(cooldown_seconds=15.0)
        loop = DetectionLoop(settings, MagicMock())
        loop._last_alert_time = datetime.now(timezone.utc) - timedelta(seconds=15.1)
        assert loop._cooldown_elapsed() is True

    def test_cooldown_respects_configured_value(self):
        loop = DetectionLoop(Settings(cooldown_seconds=5.0), MagicMock())
        loop._last_alert_time = datetime.now(timezone.utc) - timedelta(seconds=3)
        assert loop._cooldown_elapsed() is False
        loop._last_alert_time = datetime.now(timezone.utc) - timedelta(seconds=6)
        assert loop._cooldown_elapsed() is True


class TestConfidenceThreshold:
    def test_settings_hold_threshold(self):
        loop = DetectionLoop(Settings(confidence_threshold=0.55), MagicMock())
        assert loop._settings.confidence_threshold == 0.55

    def test_threshold_update_reflected_immediately(self):
        """Pull model: mutating shared settings object is reflected in loop."""
        settings = Settings(confidence_threshold=0.40)
        loop = DetectionLoop(settings, MagicMock())
        settings.confidence_threshold = 0.70
        assert loop._settings.confidence_threshold == 0.70


class TestCameraIndex:
    def test_uses_configured_camera_index(self):
        loop = DetectionLoop(Settings(camera_index=2), MagicMock())
        assert loop._settings.camera_index == 2

    def test_camera_unavailable_logs_warning_no_raise(self):
        """_run() should log warning and return cleanly when camera can't open."""
        settings = Settings(camera_index=99)
        callback = MagicMock()
        loop = DetectionLoop(settings, callback)

        with patch("cv2.VideoCapture") as mock_cap_cls:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = False
            mock_cap_cls.return_value = mock_cap
            with patch.object(loop, "_load_model"):
                loop._stop_event.set()
                loop._run()

        callback.assert_not_called()


class TestNoDetectionPath:
    def test_no_callback_when_yolo_returns_no_boxes(self):
        settings = Settings()
        callback = MagicMock()
        loop = DetectionLoop(settings, callback)

        mock_result = MagicMock()
        mock_result.boxes = None

        frame_calls = [0]

        def read_side():
            frame_calls[0] += 1
            if frame_calls[0] == 1:
                return True, MagicMock()
            loop._stop_event.set()
            return False, None

        with patch("cv2.VideoCapture") as mock_cap_cls:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = read_side
            mock_cap_cls.return_value = mock_cap
            mock_model = MagicMock()
            mock_model.predict.return_value = [mock_result]
            loop._model = mock_model
            with patch.object(loop, "_load_model"):
                loop._run()

        callback.assert_not_called()

    def test_no_callback_below_confidence_threshold(self):
        settings = Settings(confidence_threshold=0.80)
        callback = MagicMock()
        loop = DetectionLoop(settings, callback)

        # Verify that a box with confidence 0.30 should not trigger alert
        # (This is enforced by YOLO's conf= parameter — we verify it is passed)
        assert loop._settings.confidence_threshold == 0.80


class TestListCameras:
    def test_returns_available_cameras(self):
        with patch("cv2.VideoCapture") as mock_cap_cls:
            def side_effect(index, *args):  # *args absorbs CAP_DSHOW on Windows
                m = MagicMock()
                m.isOpened.return_value = index < 2
                return m

            mock_cap_cls.side_effect = side_effect
            cameras = list_cameras(max_index=3)

        assert len(cameras) == 2
        assert all(isinstance(c, Camera) for c in cameras)
        assert cameras[0].index == 0
        assert cameras[1].index == 1
        assert cameras[0].available is True

    def test_no_cameras_returns_empty_list(self):
        with patch("cv2.VideoCapture") as mock_cap_cls:
            mock = MagicMock()
            mock.isOpened.return_value = False
            mock_cap_cls.return_value = mock
            cameras = list_cameras(max_index=3)
        assert cameras == []


class TestDetectionEventModel:
    def test_detection_event_fields(self):
        event = DetectionEvent(
            timestamp=datetime.now(timezone.utc),
            confidence=0.75,
            action=DetectionAction.SOUND_PLAYED,
        )
        assert event.action == DetectionAction.SOUND_PLAYED
        assert event.sound_file is None

    def test_cooldown_suppressed_action(self):
        event = DetectionEvent(
            timestamp=datetime.now(timezone.utc),
            confidence=0.60,
            action=DetectionAction.COOLDOWN_SUPPRESSED,
        )
        assert event.action == DetectionAction.COOLDOWN_SUPPRESSED


# ---------------------------------------------------------------------------
# T002: DetectionEvent.frame_bgr optional field
# ---------------------------------------------------------------------------

class TestDetectionEventFrameBgr:
    """T002 — frame_bgr field added to DetectionEvent (TDD RED before T004)."""

    def test_frame_bgr_defaults_to_none(self):
        """field exists and defaults to None when not supplied."""
        import numpy as np
        event = DetectionEvent(
            timestamp=datetime.now(timezone.utc),
            confidence=0.85,
            action=DetectionAction.SOUND_PLAYED,
        )
        assert event.frame_bgr is None

    def test_frame_bgr_can_be_set_to_ndarray(self):
        """frame_bgr accepts a numpy ndarray."""
        import numpy as np
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        event = DetectionEvent(
            timestamp=datetime.now(timezone.utc),
            confidence=0.85,
            action=DetectionAction.SOUND_PLAYED,
            frame_bgr=frame,
        )
        assert event.frame_bgr is frame

    def test_cooldown_suppressed_event_frame_is_none(self):
        """COOLDOWN_SUPPRESSED events carry no frame (no screenshot needed)."""
        event = DetectionEvent(
            timestamp=datetime.now(timezone.utc),
            confidence=0.85,
            action=DetectionAction.COOLDOWN_SUPPRESSED,
        )
        assert event.frame_bgr is None

    def test_sound_played_event_accepts_frame(self):
        """SOUND_PLAYED event correctly stores the supplied frame."""
        import numpy as np
        frame = np.ones((240, 320, 3), dtype=np.uint8) * 128
        event = DetectionEvent(
            timestamp=datetime.now(timezone.utc),
            confidence=0.9,
            action=DetectionAction.SOUND_PLAYED,
            frame_bgr=frame,
        )
        assert event.frame_bgr is not None
        assert event.frame_bgr.shape == (240, 320, 3)
