"""Integration tests for the alert-effectiveness pipeline (T017).

Verifies that on_detection() → on_verification() drives EffectivenessTracker
through the full cycle and produces exactly one annotated JPEG on disk, with
the correct visual annotations (bounding-box colour, outcome-strip colour).

These tests use *real* numpy frames and real cv2 encoding/decoding but write
to a pytest tmp_path so they never touch the production screenshots folder.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from catguard.annotation import (
    BOX_COLOR,
    FAILURE_BG,
    SUCCESS_BG,
    EffectivenessTracker,
)
from catguard.config import Settings
from catguard.detection import BoundingBox

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_frame(h: int = 200, w: int = 300) -> np.ndarray:
    """Return a solid grey BGR frame."""
    return np.full((h, w, 3), 128, dtype=np.uint8)


def _wait_for_file(directory: Path, timeout: float = 3.0) -> Path:
    """Block until exactly one JPEG file appears in *directory* tree."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        jpegs = list(directory.rglob("*.jpg"))
        if jpegs:
            return jpegs[0]
        time.sleep(0.05)
    raise TimeoutError(
        f"No JPEG file appeared in {directory} within {timeout}s."
    )


def _load_jpeg(path: Path) -> np.ndarray:
    """Load a JPEG from disk as a BGR ndarray."""
    import cv2  # noqa: PLC0415
    frame = cv2.imread(str(path))
    assert frame is not None, f"cv2.imread returned None for {path}"
    return frame


def _pixel_color_at(frame: np.ndarray, y: int, x: int) -> tuple[int, int, int]:
    """Return the BGR tuple at (y, x)."""
    b, g, r = frame[y, x]
    return (int(b), int(g), int(r))


def _bottom_strip_center_y(frame: np.ndarray) -> int:
    """Return the approximate y-coordinate near the center of the outcome strip."""
    from catguard.annotation import BAR_HEIGHT

    h = frame.shape[0]
    rect_y1 = h - BAR_HEIGHT
    return (rect_y1 + h) // 2


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_settings(tmp_path: Path) -> Settings:
    """Settings pointing all tracking output to tmp_path."""
    return Settings(tracking_directory=str(tmp_path))


# ---------------------------------------------------------------------------
# T017a: outcome=deterred — green strip in saved JPEG
# ---------------------------------------------------------------------------

class TestEffectivenessIntegrationDeterred:
    """Full pipeline: on_detection → on_verification(has_cat=False) → green JPEG."""

    def test_exactly_one_jpeg_written(self, tmp_settings: Settings, tmp_path: Path):
        errors: list[str] = []
        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=errors.append,
        )

        frame = _make_frame()
        boxes = [BoundingBox(x1=10, y1=10, x2=60, y2=60, confidence=0.85)]
        tracker.on_detection(frame, boxes, "alert_sound.wav")
        tracker.on_verification(has_cat=False, boxes=[])

        jpeg_path = _wait_for_file(tmp_path)
        all_jpegs = list(tmp_path.rglob("*.jpg"))

        assert len(all_jpegs) == 1, f"Expected 1 JPEG, found {len(all_jpegs)}"
        assert not errors, f"Unexpected errors: {errors}"

    def test_green_pixel_in_bottom_strip(self, tmp_settings: Settings, tmp_path: Path):
        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=lambda msg: None,
        )

        frame = _make_frame()
        tracker.on_detection(frame, [], "alert_sound.wav")
        tracker.on_verification(has_cat=False, boxes=[])

        jpeg_path = _wait_for_file(tmp_path)
        saved = _load_jpeg(jpeg_path)

        # Bottom strip should contain the SUCCESS_BG (green) colour.
        # Check a pixel near the bottom-center of the frame.
        h, w = saved.shape[:2]
        center_x = w // 2
        strip_y = _bottom_strip_center_y(saved)
        b, g, r = _pixel_color_at(saved, strip_y, center_x)

        # Green channel should dominate and red/blue should be low.
        assert g > 100, f"Expected green dominant at outcome strip, got BGR=({b},{g},{r})"
        assert r < 50, f"Red channel too high for deterred strip: BGR=({b},{g},{r})"
        assert b < 50, f"Blue channel too high for deterred strip: BGR=({b},{g},{r})"

    def test_bounding_box_green_border_present(
        self, tmp_settings: Settings, tmp_path: Path
    ):
        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=lambda msg: None,
        )

        frame = _make_frame()
        boxes = [BoundingBox(x1=30, y1=30, x2=80, y2=80, confidence=0.9)]
        tracker.on_detection(frame, boxes, "default.wav")
        tracker.on_verification(has_cat=False, boxes=[])

        jpeg_path = _wait_for_file(tmp_path)
        saved = _load_jpeg(jpeg_path)

        # The box border at x=30 (left edge) should be distinctly green-ish.
        # Sample mid-left-edge of the box, well below the timestamp strip.
        # JPEG compression may shift values slightly; use tolerance.
        b, g, r = _pixel_color_at(saved, 55, 30)  # mid-left-edge of box
        assert g > b and g > r, (
            f"Expected green border pixel near box left edge, got BGR=({b},{g},{r})"
        )


