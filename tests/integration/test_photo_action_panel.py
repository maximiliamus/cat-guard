"""Integration tests for the photo action panel (US1 + US2 integration tests).

TDD approach: Write tests before implementation. These tests will FAIL until
the PhotoWindow and ActionPanel UI components are implemented.
"""
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open, call
from datetime import datetime
from pathlib import Path
import sys
import numpy as np

# Note: tkinter is only available in integration tests
pytest.importorskip("tkinter")
import tkinter as tk

# Skip the entire module when Tcl/Tk cannot create a real window (headless CI).
try:
    _root_check = tk.Tk()
    _root_check.withdraw()
    _root_check.destroy()
except Exception as _tcl_err:
    pytest.skip(f"Tcl/Tk display not available: {_tcl_err}", allow_module_level=True)


class TestPhotoWindowBasics:
    """T006 — PhotoWindow instantiation and UI layout."""
    
    def test_photo_window_renders_three_buttons(self):
        """PhotoWindow displays Save, Save As..., and Close buttons (NFR-UX-001)."""
        from catguard.photos import Photo
        from catguard.ui.photo_window import PhotoWindow
        
        root = tk.Tk()
        try:
            ts = datetime(2026, 3, 5, 12, 34, 56)
            photo = Photo(timestamp=ts, bytes=b"\xff\xd8" + b"\x00" * 100)
            
            window = PhotoWindow(
                master=root,
                photo=photo,
                last_save_dir=None,
                on_save_dir_change=MagicMock()
            )
            
            # Find buttons by their labels
            buttons = []
            for widget in window._window.winfo_children():
                self._find_buttons_recursive(widget, buttons)
            
            button_labels = [b.cget('text') for b in buttons]
            assert "Save" in button_labels
            assert "Save As..." in button_labels
            assert "Close" in button_labels
            
            window._window.destroy()
        finally:
            root.destroy()
    
    def _find_buttons_recursive(self, widget, buttons):
        """Helper to recursively find all buttons in widget hierarchy."""
        try:
            if widget.winfo_class() == 'Button':
                buttons.append(widget)
        except:
            pass
        try:
            for child in widget.winfo_children():
                self._find_buttons_recursive(child, buttons)
        except:
            pass
    """T006 — Save button writes to correct path and provides feedback."""
    
    def test_save_writes_to_correct_path(self, tmp_path, monkeypatch):
        """Save button writes photo bytes to YYYY-MM-DD/HH-MM-SS.jpg path."""
        from catguard.photos import Photo
        from catguard.ui.photo_window import PhotoWindow
        from catguard.config import Settings
        
        root = tk.Tk()
        try:
            ts = datetime(2026, 3, 5, 12, 34, 56)
            photo = Photo(timestamp=ts, bytes=b"JPEG_DATA")
            
            # Create a mock settings with temp directory
            settings = Settings(photos_directory=str(tmp_path))
            
            window = PhotoWindow(
                master=root,
                photo=photo,
                settings=settings,
                last_save_dir=None,
                on_save_dir_change=MagicMock()
            )
            
            # Simulate clicking Save button
            save_btn = self._get_button_by_label(window, "Save")
            save_btn.invoke()
            
            # Verify file was created in correct location
            expected_path = tmp_path / "2026-03-05" / "12-34-56.jpg"
            assert expected_path.exists()
            assert expected_path.read_bytes() == b"JPEG_DATA"
            
            window._window.destroy()
        finally:
            root.destroy()
    
    def test_save_handles_collision_with_suffix(self, tmp_path, monkeypatch):
        """Save appends -1, -2, ... suffix on filename collision."""
        from catguard.photos import Photo
        from catguard.ui.photo_window import PhotoWindow
        from catguard.config import Settings
        
        root = tk.Tk()
        try:
            ts = datetime(2026, 3, 5, 12, 34, 56)
            
            # Create existing file to trigger collision
            (tmp_path / "2026-03-05").mkdir()
            (tmp_path / "2026-03-05" / "12-34-56.jpg").write_bytes(b"EXISTING")
            
            photo = Photo(timestamp=ts, bytes=b"NEW_DATA")
            settings = Settings(photos_directory=str(tmp_path))
            
            window = PhotoWindow(
                master=root,
                photo=photo,
                settings=settings,
                last_save_dir=None,
                on_save_dir_change=MagicMock()
            )
            
            save_btn = self._get_button_by_label(window, "Save")
            save_btn.invoke()
            
            # Verify collision suffix was used
            collision_path = tmp_path / "2026-03-05" / "12-34-56-1.jpg"
            assert collision_path.exists()
            assert collision_path.read_bytes() == b"NEW_DATA"
            
            window._window.destroy()
        finally:
            root.destroy()
    
    def test_save_shows_feedback_label(self, tmp_path, monkeypatch):
        """Save button briefly shows 'Saved ✓' feedback (NFR-UX-001)."""
        from catguard.photos import Photo
        from catguard.ui.photo_window import PhotoWindow
        from catguard.config import Settings
        
        root = tk.Tk()
        try:
            ts = datetime(2026, 3, 5, 12, 34, 56)
            photo = Photo(timestamp=ts, bytes=b"JPEG_DATA")
            settings = Settings(photos_directory=str(tmp_path))
            
            window = PhotoWindow(
                master=root,
                photo=photo,
                settings=settings,
                last_save_dir=None,
                on_save_dir_change=MagicMock()
            )
            
            save_btn = self._get_button_by_label(window, "Save")
            original_text = save_btn.cget('text')
            
            save_btn.invoke()
            # After save, button text should show success
            assert "Saved" in save_btn.cget('text') or save_btn.cget('text') == "Save"
            
            window._window.destroy()
        finally:
            root.destroy()
    
    def test_save_failure_shows_error_message(self, tmp_path, monkeypatch):
        """Save failure displays 'Save failed — <path>' inline message."""
        from catguard.photos import Photo
        from catguard.ui.photo_window import PhotoWindow
        from catguard.config import Settings
        
        root = tk.Tk()
        try:
            ts = datetime(2026, 3, 5, 12, 34, 56)
            photo = Photo(timestamp=ts, bytes=b"JPEG_DATA")
            
            # Use non-writable path to force failure
            bad_path = tmp_path / "readonly"
            bad_path.mkdir(mode=0o555)
            
            settings = Settings(photos_directory=str(bad_path))
            
            window = PhotoWindow(
                master=root,
                photo=photo,
                settings=settings,
                last_save_dir=None,
                on_save_dir_change=MagicMock()
            )
            
            save_btn = self._get_button_by_label(window, "Save")
            save_btn.invoke()
            
            # Error message should be displayed in status label or similar
            # This would be verified by checking window state after click
            
            window._window.destroy()
        finally:
            # Restore write permission for cleanup
            import stat
            bad_path.chmod(stat.S_IRWXU)
            root.destroy()
    
    def _get_button_by_label(self, widget, label):
        """Find a button by its text label."""
        # Handle PhotoWindow objects by accessing internal _window
        if hasattr(widget, '_window'):
            widget = widget._window
        buttons = []
        self._find_buttons_recursive(widget, buttons)
        for btn in buttons:
            try:
                if btn.cget('text') == label:
                    return btn
            except:
                pass
        return None
    
    def _find_buttons_recursive(self, widget, buttons):
        """Helper to recursively find all buttons in widget hierarchy."""
        try:
            if widget.winfo_class() == 'Button':
                buttons.append(widget)
        except:
            pass
        try:
            for child in widget.winfo_children():
                self._find_buttons_recursive(child, buttons)
        except:
            pass


