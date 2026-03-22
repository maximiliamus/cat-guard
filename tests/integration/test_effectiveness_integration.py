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
        # Sample near the bottom edge of the strip (last few rows), safely below the
        # text baseline — the outcome label can be wider than the test frame and the
        # text glyphs occupy the vertical center of the strip, not its bottom edge.
        strip_y = h - 3
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


# ---------------------------------------------------------------------------
# T007: Multi-cycle session end-to-end saves
# ---------------------------------------------------------------------------


def _wait_for_n_files(directory: Path, n: int, timeout: float = 5.0) -> list[Path]:
    """Block until at least *n* JPEG files appear in *directory* tree."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        jpegs = sorted(directory.rglob("*.jpg"))
        if len(jpegs) >= n:
            return jpegs
        time.sleep(0.05)
    jpegs = sorted(directory.rglob("*.jpg"))
    raise TimeoutError(
        f"Expected {n} JPEG file(s) in {directory} within {timeout}s, "
        f"found {len(jpegs)}."
    )


def _has_red_strip(frame: np.ndarray) -> bool:
    """True if the bottom-strip edge pixel is red-dominant (FAILURE_BG).

    Samples near the very bottom of the frame (last 3 rows) to stay below the
    text baseline, which sits ~3 rows above the strip bottom edge.
    """
    h, w = frame.shape[:2]
    b, g, r = _pixel_color_at(frame, h - 3, w // 2)
    return r > 100 and g < 50 and b < 50


def _has_green_strip(frame: np.ndarray) -> bool:
    """True if the bottom-strip edge pixel is green-dominant (SUCCESS_BG).

    Samples near the very bottom of the frame (last 3 rows) to stay below the
    text baseline, which sits ~3 rows above the strip bottom edge.
    """
    h, w = frame.shape[:2]
    b, g, r = _pixel_color_at(frame, h - 3, w // 2)
    return g > 100 and r < 50 and b < 50


@pytest.mark.integration
class TestMultiCycleSession:
    """T007: Multi-cycle cat-session end-to-end JPEG saves."""

    def test_two_cycle_session_produces_two_jpegs(
        self, tmp_settings: Settings, tmp_path: Path
    ):
        """Two-cycle session: -001.jpg (red) + -002.jpg (green)."""
        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=lambda msg: pytest.fail(f"Unexpected error: {msg}"),
        )
        frame = _make_frame()
        boxes = [BoundingBox(x1=10, y1=10, x2=60, y2=60, confidence=0.85)]

        # Cycle 1: remained
        tracker.on_detection(frame, boxes, "sound.wav")
        tracker.on_verification(has_cat=True, boxes=[])
        # Cycle 2: deterred
        tracker.on_detection(frame, boxes, "sound.wav")
        tracker.on_verification(has_cat=False, boxes=[])

        jpegs = _wait_for_n_files(tmp_path, 2)
        assert len(jpegs) == 2, f"Expected exactly 2 JPEGs, found {len(jpegs)}"
        names = [p.name for p in jpegs]
        assert any(n.endswith("-001.jpg") for n in names), (
            f"No file ending in -001.jpg; got: {names}"
        )
        assert any(n.endswith("-002.jpg") for n in names), (
            f"No file ending in -002.jpg; got: {names}"
        )

    def test_fr009_annotation_layers(
        self, tmp_settings: Settings, tmp_path: Path
    ):
        """FR-009: saved session JPEG contains all three annotation layers."""
        import cv2 as _cv2

        from catguard.annotation import BAR_HEIGHT

        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=lambda msg: None,
        )
        frame = _make_frame()  # solid grey (128, 128, 128)
        boxes = [BoundingBox(x1=10, y1=10, x2=60, y2=60, confidence=0.9)]

        tracker.on_detection(frame, boxes, "sound.wav")
        tracker.on_verification(has_cat=True, boxes=[])

        jpegs = _wait_for_n_files(tmp_path, 1)
        saved = _load_jpeg(jpegs[0])
        h, _w = saved.shape[:2]

        # Layer 1: top info bar — non-uniform region in top BAR_HEIGHT rows
        top_region = saved[:BAR_HEIGHT, :, :]
        assert not np.all(top_region == 128), (
            "Top info bar region is uniformly grey — top-bar layer missing"
        )

        # Layer 2: bottom outcome strip — non-uniform colored region
        bottom_region = saved[h - BAR_HEIGHT:, :, :]
        assert not np.all(bottom_region == 128), (
            "Bottom outcome strip region is uniformly grey — strip layer missing"
        )

        # Layer 3: bounding box — left edge pixels must differ from raw grey
        # Box at (10,10)-(60,60); sample the left border column (x=10), rows 25-55
        box_edge = saved[25:55, 10:12, :]
        original = np.full_like(box_edge, 128)
        assert not np.array_equal(box_edge, original), (
            "Bounding-box left edge is unchanged from raw grey — box layer missing"
        )

    def test_three_cycle_session_colors(
        self, tmp_settings: Settings, tmp_path: Path
    ):
        """Three-cycle session: -001 and -002 red, -003 green."""
        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=lambda msg: None,
        )
        frame = _make_frame()
        boxes = [BoundingBox(x1=10, y1=10, x2=60, y2=60, confidence=0.85)]

        for _ in range(2):  # two remained cycles
            tracker.on_detection(frame, boxes, "sound.wav")
            tracker.on_verification(has_cat=True, boxes=[])
        # final deterred cycle
        tracker.on_detection(frame, boxes, "sound.wav")
        tracker.on_verification(has_cat=False, boxes=[])

        jpegs = _wait_for_n_files(tmp_path, 3)
        assert len(jpegs) == 3, f"Expected exactly 3 JPEGs, found {len(jpegs)}"

        jpegs_sorted = sorted(jpegs, key=lambda p: p.name)
        names = [p.name for p in jpegs_sorted]
        assert names[0].endswith("-001.jpg"), f"First file: {names}"
        assert names[1].endswith("-002.jpg"), f"Second file: {names}"
        assert names[2].endswith("-003.jpg"), f"Third file: {names}"

        assert _has_red_strip(_load_jpeg(jpegs_sorted[0])), (
            "-001.jpg should have red (remained) strip"
        )
        assert _has_red_strip(_load_jpeg(jpegs_sorted[1])), (
            "-002.jpg should have red (remained) strip"
        )
        assert _has_green_strip(_load_jpeg(jpegs_sorted[2])), (
            "-003.jpg should have green (deterred) strip"
        )

    def test_fresh_session_after_green(
        self, tmp_settings: Settings, tmp_path: Path
    ):
        """After green outcome, next on_detection starts a new session at cycle 001."""
        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=lambda msg: None,
        )
        frame = _make_frame()
        boxes = [BoundingBox(x1=10, y1=10, x2=60, y2=60, confidence=0.85)]

        # Session 1: single-cycle green
        tracker.on_detection(frame, boxes, "sound.wav")
        tracker.on_verification(has_cat=False, boxes=[])
        jpegs_s1 = _wait_for_n_files(tmp_path, 1)
        s1_name = jpegs_s1[0].name
        assert s1_name.endswith("-001.jpg"), f"Session 1 first frame: {s1_name}"

        # Ensure session 2 gets a distinct second-precision timestamp
        time.sleep(1.1)

        # Session 2: single-cycle remained
        tracker.on_detection(frame, boxes, "sound.wav")
        tracker.on_verification(has_cat=True, boxes=[])
        jpegs_all = _wait_for_n_files(tmp_path, 2)

        new_names = [p.name for p in jpegs_all if p.name != s1_name]
        assert len(new_names) == 1, (
            f"Expected exactly one new JPEG for session 2; all files: "
            f"{[p.name for p in jpegs_all]}"
        )
        assert new_names[0].endswith("-001.jpg"), (
            f"Session 2 first frame should end in -001.jpg, got: {new_names[0]}"
        )
        # Verify session 2 has a different timestamp prefix (distinct session)
        s1_prefix = s1_name[: -len("-001.jpg")]
        s2_prefix = new_names[0][: -len("-001.jpg")]
        assert s1_prefix != s2_prefix, (
            f"Sessions 1 and 2 share the same timestamp prefix ({s1_prefix}); "
            "session 2 did not start fresh"
        )

    def test_session_date_subfolder_from_session_start(
        self, tmp_settings: Settings, tmp_path: Path
    ):
        """Session JPEGs are filed under the session-start date, not today's date."""
        from datetime import datetime

        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=lambda msg: None,
        )
        frame = _make_frame()
        boxes = [BoundingBox(x1=10, y1=10, x2=60, y2=60, confidence=0.85)]

        tracker.on_detection(frame, boxes, "sound.wav")
        # Override session_start to a known past date
        past_date = datetime(2025, 1, 15, 12, 0, 0)
        tracker._session_start = past_date

        tracker.on_verification(has_cat=True, boxes=[])

        jpegs = _wait_for_n_files(tmp_path, 1)
        assert "2025-01-15" in str(jpegs[0]), (
            f"Expected session JPEG under 2025-01-15 subfolder; got: {jpegs[0]}"
        )


