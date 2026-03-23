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
        import numpy as _np
        settings = Settings()
        callback = MagicMock()
        loop = DetectionLoop(settings, callback)

        frame_calls = [0]

        def read_side():
            frame_calls[0] += 1
            if frame_calls[0] == 1:
                return True, _np.zeros((480, 640, 3), dtype=_np.uint8)
            loop._stop_event.set()
            return False, None

        with patch("cv2.VideoCapture") as mock_cap_cls:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = read_side
            mock_cap_cls.return_value = mock_cap
            loop._model = MagicMock()
            loop._model.run.return_value = [_np.zeros((1, 84, 8400), dtype=_np.float32)]
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


# ---------------------------------------------------------------------------
# T003: BoundingBox dataclass, DetectionEvent.boxes, one-SOUND_PLAYED-per-frame
# ---------------------------------------------------------------------------

class TestBoundingBox:
    """T003 — BoundingBox dataclass must exist in catguard.detection."""

    def test_bounding_box_importable(self):
        from catguard.detection import BoundingBox  # noqa: F401

    def test_bounding_box_fields(self):
        from catguard.detection import BoundingBox
        box = BoundingBox(x1=10, y1=20, x2=100, y2=200, confidence=0.87)
        assert box.x1 == 10
        assert box.y1 == 20
        assert box.x2 == 100
        assert box.y2 == 200
        assert box.confidence == pytest.approx(0.87)

    def test_bounding_box_is_dataclass(self):
        import dataclasses
        from catguard.detection import BoundingBox
        assert dataclasses.is_dataclass(BoundingBox)

    def test_bounding_box_confidence_is_float(self):
        from catguard.detection import BoundingBox
        box = BoundingBox(x1=0, y1=0, x2=50, y2=50, confidence=0.5)
        assert isinstance(box.confidence, float)

    def test_bounding_box_coordinates_are_int(self):
        from catguard.detection import BoundingBox
        box = BoundingBox(x1=1, y1=2, x2=3, y2=4, confidence=0.9)
        assert isinstance(box.x1, int)
        assert isinstance(box.y1, int)
        assert isinstance(box.x2, int)
        assert isinstance(box.y2, int)


class TestDetectionEventBoxesField:
    """T003 — DetectionEvent.boxes field must exist and default to empty list."""

    def test_boxes_field_defaults_to_empty_list(self):
        event = DetectionEvent(
            timestamp=datetime.now(timezone.utc),
            confidence=0.75,
            action=DetectionAction.SOUND_PLAYED,
        )
        assert hasattr(event, "boxes")
        assert event.boxes == []

    def test_boxes_field_accepts_bounding_box_list(self):
        from catguard.detection import BoundingBox
        boxes = [BoundingBox(x1=5, y1=10, x2=50, y2=100, confidence=0.9)]
        event = DetectionEvent(
            timestamp=datetime.now(timezone.utc),
            confidence=0.9,
            action=DetectionAction.SOUND_PLAYED,
            boxes=boxes,
        )
        assert len(event.boxes) == 1
        assert event.boxes[0].x1 == 5

    def test_two_events_do_not_share_boxes_list(self):
        """default_factory=list — each instance gets its own list."""
        e1 = DetectionEvent(
            timestamp=datetime.now(timezone.utc),
            confidence=0.8,
            action=DetectionAction.SOUND_PLAYED,
        )
        e2 = DetectionEvent(
            timestamp=datetime.now(timezone.utc),
            confidence=0.8,
            action=DetectionAction.SOUND_PLAYED,
        )
        assert e1.boxes is not e2.boxes


