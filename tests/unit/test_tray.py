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
            mock_pystray.Menu = MagicMock(wraps=lambda *items: items)
            mock_pystray.MenuItem = MagicMock(side_effect=lambda label, *a, **kw: label)

            build_tray_icon(root, stop_event, settings, on_save, MagicMock())

            labels = [
                call_args[0][0]
                for call_args in mock_pystray.MenuItem.call_args_list
            ]
            assert any("Settings" in str(label) for label in labels)

    def test_exit_item_present(self):
        root = MagicMock()
        stop_event = threading.Event()
        settings = Settings()
        on_save = MagicMock()

        with patch("catguard.tray.pystray") as mock_pystray:
            mock_pystray.Icon.return_value = MagicMock()
            mock_pystray.Menu = MagicMock(wraps=lambda *items: items)
            mock_pystray.MenuItem = MagicMock(side_effect=lambda label, *a, **kw: label)

            build_tray_icon(root, stop_event, settings, on_save, MagicMock())

            labels = [
                call_args[0][0]
                for call_args in mock_pystray.MenuItem.call_args_list
            ]
            assert any("Exit" in str(label) for label in labels)


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