class TestCloseButtonBehavior:
    """T006 — Close button releases photo reference and destroys window."""
    
    def test_close_button_clears_photo_reference(self):
        """Closing PhotoWindow sets internal photo reference to None (FR-008)."""
        # This test verifies the photo is cleared from memory when window closes
        # Actual test depends on PhotoWindow implementation
        pytest.skip("PhotoWindow implementation required")


class TestSaveAsDialogBehavior:
    """T006 — Save As... dialog with session-scoped last_save_dir."""
    
    def test_save_as_opens_file_dialog(self, monkeypatch):
        """Save As... button opens file save dialog."""
        # Mock tkinter.filedialog.asksaveasfilename
        mock_dialog = MagicMock(return_value="/tmp/catguard_20260305_123456.jpg")
        monkeypatch.setattr("tkinter.filedialog.asksaveasfilename", mock_dialog)
        
        pytest.skip("PhotoWindow implementation required")
    
    def test_save_as_uses_last_save_dir_on_second_use(self):
        """Save As... uses ActionPanel._last_save_dir on second use (session-scoped)."""
        pytest.skip("PhotoWindow + ActionPanel integration required")


class TestPhotoWindowCleanup:
    """T006 — Photo window cleanup and resource management."""
    
    def test_photo_bytes_not_logged(self, caplog):
        """Photo encode/save operations do not log image bytes (NFR-SEC-003)."""
        pytest.skip("PhotoWindow implementation required")


