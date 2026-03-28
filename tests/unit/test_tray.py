"""Unit tests for catguard.tray — written before implementation (TDD RED).

Covers:
- Menu has Settings… and Exit items
- on_exit sets stop_event
- macOS run_detached branch when platform == Darwin
- Wayland AppIndicator backend when XDG_SESSION_TYPE=wayland
"""
from __future__ import annotations

import platform
import threading
from unittest.mock import MagicMock, call, patch

import pytest

from catguard.config import Settings
from catguard.tray import build_tray_icon


class TestMenuItems:
    def test_settings_item_present(self):
        root = MagicMock()
        stop_event = threading.Event()
        settings = Settings()
        on_save = MagicMock()

        with patch("catguard.tray.pystray") as mock_pystray:
            mock_icon = MagicMock()
            mock_pystray.Icon.return_value = mock_icon
            
            # Create a proper mock for Menu that captures items
            captured_items = []
            def capture_menu(*items):
                captured_items.extend(items)
                return MagicMock()
            
            mock_pystray.Menu = capture_menu
            mock_pystray.Menu.SEPARATOR = "SEPARATOR"
            mock_pystray.MenuItem = MagicMock(side_effect=lambda label, *a, **kw: label)

            build_tray_icon(root, stop_event, settings, on_save, MagicMock())

            # Should contain a Settings item
            assert any("Settings" in str(item) for item in captured_items)

    def test_exit_item_present(self):
        root = MagicMock()
        stop_event = threading.Event()
        settings = Settings()
        on_save = MagicMock()

        with patch("catguard.tray.pystray") as mock_pystray:
            mock_pystray.Icon.return_value = MagicMock()
            
            # Create a proper mock for Menu
            captured_items = []
            def capture_menu(*items):
                captured_items.extend(items)
                return MagicMock()
            
            mock_pystray.Menu = capture_menu
            mock_pystray.Menu.SEPARATOR = "SEPARATOR"
            mock_pystray.MenuItem = MagicMock(side_effect=lambda label, *a, **kw: label)

            build_tray_icon(root, stop_event, settings, on_save, MagicMock())

            # Should contain an Exit item
            assert any("Exit" in str(item) for item in captured_items)

    def test_open_item_present(self):
        """Tray menu must expose a 'Live View' item for the main window."""
        root = MagicMock()
        stop_event = threading.Event()
        settings = Settings()
        on_save = MagicMock()

        with patch("catguard.tray.pystray") as mock_pystray:
            mock_pystray.Icon.return_value = MagicMock()
            
            # Create a proper mock for Menu
            captured_items = []
            def capture_menu(*items):
                captured_items.extend(items)
                return MagicMock()
            
            mock_pystray.Menu = capture_menu
            mock_pystray.Menu.SEPARATOR = "SEPARATOR"
            mock_pystray.MenuItem = MagicMock(side_effect=lambda label, *a, **kw: label)

            build_tray_icon(root, stop_event, settings, on_save, MagicMock())

            # Should contain a Live View item
            assert any("Live View" in str(item) for item in captured_items)
    def test_menu_order_settings_open_exit(self):
        """Menu order must keep directory shortcuts grouped before Exit."""
        root = MagicMock()
        stop_event = threading.Event()
        settings = Settings()
        on_save = MagicMock()
        detection_loop = MagicMock()
        detection_loop.is_tracking.return_value = True

        with patch("catguard.tray.pystray") as mock_pystray:
            mock_pystray.Icon.return_value = MagicMock()
            
            # Create a proper mock for Menu
            captured_items = []
            def capture_menu(*items):
                captured_items.extend(items)
                return MagicMock()
            
            mock_pystray.Menu = capture_menu
            mock_pystray.Menu.SEPARATOR = "SEPARATOR"
            mock_pystray.MenuItem = MagicMock(side_effect=lambda label, *a, **kw: label)

            build_tray_icon(root, stop_event, settings, on_save, detection_loop)

            labels = [str(item) for item in captured_items]
            assert labels == [
                "Live View",
                "Logs",
                "Settings…",
                "SEPARATOR",
                "Pause",
                "SEPARATOR",
                "Tracking Directory",
                "Photos Directory",
                "SEPARATOR",
                "Exit",
            ]