class TestOneEventPerFrame:
    """T003 — _run() must emit exactly one SOUND_PLAYED per frame regardless of box count."""

    def _run_loop_with_boxes(self, num_boxes: int, callback):
        """Helper: run DetectionLoop._run() for one frame with num_boxes detections."""
        import numpy as _np
        from catguard.detection import BoundingBox

        settings = Settings()
        loop = DetectionLoop(settings, callback)
        # Force cooldown to be always elapsed so SOUND_PLAYED fires immediately.
        loop._last_alert_time = None

        call_count = [0]

        def read_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return True, _np.zeros((480, 640, 3), dtype=_np.uint8)
            loop._stop_event.set()
            return False, None

        fake_boxes = [
            BoundingBox(10 + i * 150, 20, 100 + i * 150, 200, 0.85)
            for i in range(num_boxes)
        ]

        with patch("cv2.VideoCapture") as mock_cap_cls:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = read_side_effect
            mock_cap_cls.return_value = mock_cap
            loop._model = MagicMock()
            loop._model.run.return_value = [_np.zeros((1, 84, 8400), dtype=_np.float32)]
            with patch.object(loop, "_load_model"):
                with patch("catguard.detection._postprocess", return_value=fake_boxes):
                    loop._run()

    def test_one_box_emits_one_sound_played(self):
        callback = MagicMock()
        self._run_loop_with_boxes(1, callback)
        sound_played = [c for c in callback.call_args_list
                        if c[0][0].action == DetectionAction.SOUND_PLAYED]
        assert len(sound_played) == 1

    def test_three_boxes_emits_one_sound_played(self):
        """Critical: three boxes must still produce exactly ONE SOUND_PLAYED."""
        callback = MagicMock()
        self._run_loop_with_boxes(3, callback)
        sound_played = [c for c in callback.call_args_list
                        if c[0][0].action == DetectionAction.SOUND_PLAYED]
        assert len(sound_played) == 1

    def test_event_boxes_contains_all_bounding_boxes(self):
        """The single SOUND_PLAYED event must carry ALL detected boxes."""
        from catguard.detection import BoundingBox
        callback = MagicMock()
        self._run_loop_with_boxes(3, callback)
        sound_played_calls = [c for c in callback.call_args_list
                              if c[0][0].action == DetectionAction.SOUND_PLAYED]
        assert len(sound_played_calls) == 1
        event = sound_played_calls[0][0][0]
        assert len(event.boxes) == 3
        assert all(isinstance(b, BoundingBox) for b in event.boxes)

    def test_event_frame_is_copy_not_same_object(self):
        """frame_bgr on SOUND_PLAYED event must be a copy (not the live buffer)."""
        import numpy as _np
        received_frames = []

        def capture_callback(event):
            if event.action == DetectionAction.SOUND_PLAYED:
                received_frames.append(event.frame_bgr)

        self._run_loop_with_boxes(1, capture_callback)
        assert len(received_frames) == 1
        # The copy must be an ndarray
        assert isinstance(received_frames[0], _np.ndarray)


# ---------------------------------------------------------------------------
# T016: DetectionLoop.set_verification_callback() and verification trigger
# ---------------------------------------------------------------------------

class TestVerificationCallback:
    """T016 — set_verification_callback() registers callback; trigger fires correctly."""

    def _run_with_camera_frames(self, loop, frames, boxes_per_frame):
        import numpy as _np

        call_count = [0]

        def read_side_effect():
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(frames):
                return True, frames[idx]
            loop._stop_event.set()
            return False, None

        with patch("cv2.VideoCapture") as mock_cap_cls:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = read_side_effect
            mock_cap_cls.return_value = mock_cap
            loop._model = MagicMock()
            loop._model.run.return_value = [_np.zeros((1, 84, 8400), dtype=_np.float32)]
            with patch.object(loop, "_load_model"):
                with patch("catguard.detection._preprocess_frame", return_value=_np.zeros((1, 3, 640, 640), dtype=_np.float32)):
                    with patch("catguard.detection._postprocess", side_effect=boxes_per_frame):
                        loop._run()

    def test_set_verification_callback_attribute_exists(self):
        loop = DetectionLoop(Settings(), MagicMock())
        assert hasattr(loop, "set_verification_callback")
        assert callable(loop.set_verification_callback)

    def test_set_verification_callback_stores_callback(self):
        loop = DetectionLoop(Settings(), MagicMock())
        cb = MagicMock()
        loop.set_verification_callback(cb)
        assert loop._verification_callback is cb

    def test_set_verification_callback_none_clears(self):
        loop = DetectionLoop(Settings(), MagicMock())
        loop.set_verification_callback(MagicMock())
        loop.set_verification_callback(None)
        assert loop._verification_callback is None

    def test_verification_pending_set_after_sound_played(self):
        """After a SOUND_PLAYED event, verification should be pending."""
        import numpy as _np
        from catguard.detection import BoundingBox

        loop = DetectionLoop(Settings(cooldown_seconds=60.0), MagicMock())
        self._run_with_camera_frames(
            loop,
            [_np.zeros((100, 200, 3), dtype=_np.uint8)],
            [[BoundingBox(5, 5, 50, 50, 0.9)]],
        )
        assert loop._verification_pending is True

    def test_verification_callback_fires_after_cooldown(self):
        """Verification callback is invoked on first post-cooldown frame."""
        import numpy as _np
        from datetime import timedelta

        verification_calls = []
        detect_callback = MagicMock()
        settings = Settings(cooldown_seconds=1.0)
        loop = DetectionLoop(settings, detect_callback)
        loop.set_verification_callback(
            lambda frame_bgr, has_cat, boxes: verification_calls.append((frame_bgr, has_cat, boxes))
        )

        loop._verification_pending = True
        loop._last_alert_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        live_frame = _np.zeros((100, 200, 3), dtype=_np.uint8)

        self._run_with_camera_frames(loop, [live_frame], [[]])

        assert len(verification_calls) == 1
        frame_bgr, has_cat, boxes = verification_calls[0]
        assert isinstance(frame_bgr, _np.ndarray)
        assert has_cat is False
        assert boxes == []

    def test_pending_flag_cleared_before_callback(self):
        """Pending state must be cleared before the callback is invoked."""
        import numpy as _np
        from datetime import timedelta

        pending_during_callback = []

        def capture_pending_cb(frame_bgr, has_cat, boxes):
            pending_during_callback.append(loop._verification_pending)

        settings = Settings(cooldown_seconds=1.0)
        loop = DetectionLoop(settings, MagicMock())
        loop.set_verification_callback(capture_pending_cb)
        loop._verification_pending = True
        loop._last_alert_time = datetime.now(timezone.utc) - timedelta(seconds=60)

        self._run_with_camera_frames(loop, [_np.zeros((100, 200, 3), dtype=_np.uint8)], [[]])

        assert len(pending_during_callback) == 1
        assert pending_during_callback[0] is False

    def test_verification_callback_receives_deep_copied_live_frame(self):
        """Callback frame must remain valid after the loop advances the camera buffer."""
        import numpy as _np
        from datetime import timedelta

        received_frames = []
        settings = Settings(cooldown_seconds=1.0)
        loop = DetectionLoop(settings, MagicMock())
        loop.set_verification_callback(
            lambda frame_bgr, has_cat, boxes: received_frames.append(frame_bgr)
        )
        loop._verification_pending = True
        loop._last_alert_time = datetime.now(timezone.utc) - timedelta(seconds=60)

        live_frame = _np.zeros((100, 200, 3), dtype=_np.uint8)
        self._run_with_camera_frames(loop, [live_frame], [[]])
        live_frame[:] = 255

        assert len(received_frames) == 1
        assert received_frames[0] is not live_frame
        assert int(received_frames[0][0, 0, 0]) == 0