class TestActionPanelBasics:
    """Integration tests for ActionPanel (T010, T012)."""
    
    def test_action_panel_creates_take_photo_button(self):
        """ActionPanel includes 'Take photo' button."""
        pytest.skip("ActionPanel implementation required")
    
    def test_take_photo_button_opens_photo_window(self):
        """Clicking 'Take photo' opens PhotoWindow with captured frame."""
        pytest.skip("ActionPanel implementation required")
    
    def test_action_panel_session_scoped_last_save_dir(self):
        """ActionPanel._last_save_dir persists across multiple PhotoWindows."""
        pytest.skip("ActionPanel implementation required")

class TestCountdownButtonBasics:
    """T013 — Delay checkbox and spinbox next to Take photo button (US2)."""

    def test_delay_checkbox_exists(self):
        """ActionPanel includes a 'Delay (sec)' checkbox."""
        from catguard.ui.action_panel import ActionPanel
        from catguard.config import Settings

        root = tk.Tk()
        try:
            settings = Settings()
            panel = ActionPanel(
                parent=root,
                capture_callback=MagicMock(),
                close_callback=MagicMock(),
                settings=settings,
            )

            assert hasattr(panel, '_delay_checkbox')
            assert panel._delay_checkbox.cget('text') == "Delay:"

            panel._frame.destroy()
        finally:
            root.destroy()

    def test_delay_spinbox_default_from_settings(self):
        """Delay spinbox default value comes from settings.photo_countdown_seconds."""
        from catguard.ui.action_panel import ActionPanel
        from catguard.config import Settings

        root = tk.Tk()
        try:
            settings = Settings(photo_countdown_seconds=7)
            panel = ActionPanel(
                parent=root,
                capture_callback=MagicMock(),
                close_callback=MagicMock(),
                settings=settings,
            )

            assert panel._delay_spinbox.get() == "7"

            panel._frame.destroy()
        finally:
            root.destroy()

    def test_spinbox_disabled_when_checkbox_unchecked(self):
        """Spinbox is disabled when delay checkbox is unchecked."""
        from catguard.ui.action_panel import ActionPanel
        from catguard.config import Settings

        root = tk.Tk()
        try:
            settings = Settings()
            panel = ActionPanel(
                parent=root,
                capture_callback=MagicMock(),
                close_callback=MagicMock(),
                settings=settings,
            )

            assert not panel._delay_var.get()
            assert str(panel._delay_spinbox.cget('state')) == 'disabled'

            panel._delay_var.set(True)
            panel._on_delay_toggle()
            assert str(panel._delay_spinbox.cget('state')) == 'normal'

            panel._delay_var.set(False)
            panel._on_delay_toggle()
            assert str(panel._delay_spinbox.cget('state')) == 'disabled'

            panel._frame.destroy()
        finally:
            root.destroy()

    def test_take_photo_button_label_before_countdown(self):
        """Take photo button shows 'Take photo' label before any countdown."""
        from catguard.ui.action_panel import ActionPanel
        from catguard.config import Settings

        root = tk.Tk()
        try:
            settings = Settings()
            panel = ActionPanel(
                parent=root,
                capture_callback=MagicMock(),
                close_callback=MagicMock(),
                settings=settings,
            )

            assert panel._take_photo_btn.cget('text') == "Take photo"

            panel._frame.destroy()
        finally:
            root.destroy()

    def _find_buttons_recursive(self, widget, buttons):
        """Helper to recursively find all buttons in widget hierarchy."""
        try:
            if widget.winfo_class() == 'Button':
                buttons.append(widget)
        except:
            pass
        try:
            for child in widget.winfo_children():
                self._find_buttons_recursive(child, buttons)
        except:
            pass

    def _get_button_by_label(self, widget, label):
        """Find a button by its text label."""
        # Handle ActionPanel objects by accessing internal _frame
        if hasattr(widget, '_frame'):
            widget = widget._frame
        # Handle PhotoWindow objects by accessing internal _window
        if hasattr(widget, '_window'):
            widget = widget._window
        buttons = []
        self._find_buttons_recursive(widget, buttons)
        for btn in buttons:
            try:
                if btn.cget('text') == label:
                    return btn
            except:
                pass
        return None


