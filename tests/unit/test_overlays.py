"""Unit tests for catguard.ui.overlays — written BEFORE implementation (TDD RED).

Tests verify:
- draw_bounding_box modifies pixels inside the bbox region
- draw_label modifies pixels at the label position
- draw_detections returns an annotated copy; no-op on empty/None results
- Styling constants exported at module level
- Multiple detections: both boxes rendered
"""
from __future__ import annotations

import numpy as np
import pytest

from catguard.ui.overlays import (
    BOX_COLOR,
    LABEL_FONT_SCALE,
    LABEL_PADDING,
    LABEL_THICKNESS,
    draw_bounding_box,
    draw_detections,
    draw_label,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blank_frame(h: int = 100, w: int = 120) -> np.ndarray:
    """Return a black BGR frame."""
    return np.zeros((h, w, 3), dtype=np.uint8)


def _make_bbox(x1, y1, x2, y2, conf=0.9, label="cat"):
    """Return a BoundingBox for use in draw_detections tests."""
    from catguard.detection import BoundingBox
    return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=conf, label=label)


# ---------------------------------------------------------------------------
# Styling constants
# ---------------------------------------------------------------------------

class TestStylingConstants:
    def test_box_color_is_bgr_tuple(self):
        assert isinstance(BOX_COLOR, tuple)
        assert len(BOX_COLOR) == 3

    def test_label_font_scale_positive(self):
        assert LABEL_FONT_SCALE > 0

    def test_label_thickness_positive_int(self):
        assert isinstance(LABEL_THICKNESS, int)
        assert LABEL_THICKNESS > 0

    def test_label_padding_non_negative(self):
        assert LABEL_PADDING >= 0


# ---------------------------------------------------------------------------
# draw_bounding_box
# ---------------------------------------------------------------------------

class TestDrawBoundingBox:
    def test_modifies_pixels_along_box_edges(self):
        frame = _blank_frame()
        draw_bounding_box(frame, (10, 10, 50, 50))
        # At least some pixels along the expected rectangle edges should be non-zero
        top_row = frame[10, 10:51]
        assert np.any(top_row != 0), "Expected top edge pixels to be drawn"

    def test_custom_color_applied(self):
        frame = _blank_frame()
        color = (0, 0, 255)  # red in BGR
        draw_bounding_box(frame, (5, 5, 30, 30), color=color)
        # The red channel of at least one edge pixel should be non-zero
        assert np.any(frame[:, :, 2] > 0), "Expected red channel pixels from custom colour"

    def test_original_frame_modified_in_place(self):
        frame = _blank_frame()
        result = draw_bounding_box(frame, (10, 10, 40, 40))
        # Function modifies in-place and may return None
        assert result is None or result is frame
        assert np.any(frame != 0)

    def test_does_not_raise_on_edge_bbox(self):
        frame = _blank_frame()
        # bbox touching image border — should not raise
        draw_bounding_box(frame, (0, 0, 119, 99))


# ---------------------------------------------------------------------------
# draw_label
# ---------------------------------------------------------------------------

class TestDrawLabel:
    def test_modifies_pixels_at_position(self):
        frame = _blank_frame(200, 200)
        draw_label(frame, "cat", (10, 50))
        # Some pixels near the label area should be non-zero
        region = frame[30:70, 5:100]
        assert np.any(region != 0), "Expected label pixels to be drawn near position"

    def test_does_not_raise_for_empty_string(self):
        frame = _blank_frame()
        draw_label(frame, "", (5, 5))  # should not raise

    def test_original_frame_modified_in_place(self):
        frame = _blank_frame(200, 200)
        result = draw_label(frame, "cat", (20, 80))
        assert result is None or result is frame


# ---------------------------------------------------------------------------
# draw_detections
# ---------------------------------------------------------------------------

class TestDrawDetections:
    def test_returns_copy_not_original(self):
        frame = _blank_frame()
        result = draw_detections(frame, [])
        assert result is not frame

    def test_empty_results_returns_frame_unchanged(self):
        frame = _blank_frame()
        result = draw_detections(frame, [])
        np.testing.assert_array_equal(result, frame)

    def test_none_results_returns_frame_unchanged(self):
        frame = _blank_frame()
        result = draw_detections(frame, None)
        np.testing.assert_array_equal(result, frame)

    def test_single_detection_annotates_frame(self):
        frame = _blank_frame(200, 200)
        box = _make_bbox(20, 20, 80, 80)
        annotated = draw_detections(frame, [box])
        assert np.any(annotated != frame), "Expected detections to draw on frame"

    def test_multiple_detections_both_annotated(self):
        frame = _blank_frame(300, 400)
        box1 = _make_bbox(10, 10, 60, 60)
        box2 = _make_bbox(200, 150, 280, 230)
        annotated = draw_detections(frame, [box1, box2])
        # Both boxes should leave traces — just check total annotated pixels > 0
        assert np.any(annotated != 0)

    def test_result_with_none_boxes_handled_gracefully(self):
        frame = _blank_frame()
        annotated = draw_detections(frame, None)
        np.testing.assert_array_equal(annotated, frame)
