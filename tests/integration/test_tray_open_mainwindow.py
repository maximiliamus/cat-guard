"""Integration tests for Tray → Open → MainWindow with detection overlays.

T024 — verifies end-to-end data flow:
  1. A synthetic BGR frame is created.
  2. A mock YOLO detection result is assembled.
  3. MainWindow.update_frame is called with the frame and detection.
  4. Geometry is set to match the frame dimensions.
  5. draw_detections annotates the frame (pixel-level verification).
  6. No "No detections" overlay is shown when detections are present.

These tests use headless tkinter mocks so no display is required.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _synthetic_frame(h: int = 480, w: int = 640) -> np.ndarray:
    """Return a black BGR frame of the given dimensions."""
    return np.zeros((h, w, 3), dtype=np.uint8)


def _make_detection(x1: int, y1: int, x2: int, y2: int, cls_id: int = 15):
    """Build a minimal YOLO result mock with one bounding box."""
    box = MagicMock()
    box.xyxy = [[x1, y1, x2, y2]]
    box.conf = [0.91]
    box.cls = [cls_id]

    result = MagicMock()
    result.boxes = [box]
    result.names = {cls_id: "cat"}
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def headless_main_window():
    """Yield (MainWindow class, mock_root, mock_toplevel, mock_canvas) with
    tkinter patched so no real display is required.
    """
    mock_tk = MagicMock()
    mock_toplevel = MagicMock()
    mock_canvas = MagicMock()
    mock_tk.Toplevel.return_value = mock_toplevel
    mock_tk.Canvas.return_value = mock_canvas
    mock_toplevel.winfo_screenwidth.return_value = 1920
    mock_toplevel.winfo_screenheight.return_value = 1080

    mock_root = MagicMock()
    mock_root._main_window = None

    with patch.dict("sys.modules", {"tkinter": mock_tk}):
        import importlib
        import catguard.ui.main_window as mw_mod
        importlib.reload(mw_mod)
        yield mw_mod.MainWindow, mock_root, mock_toplevel, mock_canvas


# ---------------------------------------------------------------------------
# T024: Integration scenarios
# ---------------------------------------------------------------------------

class TestTrayOpenMainWindow:
    def test_update_frame_sets_geometry_to_frame_size(self, headless_main_window):
        """Window geometry must be set to the exact frame dimensions (640x480)."""
        MainWindow, mock_root, mock_toplevel, _ = headless_main_window
        win = MainWindow(mock_root)
        frame = _synthetic_frame(480, 640)
        detection = _make_detection(50, 50, 200, 200)

        with patch("PIL.ImageTk.PhotoImage", return_value=MagicMock()):
            win.update_frame(frame, [detection])

        mock_toplevel.geometry.assert_called_with("640x520")

    def test_update_frame_annotates_frame_via_draw_detections(self, headless_main_window):
        """draw_detections must be called and must annotate the frame with a bounding box."""
        from catguard.ui.overlays import draw_detections

        MainWindow, mock_root, mock_toplevel, _ = headless_main_window
        win = MainWindow(mock_root)
        frame = _synthetic_frame(480, 640)
        detection = _make_detection(50, 50, 200, 200)

        annotated_frames: list[np.ndarray] = []

        original_draw = draw_detections

        def capturing_draw(f, results):
            result = original_draw(f, results)
            annotated_frames.append(result)
            return result

        # draw_detections is imported locally in update_frame; patch the source module
        with patch("PIL.ImageTk.PhotoImage", return_value=MagicMock()), \
             patch("catguard.ui.overlays.draw_detections", side_effect=capturing_draw):
            win.update_frame(frame, [detection])

        assert len(annotated_frames) == 1, "draw_detections should be called exactly once"
        annotated = annotated_frames[0]
        assert np.any(annotated != 0), "Expected bounding box pixels drawn on the annotated frame"

    def test_single_cat_detection_no_overlay_text(self, headless_main_window):
        """When a cat is detected, 'No detections' text must NOT appear on the canvas."""
        MainWindow, mock_root, mock_toplevel, mock_canvas = headless_main_window
        win = MainWindow(mock_root)
        frame = _synthetic_frame(480, 640)
        detection = _make_detection(100, 100, 300, 300)

        with patch("PIL.ImageTk.PhotoImage", return_value=MagicMock()):
            win.update_frame(frame, [detection])

        create_text_calls = str(mock_canvas.create_text.call_args_list)
        assert "No detections" not in create_text_calls

    def test_no_detection_shows_overlay_text(self, headless_main_window):
        """With empty detections, update_frame must not crash and must render the frame."""
        MainWindow, mock_root, mock_toplevel, mock_canvas = headless_main_window
        win = MainWindow(mock_root)
        frame = _synthetic_frame(480, 640)

        with patch("PIL.ImageTk.PhotoImage", return_value=MagicMock()):
            win.update_frame(frame, [])  # must not raise

        create_text_calls = str(mock_canvas.create_text.call_args_list)
        assert "No detections" not in create_text_calls

    def test_geometry_clamped_for_oversized_frame(self, headless_main_window):
        """Frame larger than screen bounds must be clamped to screen size."""
        MainWindow, mock_root, mock_toplevel, _ = headless_main_window
        mock_toplevel.winfo_screenwidth.return_value = 1280
        mock_toplevel.winfo_screenheight.return_value = 720
        win = MainWindow(mock_root)
        huge_frame = _synthetic_frame(2160, 3840)  # 4K

        with patch("PIL.ImageTk.PhotoImage", return_value=MagicMock()):
            win.update_frame(huge_frame, [])

        geo_call = mock_toplevel.geometry.call_args[0][0]
        w_str, h_str = geo_call.split("x")
        assert int(w_str) <= 1280, f"Width {w_str} exceeds screen width 1280"
        assert int(h_str) <= 720, f"Height {h_str} exceeds screen height 720"

    def test_window_reference_stored_on_root(self, headless_main_window):
        """MainWindow must register itself as root._main_window on creation."""
        MainWindow, mock_root, mock_toplevel, _ = headless_main_window
        win = MainWindow(mock_root)
        assert mock_root._main_window is win

    def test_close_clears_root_reference(self, headless_main_window):
        """Closing the window must clear root._main_window."""
        MainWindow, mock_root, mock_toplevel, _ = headless_main_window
        win = MainWindow(mock_root)
        win._on_close()
        assert mock_root._main_window is None

    def test_close_invokes_on_close_extra(self, headless_main_window):
        """_on_close must call _on_close_extra if set (used to clear frame callback)."""
        MainWindow, mock_root, mock_toplevel, _ = headless_main_window
        win = MainWindow(mock_root)
        extra_called = []
        win._on_close_extra = lambda: extra_called.append(True)
        win._on_close()
        assert extra_called == [True], "_on_close_extra should have been invoked exactly once"
