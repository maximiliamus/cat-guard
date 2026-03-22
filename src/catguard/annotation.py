"""Frame annotation and delayed-save for alert effectiveness tracking.

Responsibilities:
- annotate_frame(): apply bounding boxes, sound label, and outcome overlay to a frame
- build_sound_label(): normalise play_alert() return value for display
- EffectivenessTracker: manage pending snapshot lifecycle (store → verify → save)
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
       green for ``"deterred"``, red for ``"remained"``, absent for ``None``.

    Parameters
    ----------
    frame_bgr:
        Source BGR ndarray; a copy is made internally — not modified in place.
    boxes:
        Detected bounding boxes to annotate.
    sound_label:
        Text for the top-left corner (already normalised by build_sound_label).
    outcome:
        ``"deterred"``, ``"remained"``, or ``None`` (unknown / not yet determined).
        Determines the **colour** of the outcome strip.  When ``None``, no strip
        is drawn regardless of *outcome_message*.
    outcome_message:
        Optional custom text for the outcome strip.  When provided and *outcome*
        is ``"deterred"`` or ``"remained"``, this string replaces the hardcoded
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
    if outcome == "deterred":
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
    """Manages the pending screenshot lifecycle for alert effectiveness tracking.

    State machine::

        [idle]
          ──on_detection()──▶ [pending: frame held in memory]
                                    │
                      on_detection() while pending → silently ignored (FR-005a)
                                    │
                              on_verification(has_cat)
                                    │
                          ┌─────────┴──────────┐
                     has_cat=False          has_cat=True
                          │                     │
                   outcome="deterred"    outcome="remained"
                          └─────────┬──────────┘
                          annotate_frame(outcome)
                          _save_annotated_async()
                          clear pending state
                                    │
                                 [idle]

    Thread safety: on_detection() is called from the main thread (main.py
    on_cat_detected callback); on_verification() is called from the
    DetectionLoop daemon thread.  The pending state is guarded by the fact
    that only one SOUND_PLAYED event fires per cooldown cycle (FR-005a) and
    the loop clears _pending_frame before invoking on_verification.
    """

    def __init__(
        self,
        settings: "Settings",
        is_window_open: Callable[[], bool],
        on_error: Callable[[str], None],
    ) -> None:
        self._settings = settings
        self._is_window_open = is_window_open
        self._on_error = on_error

        self._pending_frame: Optional["np.ndarray"] = None
        self._pending_boxes: "list[BoundingBox]" = []
        self._pending_sound: Optional[str] = None

        # Session tracking state (FR-010, Plan Change 2)
        self._session_start: Optional[_dt] = None
        self._cycle_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def _is_pending(self) -> bool:
        """True while a detection frame is held in memory awaiting verification."""
        return self._pending_frame is not None

    def on_detection(
        self,
        frame: "np.ndarray",
        boxes: "list[BoundingBox]",
        sound_label: str,
    ) -> None:
        """Store a deep copy of the detection frame for later annotation.

        Three-state logic (FR-005a, FR-010, Plan Change 2):
        (a) Already pending → silently ignore (mid-cycle guard).
        (b) No active session → start new session (set _session_start, _cycle_count=1).
        (c) Session open, between cycles → increment _cycle_count.
        Common step: store pending frame, boxes, sound.
        """
        # State (a): already pending — ignore until verification clears it
        if self._is_pending:
            logger.debug(
                "EffectivenessTracker.on_detection: already pending — ignoring "
                "(FR-005a)."
            )
            return

        if self._session_start is None:
            # State (b): no active session — start a new one
            self._session_start = _dt.now()
            self._cycle_count = 1
            logger.info(
                "EffectivenessTracker.on_detection: new session started at %s.",
                self._session_start,
            )
        else:
            # State (c): session open, between cycles — advance cycle counter
            self._cycle_count += 1
            logger.debug(
                "EffectivenessTracker.on_detection: session cycle %d.",
                self._cycle_count,
            )

        self._pending_frame = frame.copy()
        self._pending_boxes = list(boxes)
        self._pending_sound = sound_label
        logger.debug(
            "EffectivenessTracker.on_detection: stored frame (%dx%d), "
            "%d box(es), sound=%r.",
            frame.shape[1], frame.shape[0],
            len(boxes),
            sound_label,
        )

    def on_verification(
        self,
        has_cat: bool,
        boxes: "list[BoundingBox]",
    ) -> None:
        """Annotate and async-save the pending frame using the verification result.

        Multi-cycle session logic (FR-010, Plan Change 2):
        1. Guard — no-op if _pending_frame is None or _session_start is None.
        2. Capture locals (frame, boxes, sound, session_start, cycle_count).
        3. Clear pending state (_pending_frame, _pending_boxes, _pending_sound).
        4. Compute elapsed_s = int(cycle_count * cooldown_seconds).
        5. Build timed outcome message.
        6. Build session filepath via build_session_filepath.
        7. Annotate frame with outcome_message.
        8. Dispatch _save_annotated_async with explicit filepath.
        9. If has_cat=False: close session (_session_start=None, _cycle_count=0).

        Called from DetectionLoop daemon thread at cooldown expiry.
        """
        # Step 1: guard
        if self._pending_frame is None or self._session_start is None:
            logger.debug(
                "EffectivenessTracker.on_verification: not pending or no session — no-op."
            )
            return

        # Step 2: capture locals
        frame = self._pending_frame
        pending_boxes = self._pending_boxes
        sound_label = self._pending_sound
        session_start = self._session_start
        cycle_count = self._cycle_count

        # Step 3: clear pending state
        self._pending_frame = None
        self._pending_boxes = []
        self._pending_sound = None

        # Step 4: compute elapsed time
        elapsed_s = int(cycle_count * self._settings.cooldown_seconds)

        # Step 5: build timed outcome message and outcome key
        if has_cat:
            outcome: Optional[str] = "remained"
            outcome_message = f"Cat remained after alert: {elapsed_s}s"
            logger.info(
                "EffectivenessTracker.on_verification: outcome=remained "
                "(cycle=%d, elapsed=%ds, %d verification box(es)).",
                cycle_count, elapsed_s, len(boxes),
            )
        else:
            outcome = "deterred"
            outcome_message = f"Cat disappeared after alert: {elapsed_s}s"
            logger.info(
                "EffectivenessTracker.on_verification: outcome=deterred "
                "(cycle=%d, elapsed=%ds).",
                cycle_count, elapsed_s,
            )

        # Step 6: build session filepath
        from catguard.screenshots import build_session_filepath, resolve_root
        filepath = build_session_filepath(
            resolve_root(self._settings), session_start, cycle_count
        )

        # Step 7: annotate frame
        label = build_sound_label(sound_label)
        annotated = annotate_frame(
            frame, pending_boxes, label, outcome, outcome_message=outcome_message
        )

        # Step 8: dispatch async save with explicit filepath (bypasses suppression checks)
        logger.info(
            "EffectivenessTracker.on_verification: dispatching async save to %s.",
            filepath,
        )
        _save_annotated_async(
            annotated,
            self._settings,
            lambda: False,
            self._on_error,
            filepath=filepath,
        )

        # Step 9: close session on green outcome
        if not has_cat:
            self._session_start = None
            self._cycle_count = 0
            logger.info("EffectivenessTracker.on_verification: session closed.")

    def abandon(self) -> None:
        """Immediately abandon the active session and discard any pending frame.

        Called on any pause: manual pause, camera error, or time-window boundary
        (Plan Change 6, FR-010).  Safe to call at any time — idempotent no-op
        when no session is active.

        Resets all state to the same initial values as __init__:
        - _pending_frame = None
        - _pending_boxes = []
        - _pending_sound  = None
        - _session_start  = None
        - _cycle_count    = 0
        """
        was_active = self._session_start is not None or self._pending_frame is not None
        if was_active:
            logger.info(
                "EffectivenessTracker.abandon: session abandoned "
                "(cycle=%d, session_start=%s).",
                self._cycle_count,
                self._session_start,
            )
        self._pending_frame = None
        self._pending_boxes = []
        self._pending_sound = None
        self._session_start = None
        self._cycle_count = 0