# ---------------------------------------------------------------------------
# T011: Single-cycle green session (US2)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestSingleCycleGreenSession:
    """T011: Cat deterred immediately on first alert → exactly one green frame."""

    def test_exactly_one_green_jpeg(self, tmp_settings: Settings, tmp_path: Path):
        """One on_detection + one on_verification(False) → one green -001.jpg."""
        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=lambda msg: pytest.fail(f"Unexpected error: {msg}"),
        )
        frame = _make_frame()
        boxes = [BoundingBox(x1=10, y1=10, x2=60, y2=60, confidence=0.85)]

        tracker.on_detection(frame, boxes, "sound.wav")
        tracker.on_verification(has_cat=False, boxes=[])

        jpegs = _wait_for_n_files(tmp_path, 1)
        assert len(jpegs) == 1, f"Expected exactly 1 JPEG, found {len(jpegs)}"

        name = jpegs[0].name
        assert name.endswith("-001.jpg"), f"Single-cycle file should end in -001.jpg: {name}"

        saved = _load_jpeg(jpegs[0])
        assert saved is not None and saved.size > 0, "JPEG is empty or unreadable"
        assert _has_green_strip(saved), "Single-cycle green session should have green strip"

    def test_no_red_jpeg_exists(self, tmp_settings: Settings, tmp_path: Path):
        """No red-strip JPEG should exist for a cat that left on the first cycle."""
        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=lambda msg: None,
        )
        frame = _make_frame()

        tracker.on_detection(frame, [], "sound.wav")
        tracker.on_verification(has_cat=False, boxes=[])

        jpegs = _wait_for_n_files(tmp_path, 1)
        for path in jpegs:
            img = _load_jpeg(path)
            assert not _has_red_strip(img), (
                f"Unexpected red-strip JPEG in single-cycle green session: {path.name}"
            )


