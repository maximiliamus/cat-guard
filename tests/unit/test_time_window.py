"""Unit tests for catguard.time_window — TimeWindowMonitor.

Covers (TDD — T005):
- _is_in_window(): normal window, cross-midnight, zero-length, boundary values
- TimeWindowMonitor state transitions:
    - window active on start → no pause
    - window inactive on start → auto-pause
    - window exit → pause (FR-002)
    - window entry → resume (FR-003)
    - user override while outside window → camera stays on (FR-004b)
    - manual pause not overridden by monitor (FR-004)
    - cross-midnight window handled correctly
    - zero-length window (start==end) → passthrough (FR-005)
    - window disabled → passthrough (FR-005)
"""
from __future__ import annotations

from datetime import time
from unittest.mock import MagicMock, patch, call

import pytest

from catguard.time_window import TimeWindowMonitor, _is_in_window


# ---------------------------------------------------------------------------
# _is_in_window() pure-function tests
# ---------------------------------------------------------------------------

class TestIsInWindow:
    def test_inside_normal_window(self):
        assert _is_in_window(time(10, 0), "08:00", "18:00") is True

    def test_before_normal_window(self):
        assert _is_in_window(time(7, 59), "08:00", "18:00") is False

    def test_after_normal_window(self):
        assert _is_in_window(time(18, 0), "08:00", "18:00") is False

    def test_at_start_boundary_inclusive(self):
        assert _is_in_window(time(8, 0), "08:00", "18:00") is True

    def test_at_end_boundary_exclusive(self):
        assert _is_in_window(time(18, 0), "08:00", "18:00") is False

    def test_cross_midnight_inside(self):
        assert _is_in_window(time(23, 0), "22:00", "06:00") is True

    def test_cross_midnight_inside_early_morning(self):
        assert _is_in_window(time(2, 30), "22:00", "06:00") is True

    def test_cross_midnight_outside(self):
        assert _is_in_window(time(12, 0), "22:00", "06:00") is False

    def test_zero_length_window_returns_false(self):
        assert _is_in_window(time(9, 0), "09:00", "09:00") is False


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_detection_loop(is_tracking: bool = True) -> MagicMock:
    loop = MagicMock()
    loop.is_tracking.return_value = is_tracking
    return loop


def _make_settings(
    enabled: bool = True,
    start: str = "08:00",
    end: str = "18:00",
) -> MagicMock:
    s = MagicMock()
    s.tracking_window_enabled = enabled
    s.tracking_window_start = start
    s.tracking_window_end = end
    return s


# ---------------------------------------------------------------------------
# TimeWindowMonitor.check() state machine
# ---------------------------------------------------------------------------

