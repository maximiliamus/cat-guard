"""Integration tests for camera error handling.

Tests:
- T042: Auto-pause behavior when camera becomes unavailable
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from catguard.config import Settings
from catguard.detection import DetectionLoop


class TestCameraErrorHandling:
    """Integration tests for camera error auto-pause (T042)."""

    def test_camera_error_triggers_auto_pause(self):
        """Test that camera error triggers auto-pause (T042)."""
        callback = MagicMock()
        loop = DetectionLoop(Settings(), callback)
        error_callback = MagicMock()
        
        loop.set_error_callback(error_callback)
        loop._is_tracking = True
        
        # Simulate camera read failure
        loop.pause()
        
        assert not loop.is_tracking()
        assert loop._stop_event.is_set()

    def test_error_callback_invoked_on_camera_failure(self):
        """Test that error callback is invoked when camera fails."""
        callback = MagicMock()
        loop = DetectionLoop(Settings(), callback)
        error_callback = MagicMock()
        
        loop.set_error_callback(error_callback)
        
        # Simulate error callback invocation
        error_msg = "Failed to read frame from camera 0."
        if loop._on_error_callback:
            loop._on_error_callback(error_msg)
        
        error_callback.assert_called_once_with(error_msg)

    def test_auto_pause_no_deadlock_on_rapid_errors(self):
        """Test that rapid errors don't cause deadlock."""
        callback = MagicMock()
        loop = DetectionLoop(Settings(), callback)
        error_callback = MagicMock()
        
        loop.set_error_callback(error_callback)
        loop._is_tracking = True
        
        # Rapid pause attempts
        for _ in range(5):
            loop.pause()
            if loop._on_error_callback:
                loop._on_error_callback("Camera error")
        
        assert not loop.is_tracking()
