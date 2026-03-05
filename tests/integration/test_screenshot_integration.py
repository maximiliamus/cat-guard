"""Integration tests for screenshot capture on detection.

T007: End-to-end verification that a real JPEG file is created on disk
      when save_screenshot() is called with a synthetic frame.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from catguard.config import Settings
from catguard.screenshots import save_screenshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blank_frame(h: int = 480, w: int = 640) -> np.ndarray:
    """Return a synthetic BGR frame (all zeros — valid cv2 input)."""
    return np.zeros((h, w, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# T007: Real file creation on disk
# ---------------------------------------------------------------------------

class TestScreenshotIntegration:
    def test_jpeg_file_created_for_synthetic_frame(self, tmp_path):
        """A real .jpg file must appear on disk within the correct date folder."""
        s = Settings(tracking_directory=str(tmp_path))

        with patch("catguard.screenshots.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 1, 22, 30, 0)
            save_screenshot(
                _blank_frame(),
                s,
                is_window_open=lambda: False,
                on_error=lambda msg: (_ for _ in ()).throw(AssertionError(msg)),
            )

        expected_dir = tmp_path / "2026-03-01"
        jpgs = list(expected_dir.glob("*.jpg"))
        assert len(jpgs) == 1, f"Expected 1 .jpg in {expected_dir}, got: {jpgs}"
        assert jpgs[0].stat().st_size > 0, "JPEG file must not be empty"

    def test_file_is_valid_jpeg(self, tmp_path):
        """Saved file must be a readable JPEG."""
        import cv2

        s = Settings(tracking_directory=str(tmp_path))
        frame = _blank_frame()

        save_screenshot(frame, s, is_window_open=lambda: False, on_error=MagicMock())

        jpgs = list(tmp_path.rglob("*.jpg"))
        assert jpgs, "No JPEG found"
        loaded = cv2.imread(str(jpgs[0]))
        assert loaded is not None, "cv2.imread could not read the saved JPEG"

    def test_two_saves_same_second_produce_unique_files(self, tmp_path):
        """Same-second collisions must yield two distinct file paths."""
        s = Settings(tracking_directory=str(tmp_path))

        fixed_ts = datetime(2026, 3, 1, 22, 30, 0)
        with patch("catguard.screenshots.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_ts
            save_screenshot(
                _blank_frame(), s, is_window_open=lambda: False, on_error=MagicMock()
            )
            save_screenshot(
                _blank_frame(), s, is_window_open=lambda: False, on_error=MagicMock()
            )

        jpgs = list(tmp_path.rglob("*.jpg"))
        assert len(jpgs) == 2, f"Expected 2 files for same-second saves, got: {jpgs}"
        assert jpgs[0].name != jpgs[1].name

    def test_no_file_when_window_open(self, tmp_path):
        """FR-012: no file when main window is open (integration guard)."""
        s = Settings(tracking_directory=str(tmp_path))
        save_screenshot(
            _blank_frame(), s, is_window_open=lambda: True, on_error=MagicMock()
        )
        assert list(tmp_path.rglob("*.jpg")) == []

    def test_error_callback_on_write_failure(self, tmp_path):
        """US3: on_error is called (not raised) when write fails."""
        import cv2
        from unittest.mock import MagicMock, patch

        s = Settings(tracking_directory=str(tmp_path))
        on_error = MagicMock()

        with patch("pathlib.Path.write_bytes", side_effect=PermissionError("read-only")):
            save_screenshot(
                _blank_frame(), s, is_window_open=lambda: False, on_error=on_error
            )

        on_error.assert_called_once()


# ---------------------------------------------------------------------------
# import guard for MagicMock
# ---------------------------------------------------------------------------
from unittest.mock import MagicMock  # noqa: E402 (placed after test definitions intentionally)
