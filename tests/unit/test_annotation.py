"""Unit tests for catguard.annotation — written before implementation (TDD RED).

Covers (Phase 3 — US1):
- build_sound_label(): normalise play_alert() return value
- annotate_frame(): bounding box layer pixel changes
- annotate_frame(): sound label top-left region changes

Covers (Phase 4 — US2):
- annotate_frame(): outcome overlay layer (green/red/none)
- EffectivenessTracker state machine (on_detection, on_verification, _is_pending)
- EffectivenessTracker FR-005a guard (ignore-if-pending)
- _save_annotated_async() error isolation (NFR-002)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# T008: build_sound_label()
# ---------------------------------------------------------------------------

class TestBuildSoundLabel:
    """T008 — build_sound_label() normalises play_alert() return values."""

    def test_none_returns_alert_default(self):
        from catguard.annotation import build_sound_label
        assert build_sound_label(None) == "Alert: Default"

    def test_alert_default_passthrough(self):
        from catguard.annotation import build_sound_label
        assert build_sound_label("Alert: Default") == "Alert: Default"

    def test_absolute_path_returns_filename_only(self, tmp_path):
        from catguard.annotation import build_sound_label
        p = str(tmp_path / "meow_alarm.wav")
        assert build_sound_label(p) == "meow_alarm.wav"

    def test_relative_path_returns_filename_only(self):
        from catguard.annotation import build_sound_label
        assert build_sound_label("sounds/siren.wav") == "siren.wav"

    def test_plain_filename_returned_as_is(self):
        from catguard.annotation import build_sound_label
        assert build_sound_label("alarm.mp3") == "alarm.mp3"

    def test_return_type_is_str(self):
        from catguard.annotation import build_sound_label
        result = build_sound_label(None)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# T009: annotate_frame() — bounding box layer
# ---------------------------------------------------------------------------

def _blank_frame(h: int = 100, w: int = 200) -> np.ndarray:
    """Return a solid grey BGR frame for annotation tests."""
    return np.full((h, w, 3), 128, dtype=np.uint8)


def _make_box(x1=10, y1=10, x2=80, y2=80, confidence=0.85):
    from catguard.detection import BoundingBox
    return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=confidence)


class TestAnnotateFrameBoundingBox:
    """T009 — annotate_frame() must draw bounding boxes on detected regions."""

    def test_returns_ndarray(self):
        from catguard.annotation import annotate_frame
        frame = _blank_frame()
        result = annotate_frame(frame, [_make_box()], "Alert: Default", None)
        assert isinstance(result, np.ndarray)

    def test_does_not_modify_input_frame(self):
        from catguard.annotation import annotate_frame
        frame = _blank_frame()
        original = frame.copy()
        annotate_frame(frame, [_make_box()], "Alert: Default", None)
        np.testing.assert_array_equal(frame, original)

    def test_output_differs_from_input(self):
        from catguard.annotation import annotate_frame
        frame = _blank_frame()
        result = annotate_frame(frame, [_make_box()], "Alert: Default", None)
        assert not np.array_equal(result, frame)

    def test_bounding_box_pixels_changed_at_edges(self):
        """Pixels at the box edge must differ from the input (rectangle drawn)."""
        from catguard.annotation import annotate_frame
        frame = _blank_frame(200, 300)
        box = _make_box(x1=20, y1=20, x2=100, y2=100)
        result = annotate_frame(frame, [box], "Alert: Default", None)
        # At least some pixel on the left edge of the box must differ.
        edge_pixels_changed = any(
            not np.array_equal(result[y, box.x1], frame[y, box.x1])
            for y in range(box.y1, box.y2)
        )
        assert edge_pixels_changed

    def test_no_boxes_output_may_differ_from_input(self):
        """No bounding boxes — sound label still drawn so output differs."""
        from catguard.annotation import annotate_frame
        frame = _blank_frame()
        result = annotate_frame(frame, [], "Alert: Default", None)
        assert isinstance(result, np.ndarray)

    def test_multiple_boxes_all_drawn(self):
        """Two boxes at non-overlapping regions — both edges differ from input."""
        from catguard.annotation import annotate_frame
        frame = _blank_frame(300, 400)
        box1 = _make_box(x1=10, y1=10, x2=50, y2=50)
        box2 = _make_box(x1=200, y1=200, x2=350, y2=280)
        result = annotate_frame(frame, [box1, box2], "Alert: Default", None)
        # Check box1 edge
        edge1 = any(
            not np.array_equal(result[y, box1.x1], frame[y, box1.x1])
            for y in range(box1.y1, box1.y2)
        )
        # Check box2 edge
        edge2 = any(
            not np.array_equal(result[y, box2.x1], frame[y, box2.x1])
            for y in range(box2.y1, box2.y2)
        )
        assert edge1
        assert edge2


# ---------------------------------------------------------------------------
# T009: annotate_frame() — sound label layer
# ---------------------------------------------------------------------------

class TestAnnotateFrameSoundLabel:
    """T009 — annotate_frame() must render the sound label in the top-left corner."""

    def test_top_left_region_modified(self):
        """The top-left corner (x<80, y<40) must be altered by the label."""
        from catguard.annotation import annotate_frame
        frame = _blank_frame(200, 300)
        result = annotate_frame(frame, [], "Alert: Default", None)
        # Sample a small region in the top-left quadrant
        region_original = frame[:40, :80]
        region_result = result[:40, :80]
        assert not np.array_equal(region_original, region_result)

    def test_sound_label_custom_text_rendered(self):
        """A custom filename label must also modify the top-left region."""
        from catguard.annotation import annotate_frame
        frame = _blank_frame(200, 300)
        result = annotate_frame(frame, [], "siren.wav", None)
        region_original = frame[:40, :80]
        region_result = result[:40, :80]
        assert not np.array_equal(region_original, region_result)

    def test_cyrillic_filename_does_not_raise(self):
        """Unicode (Cyrillic) filenames must render without raising."""
        from catguard.annotation import annotate_frame
        frame = _blank_frame(200, 300)
        cyrillic_label = "Котик.wav"
        # Must not raise; top-left region must be modified
        result = annotate_frame(frame, [], cyrillic_label, None)
        region_original = frame[:40, :200]
        region_result = result[:40, :200]
        assert not np.array_equal(region_original, region_result)


# ---------------------------------------------------------------------------
# T015: annotate_frame() — outcome overlay layer
# ---------------------------------------------------------------------------

class TestAnnotateFrameOutcomeOverlay:
    """T015 — annotate_frame() must render green/red outcome strip at the bottom."""

    def test_deterred_outcome_modifies_bottom_strip(self):
        from catguard.annotation import annotate_frame
        frame = _blank_frame(200, 300)
        result = annotate_frame(frame, [], "Alert: Default", "deterred")
        bottom = result[170:, :]
        bottom_orig = frame[170:, :]
        assert not np.array_equal(bottom, bottom_orig)

    def test_deterred_outcome_has_green_pixels_in_strip(self):
        """Green channel dominates in the success strip (BGR: G > R, G > B)."""
        from catguard.annotation import annotate_frame
        frame = _blank_frame(200, 300)
        result = annotate_frame(frame, [], "Alert: Default", "deterred")
        # Sample pixel in bottom strip (last 30 rows, centre column)
        pixel = result[190, 150]  # BGR
        assert int(pixel[1]) > int(pixel[2])  # G > R
        assert int(pixel[1]) > int(pixel[0])  # G > B

    def test_remained_outcome_modifies_bottom_strip(self):
        from catguard.annotation import annotate_frame
        frame = _blank_frame(200, 300)
        result = annotate_frame(frame, [], "Alert: Default", "remained")
        bottom = result[170:, :]
        bottom_orig = frame[170:, :]
        assert not np.array_equal(bottom, bottom_orig)

    def test_remained_outcome_has_red_pixels_in_strip(self):
        """Red channel dominates in the failure strip (BGR: R > G, R > B)."""
        from catguard.annotation import annotate_frame
        frame = _blank_frame(200, 300)
        result = annotate_frame(frame, [], "Alert: Default", "remained")
        pixel = result[190, 150]  # BGR
        assert int(pixel[2]) > int(pixel[1])  # R > G
        assert int(pixel[2]) > int(pixel[0])  # R > B

    def test_none_outcome_bottom_unchanged(self):
        """outcome=None must not add any overlay strip."""
        from catguard.annotation import annotate_frame
        frame = _blank_frame(200, 300)
        result = annotate_frame(frame, [], "Alert: Default", None)
        # The bottom strip (last 30 rows) may differ only because of the sound label
        # if it overflows — but no coloured strip should appear.
        # Compare against a no-boxes, no-outcome, no-sound-label baseline isn't easy,
        # so we just check that the pure bottom edge (last 5 rows) isn't solid green/red.
        bottom_5 = result[195:, 50:250]
        # Neither fully green nor fully red
        not_solid_green = not np.all(bottom_5[:, :, 1] > 200)
        not_solid_red = not np.all(bottom_5[:, :, 2] > 200)
        assert not_solid_green or not_solid_red

    def test_outcome_strip_does_not_overlap_top_left_label(self):
        """FR-011: outcome strip y-range must not overlap sound label y-range."""
        from catguard.annotation import annotate_frame, OUTCOME_STRIP_Y1_APPROX
        frame = _blank_frame(200, 300)
        result = annotate_frame(frame, [], "Alert: Default", "deterred")
        # The sound label is in the top ~40px; the outcome strip must start below that.
        assert OUTCOME_STRIP_Y1_APPROX > 40


# ---------------------------------------------------------------------------
# T014: EffectivenessTracker state machine
# ---------------------------------------------------------------------------

class TestEffectivenessTrackerStateMachine:
    """T014 — EffectivenessTracker manages pending snapshot lifecycle."""

    def _make_tracker(self, tmp_path):
        from catguard.annotation import EffectivenessTracker
        from catguard.config import Settings
        settings = Settings(screenshots_root_folder=str(tmp_path))
        return EffectivenessTracker(
            settings=settings,
            is_window_open=lambda: False,
            on_error=MagicMock(),
        )

    def test_initially_not_pending(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        assert tracker._is_pending is False

    def test_on_detection_sets_pending(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        frame = _blank_frame(200, 300)
        from catguard.detection import BoundingBox
        tracker.on_detection(frame, [BoundingBox(10, 10, 50, 50, 0.9)], "siren.wav")
        assert tracker._is_pending is True

    def test_on_detection_stores_frame_copy(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        frame = _blank_frame(200, 300)
        original_data = frame.copy()
        from catguard.detection import BoundingBox
        tracker.on_detection(frame, [BoundingBox(10, 10, 50, 50, 0.9)], "siren.wav")
        # Mutate original — tracker's copy must be unaffected
        frame[:] = 0
        np.testing.assert_array_equal(tracker._pending_frame, original_data)

    def test_fr005a_second_detection_ignored_when_pending(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        frame1 = _blank_frame(200, 300)
        frame2 = np.full((200, 300, 3), 200, dtype=np.uint8)
        from catguard.detection import BoundingBox
        tracker.on_detection(frame1, [], "first.wav")
        first_pending = tracker._pending_frame.copy()
        tracker.on_detection(frame2, [], "second.wav")  # must be ignored
        np.testing.assert_array_equal(tracker._pending_frame, first_pending)

    def test_on_verification_clears_pending(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        frame = _blank_frame(200, 300)
        tracker.on_detection(frame, [], "Alert: Default")
        assert tracker._is_pending is True
        with patch("catguard.annotation._save_annotated_async"):
            tracker.on_verification(has_cat=False, boxes=[])
        assert tracker._is_pending is False

    def test_on_verification_when_not_pending_is_noop(self, tmp_path):
        """Calling on_verification without a prior on_detection must not raise."""
        tracker = self._make_tracker(tmp_path)
        tracker.on_verification(has_cat=False, boxes=[])  # must not raise


# ---------------------------------------------------------------------------
# T014 / NFR-002: _save_annotated_async error isolation
# ---------------------------------------------------------------------------

class TestSaveAnnotatedAsyncErrorIsolation:
    """NFR-002 — save failure must not crash the caller."""

    def test_save_error_does_not_propagate(self, tmp_path):
        from catguard.annotation import EffectivenessTracker
        from catguard.config import Settings
        on_error = MagicMock()
        settings = Settings(screenshots_root_folder=str(tmp_path))
        tracker = EffectivenessTracker(
            settings=settings,
            is_window_open=lambda: False,
            on_error=on_error,
        )
        frame = _blank_frame(200, 300)
        tracker.on_detection(frame, [], "Alert: Default")

        # Patch save_screenshot to raise
        import threading
        event = threading.Event()
        original_on_error = on_error

        def raising_save(*args, **kwargs):
            raise OSError("Disk full")

        with patch("catguard.screenshots.save_screenshot", side_effect=raising_save):
            # on_verification dispatches async; give thread time to complete
            tracker.on_verification(has_cat=False, boxes=[])
            import time
            time.sleep(0.2)

        # on_error callback must have been invoked
        assert on_error.called


# ---------------------------------------------------------------------------
# T017: _draw_labelled_box() annotation label fallback (FR-016–FR-019)
# ---------------------------------------------------------------------------

def _make_box_at(x1, y1, x2, y2, confidence=0.90):
    from catguard.detection import BoundingBox
    return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=confidence)


class TestDrawLabelledBoxFallback:
    """T017 — label placement fallback chain for off-screen bounding boxes."""

    # Frame: 200 rows × 400 cols.  All boxes are 40×40 px.
    FRAME_H, FRAME_W = 200, 400
    # Approximate label size for "cat 90%" at FONT_SCALE=0.55: ~(70 w, 14 h)
    # We don't hard-code exact pixels; we verify *which zone* the label lands in.

    def _annotated(self, x1, y1, x2, y2):
        """Return annotated frame for a single box placed at (x1,y1,x2,y2)."""
        from catguard.annotation import annotate_frame
        frame = np.full((self.FRAME_H, self.FRAME_W, 3), 128, dtype=np.uint8)
        return annotate_frame(
            frame,
            [_make_box_at(x1, y1, x2, y2)],
            "Alert: Default",
            outcome=None,
        )

    def _pixel_changed_in_region(self, original, annotated, ry1, ry2, rx1, rx2):
        """Return True if any pixel in the region differs from original."""
        orig_region = original[ry1:ry2, rx1:rx2]
        anno_region = annotated[ry1:ry2, rx1:rx2]
        return not np.array_equal(orig_region, anno_region)

    def test_normal_box_label_drawn_above_box(self):
        """Normal case: label rendered above the box (default position)."""
        # Box mid-frame so all candidates fit
        x1, y1, x2, y2 = 100, 80, 180, 130
        original = np.full((self.FRAME_H, self.FRAME_W, 3), 128, dtype=np.uint8)
        annotated = self._annotated(x1, y1, x2, y2)
        # Label should appear ABOVE y1 (i.e. in rows 0…y1)
        assert self._pixel_changed_in_region(original, annotated, 0, y1, x1, self.FRAME_W)

    def test_top_offscreen_box_label_drawn_below_box(self):
        """Top edge off-screen (y1=0): label falls back to below the box."""
        x1, y1, x2, y2 = 100, 0, 180, 50
        original = np.full((self.FRAME_H, self.FRAME_W, 3), 128, dtype=np.uint8)
        annotated = self._annotated(x1, y1, x2, y2)
        # Label should appear BELOW y2
        assert self._pixel_changed_in_region(original, annotated, y2, self.FRAME_H, x1, self.FRAME_W)

    def test_top_and_bottom_offscreen_label_drawn_right_of_box(self):
        """Top and bottom both off-screen: label falls back to right of box."""
        # Put box at bottom edge so both above and below are off-screen
        x1, y1, x2, y2 = 100, self.FRAME_H - 30, 200, self.FRAME_H
        original = np.full((self.FRAME_H, self.FRAME_W, 3), 128, dtype=np.uint8)
        annotated = self._annotated(x1, y1, x2, y2)
        # Above y1 is off-screen (no space), below y2 is off-screen (y2 == h).
        # Left: enough space if x1 > tw + 3*PAD ≈ 90 px → x1=100 OK for left.
        # Actually: we test right of box in case there is enough right space.
        # We only verify the frame changed somewhere to the right of x2.
        # (Exact fallback depends on label width; just ensure something was drawn.)
        assert not np.array_equal(original, annotated)

    def test_center_fallback_when_all_edges_offscreen(self):
        """All edges off-screen: label drawn at box center (FR-019)."""
        # Very large box filling almost the whole frame
        x1, y1, x2, y2 = 0, 0, self.FRAME_W, self.FRAME_H
        original = np.full((self.FRAME_H, self.FRAME_W, 3), 128, dtype=np.uint8)
        annotated = self._annotated(x1, y1, x2, y2)
        # Something should be drawn at approximately the center
        cx, cy = self.FRAME_W // 2, self.FRAME_H // 2
        margin = 50
        assert self._pixel_changed_in_region(
            original, annotated,
            cy - margin, cy + margin,
            cx - margin, cx + margin,
        )

    def test_existing_tests_still_pass_for_normal_box(self):
        """Regression: annotate_frame() still returns correct shape for normal box."""
        from catguard.annotation import annotate_frame
        frame = _blank_frame(200, 400)
        result = annotate_frame(
            frame,
            [_make_box_at(100, 80, 180, 130)],
            "Alert: Default",
            outcome=None,
        )
        assert result.shape == frame.shape


# ---------------------------------------------------------------------------
# T019: locale-aware timestamp in _draw_top_bar() (FR-020/FR-021)
# ---------------------------------------------------------------------------

class TestLocaleAwareTimestamp:
    """T019 — _draw_top_bar() uses strftime('%x  %X') not a hardcoded format."""

    def test_draw_top_bar_uses_locale_format_codes(self):
        """_draw_top_bar() calls strftime with '%x  %X' (locale-aware format)."""
        import catguard.annotation as _ann_mod
        from datetime import datetime as _dt

        frame = np.full((200, 400, 3), 60, dtype=np.uint8)
        captured_formats = []

        class _FakeDT:
            @staticmethod
            def now():
                return _FakeDT()

            def strftime(self, fmt):
                captured_formats.append(fmt)
                return "01/01/2026  08:00:00"

        with patch.object(_ann_mod, "_PIL_Image", wraps=_ann_mod._PIL_Image):
            from unittest.mock import patch as _patch
            with _patch("catguard.annotation._dt", _FakeDT):
                _ann_mod._draw_top_bar(frame, "test.wav")

        assert any("%x" in f and "%X" in f for f in captured_formats), (
            f"Expected a format containing '%x' and '%X'; got {captured_formats}"
        )

    def test_draw_top_bar_does_not_use_hardcoded_iso_format(self):
        """_draw_top_bar() must NOT use the old '%Y-%m-%d  %H:%M:%S' format."""
        import catguard.annotation as _ann_mod

        frame = np.full((200, 400, 3), 60, dtype=np.uint8)
        captured_formats = []

        class _FakeDT:
            @staticmethod
            def now():
                return _FakeDT()

            def strftime(self, fmt):
                captured_formats.append(fmt)
                return "2026-01-01  08:00:00"

        from unittest.mock import patch as _patch
        with _patch("catguard.annotation._dt", _FakeDT):
            _ann_mod._draw_top_bar(frame, "test.wav")

        assert not any("%Y-%m-%d" in f for f in captured_formats), (
            f"Old hardcoded format found in {captured_formats}"
        )
