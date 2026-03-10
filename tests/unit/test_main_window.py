"""Unit tests for catguard.ui.main_window — written BEFORE implementation (TDD RED).

Uses mocked tkinter so tests run headlessly (no display required).

Tests verify:
- MainWindow instantiation creates a Toplevel and stores it on root
- show_or_focus creates the window once; focuses on re-call
- update_frame sets window geometry to frame w×h on first call
- update_frame handles subsequent calls without re-setting geometry
- _show_no_source_message renders a message label
- _on_close destroys window and clears root._main_window
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_root():
    root = MagicMock()
    root._main_window = None
    return root


def _blank_frame(h: int = 480, w: int = 640) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# We patch tkinter at import time so no display is required
# ---------------------------------------------------------------------------

@pytest.fixture()
def patched_tk(monkeypatch):
    """Patch tk.Toplevel and tk.Canvas so MainWindow can be instantiated headlessly."""
    mock_tk = MagicMock()
    mock_toplevel_instance = MagicMock()
    mock_tk.Toplevel.return_value = mock_toplevel_instance
    mock_canvas_instance = MagicMock()
    mock_tk.Canvas.return_value = mock_canvas_instance
    # winfo_screenwidth / height used for clamping large frames
    mock_toplevel_instance.winfo_screenwidth.return_value = 1920
    mock_toplevel_instance.winfo_screenheight.return_value = 1080
    with patch.dict("sys.modules", {"tkinter": mock_tk}):
        # Re-import main_window with the patched tkinter
        import importlib
        import catguard.ui.main_window as mw_mod
        importlib.reload(mw_mod)
        yield mw_mod, mock_tk, mock_toplevel_instance, mock_canvas_instance


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

class TestMainWindowInit:
    def test_creates_toplevel(self, patched_tk):
        mw_mod, mock_tk, toplevel_inst, _ = patched_tk
        root = _make_root()
        mw_mod.MainWindow(root)
        mock_tk.Toplevel.assert_called_once_with(root)

    def test_stores_reference_on_root(self, patched_tk):
        mw_mod, mock_tk, _, _ = patched_tk
        root = _make_root()
        win = mw_mod.MainWindow(root)
        assert root._main_window is win

    def test_binds_on_close(self, patched_tk):
        mw_mod, mock_tk, toplevel_inst, _ = patched_tk
        root = _make_root()
        mw_mod.MainWindow(root)
        # protocol should be registered for WM_DELETE_WINDOW
        toplevel_inst.protocol.assert_called_once_with("WM_DELETE_WINDOW", toplevel_inst.protocol.call_args[0][1])

    def test_window_initially_hidden(self, patched_tk):
        mw_mod, mock_tk, toplevel_inst, _ = patched_tk
        root = _make_root()
        mw_mod.MainWindow(root)
        toplevel_inst.withdraw.assert_called_once()


# ---------------------------------------------------------------------------
# show_or_focus
# ---------------------------------------------------------------------------

class TestShowOrFocus:
    def test_deiconifies_on_first_call(self, patched_tk):
        mw_mod, mock_tk, toplevel_inst, _ = patched_tk
        root = _make_root()
        win = mw_mod.MainWindow(root)
        win.show_or_focus()
        toplevel_inst.deiconify.assert_called()

    def test_raises_window_on_second_call(self, patched_tk):
        mw_mod, mock_tk, toplevel_inst, _ = patched_tk
        root = _make_root()
        win = mw_mod.MainWindow(root)
        win.show_or_focus()
        win.show_or_focus()
        # lift() should be called to bring the existing window to front
        toplevel_inst.lift.assert_called()


# ---------------------------------------------------------------------------
# update_frame
# ---------------------------------------------------------------------------

class TestUpdateFrame:
    def test_sets_geometry_on_first_call(self, patched_tk):
        mw_mod, mock_tk, toplevel_inst, _ = patched_tk
        root = _make_root()
        win = mw_mod.MainWindow(root)
        frame = _blank_frame(480, 640)
        win.update_frame(frame, [])
        # geometry should have been called with "640x520" (480 frame + 40px action panel)
        toplevel_inst.geometry.assert_called_with("640x520")

    def test_skips_geometry_on_same_size_frame(self, patched_tk):
        """geometry() is not called again when the frame size is unchanged (perf guard)."""
        mw_mod, mock_tk, toplevel_inst, _ = patched_tk
        root = _make_root()
        win = mw_mod.MainWindow(root)
        frame = _blank_frame(480, 640)
        win.update_frame(frame, [])
        toplevel_inst.geometry.reset_mock()
        win.update_frame(frame, [])
        toplevel_inst.geometry.assert_not_called()

    def test_clamps_geometry_to_screen_size(self, patched_tk):
        """A frame larger than screen bounds should be clamped."""
        mw_mod, mock_tk, toplevel_inst, _ = patched_tk
        toplevel_inst.winfo_screenwidth.return_value = 1920
        toplevel_inst.winfo_screenheight.return_value = 1080
        root = _make_root()
        win = mw_mod.MainWindow(root)
        huge_frame = _blank_frame(2160, 3840)  # 4K larger than screen
        win.update_frame(huge_frame, [])
        geo_call = toplevel_inst.geometry.call_args[0][0]
        w_str, h_str = geo_call.split("x")
        assert int(w_str) <= 1920
        assert int(h_str) <= 1080


# ---------------------------------------------------------------------------
# _on_close
# ---------------------------------------------------------------------------

class TestOnClose:
    def test_destroys_toplevel(self, patched_tk):
        mw_mod, mock_tk, toplevel_inst, _ = patched_tk
        root = _make_root()
        win = mw_mod.MainWindow(root)
        win._on_close()
        toplevel_inst.destroy.assert_called_once()

    def test_clears_root_reference(self, patched_tk):
        mw_mod, mock_tk, _, _ = patched_tk
        root = _make_root()
        win = mw_mod.MainWindow(root)
        win._on_close()
        assert root._main_window is None

    def test_sets_closed_flag(self, patched_tk):
        """_closed must be True after _on_close so stale callbacks are dropped."""
        mw_mod, mock_tk, _, _ = patched_tk
        root = _make_root()
        win = mw_mod.MainWindow(root)
        assert not win._closed
        win._on_close()
        assert win._closed

    def test_update_frame_after_close_is_silently_dropped(self, patched_tk):
        """update_frame called after close must not raise (race-condition guard)."""
        mw_mod, mock_tk, toplevel_inst, canvas_inst = patched_tk
        root = _make_root()
        win = mw_mod.MainWindow(root)
        win._on_close()
        # Simulate a stale root.after callback arriving after the window is gone
        frame = _blank_frame(480, 640)
        # Must not raise; canvas should NOT be touched
        win.update_frame(frame, [])
        canvas_inst.create_image.assert_not_called()
        canvas_inst.itemconfig.assert_not_called()


# ---------------------------------------------------------------------------
# _show_no_source_message
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# T010a: _main_window_visible visibility flag
# ---------------------------------------------------------------------------

class TestMainWindowVisibilityFlag:
    """T010a \u2014 _main_window_visible bool toggled by show_or_focus / _on_close."""

    def test_show_or_focus_sets_visible_true(self, patched_tk):
        """show_or_focus() must set root._main_window_visible = True."""
        mw_mod, mock_tk, toplevel_inst, _ = patched_tk
        root = _make_root()
        win = mw_mod.MainWindow(root)
        # Simulate startup default
        root._main_window_visible = False
        win.show_or_focus()
        assert root._main_window_visible is True

    def test_on_close_sets_visible_false(self, patched_tk):
        """_on_close() must set root._main_window_visible = False."""
        mw_mod, mock_tk, toplevel_inst, _ = patched_tk
        root = _make_root()
        win = mw_mod.MainWindow(root)
        root._main_window_visible = True
        win._on_close()
        assert root._main_window_visible is False

    def test_flag_toggles_correctly_on_show_then_close(self, patched_tk):
        """Round-trip: show -> True, close -> False."""
        mw_mod, mock_tk, toplevel_inst, _ = patched_tk
        root = _make_root()
        win = mw_mod.MainWindow(root)
        root._main_window_visible = False
        win.show_or_focus()
        assert root._main_window_visible is True
        win._on_close()
        assert root._main_window_visible is False


class TestNoSourceMessage:
    def test_creates_label_with_message(self, patched_tk):
        mw_mod, mock_tk, toplevel_inst, _ = patched_tk
        root = _make_root()
        win = mw_mod.MainWindow(root)
        win._show_no_source_message()
        # A Label widget should have been created
        mock_tk.Label.assert_called()
        label_call_kwargs = mock_tk.Label.call_args
        # The label text should contain a human-readable message
        call_args_flat = str(label_call_kwargs)
        assert any(keyword in call_args_flat.lower() for keyword in ("source", "unavailable", "capture", "no"))


# ---------------------------------------------------------------------------
# T021: update_frame with empty detections shows "No detections" on canvas
# ---------------------------------------------------------------------------

class TestUpdateFrameNoDetections:
    def test_empty_detections_shows_no_detections_text(self, patched_tk):
        """update_frame with [] detections must not crash and must render the frame."""
        mw_mod, mock_tk, toplevel_inst, canvas_inst = patched_tk
        root = _make_root()
        win = mw_mod.MainWindow(root)
        frame = _blank_frame(480, 640)

        with patch("PIL.ImageTk.PhotoImage", return_value=MagicMock()):
            win.update_frame(frame, [])  # must not raise

        # Canvas image must have been created/updated
        assert canvas_inst.create_image.called or canvas_inst.itemconfig.called

    def test_detections_present_no_overlay_text(self, patched_tk):
        """update_frame with detections must not show any 'No detections' text."""
        from unittest.mock import MagicMock as MM
        mw_mod, mock_tk, toplevel_inst, canvas_inst = patched_tk
        root = _make_root()
        win = mw_mod.MainWindow(root)
        frame = _blank_frame(480, 640)

        box = MM()
        box.xyxy = [[10, 10, 50, 50]]
        box.conf = [0.9]
        box.cls = [15]
        result = MM()
        result.boxes = [box]
        result.names = {15: "cat"}

        with patch("PIL.ImageTk.PhotoImage", return_value=MagicMock()):
            win.update_frame(frame, [result])  # must not raise

        create_text_calls = str(canvas_inst.create_text.call_args_list)
        assert "No detections" not in create_text_calls