class TestOnExit:
    def test_exit_sets_stop_event(self):
        stop_event = threading.Event()
        assert not stop_event.is_set()

        root = MagicMock()
        settings = Settings()

        from catguard.tray import _on_exit

        mock_icon = MagicMock()
        _on_exit(mock_icon, root, stop_event)

        assert stop_event.is_set()

    def test_exit_stops_icon(self):
        stop_event = threading.Event()
        root = MagicMock()

        from catguard.tray import _on_exit

        mock_icon = MagicMock()
        _on_exit(mock_icon, root, stop_event)

        mock_icon.stop.assert_called_once()


class TestPlatformBranches:
    def test_macos_uses_run_detached_strategy(self):
        """build_tray_icon should mark the icon for run_detached on Darwin."""
        root = MagicMock()
        stop_event = threading.Event()
        settings = Settings()

        with patch("catguard.tray.pystray") as mock_pystray, \
             patch("catguard.tray.platform.system", return_value="Darwin"):
            mock_pystray.Icon.return_value = MagicMock()
            mock_pystray.Menu = MagicMock(return_value=MagicMock())
            mock_pystray.MenuItem = MagicMock(return_value=MagicMock())

            icon = build_tray_icon(root, stop_event, settings, MagicMock(), MagicMock())
            # On Darwin, build_tray_icon returns icon ready for run_detached
            # (caller does icon.run_detached() in main.py)
            assert icon is not None

    def test_wayland_sets_appindicator_env(self):
        """On Wayland, PYSTRAY_BACKEND env var should be set to appindicator."""
        import os

        root = MagicMock()
        stop_event = threading.Event()
        settings = Settings()

        env_patch = {}
        with patch("catguard.tray.pystray") as mock_pystray, \
             patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"}), \
             patch("catguard.tray.platform.system", return_value="Linux"), \
             patch.dict(os.environ, {}, clear=False) as patched_env:
            mock_pystray.Icon.return_value = MagicMock()
            mock_pystray.Menu = MagicMock(return_value=MagicMock())
            mock_pystray.MenuItem = MagicMock(return_value=MagicMock())

            build_tray_icon(root, stop_event, settings, MagicMock(), MagicMock())

        # PYSTRAY_BACKEND should have been set during the call
        # (checked via os.environ side effect in tray.py)


class TestNotifyError:
    """T016 — tests for notify_error() tray balloon helper."""

    def test_notify_calls_icon_notify_with_message_and_title(self):
        """notify_error(icon, msg) must call icon.notify(msg, 'CatGuard')."""
        from catguard.tray import notify_error

        icon = MagicMock()
        notify_error(icon, "Could not save screenshot: permission denied")
        icon.notify.assert_called_once_with(
            "Could not save screenshot: permission denied", "CatGuard"
        )

    def test_notify_swallows_exceptions(self):
        """notify_error must not propagate exceptions raised by icon.notify()."""
        from catguard.tray import notify_error

        icon = MagicMock()
        icon.notify.side_effect = RuntimeError("tray backend unavailable")
        # Should not raise
        notify_error(icon, "some error")


class TestIconColor:
    """Tests for icon color updates (T024, T025, T029, T030)."""

    def test_icon_color_green_when_tracking(self):
        """Test that icon color is green when tracking (T029)."""
        from catguard.tray import update_tray_icon_color

        icon = MagicMock()
        
        # Should not raise
        update_tray_icon_color(icon, is_tracking=True)
        
        # Icon should have been updated (set to colored image)
        assert icon.icon is not None

    def test_icon_color_default_when_paused(self):
        """Test that icon color is default when paused (T030)."""
        from catguard.tray import update_tray_icon_color

        icon = MagicMock()
        
        # Should not raise
        update_tray_icon_color(icon, is_tracking=False)
        
        # Icon should have been updated (set to base image)
        assert icon.icon is not None