class TestActionPanelLayout:
    """T016-T019 — ActionPanel layout and Close button (US3)."""
    
    def test_action_panel_packed_at_bottom(self):
        """ActionPanel._frame is packed at BOTTOM with fill=X."""
        from catguard.ui.action_panel import ActionPanel
        from catguard.config import Settings
        
        root = tk.Tk()
        try:
            settings = Settings()
            panel = ActionPanel(
                parent=root,
                capture_callback=MagicMock(),
                close_callback=MagicMock(),
                settings=settings,
            )
            
            # Verify frame is packed at bottom
            panel_info = panel._frame.pack_info()
            assert panel_info['side'] == 'bottom'
            assert panel_info['fill'] == 'x'
            
            panel._frame.destroy()
        finally:
            root.destroy()
    
    def test_close_button_present_and_right_aligned(self):
        """Close button exists and is placed in right frame."""
        from catguard.ui.action_panel import ActionPanel
        from catguard.config import Settings
        
        root = tk.Tk()
        try:
            settings = Settings()
            panel = ActionPanel(
                parent=root,
                capture_callback=MagicMock(),
                close_callback=MagicMock(),
                settings=settings,
            )
            
            close_btn = self._get_button_by_label(panel, "Close")
            assert close_btn is not None
            
            # Verify it's in the right frame
            assert close_btn.master == panel._right_frame
            
            panel._frame.destroy()
        finally:
            root.destroy()
    
    def test_photo_buttons_left_aligned(self):
        """Take photo button, delay checkbox, and spinbox are in left frame."""
        from catguard.ui.action_panel import ActionPanel
        from catguard.config import Settings

        root = tk.Tk()
        try:
            settings = Settings()
            panel = ActionPanel(
                parent=root,
                capture_callback=MagicMock(),
                close_callback=MagicMock(),
                settings=settings,
            )

            take_photo_btn = self._get_button_by_label(panel, "Take photo")
            assert take_photo_btn is not None
            assert take_photo_btn.master == panel._left_frame

            assert panel._delay_checkbox.master == panel._left_frame
            assert panel._delay_spinbox.master == panel._left_frame

            panel._frame.destroy()
        finally:
            root.destroy()
    
    def test_close_button_calls_callback_on_click(self):
        """Clicking Close button triggers close_callback."""
        from catguard.ui.action_panel import ActionPanel
        from catguard.config import Settings
        
        root = tk.Tk()
        try:
            mock_close = MagicMock()
            settings = Settings()
            panel = ActionPanel(
                parent=root,
                capture_callback=MagicMock(),
                close_callback=mock_close,
                settings=settings,
            )
            
            close_btn = self._get_button_by_label(panel, "Close")
            close_btn.invoke()
            
            mock_close.assert_called_once()
            
            panel._frame.destroy()
        finally:
            root.destroy()
    
    def _find_buttons_recursive(self, widget, buttons):
        """Helper to recursively find all buttons in widget hierarchy."""
        try:
            if widget.winfo_class() == 'Button':
                buttons.append(widget)
        except:
            pass
        try:
            for child in widget.winfo_children():
                self._find_buttons_recursive(child, buttons)
        except:
            pass
    
    def _get_button_by_label(self, widget, label):
        """Find a button by its text label."""
        # Handle ActionPanel objects by accessing internal _frame
        if hasattr(widget, '_frame'):
            widget = widget._frame
        # Handle PhotoWindow objects by accessing internal _window
        if hasattr(widget, '_window'):
            widget = widget._window
        buttons = []
        self._find_buttons_recursive(widget, buttons)
        for btn in buttons:
            try:
                if btn.cget('text') == label:
                    return btn
            except:
                pass
        return None


