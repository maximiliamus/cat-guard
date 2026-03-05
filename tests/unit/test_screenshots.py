"""Unit tests for catguard.screenshots — TDD (written before implementation).

Covers (by task):
  T006 : resolve_root, build_filepath, save_screenshot happy path +
         same-second collision, window-open suppression, FR-011/frame=None guard,
         JPEG quality parameter (FR-017)
  T015 : save_screenshot error paths — on_error callback, no exception propagation
  T020 : is_within_time_window — disabled, same-day, midnight-spanning, degenerate
"""
from __future__ import annotations

from datetime import datetime, time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from catguard.config import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blank_frame(h: int = 480, w: int = 640) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def _settings(**kwargs) -> Settings:
    return Settings(**kwargs)


# ---------------------------------------------------------------------------
# T006: resolve_root
# ---------------------------------------------------------------------------

class TestResolveRoot:
    def test_default_tracking_directory_used(self):
        from catguard.screenshots import resolve_root

        s = _settings(tracking_directory="images/CatGuard/tracking")
        result = resolve_root(s)
        assert result == Path("images/CatGuard/tracking").resolve()

    def test_absolute_path_returned_as_is(self):
        from catguard.screenshots import resolve_root

        s = _settings(tracking_directory="/custom/root")
        result = resolve_root(s)
        # On Windows, resolve() adds the drive letter; on Unix it stays as is
        assert isinstance(result, Path)
        assert result.is_absolute()
        assert str(result).endswith("custom/root") or str(result).endswith("custom\\root")

    def test_relative_path_resolved(self):
        from catguard.screenshots import resolve_root

        s = _settings(tracking_directory="images/CatGuard/tracking")
        result = resolve_root(s)
        assert isinstance(result, Path)
        assert result.is_absolute()


# ---------------------------------------------------------------------------
# T006: build_filepath
# ---------------------------------------------------------------------------

class TestBuildFilepath:
    def test_returns_correct_date_folder(self, tmp_path):
        from catguard.screenshots import build_filepath

        ts = datetime(2026, 3, 1, 22, 30, 45)
        result = build_filepath(tmp_path, ts)
        assert result.parent == tmp_path / "2026-03-01"

    def test_returns_hh_mm_ss_filename(self, tmp_path):
        from catguard.screenshots import build_filepath

        ts = datetime(2026, 3, 1, 22, 30, 45)
        result = build_filepath(tmp_path, ts)
        assert result.name == "22-30-45.jpg"

    def test_no_collision_no_counter_suffix(self, tmp_path):
        from catguard.screenshots import build_filepath

        ts = datetime(2026, 3, 1, 22, 30, 45)
        result = build_filepath(tmp_path, ts)
        assert result.name == "22-30-45.jpg"

    def test_same_second_collision_appends_counter(self, tmp_path):
        from catguard.screenshots import build_filepath

        ts = datetime(2026, 3, 1, 22, 30, 45)
        date_dir = tmp_path / "2026-03-01"
        date_dir.mkdir()
        (date_dir / "22-30-45.jpg").write_bytes(b"x")

        result = build_filepath(tmp_path, ts)
        assert result.name == "22-30-45-1.jpg"

    def test_multiple_collisions_increments_counter(self, tmp_path):
        from catguard.screenshots import build_filepath

        ts = datetime(2026, 3, 1, 22, 30, 45)
        date_dir = tmp_path / "2026-03-01"
        date_dir.mkdir()
        (date_dir / "22-30-45.jpg").write_bytes(b"x")
        (date_dir / "22-30-45-1.jpg").write_bytes(b"x")

        result = build_filepath(tmp_path, ts)
        assert result.name == "22-30-45-2.jpg"

    def test_result_is_path_object(self, tmp_path):
        from catguard.screenshots import build_filepath

        ts = datetime(2026, 3, 1, 8, 0, 0)
        result = build_filepath(tmp_path, ts)
        assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# T006: save_screenshot — happy path + guards
# ---------------------------------------------------------------------------

