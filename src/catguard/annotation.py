"""Frame annotation and async save helpers for cat-session tracking.

Responsibilities:
- annotate_frame(): apply bounding boxes, sound label, and outcome overlay to a frame
- build_sound_label(): normalise play_alert() return value for display
- format_session_duration(): render compact elapsed durations for overlays and logs
- EffectivenessTracker: manage session metadata and save the on-disk frame timeline
- _save_annotated_async(): fire-and-forget daemon thread for async disk write

All annotation is applied to a *copy* of the input frame; the original is never
modified.  Disk writes are always asynchronous and errors are isolated so they
never propagate to the detection loop (NFR-002).
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime as _dt
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]

try:
    from PIL import Image as _PIL_Image
    from PIL import ImageDraw as _PIL_ImageDraw
    from PIL import ImageFont as _PIL_ImageFont
except ImportError:  # pragma: no cover
    _PIL_Image = None  # type: ignore[assignment]
    _PIL_ImageDraw = None  # type: ignore[assignment]
    _PIL_ImageFont = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from catguard.config import Settings
    from catguard.detection import BoundingBox

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Visual constants  (research.md §1, §2)
# ---------------------------------------------------------------------------

BOX_COLOR = (0, 200, 0)        # BGR — softer than pure green
BOX_THICKNESS = 2

FONT = cv2.FONT_HERSHEY_SIMPLEX if cv2 is not None else None
FONT_SCALE = 0.55
FONT_THICK = 1
LABEL_PAD = 4
LINE_TYPE = cv2.LINE_AA if cv2 is not None else None

DETECTED_BG = (64, 64, 64)     # BGR dark gray
SUCCESS_BG = (0, 180, 0)       # BGR green
FAILURE_BG = (0, 0, 200)       # BGR red
TEXT_COLOR = (255, 255, 255)    # white
OUTCOME_FONT_SCALE = 0.7
OUTCOME_THICK = 2
OUTCOME_PAD = 10

# Approximate y-start of the outcome strip in a typical frame.
# Used by tests to verify non-overlap with the sound label zone.
# Actual value depends on frame height; this constant reflects a 200px frame.
OUTCOME_STRIP_Y1_APPROX = 150  # ~bottom 50px of a 200px frame

# Font size used by all PIL-rendered text overlays (sound label, timestamp).
OVERLAY_FONT_SIZE = 16
OVERLAY_PAD = 4  # pixels of padding around PIL text labels
OVERLAY_BG = (0, 0, 0)  # pure black background for top-bar labels

# Both the top info bar and the bottom outcome strip use this exact pixel height
# so the two bands are visually symmetric.
BAR_HEIGHT = OVERLAY_FONT_SIZE + OVERLAY_PAD * 4  # 16 + 16 = 32 px


# ---------------------------------------------------------------------------
# T011: build_sound_label()
# ---------------------------------------------------------------------------

def build_sound_label(value: Optional[str]) -> str:
    """Normalise the raw string returned by play_alert() for screenshot display.

    | Input                | Output                    |
    |----------------------|---------------------------|
    | None                 | "Alert: Default"          |
    | "Alert: Default"     | "Alert: Default" (pass-through) |
    | absolute path string | Path(value).name          |
    | relative path string | Path(value).name          |
    | plain filename       | value (pass-through)      |
    """
    if value is None:
        return "Alert: Default"
    return Path(value).name


def format_session_duration(total_seconds: float | int) -> str:
    """Return a compact human-readable session duration string."""
    total = max(0, int(total_seconds))
    if total < 60:
        return f"{total}s"

    minutes, seconds = divmod(total, 60)
    if total < 3600:
        return f"{minutes}m {seconds}s"

    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {seconds}s"


# ---------------------------------------------------------------------------
# T012 + T013 + T018: annotate_frame()
# ---------------------------------------------------------------------------

def annotate_frame(
    frame_bgr: "np.ndarray",
    boxes: "list[BoundingBox]",
    sound_label: str,
    outcome: Optional[str],
    outcome_message: Optional[str] = None,
) -> "np.ndarray":
    """Apply all three annotation layers to a *copy* of the input frame.

    Layers (non-overlapping by design — research.md annotation zones):
    1. **Bounding boxes** — rectangle + confidence % label on filled rect,
       drawn on the detected cat regions.
    2. **Sound label** — filename or "Alert: Default" in the top-left corner.
    3. **Outcome overlay** — full-width filled strip at the bottom edge:
       dark gray for ``"detected"``, green for ``"deterred"``,
       red for ``"remained"``, absent for ``None``.

    Parameters
    ----------
    frame_bgr:
        Source BGR ndarray; a copy is made internally — not modified in place.
    boxes:
        Detected bounding boxes to annotate.
    sound_label:
        Text for the top-left corner (already normalised by build_sound_label).
    outcome:
        ``"detected"``, ``"deterred"``, ``"remained"``, or ``None``.
        Determines the **colour** of the outcome strip. When ``None``, no strip
        is drawn regardless of *outcome_message*.
    outcome_message:
        Optional custom text for the outcome strip. When provided and *outcome*
        is not ``None``, this string replaces the hardcoded
        default strip text.  Useful for session-timed labels such as
        ``"Cat remained after alert: 30s"``.

    Returns
    -------
    np.ndarray
        New annotated BGR ndarray.
    """
    out = frame_bgr.copy()

    # --- Layer 1: Bounding boxes (T012) -----------------------------------
    for box in boxes:
        label = f"{box.label} {int(box.confidence * 100)}%"
        _draw_labelled_box(out, box.x1, box.y1, box.x2, box.y2, label)

    # --- Layer 2: Top info bar — sound label left, timestamp right (T013) --
    _draw_top_bar(out, sound_label)

    # --- Layer 3: Outcome overlay bottom strip (T018) ----------------------
    if outcome == "detected":
        text = outcome_message if outcome_message is not None else "Cat detected"
        _draw_outcome_strip(out, DETECTED_BG, text)
    elif outcome == "deterred":
        text = outcome_message if outcome_message is not None else "Cat disappeared after alert"
        _draw_outcome_strip(out, SUCCESS_BG, text)
    elif outcome == "remained":
        text = outcome_message if outcome_message is not None else "Cat remained after alert"
        _draw_outcome_strip(out, FAILURE_BG, text)
    else:
        # outcome=None: no strip drawn; warn so it shows up in logs (T024)
        logger.warning(
            "annotate_frame: outcome is %r — no outcome strip will be drawn.",
            outcome,
        )

    return out


def _draw_labelled_box(
    frame: "np.ndarray",
    x1: int, y1: int, x2: int, y2: int,
    label: str,
) -> None:
    """Draw a bounding box rectangle with a confidence label on a filled rect.

    Label placement uses a 5-candidate fallback chain to stay on-screen
    (FR-016–FR-019, research.md R-003):
      1. Above box (default)
      2. Below box
      3. Left of box
      4. Right of box
      5. Center of box (last resort — always used if no edge position fits)
    """
    h, w = frame.shape[:2]

    # Draw the box outline
    cv2.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, BOX_THICKNESS)

    # Measure label text dimensions
    (tw, th), baseline = cv2.getTextSize(label, FONT, FONT_SCALE, FONT_THICK)

    def _label_fits(lx: int, ly: int) -> bool:
        """Return True if the label background rect fits entirely within the frame."""
        bg_x1 = lx - LABEL_PAD
        bg_y1 = ly - th - LABEL_PAD
        bg_x2 = lx + tw + LABEL_PAD
        bg_y2 = ly + baseline + LABEL_PAD
        return bg_x1 >= 0 and bg_y1 >= 0 and bg_x2 <= w and bg_y2 <= h

    mid_y_label = (y1 + y2) // 2  # vertical midpoint of the box

    # Ordered candidate anchor points (label_x, label_y)
    candidates = [
        (x1, y1 - LABEL_PAD),                          # 1. above box
        (x1, y2 + th + LABEL_PAD),                     # 2. below box
        (x1 - tw - 2 * LABEL_PAD, mid_y_label),        # 3. left of box
        (x2 + LABEL_PAD, mid_y_label),                  # 4. right of box
    ]

    chosen_lx, chosen_ly = None, None
    for lx, ly in candidates:
        if _label_fits(lx, ly):
            chosen_lx, chosen_ly = lx, ly
            break

    # 5. Center fallback — always drawn, even if partially off-screen (FR-019)
    if chosen_lx is None:
        chosen_lx = (x1 + x2) // 2 - tw // 2
        chosen_ly = (y1 + y2) // 2
        logger.debug(
            "_draw_labelled_box: all edge positions off-screen for box "
            "(%d,%d,%d,%d) — using center fallback.",
            x1, y1, x2, y2,
        )

    # Render background rect + text at the chosen position
    bg_x1 = chosen_lx - LABEL_PAD
    bg_y1 = chosen_ly - th - LABEL_PAD
    bg_x2 = chosen_lx + tw + LABEL_PAD
    bg_y2 = chosen_ly + baseline + LABEL_PAD
    cv2.rectangle(frame, (bg_x1, bg_y1), (bg_x2, bg_y2), BOX_COLOR, -1)
    cv2.putText(
        frame, label, (chosen_lx, chosen_ly),
        FONT, FONT_SCALE, TEXT_COLOR, FONT_THICK, LINE_TYPE,
    )


def _load_unicode_font(size: int = 16):
    """Return a PIL font that covers Unicode (Cyrillic, CJK, etc.).

    Tries a prioritised list of system TrueType fonts and falls back to the
    PIL built-in bitmap font, which at least won't raise even if it can't
    render non-ASCII glyphs correctly.
    """
    _CANDIDATE_FONTS = [
        # Windows
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
        # Linux / WSL
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
        # macOS
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in _CANDIDATE_FONTS:
        try:
            return _PIL_ImageFont.truetype(path, size)
        except (OSError, AttributeError):
            continue
    # Last resort: PIL's built-in default (ASCII only, but never raises)
    return _PIL_ImageFont.load_default()


def _draw_top_bar(frame: "np.ndarray", sound_label: str) -> None:
    """Render a full-width black info bar at the top of the frame in-place.

    The bar is exactly BAR_HEIGHT pixels tall — the same as the bottom outcome
    strip — so both bands are visually symmetric.

    Left side : alert sound filename (Unicode-safe via Pillow).
    Right side: current local date/time.
    """
    timestamp = _dt.now().strftime("%x  %X")  # locale-aware (FR-020/FR-021; R-002)

    _h, w = frame.shape[:2]
    pad = OVERLAY_PAD

    if _PIL_Image is None or _PIL_ImageDraw is None or _PIL_ImageFont is None:
        _draw_top_bar_cv2(frame, sound_label, timestamp)
        return

    pil_img = _PIL_Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = _PIL_ImageDraw.Draw(pil_img)
    font = _load_unicode_font(OVERLAY_FONT_SIZE)

    # Full-width background strip
    draw.rectangle((0, 0, w, BAR_HEIGHT), fill=OVERLAY_BG)

    # Pin both texts to the vertical midpoint of the bar using anchor="lm"
    # (left-middle). This makes Pillow place the text so its visual centre
    # sits exactly at mid_y, irrespective of per-glyph ascender/descender
    # offsets that vary between "filename" strings and digit-heavy timestamps.
    mid_y = BAR_HEIGHT // 2
    ts_w = int(draw.textlength(timestamp, font=font))

    # Left: sound label
    draw.text((pad, mid_y), sound_label, font=font, fill=(255, 255, 255), anchor="lm")
    # Right: timestamp — identical mid_y guarantees baseline alignment
    draw.text((w - ts_w - pad, mid_y), timestamp, font=font, fill=(255, 255, 255), anchor="lm")

    # Write back to frame in-place (BGR)
    frame[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def _draw_top_bar_cv2(frame: "np.ndarray", sound_label: str, timestamp: str) -> None:
    """Fallback top-bar renderer used when Pillow is unavailable."""
    _h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, BAR_HEIGHT), OVERLAY_BG, -1)

    (_, sound_h), sound_baseline = cv2.getTextSize(
        sound_label, FONT, FONT_SCALE, FONT_THICK
    )
    (ts_w, ts_h), ts_baseline = cv2.getTextSize(
        timestamp, FONT, FONT_SCALE, FONT_THICK
    )
    sound_y = (BAR_HEIGHT + sound_h - sound_baseline) // 2
    ts_y = (BAR_HEIGHT + ts_h - ts_baseline) // 2

    cv2.putText(
        frame, sound_label, (OVERLAY_PAD, sound_y),
        FONT, FONT_SCALE, TEXT_COLOR, FONT_THICK, LINE_TYPE,
    )
    cv2.putText(
        frame, timestamp, (w - ts_w - OVERLAY_PAD, ts_y),
        FONT, FONT_SCALE, TEXT_COLOR, FONT_THICK, LINE_TYPE,
    )


def _draw_outcome_strip(
    frame: "np.ndarray",
    bg_color: tuple,
    text: str,
) -> None:
    """Render a full-width filled strip with outcome text at the bottom edge.

    Strip height equals BAR_HEIGHT so the top and bottom bands are symmetric.
    """
    h, w = frame.shape[:2]
    rect_y1 = h - BAR_HEIGHT
    # Full-width background strip
    cv2.rectangle(frame, (0, rect_y1), (w, h), bg_color, -1)
    # Center text vertically within the strip
    (tw, th), baseline = cv2.getTextSize(
        text, FONT, OUTCOME_FONT_SCALE, OUTCOME_THICK
    )
    margin = (BAR_HEIGHT - th - baseline) // 2
    text_y = rect_y1 + margin + th
    cv2.putText(
        frame, text,
        (OUTCOME_PAD, text_y),
        FONT, OUTCOME_FONT_SCALE, TEXT_COLOR, OUTCOME_THICK, LINE_TYPE,
    )


# ---------------------------------------------------------------------------
# T019: _save_annotated_async()
# ---------------------------------------------------------------------------


def _save_annotated_async(
    frame: "np.ndarray",
    settings: "Settings",
    is_window_open: Callable[[], bool],
    on_error: Callable[[str], None],
    filepath: Optional[Path] = None,
) -> None:
    """Fire-and-forget daemon thread: annotate and save *frame* to disk.

    Mirrors the _play_async pattern in audio.py.  All exceptions are caught,
    logged, and forwarded to *on_error* — they never propagate to the caller
    (NFR-002).  The thread is daemonised so it does not block app exit.

    When *filepath* is provided it is forwarded unchanged to ``save_screenshot``,
    which bypasses both the window-open and time-window suppression checks and
    writes to the caller-supplied path directly.
    """
    def _worker() -> None:
        try:
            from catguard.screenshots import save_screenshot
            logger.info(
                "_save_annotated_async: dispatching save (is_window_open=%s, filepath=%s)",
                is_window_open(),
                filepath,
            )
            save_screenshot(frame, settings, is_window_open, on_error, filepath=filepath)
            logger.info("_save_annotated_async: save completed.")
        except Exception as exc:
            msg = f"Annotated screenshot save failed: {exc}"
            logger.error(msg, exc_info=True)
            try:
                on_error(msg)
            except Exception:
                logger.exception("on_error callback raised in _save_annotated_async.")

    threading.Thread(target=_worker, name="AnnotatedSave", daemon=True).start()


# ---------------------------------------------------------------------------
# T020: EffectivenessTracker
# ---------------------------------------------------------------------------

class EffectivenessTracker:
    """Manage the saved on-disk timeline for one active cat session."""

    def __init__(
        self,
        settings: "Settings",
        is_window_open: Callable[[], bool],
        on_error: Callable[[str], None],
    ) -> None:
        self._settings = settings
        self._is_window_open = is_window_open
        self._on_error = on_error

        self._session_start: Optional[_dt] = None
        self._cycle_count: int = 0
        self._frame_index: int = 0
        self._active_sound_label: Optional[str] = None
        self._awaiting_verification: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def _is_pending(self) -> bool:
        """True while the active alert cycle is waiting for verification."""
        return self._awaiting_verification

    def on_detection(
        self,
        frame: "np.ndarray",
        boxes: "list[BoundingBox]",
        sound_label: str,
    ) -> None:
        """Start or advance a session when an alerting detection fires."""
        if self._is_pending:
            logger.debug(
                "EffectivenessTracker.on_detection: already awaiting verification; "
                "ignoring duplicate detection."
            )
            return

        if frame is None:
            logger.debug(
                "EffectivenessTracker.on_detection: detection frame missing; ignoring."
            )
            return

        from catguard.screenshots import build_session_filepath, resolve_root

        is_new_session = self._session_start is None
        if self._session_start is None:
            self._session_start = _dt.now()
            self._cycle_count = 1
            self._frame_index = 1
        else:
            self._cycle_count += 1
        self._active_sound_label = sound_label
        self._awaiting_verification = True

        if not is_new_session:
            logger.info(
                "EffectivenessTracker.on_detection: cycle %d started for existing "
                "session (frame_index=%d, sound=%r).",
                self._cycle_count,
                self._frame_index,
                sound_label,
            )
            return

        filepath = build_session_filepath(
            resolve_root(self._settings), self._session_start, self._frame_index
        )
        annotated = annotate_frame(
            frame,
            boxes,
            build_sound_label(sound_label),
            "detected",
        )
        logger.info(
            "EffectivenessTracker.on_detection: session started at %s "
            "(cycle=%d, frame_index=%d, filepath=%s).",
            self._session_start,
            self._cycle_count,
            self._frame_index,
            filepath,
        )
        _save_annotated_async(
            annotated,
            self._settings,
            lambda: False,
            self._on_error,
            filepath=filepath,
        )

    def on_verification(
        self,
        frame_bgr: "np.ndarray",
        has_cat: bool,
        boxes: "list[BoundingBox]",
    ) -> None:
        """Annotate and save the live verification frame for the current cycle."""
        if self._session_start is None or not self._awaiting_verification:
            logger.debug(
                "EffectivenessTracker.on_verification: no active verification pending."
            )
            return

        session_start = self._session_start
        cycle_count = self._cycle_count
        next_frame_index = self._frame_index + 1
        sound_label = build_sound_label(self._active_sound_label)
        self._awaiting_verification = False
        elapsed_s = int(cycle_count * self._settings.cooldown_seconds)
        elapsed_text = format_session_duration(elapsed_s)

        if has_cat:
            outcome: Optional[str] = "remained"
            outcome_message = f"Cat remained after alert: {elapsed_text}"
        else:
            outcome = "deterred"
            outcome_message = f"Cat disappeared after alert: {elapsed_text}"

        from catguard.screenshots import build_session_filepath, resolve_root
        filepath = build_session_filepath(
            resolve_root(self._settings), session_start, next_frame_index
        )

        annotated = annotate_frame(
            frame_bgr,
            boxes,
            sound_label,
            outcome,
            outcome_message=outcome_message,
        )
        self._frame_index = next_frame_index
        logger.info(
            "EffectivenessTracker.on_verification: outcome=%s "
            "(cycle=%d, frame_index=%d, elapsed=%s, filepath=%s).",
            outcome,
            cycle_count,
            self._frame_index,
            elapsed_text,
            filepath,
        )
        _save_annotated_async(
            annotated,
            self._settings,
            lambda: False,
            self._on_error,
            filepath=filepath,
        )

        if has_cat:
            return

        total_frames = self._frame_index
        logger.info(
            "EffectivenessTracker.on_verification: session closed "
            "(saved_frames=%d, elapsed=%s).",
            total_frames,
            elapsed_text,
        )
        self._reset_session()

    def abandon(self) -> None:
        """Immediately abandon the active session without creating a closing frame."""
        was_active = self._session_start is not None or self._awaiting_verification
        if was_active:
            elapsed_text = format_session_duration(
                int(self._cycle_count * self._settings.cooldown_seconds)
            )
            logger.info(
                "EffectivenessTracker.abandon: session abandoned "
                "(cycle=%d, frame_index=%d, elapsed=%s, session_start=%s).",
                self._cycle_count,
                self._frame_index,
                elapsed_text,
                self._session_start,
            )
        self._reset_session()

    def _reset_session(self) -> None:
        """Return the tracker to its idle state."""
        self._session_start = None
        self._cycle_count = 0
        self._frame_index = 0
        self._active_sound_label = None
        self._awaiting_verification = False