class TestTimeWindowMonitorCheck:
    """Direct tests of _check() without running the daemon thread."""

    def test_window_disabled_no_action(self):
        """FR-005: disabled window → monitor does nothing."""
        loop = _make_detection_loop(is_tracking=True)
        settings = _make_settings(enabled=False)
        cb = MagicMock()
        m = TimeWindowMonitor(loop, settings, cb)

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(14, 0)
            m._check()

        loop.pause.assert_not_called()
        loop.resume.assert_not_called()
        cb.assert_not_called()

    def test_inside_window_tracking_no_action(self):
        """Inside window, already tracking → no-op."""
        loop = _make_detection_loop(is_tracking=True)
        settings = _make_settings(start="08:00", end="18:00")
        cb = MagicMock()
        m = TimeWindowMonitor(loop, settings, cb)

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(12, 0)
            m._check()

        loop.pause.assert_not_called()
        loop.resume.assert_not_called()
        cb.assert_not_called()

    def test_outside_window_tracking_auto_pause(self):
        """FR-002: outside window, tracking → monitor pauses detection."""
        loop = _make_detection_loop(is_tracking=True)
        settings = _make_settings(start="08:00", end="18:00")
        cb = MagicMock()
        m = TimeWindowMonitor(loop, settings, cb)

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(20, 0)
            m._check()

        loop.pause.assert_called_once()
        cb.assert_called_once_with(False)
        assert m._monitor_paused is True

    def test_inside_window_monitor_paused_resumes(self):
        """FR-003: window just opened, monitor previously paused → resume."""
        loop = _make_detection_loop(is_tracking=False)
        settings = _make_settings(start="08:00", end="18:00")
        cb = MagicMock()
        m = TimeWindowMonitor(loop, settings, cb)
        m._monitor_paused = True  # simulate that monitor caused the pause

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(9, 0)
            m._check()

        loop.resume.assert_called_once()
        cb.assert_called_once_with(True)
        assert m._monitor_paused is False

    def test_manual_pause_not_overridden(self):
        """FR-004: manual pause (_monitor_paused=False) → monitor does not resume."""
        loop = _make_detection_loop(is_tracking=False)
        settings = _make_settings(start="08:00", end="18:00")
        cb = MagicMock()
        m = TimeWindowMonitor(loop, settings, cb)
        m._monitor_paused = False  # manual pause — not caused by monitor

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(9, 0)
            m._check()

        loop.resume.assert_not_called()
        cb.assert_not_called()

    def test_user_override_outside_window_no_pause(self):
        """FR-004b: user override active → monitor does NOT re-pause the camera."""
        loop = _make_detection_loop(is_tracking=True)
        settings = _make_settings(start="08:00", end="18:00")
        cb = MagicMock()
        m = TimeWindowMonitor(loop, settings, cb)
        m._user_override = True  # user clicked Resume while outside window

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(20, 0)
            m._check()

        loop.pause.assert_not_called()
        cb.assert_not_called()

    def test_user_override_cleared_when_window_reopens(self):
        """FR-004b: when window opens again, user override is cleared."""
        loop = _make_detection_loop(is_tracking=True)
        settings = _make_settings(start="08:00", end="18:00")
        cb = MagicMock()
        m = TimeWindowMonitor(loop, settings, cb)
        m._user_override = True

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(10, 0)  # inside
            m._check()

        assert m._user_override is False

    def test_cross_midnight_window_outside_pauses(self):
        """Cross-midnight window: midday is outside → auto-pause."""
        loop = _make_detection_loop(is_tracking=True)
        settings = _make_settings(start="22:00", end="06:00")
        cb = MagicMock()
        m = TimeWindowMonitor(loop, settings, cb)

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(14, 0)
            m._check()

        loop.pause.assert_called_once()

    def test_cross_midnight_window_inside_at_midnight(self):
        """Cross-midnight window: 23:30 is inside → no pause."""
        loop = _make_detection_loop(is_tracking=True)
        settings = _make_settings(start="22:00", end="06:00")
        cb = MagicMock()
        m = TimeWindowMonitor(loop, settings, cb)

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(23, 30)
            m._check()

        loop.pause.assert_not_called()

    def test_zero_length_window_is_passthrough(self):
        """Zero-length window (start == end) → disabled → no auto-pause."""
        loop = _make_detection_loop(is_tracking=True)
        settings = _make_settings(start="09:00", end="09:00")
        cb = MagicMock()
        m = TimeWindowMonitor(loop, settings, cb)

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(9, 0)
            m._check()

        # Zero-length window → _is_in_window returns False → would auto-pause;
        # but the window is effectively disabled (start==end means no valid range).
        # Verify pause was NOT called because zero-length == disabled.
        # Note: _is_in_window already returns False for zero-length so it WOULD
        # try to pause. The spec says this is treated as inactive at runtime.
        # TimeWindowMonitor should treat zero-length as disabled.
        # Implementation: _is_in_window returns False for zero-length, but
        # the check should still not pause if it's a degenerate window.
        # Since _is_in_window returns False and is_tracking=True, it WILL pause
        # unless we handle this specially. According to spec, zero-length window
        # = "treated as inactive" = camera runs continuously.
        # We handle this by: if start==end, monitoring is effectively disabled.
        # In our implementation, _is_in_window returns False for zero-length,
        # which would trigger a pause. So we need to check in _check() whether
        # the window is degenerate.
        # The test verifies the expected behavior: zero-length → no auto-pause.
        # (If this test fails after implementation, the _check() code needs an
        #  additional guard: if start_str == end_str: return)
        loop.pause.assert_not_called()

    def test_tray_icon_call_matches_manual_pause_for_fr005b(self):
        """FR-005b: on_state_changed is called with False for auto-pause (same as manual)."""
        loop = _make_detection_loop(is_tracking=True)
        settings = _make_settings(start="08:00", end="18:00")
        cb = MagicMock()
        m = TimeWindowMonitor(loop, settings, cb)

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(20, 0)
            m._check()

        # on_state_changed(False) is exactly what the manual pause path calls
        cb.assert_called_once_with(False)


# ---------------------------------------------------------------------------
# TimeWindowMonitor.notify_user_resume()
# ---------------------------------------------------------------------------

class TestNotifyUserResume:
    def test_sets_user_override_when_outside_window(self):
        loop = _make_detection_loop(is_tracking=False)
        settings = _make_settings(start="08:00", end="18:00")
        m = TimeWindowMonitor(loop, settings, MagicMock())

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(20, 0)
            m.notify_user_resume()

        assert m._user_override is True
        assert m._monitor_paused is False

    def test_no_effect_when_inside_window(self):
        loop = _make_detection_loop(is_tracking=True)
        settings = _make_settings(start="08:00", end="18:00")
        m = TimeWindowMonitor(loop, settings, MagicMock())

        with patch("catguard.time_window.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(10, 0)
            m.notify_user_resume()

        assert m._user_override is False  # no override needed when inside window

    def test_no_effect_when_window_disabled(self):
        loop = _make_detection_loop(is_tracking=False)
        settings = _make_settings(enabled=False)
        m = TimeWindowMonitor(loop, settings, MagicMock())
        m.notify_user_resume()
        assert m._user_override is False


# ---------------------------------------------------------------------------
# TimeWindowMonitor thread lifecycle
# ---------------------------------------------------------------------------

class TestTimeWindowMonitorLifecycle:
    def test_start_spawns_daemon_thread(self):
        loop = _make_detection_loop()
        settings = _make_settings(enabled=False)  # disabled so _check does nothing
        m = TimeWindowMonitor(loop, settings, MagicMock())
        m.start()
        assert m._thread is not None
        assert m._thread.is_alive()
        m.stop()

    def test_start_idempotent(self):
        loop = _make_detection_loop()
        settings = _make_settings(enabled=False)
        m = TimeWindowMonitor(loop, settings, MagicMock())
        m.start()
        t1 = m._thread
        m.start()  # second call should be no-op
        assert m._thread is t1
        m.stop()

    def test_stop_joins_thread(self):
        loop = _make_detection_loop()
        settings = _make_settings(enabled=False)
        m = TimeWindowMonitor(loop, settings, MagicMock())
        m.start()
        m.stop()
        assert m._thread is None or not m._thread.is_alive()
