"""Screenshot capture on cat detection.

Pure functions — no tkinter dependency.
All I/O is synchronous; runs on the DetectionLoop daemon thread.

Public API
----------
resolve_root(settings)           → Path
build_filepath(root, ts)         → Path
is_within_time_window(settings)  → bool
save_screenshot(frame_bgr, settings, is_window_open, on_error)
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

try:
    import cv2  # noqa: F401 — imported here so tests can patch catguard.screenshots.cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]

if TYPE_CHECKING:
    import numpy as np
    from catguard.config import Settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# resolve_root
# ---------------------------------------------------------------------------

def resolve_root(settings: "Settings") -> Path:
    """Return the effective tracking root folder as an absolute Path.

    Uses ``settings.tracking_directory``. If it's a relative path, 
    it's resolved relative to the current working directory.
    """
    path = Path(settings.tracking_directory)
    if not path.is_absolute():
        path = path.resolve()
    return path


# ---------------------------------------------------------------------------
# build_filepath
# ---------------------------------------------------------------------------

def build_filepath(root: Path, ts: datetime) -> Path:
    """Return a collision-safe JPEG file path for *ts* inside *root*.

    Structure: ``<root>/<yyyy-mm-dd>/<HH-MM-SS[-N]>.jpg``

    If ``<HH-MM-SS>.jpg`` already exists, a counter suffix is appended:
    ``<HH-MM-SS-1>.jpg``, ``<HH-MM-SS-2>.jpg``, … until an unused name is found.
    """
    date_folder = root / ts.strftime("%Y-%m-%d")
    base_name = ts.strftime("%H-%M-%S")

    candidate = date_folder / f"{base_name}.jpg"
    if not candidate.exists():
        return candidate

    counter = 1
    while True:
        candidate = date_folder / f"{base_name}-{counter}.jpg"
        if not candidate.exists():
            return candidate
        counter += 1


# ---------------------------------------------------------------------------
# is_within_time_window
# ---------------------------------------------------------------------------

def is_within_time_window(settings: "Settings") -> bool:
    """Return True if the current wall-clock time falls inside the configured window.

    Always returns True when the time window is disabled.

    Window semantics (FR-013 to FR-016):
    - If ``start < end``: same-day window — True when ``start ≤ now < end``
    - If ``start > end``: midnight-spanning — True when ``now ≥ start OR now < end``
    - If ``start == end``: degenerate — treated as disabled (True), logs warning
    """
    if not settings.tracking_window_enabled:
        return True

    import re
    _HHMM_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")

    def _parse(t: str):
        from datetime import time as dt_time
        if not isinstance(t, str) or not _HHMM_RE.match(t):
            return None
        h, m = int(t[:2]), int(t[3:])
        return dt_time(h, m)

    start = _parse(settings.tracking_window_start)
    end = _parse(settings.tracking_window_end)

    if start is None or end is None:
        logger.warning(
            "Invalid time window values (%r, %r) — treating as disabled.",
            settings.tracking_window_start,
            settings.tracking_window_end,
        )
        return True

    if start == end:
        logger.warning(
            "Time window start == end (%r) — degenerate case; treating as disabled.",
            settings.tracking_window_start,
        )
        return True

    now = datetime.now().time()

    if start < end:  # Same-day window, e.g. 08:00–18:00
        return start <= now < end
    else:
        # Midnight-spanning window, e.g. 22:00–06:00
        return now >= start or now < end


# ---------------------------------------------------------------------------
# save_screenshot
# ---------------------------------------------------------------------------

def save_screenshot(
    frame_bgr: Optional["np.ndarray"],
    settings: "Settings",
    is_window_open: Callable[[], bool],
    on_error: Callable[[str], None],
) -> None:
    """Attempt to save *frame_bgr* as a maximum-compression JPEG.

    Silently skips (no file, no error) when:
    - *frame_bgr* is None  (cooldown-suppressed event — FR-011)
    - The main window is open  (FR-012)
    - Outside the configured time window  (FR-015)

    On any I/O failure, logs the error and calls ``on_error(message)``.
    Never raises; the alert sound path is completely unaffected.
    """
    # FR-011: cooldown-suppressed events carry no frame
    if frame_bgr is None:
        return

    # FR-012: suppress when main window is visible
    if is_window_open():
        logger.info("save_screenshot: skipped — main window is open.")
        return

    # FR-015: suppress outside the configured time window
    if not is_within_time_window(settings):
        logger.info("save_screenshot: skipped — outside configured time window.")
        return

    try:
        root = resolve_root(settings)
        path = build_filepath(root, datetime.now())
        path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("save_screenshot: attempting to save screenshot to %s", path)

        # Use a high-quality JPEG setting so images remain human-readable.
        # Lower numbers are higher compression / lower quality; use 90 for
        # a good trade-off between size and visual fidelity.
        ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            raise RuntimeError("cv2.imencode returned False — could not encode frame.")

        path.write_bytes(buf.tobytes())
        logger.info("Screenshot saved: %s", path)

    except Exception as exc:
        msg = f"Screenshot save failed: {exc}"
        logger.error(msg, exc_info=True)
        try:
            on_error(msg)
        except Exception:
            logger.exception("on_error callback itself raised an exception.")