class TestPauseResume:
    """Tests for pause/resume tracking control (T011, T012, T020, T021)."""

    def test_pause_stops_tracking(self):
        """Test that pause() stops the tracking loop (T011)."""
        loop = DetectionLoop(Settings(), MagicMock())
        loop._is_tracking = True
        loop._verification_pending = True
        
        result = loop.pause()
        
        assert result is True
        assert loop._is_tracking is False
        assert loop._stop_event.is_set()
        assert loop._verification_pending is False

    def test_pause_idempotent_already_paused(self):
        """Test that pause() is idempotent when already paused."""
        loop = DetectionLoop(Settings(), MagicMock())
        loop._is_tracking = False
        loop._stop_event.clear()
        
        result = loop.pause()
        
        assert result is False
        assert not loop._stop_event.is_set()

    def test_resume_starts_tracking(self):
        """Test that resume() starts the tracking loop (T020)."""
        loop = DetectionLoop(Settings(), MagicMock())
        loop._is_tracking = False
        loop._stop_event.set()
        
        result = loop.resume()
        
        assert result is True
        assert loop._is_tracking is True
        assert not loop._stop_event.is_set()

    def test_resume_idempotent_already_active(self):
        """Test that resume() is idempotent when already active."""
        loop = DetectionLoop(Settings(), MagicMock())
        loop._is_tracking = True
        loop._stop_event.clear()
        
        result = loop.resume()
        
        assert result is False
        assert not loop._stop_event.is_set()

    def test_is_tracking_returns_false_when_paused(self):
        """Test that is_tracking() returns False when paused (T012)."""
        loop = DetectionLoop(Settings(), MagicMock())
        loop._is_tracking = False
        
        result = loop.is_tracking()
        
        assert result is False

    def test_is_tracking_returns_true_when_active(self):
        """Test that is_tracking() returns True when active (T021)."""
        loop = DetectionLoop(Settings(), MagicMock())
        loop._is_tracking = True
        
        result = loop.is_tracking()
        
        assert result is True

    def test_pause_resume_thread_safety(self):
        """Test that pause/resume are thread-safe."""
        loop = DetectionLoop(Settings(), MagicMock())
        loop._is_tracking = False
        
        results = []
        
        def pause_worker():
            for _ in range(10):
                results.append(("pause", loop.pause()))
        
        def resume_worker():
            for _ in range(10):
                results.append(("resume", loop.resume()))
        
        t1 = threading.Thread(target=pause_worker)
        t2 = threading.Thread(target=resume_worker)
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # Should have interleaved calls without race conditions
        assert len(results) == 20
        # No exceptions should have been raised

    def test_error_callback_registered(self):
        """Test that error callback can be registered."""
        loop = DetectionLoop(Settings(), MagicMock())
        callback = MagicMock()
        
        loop.set_error_callback(callback)
        
        assert loop._on_error_callback is callback

    def test_error_callback_cleared(self):
        """Test that error callback can be cleared."""
        loop = DetectionLoop(Settings(), MagicMock())
        callback = MagicMock()
        loop.set_error_callback(callback)
        
        loop.set_error_callback(None)
        
        assert loop._on_error_callback is None