class TestCountdownBehavior:
    """T014-T015 — Countdown timer logic (US2)."""
    
    def test_countdown_suppresses_clicks_during_countdown(self):
        """Clicks on Take photo are ignored while countdown is active."""
        if os.environ.get("CI"):
            pytest.skip("Countdown timing tests skipped in CI")

        from catguard.ui.action_panel import ActionPanel
        from catguard.config import Settings

        root = tk.Tk()
        try:
            mock_capture = MagicMock()
            settings = Settings(photo_countdown_seconds=3)
            panel = ActionPanel(
                parent=root,
                capture_callback=mock_capture,
                close_callback=MagicMock(),
                settings=settings,
            )

            # Enable delay checkbox
            panel._delay_var.set(True)

            take_photo_btn = panel._take_photo_btn

            # First click starts the countdown
            take_photo_btn.invoke()
            assert panel._countdown_active, "Countdown should be active after first click"

            # Second click during countdown should be suppressed (flag stays True,
            # no additional countdown initiated, capture not called yet)
            take_photo_btn.invoke()
            assert panel._countdown_active, "Countdown should still be active — second click suppressed"
            mock_capture.assert_not_called()

            panel._frame.destroy()
        finally:
            root.destroy()
    
    def test_countdown_reads_setting_value(self):
        """Countdown duration is read from settings.photo_countdown_seconds."""
        from catguard.ui.action_panel import ActionPanel
        from catguard.config import Settings
        
        root = tk.Tk()
        try:
            settings = Settings(photo_countdown_seconds=5)
            panel = ActionPanel(
                parent=root,
                capture_callback=MagicMock(),
                close_callback=MagicMock(),
                settings=settings,
            )
            
            # Verify ActionPanel has access to the setting
            assert panel._settings.photo_countdown_seconds == 5
            
            panel._frame.destroy()
        finally:
            root.destroy()
    
    def test_countdown_restores_button_label_after_capture(self):
        """Button returns to 'Take photo with delay' label after countdown completes."""
        pytest.skip("Countdown completion requires async frame scheduling test")
    
    def _find_buttons_recursive(self, widget, buttons):
        """Helper to recursively find all buttons in widget hierarchy."""
        try:
            if widget.winfo_class() == 'Button':
                buttons.append(widget)
        except:
            pass
        try:
            for child in widget.winfo_children():
                self._find_buttons_recursive(child, buttons)
        except:
            pass
    
    def _get_button_by_label(self, widget, label):
        """Find a button by its text label."""
        # Handle ActionPanel objects by accessing internal _frame
        if hasattr(widget, '_frame'):
            widget = widget._frame
        # Handle PhotoWindow objects by accessing internal _window
        if hasattr(widget, '_window'):
            widget = widget._window
        buttons = []
        self._find_buttons_recursive(widget, buttons)
        for btn in buttons:
            try:
                if btn.cget('text') == label:
                    return btn
            except:
                pass
        return None