class TestSaveScreenshotHappyPath:
    def test_creates_file_on_disk(self, tmp_path):
        from catguard.screenshots import save_screenshot

        frame = _blank_frame()
        s = _settings(tracking_directory=str(tmp_path))
        on_error = MagicMock()

        save_screenshot(frame, s, is_window_open=lambda: False, on_error=on_error)

        jpgs = list(tmp_path.rglob("*.jpg"))
        assert len(jpgs) == 1
        on_error.assert_not_called()

    def test_saves_into_date_subfolder(self, tmp_path):
        from catguard.screenshots import save_screenshot

        frame = _blank_frame()
        s = _settings(tracking_directory=str(tmp_path))

        with patch("catguard.screenshots.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 1, 14, 0, 0)
            save_screenshot(frame, s, is_window_open=lambda: False, on_error=MagicMock())

        date_dir = tmp_path / "2026-03-01"
        assert date_dir.exists()
        assert any(date_dir.iterdir())

    def test_jpeg_quality_high_used(self, tmp_path):
        """FR-017: cv2.imencode should be called with a high JPEG quality (90)."""
        from catguard.screenshots import save_screenshot
        import cv2

        frame = _blank_frame()
        s = _settings(tracking_directory=str(tmp_path))

        with patch("catguard.screenshots.cv2") as mock_cv2:
            mock_cv2.imencode.return_value = (True, MagicMock(tobytes=lambda: b"fake"))
            mock_cv2.IMWRITE_JPEG_QUALITY = cv2.IMWRITE_JPEG_QUALITY
            save_screenshot(frame, s, is_window_open=lambda: False, on_error=MagicMock())

        mock_cv2.imencode.assert_called_once()
        call_args = mock_cv2.imencode.call_args
            # Third arg is the params list: [cv2.IMWRITE_JPEG_QUALITY, 90]
        params = call_args[0][2]
        assert params[0] == cv2.IMWRITE_JPEG_QUALITY
        assert params[1] == 90


class TestSaveScreenshotGuards:
    def test_frame_none_skips_silently(self, tmp_path):
        """FR-011: cooldown-suppressed events (frame_bgr=None) must not save."""
        from catguard.screenshots import save_screenshot

        s = _settings(tracking_directory=str(tmp_path))
        on_error = MagicMock()

        save_screenshot(None, s, is_window_open=lambda: False, on_error=on_error)

        assert list(tmp_path.rglob("*.jpg")) == []
        on_error.assert_not_called()

    def test_main_window_open_skips_silently(self, tmp_path):
        """FR-012: no screenshot when main window is open."""
        from catguard.screenshots import save_screenshot

        frame = _blank_frame()
        s = _settings(tracking_directory=str(tmp_path))
        on_error = MagicMock()

        save_screenshot(frame, s, is_window_open=lambda: True, on_error=on_error)

        assert list(tmp_path.rglob("*.jpg")) == []
        on_error.assert_not_called()

    def test_creates_missing_parent_dirs(self, tmp_path):
        """FR-005: all missing intermediate folders created on first save."""
        from catguard.screenshots import save_screenshot

        root = tmp_path / "nested" / "deep" / "root"
        s = _settings(tracking_directory=str(root))

        save_screenshot(
            _blank_frame(), s, is_window_open=lambda: False, on_error=MagicMock()
        )

        assert any(root.rglob("*.jpg"))


# ---------------------------------------------------------------------------
# T015: save_screenshot — error paths
# ---------------------------------------------------------------------------

class TestSaveScreenshotErrors:
    def test_on_error_called_when_encodefails(self, tmp_path):
        from catguard.screenshots import save_screenshot

        frame = _blank_frame()
        s = _settings(tracking_directory=str(tmp_path))
        on_error = MagicMock()

        with patch("catguard.screenshots.cv2") as mock_cv2:
            mock_cv2.imencode.return_value = (False, None)
            mock_cv2.IMWRITE_JPEG_QUALITY = 95
            save_screenshot(frame, s, is_window_open=lambda: False, on_error=on_error)

        on_error.assert_called_once()
        assert "screenshot" in on_error.call_args[0][0].lower()

    def test_on_error_called_on_oserror(self, tmp_path):
        from catguard.screenshots import save_screenshot

        frame = _blank_frame()
        s = _settings(tracking_directory=str(tmp_path))
        on_error = MagicMock()

        with patch("catguard.screenshots.cv2") as mock_cv2:
            mock_cv2.IMWRITE_JPEG_QUALITY = 95
            mock_cv2.imencode.return_value = (True, MagicMock(tobytes=lambda: b"data"))
            with patch("pathlib.Path.write_bytes", side_effect=OSError("disk full")):
                save_screenshot(
                    frame, s, is_window_open=lambda: False, on_error=on_error
                )

        on_error.assert_called_once()

    def test_exception_does_not_propagate(self, tmp_path):
        """SC-004: save failures must never raise to the caller."""
        from catguard.screenshots import save_screenshot

        frame = _blank_frame()
        s = _settings(tracking_directory=str(tmp_path))

        with patch("catguard.screenshots.cv2") as mock_cv2:
            mock_cv2.IMWRITE_JPEG_QUALITY = 95
            mock_cv2.imencode.side_effect = RuntimeError("unexpected cv2 error")
            # Must NOT raise
            save_screenshot(
                frame, s, is_window_open=lambda: False, on_error=lambda msg: None
            )


# ---------------------------------------------------------------------------
# T020: is_within_time_window
# ---------------------------------------------------------------------------

class TestIsWithinTimeWindow:
    def test_disabled_always_returns_true(self):
        from catguard.screenshots import is_within_time_window

        s = _settings(tracking_window_enabled=False)
        assert is_within_time_window(s) is True

    def test_same_day_window_inside(self):
        from catguard.screenshots import is_within_time_window

        s = _settings(
            tracking_window_enabled=True,
            tracking_window_start="08:00",
            tracking_window_end="18:00",
        )
        fake_now = datetime(2026, 3, 1, 12, 0, 0)
        with patch("catguard.screenshots.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            result = is_within_time_window(s)
        assert result is True

    def test_same_day_window_outside(self):
        from catguard.screenshots import is_within_time_window

        s = _settings(
            tracking_window_enabled=True,
            tracking_window_start="08:00",
            tracking_window_end="18:00",
        )
        fake_now = datetime(2026, 3, 1, 20, 0, 0)
        with patch("catguard.screenshots.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            result = is_within_time_window(s)
        assert result is False

    def test_midnight_spanning_window_inside_late(self):
        """23:30 falls within 22:00–06:00."""
        from catguard.screenshots import is_within_time_window

        s = _settings(
            tracking_window_enabled=True,
            tracking_window_start="22:00",
            tracking_window_end="06:00",
        )
        fake_now = datetime(2026, 3, 1, 23, 30, 0)
        with patch("catguard.screenshots.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            result = is_within_time_window(s)
        assert result is True

    def test_midnight_spanning_window_inside_early(self):
        """03:00 falls within 22:00–06:00."""
        from catguard.screenshots import is_within_time_window

        s = _settings(
            tracking_window_enabled=True,
            tracking_window_start="22:00",
            tracking_window_end="06:00",
        )
        fake_now = datetime(2026, 3, 1, 3, 0, 0)
        with patch("catguard.screenshots.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            result = is_within_time_window(s)
        assert result is True

    def test_midnight_spanning_window_outside(self):
        """14:00 is outside 22:00–06:00."""
        from catguard.screenshots import is_within_time_window

        s = _settings(
            tracking_window_enabled=True,
            tracking_window_start="22:00",
            tracking_window_end="06:00",
        )
        fake_now = datetime(2026, 3, 1, 14, 0, 0)
        with patch("catguard.screenshots.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            result = is_within_time_window(s)
        assert result is False

    def test_degenerate_equal_times_treated_as_disabled(self):
        """start == end treated as 'always within window', logs warning."""
        from catguard.screenshots import is_within_time_window

        s = _settings(
            tracking_window_enabled=True,
            tracking_window_start="12:00",
            tracking_window_end="12:00",
        )
        # Any time should be accepted
        fake_now = datetime(2026, 3, 1, 8, 0, 0)
        with patch("catguard.screenshots.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            result = is_within_time_window(s)
        assert result is True
