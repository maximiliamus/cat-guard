"""SleepWatcher — detect system wake events via time-jump polling.

Design: a daemon thread sleeps for N seconds and then compares the actual
wall-clock elapsed time against expected.  If the gap is significantly larger
than expected, the system was asleep and has just woken up.

Threshold: sleep 10 s, flag a wake event when elapsed > 30 s.  This tolerates
normal OS scheduling jitter and gives sub-10-second wake-detection latency.

Research decision: research.md R-001.
No new runtime dependencies — uses only Python stdlib (threading, time).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_SLEEP_INTERVAL_S = 10       # thread sleep interval (seconds)
_WAKE_THRESHOLD_S = 30       # gap larger than this → wake detected


class SleepWatcher:
    """Daemon that calls *on_wake* whenever a system sleep/wake cycle is detected.

    Usage::

        watcher = SleepWatcher(on_wake=my_callback)
        watcher.start()
        ...
        watcher.stop()
    """

    def __init__(self, on_wake: Callable[[], None]) -> None:
        self._on_wake = on_wake
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Spawn the daemon poll thread.  Idempotent if already running."""
        if self._thread is not None and self._thread.is_alive():
            logger.debug("SleepWatcher.start(): already running — no-op.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="SleepWatcher", daemon=True
        )
        self._thread.start()
        logger.info(
            "SleepWatcher started (sleep=%s s, wake threshold=%s s).",
            _SLEEP_INTERVAL_S,
            _WAKE_THRESHOLD_S,
        )

    def stop(self) -> None:
        """Signal the thread to stop and join with a 3 s timeout."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("SleepWatcher stopped.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Daemon loop: compare expected vs actual elapsed time."""
        last_check = time.monotonic()
        while not self._stop_event.wait(timeout=_SLEEP_INTERVAL_S):
            now = time.monotonic()
            elapsed = now - last_check
            last_check = now

            if elapsed > _WAKE_THRESHOLD_S:
                logger.info(
                    "SleepWatcher: wake from sleep detected (elapsed=%.1f s).", elapsed
                )
                try:
                    self._on_wake()
                except Exception:
                    logger.exception("SleepWatcher: on_wake callback raised an error.")
            else:
                logger.debug("SleepWatcher: tick (elapsed=%.1f s).", elapsed)
