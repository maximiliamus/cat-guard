"""Overlay drawing helpers for CatGuard main window.

Pure functions operating on numpy BGR frames (OpenCV convention).
No tkinter or pystray imports here — deliberately decoupled for testability.

Public API:
- draw_bounding_box(frame, bbox, color, thickness)
- draw_label(frame, text, position, font_scale, color, thickness)
- draw_detections(frame, results) -> annotated frame copy

Styling constants (can be imported and overridden by callers):
    BOX_COLOR, LABEL_FONT_SCALE, LABEL_THICKNESS, LABEL_PADDING
"""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Styling constants
# ---------------------------------------------------------------------------
BOX_COLOR: tuple[int, int, int] = (0, 255, 0)   # BGR green
LABEL_FONT_SCALE: float = 0.75
LABEL_THICKNESS: int = 2
LABEL_PADDING: int = 4  # pixels above bounding box top for label placement

# Top alert-bar constants — mirror annotation.BAR_HEIGHT so both windows look alike
ALERT_BAR_HEIGHT: int = 32   # pixels; matches annotation.BAR_HEIGHT
_ALERT_BAR_BG: tuple[int, int, int] = (0, 0, 0)
_ALERT_FONT_SIZE: int = 16
_ALERT_FONT_PAD: int = 4


def _load_overlay_font(size: int):
    """Return a PIL TrueType font covering Unicode; fall back to default bitmap."""
    try:
        from PIL import ImageFont as _IFont
    except ImportError:  # pragma: no cover
        return None
    _CANDIDATES = [
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in _CANDIDATES:
        try:
            return _IFont.truetype(path, size)
        except (OSError, AttributeError):
            continue
    return _IFont.load_default()


# ---------------------------------------------------------------------------
# Drawing primitives
# ---------------------------------------------------------------------------

def draw_bounding_box(
    frame: np.ndarray,
    bbox: tuple[int, int, int, int],
    color: tuple[int, int, int] = BOX_COLOR,
    thickness: int = 2,
) -> None:
    """Draw a rectangle on *frame* in-place.

    Args:
        frame:     BGR numpy array (h × w × 3), modified in-place.
        bbox:      (x1, y1, x2, y2) integer pixel coordinates.
        color:     BGR colour tuple.
        thickness: Line thickness in pixels.
    """
    import cv2
    x1, y1, x2, y2 = (int(v) for v in bbox)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)


def draw_label(
    frame: np.ndarray,
    text: str,
    position: tuple[int, int],
    font_scale: float = LABEL_FONT_SCALE,
    color: tuple[int, int, int] = BOX_COLOR,
    thickness: int = LABEL_THICKNESS,
) -> None:
    """Draw a text label on *frame* in-place.

    Args:
        frame:      BGR numpy array, modified in-place.
        text:       Label string to render.
        position:   (x, y) top-left origin of the text baseline.
        font_scale: OpenCV font scale.
        color:      BGR colour tuple.
        thickness:  Text line thickness.
    """
    import cv2
    if not text:
        return
    x, y = int(position[0]), int(position[1])
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness, cv2.LINE_AA)


def draw_detections(frame: np.ndarray, results) -> np.ndarray:
    """Return an annotated copy of *frame* with bounding boxes and class labels.

    Accepts a list of BoundingBox objects (catguard.detection.BoundingBox).
    Returns the frame unchanged (as a copy) if *results* is empty or None.

    Args:
        frame:   BGR numpy array (h × w × 3).
        results: List of BoundingBox objects, or None / empty list.

    Returns:
        A new numpy array with overlays drawn.
    """
    out = frame.copy()
    if not results:
        return out
    import cv2
    for box in results:
        try:
            label = f"{box.label} {int(box.confidence * 100)}%"
            draw_bounding_box(out, (box.x1, box.y1, box.x2, box.y2))

            # Filled background rect + label above box top-left corner
            _DRAW_THICKNESS = 1
            (tw, th), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, LABEL_FONT_SCALE, _DRAW_THICKNESS
            )
            label_x = box.x1
            label_y = max(box.y1 - LABEL_PADDING, th + LABEL_PADDING)
            cv2.rectangle(
                out,
                (label_x - LABEL_PADDING, label_y - th - LABEL_PADDING),
                (label_x + tw + LABEL_PADDING, label_y + baseline + LABEL_PADDING),
                BOX_COLOR,
                -1,
            )
            draw_label(out, label, (label_x, label_y), color=(0, 0, 0), thickness=_DRAW_THICKNESS)
        except Exception:
            logger.exception("Error drawing detection overlay for box %s", box)
    return out


def draw_alert_bar(frame: np.ndarray, sound_label: str) -> None:
    """Draw a full-width black info bar at the top of *frame* in-place.

    Renders *sound_label* (Unicode-safe via Pillow) centred vertically within
    a bar of ALERT_BAR_HEIGHT pixels — the same height used on saved screenshots.
    No-ops silently if Pillow or OpenCV is unavailable.
    """
    try:
        import cv2 as _cv2
        from PIL import Image as _PILImg
        from PIL import ImageDraw as _PILDraw
    except ImportError:  # pragma: no cover
        return

    _h, w = frame.shape[:2]
    pad = _ALERT_FONT_PAD

    pil_img = _PILImg.fromarray(_cv2.cvtColor(frame, _cv2.COLOR_BGR2RGB))
    draw = _PILDraw.Draw(pil_img)
    font = _load_overlay_font(_ALERT_FONT_SIZE)

    # Full-width background strip
    draw.rectangle((0, 0, w, ALERT_BAR_HEIGHT), fill=_ALERT_BAR_BG)

    # Use anchor="lm" so the text is pinned to the vertical midpoint of the
    # bar, matching the same centering used on saved screenshots.
    mid_y = ALERT_BAR_HEIGHT // 2
    draw.text((pad, mid_y), sound_label, font=font, fill=(255, 255, 255), anchor="lm")

    frame[:] = _cv2.cvtColor(np.array(pil_img), _cv2.COLOR_RGB2BGR)
