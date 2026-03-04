"""Integration tests for pause/resume tracking control.

Tests:
- T013: Pause via menu stops detection
- T014: Pause completes within 500ms
- T022: Resume via menu starts detection
- T023: Resume completes within 500ms
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from catguard.config import Settings
from catguard.detection import DetectionLoop


class TestPauseResumeIntegration:
    """Integration tests for pause/resume functionality."""

    def test_menu_pause_stops_detection(self):
        """Test that pause via menu stops detection loop (T013)."""
        callback = MagicMock()
        loop = DetectionLoop(Settings(), callback)
        
        # Start tracking
        loop._is_tracking = True
        assert loop.is_tracking() is True
        
        # Pause
        result = loop.pause()
        
        assert result is True
        assert loop.is_tracking() is False
        assert loop._stop_event.is_set()

    def test_pause_completes_within_500ms(self):
        """Test that pause completes within 500ms (T014)."""
        callback = MagicMock()
        loop = DetectionLoop(Settings(), callback)
        loop._is_tracking = True
        
        start = time.perf_counter()
        loop.pause()
        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        
        assert elapsed < 500, f"Pause took {elapsed}ms, should be < 500ms"
        assert not loop.is_tracking()

    def test_menu_resume_starts_detection(self):
        """Test that resume via menu starts detection loop (T022)."""
        callback = MagicMock()
        loop = DetectionLoop(Settings(), callback)
        
        # Start paused
        loop._is_tracking = False
        loop._stop_event.set()
        assert loop.is_tracking() is False
        
        # Resume
        result = loop.resume()
        
        assert result is True
        assert loop.is_tracking() is True
        assert not loop._stop_event.is_set()

    def test_resume_completes_within_500ms(self):
        """Test that resume completes within 500ms (T023)."""
        callback = MagicMock()
        loop = DetectionLoop(Settings(), callback)
        loop._is_tracking = False
        loop._stop_event.set()
        
        start = time.perf_counter()
        loop.resume()
        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        
        assert elapsed < 500, f"Resume took {elapsed}ms, should be < 500ms"
        assert loop.is_tracking()

    def test_rapid_pause_continue_no_deadlock(self):
        """Test that rapid pause/continue doesn't cause deadlock."""
        callback = MagicMock()
        loop = DetectionLoop(Settings(), callback)
        loop._is_tracking = True
        
        # Rapidly toggle pause/continue
        for _ in range(10):
            loop.pause()
            loop.resume()
        
        # Should complete without deadlock
        assert loop.is_tracking() is True


# ---------------------------------------------------------------------------
# T006: TimeWindowMonitor → DetectionLoop integration
# ---------------------------------------------------------------------------

class TestTimeWindowBoundaryCrossing:
    """Integration tests: time-window boundary triggering pause/resume on DetectionLoop."""

    def _make_monitor(self, loop, enabled=True, start="08:00", end="18:00"):
        from catguard.time_window import TimeWindowMonitor
        settings = MagicMock()
        settings.tracking_window_enabled = enabled
        settings.tracking_window_start = start
        settings.tracking_window_end = end
        cb = MagicMock()
        return TimeWindowMonitor(loop, settings, cb), cb

    def test_clock_crosses_window_end_pauses_detection(self):
        """Clock crosses window end → detection pauses (FR-002)."""
        from datetime import time as dtime
        loop = DetectionLoop(Settings(), MagicMock())
        loop._is_tracking = True
        monitor, cb = self._make_monitor(loop, start="08:00", end="18:00")

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = dtime(20, 0)
            monitor._check()

        assert not loop.is_tracking()
        cb.assert_called_once_with(False)

    def test_clock_crosses_window_start_resumes_detection(self):
        """Clock enters window after monitor-caused pause → detection resumes (FR-003)."""
        from datetime import time as dtime
        loop = DetectionLoop(Settings(), MagicMock())
        loop._is_tracking = False
        loop._stop_event.set()
        monitor, cb = self._make_monitor(loop, start="08:00", end="18:00")
        monitor._monitor_paused = True  # monitor caused the pause

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = dtime(9, 0)
            monitor._check()

        assert loop.is_tracking()
        cb.assert_called_once_with(True)

    def test_no_auto_pause_when_window_disabled(self):
        """FR-005: disabled window → detection always on."""
        from datetime import time as dtime
        loop = DetectionLoop(Settings(), MagicMock())
        loop._is_tracking = True
        monitor, cb = self._make_monitor(loop, enabled=False)

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = dtime(20, 0)
            monitor._check()

        assert loop.is_tracking()
        cb.assert_not_called()

    def test_user_override_keeps_camera_on_outside_window(self):
        """FR-004b: user Resume override → camera stays on despite being outside window."""
        from datetime import time as dtime
        loop = DetectionLoop(Settings(), MagicMock())
        loop._is_tracking = True
        monitor, cb = self._make_monitor(loop, start="08:00", end="18:00")

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = dtime(20, 0)
            monitor.notify_user_resume()
            monitor._check()

        assert loop.is_tracking()
        cb.assert_not_called()