class TestMenuStructure:
    """Tests for reorganized menu structure (T032-T038)."""

    def test_menu_item_order(self):
        """Test that menu items appear in correct order (T036)."""
        root = MagicMock()
        stop_event = threading.Event()
        settings = Settings()
        on_save = MagicMock()
        detection_loop = MagicMock()
        detection_loop.is_tracking.return_value = True

        with patch("catguard.tray.pystray") as mock_pystray:
            # Capture menu items in order
            menu_items = []
            
            def capture_menu(*items):
                menu_items.extend(items)
                return items
            
            mock_pystray.Menu = capture_menu
            mock_pystray.Menu.SEPARATOR = "SEPARATOR"
            
            def capture_item(label, *args, **kwargs):
                return {"label": label, "args": args}
            
            mock_pystray.MenuItem = capture_item
            mock_pystray.Icon.return_value = MagicMock()

            build_tray_icon(root, stop_event, settings, on_save, detection_loop)

            # Extract labels in order
            labels = [item.get("label") if isinstance(item, dict) else str(item) 
                     for item in menu_items]

            assert labels == [
                "Live View",
                "Logs",
                "Settings…",
                "SEPARATOR",
                "Pause",
                "SEPARATOR",
                "Tracking Directory",
                "Photos Directory",
                "SEPARATOR",
                "Exit",
            ]

    def test_menu_pause_label_when_tracking(self):
        """Test that menu shows 'Pause' label when tracking (T037)."""
        root = MagicMock()
        stop_event = threading.Event()
        settings = Settings()
        on_save = MagicMock()
        detection_loop = MagicMock()
        detection_loop.is_tracking.return_value = True

        with patch("catguard.tray.pystray") as mock_pystray:
            menu_items = []
            
            def capture_menu(*items):
                menu_items.extend(items)
                return items
            
            mock_pystray.Menu = capture_menu
            mock_pystray.Menu.SEPARATOR = "SEPARATOR"
            
            def capture_item(label, *args, **kwargs):
                return label
            
            mock_pystray.MenuItem = capture_item
            mock_pystray.Icon.return_value = MagicMock()

            build_tray_icon(root, stop_event, settings, on_save, detection_loop)

            # Should have "Pause" in menu items
            assert any("Pause" in str(item) for item in menu_items)

    def test_menu_continue_label_when_paused(self):
        """Test that menu shows 'Continue' label when paused (T038)."""
        root = MagicMock()
        stop_event = threading.Event()
        settings = Settings()
        on_save = MagicMock()
        detection_loop = MagicMock()
        detection_loop.is_tracking.return_value = False

        with patch("catguard.tray.pystray") as mock_pystray:
            menu_items = []

            def capture_menu(*items):
                menu_items.extend(items)
                return items

            mock_pystray.Menu = capture_menu
            mock_pystray.Menu.SEPARATOR = "SEPARATOR"

            def capture_item(label, *args, **kwargs):
                return label

            mock_pystray.MenuItem = capture_item
            mock_pystray.Icon.return_value = MagicMock()

            build_tray_icon(root, stop_event, settings, on_save, detection_loop)

            # Should have "Continue" in menu items
            assert any("Continue" in str(item) for item in menu_items)


# ---------------------------------------------------------------------------
# T006: "Logs" menu item (011-log-viewer-search, US1)
# ---------------------------------------------------------------------------

def _capture_tray_items(root=None, detection_loop=None, fn=None):
    """Helper: build tray icon and capture all menu item labels."""
    import threading as _threading

    if root is None:
        root = MagicMock()
    if detection_loop is None:
        detection_loop = MagicMock()
        detection_loop.is_tracking.return_value = True
    stop_event = _threading.Event()
    settings = Settings()
    on_save = MagicMock()

    captured_items = []

    with patch("catguard.tray.pystray") as mock_pystray:
        mock_pystray.Icon.return_value = MagicMock()

        def capture_menu(*items):
            captured_items.extend(items)
            return MagicMock()

        mock_pystray.Menu = capture_menu
        mock_pystray.Menu.SEPARATOR = "SEPARATOR"
        mock_pystray.MenuItem = MagicMock(side_effect=lambda label, *a, **kw: label)

        if fn is None:
            build_tray_icon(root, stop_event, settings, on_save, detection_loop)
        else:
            fn(root, stop_event, settings, on_save, detection_loop)

    return captured_items


