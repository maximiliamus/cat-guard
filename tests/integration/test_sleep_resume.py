"""Integration tests: SleepWatcher → DetectionLoop wake-restore flow.

Covers (T012):
- Camera active before sleep → on_wake → detection_loop.resume() called
- Camera paused before sleep → on_wake → detection_loop.resume() NOT called
- Outside time window at wake time → camera remains paused (FR-007, FR-008)
"""
from __future__ import annotations

from datetime import time as dtime
from unittest.mock import MagicMock, patch, call
import threading

import pytest

from catguard.config import Settings
from catguard.detection import DetectionLoop
from catguard.sleep_watcher import SleepWatcher
from catguard import main as main_module


def _make_on_wake_callback(detection_loop, time_window_monitor=None, now_override=None):
    """Mirror of what main.py on_wake() does: check prior state + time window."""
    was_tracking = [detection_loop.is_tracking()]

    def on_wake():
        if not was_tracking[0]:
            return  # was paused before sleep → do not restore
        if time_window_monitor is not None:
            # Evaluate time window: if outside, do not restore
            from catguard.time_window import _is_in_window
            from datetime import datetime
            settings = time_window_monitor._settings
            if settings.tracking_window_enabled:
                now = now_override if now_override is not None else datetime.now().time()
                in_window = _is_in_window(
                    now,
                    settings.tracking_window_start,
                    settings.tracking_window_end,
                )
                if not in_window:
                    return
        detection_loop.resume()

    return on_wake, was_tracking


class TestSleepWakeRestoreIntegration:
    def test_camera_active_before_sleep_restores_on_wake(self):
        """FR-007: camera was active before sleep → restored after wake."""
        loop = DetectionLoop(Settings(), MagicMock())
        loop._is_tracking = True

        on_wake, _ = _make_on_wake_callback(loop)

        # Simulate wake
        loop._is_tracking = False  # sleep "broke" the camera
        loop._stop_event.set()

        on_wake()

        assert loop.is_tracking()

    def test_camera_paused_before_sleep_stays_paused(self):
        """FR-008: camera was paused before sleep → not restored after wake."""
        loop = DetectionLoop(Settings(), MagicMock())
        loop._is_tracking = False
        loop._stop_event.set()

        was_tracking_snapshot = False
        on_wake, _ = _make_on_wake_callback(loop)
        # Override was_tracking to reflect pre-sleep state
        _[0] = False  # was NOT tracking before sleep

        on_wake()

        assert not loop.is_tracking()

    def test_outside_window_at_wake_time_stays_paused(self):
        """FR-007: camera was active pre-sleep but now outside window → remain paused."""
        from catguard.time_window import TimeWindowMonitor

        loop = DetectionLoop(Settings(), MagicMock())
        loop._is_tracking = True

        settings = MagicMock()
        settings.tracking_window_enabled = True
        settings.tracking_window_start = "08:00"
        settings.tracking_window_end = "18:00"
        monitor = TimeWindowMonitor(loop, settings, MagicMock())

        # Pass now_override = 22:00 which is outside the 08:00–18:00 window
        on_wake, _ = _make_on_wake_callback(
            loop, time_window_monitor=monitor, now_override=dtime(22, 0)
        )

        # Sleep "broke" the camera; simulate pre-sleep state was tracking=True
        loop._is_tracking = False
        loop._stop_event.set()
        _[0] = True  # was tracking before sleep

        on_wake()

        assert not loop.is_tracking()

    def test_inside_window_at_wake_restores_camera(self):
        """FR-007: camera was active pre-sleep, wake time inside window → restore."""
        from catguard.time_window import TimeWindowMonitor

        loop = DetectionLoop(Settings(), MagicMock())
        loop._is_tracking = True

        settings = MagicMock()
        settings.tracking_window_enabled = True
        settings.tracking_window_start = "08:00"
        settings.tracking_window_end = "18:00"
        monitor = TimeWindowMonitor(loop, settings, MagicMock())

        # Pass now_override = 10:00 which is inside the 08:00–18:00 window
        on_wake, was_tracking = _make_on_wake_callback(
            loop, time_window_monitor=monitor, now_override=dtime(10, 0)
        )

        loop._is_tracking = False
        loop._stop_event.set()
        was_tracking[0] = True  # was tracking before sleep

        on_wake()

        assert loop.is_tracking()

    def test_watcher_calls_on_wake_after_sleep_gap(self):
        """SleepWatcher fires on_wake when sufficient clock gap detected."""
        on_wake = MagicMock()
        watcher = SleepWatcher(on_wake=on_wake)

        iteration = [0]

        def fake_wait(timeout):
            if iteration[0] == 0:
                iteration[0] += 1
                return False  # one iteration
            return True  # stop

        watcher._stop_event.wait = fake_wait

        with patch("catguard.sleep_watcher.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 45.0, 55.0]  # 45 s gap
            watcher._run()

        on_wake.assert_called_once()


    def test_on_wake_helper_recreates_tray(self):
        """Using the real main helper ensures tray icon is rebuilt after wake."""
        # set up a fake environment similar to unit tests but with real objects
        root = MagicMock()
        root._tray_icon = MagicMock()
        old_icon = root._tray_icon
        stop_event = threading.Event()
        settings = Settings()
        settings.tracking_window_enabled = False
        on_settings_saved = MagicMock()
        loop = DetectionLoop(Settings(), MagicMock())
        loop.is_tracking = MagicMock(return_value=True)
        loop.resume = MagicMock()
        time_window_monitor = MagicMock()
        was_tracking = [True]
        on_track = MagicMock()

        with patch("catguard.main._build_and_prepare_tray_icon") as mock_build, \
             patch("threading.Thread") as mock_thread:
            new_icon = MagicMock()
            mock_build.return_value = new_icon
            callback = main_module._make_on_wake_callback(
                root,
                stop_event,
                settings,
                on_settings_saved,
                loop,
                time_window_monitor,
                was_tracking,
                on_track,
            )
            callback()

        # verify tray was replaced and tracking callback invoked
        old_icon.stop.assert_called_once()
        assert root._tray_icon is new_icon
        mock_thread.return_value.start.assert_called_once()
        on_track.assert_called_once_with(True)