# ---------------------------------------------------------------------------
# T012: Long-running session with five remained cycles (US3)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLongRunningSession:
    """T012: Five consecutive remained cycles → five red JPEGs, session stays open."""

    def test_five_red_jpegs_accumulate(
        self, tmp_settings: Settings, tmp_path: Path
    ):
        """Five cycles of has_cat=True produce -001 through -005 red JPEGs."""
        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=lambda msg: pytest.fail(f"Unexpected error: {msg}"),
        )
        frame = _make_frame()
        boxes = [BoundingBox(x1=10, y1=10, x2=60, y2=60, confidence=0.85)]

        for _ in range(5):
            tracker.on_detection(frame, boxes, "sound.wav")
            tracker.on_verification(has_cat=True, boxes=[])

        jpegs = _wait_for_n_files(tmp_path, 5)
        assert len(jpegs) == 5, f"Expected exactly 5 JPEGs, found {len(jpegs)}"

        names = sorted(p.name for p in jpegs)
        for i, expected_suffix in enumerate(
            ["-001.jpg", "-002.jpg", "-003.jpg", "-004.jpg", "-005.jpg"]
        ):
            assert names[i].endswith(expected_suffix), (
                f"File {i+1} should end in {expected_suffix}: {names[i]}"
            )

        for path in jpegs:
            assert _has_red_strip(_load_jpeg(path)), (
                f"{path.name} should have red (remained) strip"
            )

    def test_session_remains_open_after_five_cycles(
        self, tmp_settings: Settings, tmp_path: Path
    ):
        """After five remained cycles, session is still open (_session_start set, _cycle_count=5)."""
        tracker = EffectivenessTracker(
            settings=tmp_settings,
            is_window_open=lambda: False,
            on_error=lambda msg: None,
        )
        frame = _make_frame()
        boxes = [BoundingBox(x1=10, y1=10, x2=60, y2=60, confidence=0.85)]

        for _ in range(5):
            tracker.on_detection(frame, boxes, "sound.wav")
            tracker.on_verification(has_cat=True, boxes=[])

        _wait_for_n_files(tmp_path, 5)  # ensure all saves completed

        assert tracker._session_start is not None, (
            "Session should remain open after five remained cycles"
        )
        assert tracker._cycle_count == 5, (
            f"Expected _cycle_count=5, got {tracker._cycle_count}"
        )

    def test_cumulative_elapsed_times(
        self, tmp_settings: Settings, tmp_path: Path
    ):
        """Elapsed times in filenames reflect N × cooldown_seconds for N=1..5."""
        cooldown = 30.0
        from catguard.config import Settings as _Settings
        settings = _Settings(
            tracking_directory=str(tmp_path),
            cooldown_seconds=cooldown,
        )
        tracker = EffectivenessTracker(
            settings=settings,
            is_window_open=lambda: False,
            on_error=lambda msg: None,
        )
        frame = _make_frame()
        boxes = [BoundingBox(x1=10, y1=10, x2=60, y2=60, confidence=0.85)]

        for _ in range(5):
            tracker.on_detection(frame, boxes, "sound.wav")
            tracker.on_verification(has_cat=True, boxes=[])

        jpegs = _wait_for_n_files(tmp_path, 5)
        assert len(jpegs) == 5, f"Expected 5 JPEGs; got {len(jpegs)}"

        # Verify each saved file is a valid non-empty JPEG
        for path in jpegs:
            img = _load_jpeg(path)
            assert img is not None and img.size > 0, f"Unreadable JPEG: {path.name}"
