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
LABEL_FONT_SCALE: float = 0.6
LABEL_THICKNESS: int = 2
LABEL_PADDING: int = 4  # pixels above bounding box top for label placement


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

    Iterates YOLO result objects (each having a `.boxes` attribute).
    Returns the frame unchanged (as a copy) if *results* is empty or None.

    Args:
        frame:   BGR numpy array (h × w × 3).
        results: List of YOLO result objects, or None / empty list.

    Returns:
        A new numpy array with overlays drawn.
    """
    out = frame.copy()
    if not results:
        return out
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        names: dict = getattr(result, "names", {})
        for box in boxes:
            try:
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                cls_id = int(box.cls[0])
                label = names.get(cls_id, str(cls_id))
                draw_bounding_box(out, (x1, y1, x2, y2))
                # Place label above top-left corner of the box
                label_y = max(y1 - LABEL_PADDING, 12)
                draw_label(out, label, (x1, label_y))
            except Exception:
                logger.exception("Error drawing detection overlay for box %s", box)
    return out