# ---------------------------------------------------------------------------
# T017b: outcome=remained — red strip in saved JPEG
# ---------------------------------------------------------------------------

class TestEffectivenessIntegrationRemained:
    """Full pipeline: on_detection → on_verification(has_cat=True) → red JPEG."""

    def test_exactly_one_jpeg_written(self, tmp_settings: Settings, tmp_path: Path):
        errors: list[str] = []
        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=errors.append,
        )

        frame = _make_frame()
        tracker.on_detection(frame, [], "alert_sound.wav")
        tracker.on_verification(has_cat=True, boxes=[])

        jpeg_path = _wait_for_file(tmp_path)
        all_jpegs = list(tmp_path.rglob("*.jpg"))

        assert len(all_jpegs) == 1
        assert not errors, f"Unexpected errors: {errors}"

    def test_red_pixel_in_bottom_strip(self, tmp_settings: Settings, tmp_path: Path):
        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=lambda msg: None,
        )

        frame = _make_frame()
        tracker.on_detection(frame, [], "alert_sound.wav")
        tracker.on_verification(has_cat=True, boxes=[])

        jpeg_path = _wait_for_file(tmp_path)
        saved = _load_jpeg(jpeg_path)

        h, w = saved.shape[:2]
        center_x = w // 2
        strip_y = _bottom_strip_center_y(saved)
        b, g, r = _pixel_color_at(saved, strip_y, center_x)

        # FAILURE_BG = (0, 0, 200) — red-dominant in BGR.
        assert r > 100, f"Expected red dominant at outcome strip, got BGR=({b},{g},{r})"
        assert g < 50, f"Green channel too high for remained strip: BGR=({b},{g},{r})"
        assert b < 50, f"Blue channel too high for remained strip: BGR=({b},{g},{r})"


# ---------------------------------------------------------------------------
# T017c: FR-005a — second on_detection while pending is ignored (no double save)
# ---------------------------------------------------------------------------

class TestEffectivenessIntegrationFR005a:
    """FR-005a: second on_detection while pending is silently ignored."""

    def test_only_one_jpeg_when_detection_fires_twice(
        self, tmp_settings: Settings, tmp_path: Path
    ):
        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=lambda msg: None,
        )

        frame1 = _make_frame()
        frame2 = _make_frame()
        boxes = [BoundingBox(x1=5, y1=5, x2=20, y2=20, confidence=0.7)]

        tracker.on_detection(frame1, boxes, "sound_a.wav")
        tracker.on_detection(frame2, [], "sound_b.wav")  # must be ignored

        tracker.on_verification(has_cat=False, boxes=[])

        jpeg_path = _wait_for_file(tmp_path)
        all_jpegs = list(tmp_path.rglob("*.jpg"))
        assert len(all_jpegs) == 1, (
            f"FR-005a violated: expected 1 JPEG, found {len(all_jpegs)}"
        )

    def test_no_file_saved_without_verification(
        self, tmp_settings: Settings, tmp_path: Path
    ):
        """on_detection alone must not write any file — save only on verification."""
        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=lambda msg: None,
        )

        tracker.on_detection(_make_frame(), [], "sound.wav")

        # Give async thread a window to accidentally fire.
        time.sleep(0.2)
        all_jpegs = list(tmp_path.rglob("*.jpg"))
        assert all_jpegs == [], (
            "File written before on_verification() was called — unexpected."
        )
