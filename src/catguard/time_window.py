"""TimeWindowMonitor — auto-pause/resume camera based on a daily time window.

Responsibilities:
- Poll every 30 s to check whether the current time is inside the configured window.
- Pause the detection loop when the clock crosses the window end.
- Resume the detection loop when the clock crosses the window start.
- Support a user-override: if the user clicks Resume while outside the window,
  the camera stays on until the next window-end boundary (FR-004b).
- Notify main.py of state changes via on_state_changed(is_tracking: bool).

Design decisions: research.md R-005, R-006 | data-model.md TimeWindowMonitor
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, time
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from catguard.config import Settings
    from catguard.detection import DetectionLoop

logger = logging.getLogger(__name__)

_POLL_INTERVAL_S = 30


def _is_in_window(now_time: time, start_str: str, end_str: str) -> bool:
    """Return True if *now_time* is within the [start, end) window.

    Handles cross-midnight windows: when end < start the window spans
    midnight, e.g. start="22:00" end="06:00" is active from 22:00 to 06:00.
    A zero-length window (start == end) is treated as disabled → returns False.
    """
    start = time.fromisoformat(start_str)
    end = time.fromisoformat(end_str)

    if start == end:
        return False  # zero-length window → effectively disabled

    if start < end:
        return start <= now_time < end
    else:  # spans midnight
        return now_time >= start or now_time < end


class TimeWindowMonitor:
    """Daemon that auto-pauses/resumes the detection loop based on a daily time window.

    Usage::

        monitor = TimeWindowMonitor(detection_loop, settings, on_state_changed)
        monitor.start()   # starts the background poll thread
        ...
        monitor.stop()    # signals the thread to exit and joins it
    """

    def __init__(
        self,
        detection_loop: "DetectionLoop",
        settings: "Settings",
        on_state_changed: Callable[[bool], None],
    ) -> None:
        self._detection_loop = detection_loop
        self._settings = settings
        self._on_state_changed = on_state_changed
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # True when *this monitor* caused the current pause (not a manual pause).
        self._monitor_paused: bool = False
        # True when user explicitly resumed while outside the window (FR-004b).
        self._user_override: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Spawn the daemon poll thread. Idempotent."""
        if self._thread is not None and self._thread.is_alive():
            logger.debug("TimeWindowMonitor.start(): already running — no-op.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="TimeWindowMonitor", daemon=True
        )
        self._thread.start()
        logger.info("TimeWindowMonitor started (poll interval: %s s).", _POLL_INTERVAL_S)

    def stop(self) -> None:
        """Signal the thread to stop and join with a 3 s timeout."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("TimeWindowMonitor stopped.")

    def notify_user_resume(self) -> None:
        """Called by the tray Resume handler when the user overrides auto-pause.

        Sets _user_override=True so the monitor will not re-pause the camera
        until the next window-end boundary (FR-004b).
        """
        if not self._settings.tracking_window_enabled:
            return
        now = datetime.now().time()
        in_window = _is_in_window(
            now,
            self._settings.tracking_window_start,
            self._settings.tracking_window_end,
        )
        if not in_window:
            self._user_override = True
            self._monitor_paused = False
            logger.info(
                "TimeWindowMonitor: user override set — camera will stay on until next window-end."
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Background daemon: evaluate window on start, then every 30 s."""
        # Evaluate immediately on startup
        self._check()
        while not self._stop_event.wait(timeout=_POLL_INTERVAL_S):
            self._check()

    def _check(self) -> None:
        """Evaluate current time against the window and pause/resume as needed."""
        if not self._settings.tracking_window_enabled:
            return
        # Zero-length window (start == end) is treated as disabled at runtime
        if self._settings.tracking_window_start == self._settings.tracking_window_end:
            return

        now = datetime.now().time()
        in_window = _is_in_window(
            now,
            self._settings.tracking_window_start,
            self._settings.tracking_window_end,
        )
        is_tracking = self._detection_loop.is_tracking()

        logger.debug(
            "TimeWindowMonitor._check(): in_window=%s is_tracking=%s "
            "_monitor_paused=%s _user_override=%s",
            in_window, is_tracking, self._monitor_paused, self._user_override,
        )

        if in_window:
            # Window is active — clear user override (no longer needed)
            if self._user_override:
                self._user_override = False
                logger.info("TimeWindowMonitor: entered window — user override cleared.")
            # Resume if *we* caused the pause
            if not is_tracking and self._monitor_paused:
                self._monitor_paused = False
                self._detection_loop.resume()
                logger.info("TimeWindowMonitor: window opened — detection resumed.")
                self._on_state_changed(True)
        else:
            # Outside window
            if is_tracking and not self._user_override:
                # Auto-pause: window just closed (or app started outside window)
                self._monitor_paused = True
                self._detection_loop.pause()
                logger.info("TimeWindowMonitor: window closed — detection paused.")
                self._on_state_changed(False)
            elif is_tracking and self._user_override:
                # User override active — do nothing
                logger.debug("TimeWindowMonitor: outside window but user override active — no-op.")
            elif not is_tracking and not self._monitor_paused:
                # Already paused by user — do nothing
                pass
            elif not is_tracking and self._monitor_paused:
                # Already paused by us — still outside window → stay paused
                pass
