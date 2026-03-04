"""Unit tests for catguard.sleep_watcher — SleepWatcher.

Covers (TDD — T011):
- on_wake not called for a normal 10 s tick
- on_wake called when elapsed > 30 s (wake from sleep)
- stop() prevents further calls
- start() is idempotent (no duplicate threads)
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from catguard.sleep_watcher import SleepWatcher, _SLEEP_INTERVAL_S, _WAKE_THRESHOLD_S


class TestSleepWatcherUnit:
    """Drive _run() logic directly to avoid relying on real clock timing."""

    def test_on_wake_not_called_for_normal_tick(self):
        """Normal 10 s elapsed — no wake event."""
        callback = MagicMock()
        watcher = SleepWatcher(on_wake=callback)

        # Simulate one iteration: elapsed ≈ 10 s (below threshold)
        watcher._stop_event.set()  # stop after one iteration
        with patch("catguard.sleep_watcher.time") as mock_time:
            # Each call to monotonic returns: start, after-sleep (10 s later)
            mock_time.monotonic.side_effect = [0.0, 10.0, 20.0]
            mock_time.sleep = time.sleep  # not used since we use Event.wait
            watcher._run()

        callback.assert_not_called()

    def test_on_wake_called_when_elapsed_exceeds_threshold(self):
        """Elapsed > 30 s → wake detected."""
        callback = MagicMock()
        watcher = SleepWatcher(on_wake=callback)

        # Simulate: thread "wakes" with a 40 s elapsed gap
        calls = []

        def fake_wait(timeout):
            if len(calls) == 0:
                calls.append(1)
                return False  # keep running
            return True  # stop

        watcher._stop_event.wait = fake_wait

        # monotonic(): initial value, then +40 s gap
        with patch("catguard.sleep_watcher.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 40.0, 50.0]
            watcher._run()

        callback.assert_called_once()

    def test_stop_prevents_on_wake(self):
        """After stop(), on_wake is not called even if elapsed > 30 s."""
        callback = MagicMock()
        watcher = SleepWatcher(on_wake=callback)
        watcher._stop_event.set()  # pre-stop

        with patch("catguard.sleep_watcher.time") as mock_time:
            mock_time.monotonic.return_value = 0.0
            watcher._run()  # should exit immediately

        callback.assert_not_called()

    def test_start_spawns_daemon_thread(self):
        callback = MagicMock()
        watcher = SleepWatcher(on_wake=callback)
        watcher.start()
        assert watcher._thread is not None
        assert watcher._thread.is_alive()
        assert watcher._thread.daemon is True
        watcher.stop()

    def test_start_idempotent(self):
        callback = MagicMock()
        watcher = SleepWatcher(on_wake=callback)
        watcher.start()
        t1 = watcher._thread
        watcher.start()  # second call → no-op
        assert watcher._thread is t1
        watcher.stop()

    def test_stop_joins_thread(self):
        callback = MagicMock()
        watcher = SleepWatcher(on_wake=callback)
        watcher.start()
        watcher.stop()
        # After stop(), thread should be None (joined)
        assert watcher._thread is None

    def test_on_wake_exception_does_not_crash_watcher(self):
        """If on_wake() raises, the watcher loop must not crash."""
        callback = MagicMock(side_effect=RuntimeError("boom"))
        watcher = SleepWatcher(on_wake=callback)

        call_count = [0]

        def fake_wait(timeout):
            if call_count[0] == 0:
                call_count[0] += 1
                return False
            return True  # stop after one iteration

        watcher._stop_event.wait = fake_wait

        with patch("catguard.sleep_watcher.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 40.0, 50.0]
            # Should not raise
            watcher._run()

        callback.assert_called_once()