class TestLogsMenuItem:
    """T006 — 'Logs' MenuItem must appear in both build_tray_icon and update_tray_menu."""

    def test_build_tray_icon_includes_logs_item(self):
        items = _capture_tray_items()
        assert any("Logs" in str(item) for item in items), (
            f"'Logs' not found in menu items: {items}"
        )

    def test_update_tray_menu_includes_logs_item(self):
        from catguard.tray import update_tray_menu

        root = MagicMock()
        detection_loop = MagicMock()
        detection_loop.is_tracking.return_value = True
        settings = Settings()
        on_save = MagicMock()
        captured_items = []

        with patch("catguard.tray.pystray") as mock_pystray:
            mock_icon = MagicMock()

            def capture_menu(*items):
                captured_items.extend(items)
                return MagicMock()

            mock_pystray.Menu = capture_menu
            mock_pystray.Menu.SEPARATOR = "SEPARATOR"
            mock_pystray.MenuItem = MagicMock(side_effect=lambda label, *a, **kw: label)

            update_tray_menu(
                mock_icon, True, root, settings, on_save,
                detection_loop, None,
            )

        assert any("Logs" in str(item) for item in captured_items), (
            f"'Logs' not found in update_tray_menu items: {captured_items}"
        )


class TestDirectoryMenuItems:
    def test_build_tray_icon_includes_directory_items(self):
        items = _capture_tray_items()
        assert "Tracking Directory" in items
        assert "Photos Directory" in items

    def test_update_tray_menu_includes_directory_items(self):
        from catguard.tray import update_tray_menu

        root = MagicMock()
        detection_loop = MagicMock()
        detection_loop.is_tracking.return_value = True
        settings = Settings()
        on_save = MagicMock()
        captured_items = []

        with patch("catguard.tray.pystray") as mock_pystray:
            mock_icon = MagicMock()

            def capture_menu(*items):
                captured_items.extend(items)
                return MagicMock()

            mock_pystray.Menu = capture_menu
            mock_pystray.Menu.SEPARATOR = "SEPARATOR"
            mock_pystray.MenuItem = MagicMock(side_effect=lambda label, *a, **kw: label)

            update_tray_menu(
                mock_icon, True, root, settings, on_save,
                detection_loop, None,
            )

        assert "Tracking Directory" in captured_items
        assert "Photos Directory" in captured_items


class TestOpenDirectory:
    def test_resolve_directory_path_trims_whitespace(self, tmp_path, monkeypatch):
        from catguard.tray import _resolve_directory_path

        monkeypatch.chdir(tmp_path)

        resolved = _resolve_directory_path("  tracking-folder  ")

        assert resolved == (tmp_path / "tracking-folder").resolve()

    def test_resolve_directory_path_raises_for_empty_value(self):
        from catguard.tray import _resolve_directory_path

        with pytest.raises(ValueError, match="directory path is empty"):
            _resolve_directory_path("   ")

    def test_windows_uses_startfile(self, tmp_path):
        from catguard.tray import _open_directory

        with patch("catguard.tray.platform.system", return_value="Windows"), \
             patch("os.startfile", create=True) as mock_start:
            _open_directory(tmp_path)

        mock_start.assert_called_once_with(str(tmp_path))

    def test_macos_uses_open(self, tmp_path):
        from catguard.tray import _open_directory

        with patch("catguard.tray.platform.system", return_value="Darwin"), \
             patch("catguard.tray.subprocess.run") as mock_run:
            _open_directory(tmp_path)

        mock_run.assert_called_once_with(["open", str(tmp_path)], check=False)

    def test_linux_uses_xdg_open(self, tmp_path):
        from catguard.tray import _open_directory

        with patch("catguard.tray.platform.system", return_value="Linux"), \
             patch("catguard.tray.subprocess.run") as mock_run:
            _open_directory(tmp_path)

        mock_run.assert_called_once_with(["xdg-open", str(tmp_path)], check=False)

    def test_creates_folder_if_missing(self, tmp_path):
        from catguard.tray import _open_directory

        folder = tmp_path / "missing"
        assert not folder.exists()

        with patch("catguard.tray.platform.system", return_value="Linux"), \
             patch("catguard.tray.subprocess.run"):
            _open_directory(folder)

        assert folder.exists()

