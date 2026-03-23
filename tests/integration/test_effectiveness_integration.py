"""Integration tests for the cat-session screenshot timeline."""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from catguard.annotation import EffectivenessTracker, annotate_frame
from catguard.config import Settings
from catguard.detection import BoundingBox


def _make_frame(h: int = 200, w: int = 300) -> np.ndarray:
    return np.full((h, w, 3), 128, dtype=np.uint8)


def _wait_for_n_files(directory: Path, n: int, timeout: float = 5.0) -> list[Path]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        jpegs = sorted(directory.rglob("*.jpg"))
        if len(jpegs) >= n:
            return jpegs
        time.sleep(0.05)
    found = sorted(directory.rglob("*.jpg"))
    raise TimeoutError(f"Expected {n} JPEG file(s), found {len(found)} in {directory}")


def _load_jpeg(path: Path) -> np.ndarray:
    import cv2

    frame = cv2.imread(str(path))
    assert frame is not None, f"cv2.imread returned None for {path}"
    return frame


def _bottom_edge_pixel(frame: np.ndarray) -> tuple[int, int, int]:
    h, w = frame.shape[:2]
    b, g, r = frame[h - 3, w - 10]
    return int(b), int(g), int(r)


def _has_neutral_strip(frame: np.ndarray) -> bool:
    b, g, r = _bottom_edge_pixel(frame)
    return max(abs(b - g), abs(g - r), abs(b - r)) <= 20 and max(b, g, r) < 100


def _has_red_strip(frame: np.ndarray) -> bool:
    b, g, r = _bottom_edge_pixel(frame)
    return r > 90 and g < 80 and b < 80


def _has_green_strip(frame: np.ndarray) -> bool:
    b, g, r = _bottom_edge_pixel(frame)
    return g > 90 and r < 80 and b < 80


@pytest.fixture()
def tmp_settings(tmp_path: Path) -> Settings:
    return Settings(tracking_directory=str(tmp_path), cooldown_seconds=30.0)


def _make_tracker(settings: Settings, errors: list[str] | None = None) -> EffectivenessTracker:
    collected = errors if errors is not None else []
    return EffectivenessTracker(
        settings=settings,
        is_window_open=lambda: False,
        on_error=collected.append,
    )


def _boxes() -> list[BoundingBox]:
    return [BoundingBox(x1=10, y1=10, x2=60, y2=60, confidence=0.85)]


@pytest.mark.integration
class TestImmediateSessionStart:
    def test_first_detection_writes_001_before_any_verification(self, tmp_settings: Settings, tmp_path: Path):
        tracker = _make_tracker(tmp_settings)

        tracker.on_detection(_make_frame(), _boxes(), "sound.wav")

        jpegs = _wait_for_n_files(tmp_path, 1)
        assert len(jpegs) == 1
        assert jpegs[0].name.endswith("-001.jpg")
        assert _has_neutral_strip(_load_jpeg(jpegs[0]))


@pytest.mark.integration
class TestOrderedSessionTimeline:
    def test_single_cycle_session_writes_neutral_then_green(self, tmp_path: Path):
        settings = Settings(tracking_directory=str(tmp_path), cooldown_seconds=30.0)
        tracker = _make_tracker(settings)

        tracker.on_detection(_make_frame(), _boxes(), "sound.wav")
        tracker.on_verification(_make_frame(), has_cat=False, boxes=[])

        jpegs = _wait_for_n_files(tmp_path, 2)
        assert [p.name[-7:] for p in jpegs] == ["001.jpg", "002.jpg"]
        assert _has_neutral_strip(_load_jpeg(jpegs[0]))
        assert _has_green_strip(_load_jpeg(jpegs[1]))

    def test_multi_cycle_session_writes_neutral_red_green_timeline(self, tmp_path: Path):
        settings = Settings(tracking_directory=str(tmp_path), cooldown_seconds=30.0)
        tracker = _make_tracker(settings)

        tracker.on_detection(_make_frame(), _boxes(), "sound.wav")
        tracker.on_verification(_make_frame(), has_cat=True, boxes=_boxes())
        tracker.on_detection(_make_frame(), _boxes(), "sound.wav")
        tracker.on_verification(_make_frame(), has_cat=False, boxes=[])

        jpegs = _wait_for_n_files(tmp_path, 3)
        names = [p.name for p in jpegs]
        assert names[0].endswith("-001.jpg")
        assert names[1].endswith("-002.jpg")
        assert names[2].endswith("-003.jpg")

        prefix = names[0][: -len("-001.jpg")]
        assert all(name.startswith(prefix) for name in names)
        assert _has_neutral_strip(_load_jpeg(jpegs[0]))
        assert _has_red_strip(_load_jpeg(jpegs[1]))
        assert _has_green_strip(_load_jpeg(jpegs[2]))


@pytest.mark.integration
class TestSessionDurationFormatting:
    def test_saved_outcome_messages_and_logs_use_human_readable_duration(self, tmp_path: Path, caplog):
        settings = Settings(tracking_directory=str(tmp_path), cooldown_seconds=135.0)
        tracker = _make_tracker(settings)
        messages: list[str | None] = []

        def capture_message(frame_bgr, boxes, sound_label, outcome, outcome_message=None):
            messages.append(outcome_message)
            return annotate_frame(frame_bgr, boxes, sound_label, outcome, outcome_message=outcome_message)

        from unittest.mock import patch

        with patch("catguard.annotation.annotate_frame", side_effect=capture_message):
            tracker.on_detection(_make_frame(), _boxes(), "sound.wav")
            with caplog.at_level("INFO"):
                tracker.on_verification(_make_frame(), has_cat=True, boxes=_boxes())

        _wait_for_n_files(tmp_path, 2)
        assert "Cat remained after alert: 2m 15s" in messages
        assert "2m 15s" in caplog.text
        assert "135s" not in caplog.text

    def test_long_duration_logs_use_hour_minute_second_format(self, tmp_path: Path, caplog):
        settings = Settings(tracking_directory=str(tmp_path), cooldown_seconds=3765.0)
        tracker = _make_tracker(settings)

        tracker.on_detection(_make_frame(), _boxes(), "sound.wav")
        with caplog.at_level("INFO"):
            tracker.on_verification(_make_frame(), has_cat=False, boxes=[])

        _wait_for_n_files(tmp_path, 2)
        assert "1h 2m 45s" in caplog.text
        assert "3765s" not in caplog.text


@pytest.mark.integration
class TestSessionAbandonment:
    def test_abandon_preserves_saved_files_and_creates_no_synthetic_close_frame(self, tmp_path: Path):
        settings = Settings(tracking_directory=str(tmp_path), cooldown_seconds=30.0)
        tracker = _make_tracker(settings)

        tracker.on_detection(_make_frame(), _boxes(), "sound.wav")
        tracker.on_verification(_make_frame(), has_cat=True, boxes=_boxes())
        initial_files = _wait_for_n_files(tmp_path, 2)

        tracker.abandon()
        time.sleep(0.2)

        final_files = sorted(tmp_path.rglob("*.jpg"))
        assert [p.name for p in final_files] == [p.name for p in initial_files]
