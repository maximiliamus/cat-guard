"""Unit tests for catguard.autostart — written before implementation (TDD RED).

Covers enable/disable/is_enabled for each platform via mocked filesystem and
platform-specific APIs (win32com, plistlib, XDG .desktop file).
"""
from __future__ import annotations

import platform
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest


class TestWindowsAutostart:
    def _patch_platform(self, plat="Windows"):
        return patch("catguard.autostart.platform.system", return_value=plat)

    def test_enable_creates_lnk_file(self, tmp_path):
        lnk_path = tmp_path / "CatGuard.lnk"

        with self._patch_platform("Windows"), \
             patch("catguard.autostart._windows_startup_path", return_value=lnk_path), \
             patch("catguard.autostart._create_windows_shortcut") as mock_create:
            from catguard.autostart import enable_autostart
            enable_autostart()
            mock_create.assert_called_once_with(lnk_path)

    def test_disable_removes_lnk_file(self, tmp_path):
        lnk_path = tmp_path / "CatGuard.lnk"
        lnk_path.write_text("stub")

        with self._patch_platform("Windows"), \
             patch("catguard.autostart._windows_startup_path", return_value=lnk_path):
            from catguard.autostart import disable_autostart
            disable_autostart()
            assert not lnk_path.exists()

    def test_is_enabled_true_when_lnk_exists(self, tmp_path):
        lnk_path = tmp_path / "CatGuard.lnk"
        lnk_path.write_text("stub")

        with self._patch_platform("Windows"), \
             patch("catguard.autostart._windows_startup_path", return_value=lnk_path):
            from catguard.autostart import is_autostart_enabled
            assert is_autostart_enabled() is True

    def test_is_enabled_false_when_lnk_missing(self, tmp_path):
        lnk_path = tmp_path / "CatGuard.lnk"

        with self._patch_platform("Windows"), \
             patch("catguard.autostart._windows_startup_path", return_value=lnk_path):
            from catguard.autostart import is_autostart_enabled
            assert is_autostart_enabled() is False


class TestMacOSAutostart:
    def _patch_platform(self):
        return patch("catguard.autostart.platform.system", return_value="Darwin")

    def test_enable_writes_plist(self, tmp_path):
        plist_path = tmp_path / "com.catguard.app.plist"

        with self._patch_platform(), \
             patch("catguard.autostart._macos_plist_path", return_value=plist_path):
            from catguard.autostart import enable_autostart
            enable_autostart()
            assert plist_path.exists()
            content = plist_path.read_bytes()
            assert b"CatGuard" in content

    def test_disable_removes_plist(self, tmp_path):
        plist_path = tmp_path / "com.catguard.app.plist"
        plist_path.write_bytes(b"stub")

        with self._patch_platform(), \
             patch("catguard.autostart._macos_plist_path", return_value=plist_path):
            from catguard.autostart import disable_autostart
            disable_autostart()
            assert not plist_path.exists()

    def test_is_enabled_true_when_plist_exists(self, tmp_path):
        plist_path = tmp_path / "com.catguard.app.plist"
        plist_path.write_bytes(b"stub")

        with self._patch_platform(), \
             patch("catguard.autostart._macos_plist_path", return_value=plist_path):
            from catguard.autostart import is_autostart_enabled
            assert is_autostart_enabled() is True

    def test_is_enabled_false_when_plist_missing(self, tmp_path):
        plist_path = tmp_path / "com.catguard.app.plist"

        with self._patch_platform(), \
             patch("catguard.autostart._macos_plist_path", return_value=plist_path):
            from catguard.autostart import is_autostart_enabled
            assert is_autostart_enabled() is False


class TestLinuxAutostart:
    def _patch_platform(self):
        return patch("catguard.autostart.platform.system", return_value="Linux")

    def test_enable_writes_desktop_file(self, tmp_path):
        desktop_path = tmp_path / "catguard.desktop"

        with self._patch_platform(), \
             patch("catguard.autostart._linux_desktop_path", return_value=desktop_path):
            from catguard.autostart import enable_autostart
            enable_autostart()
            assert desktop_path.exists()
            content = desktop_path.read_text()
            assert "CatGuard" in content
            assert "[Desktop Entry]" in content

    def test_disable_removes_desktop_file(self, tmp_path):
        desktop_path = tmp_path / "catguard.desktop"
        desktop_path.write_text("[Desktop Entry]\n")

        with self._patch_platform(), \
             patch("catguard.autostart._linux_desktop_path", return_value=desktop_path):
            from catguard.autostart import disable_autostart
            disable_autostart()
            assert not desktop_path.exists()

    def test_is_enabled_true_when_desktop_exists(self, tmp_path):
        desktop_path = tmp_path / "catguard.desktop"
        desktop_path.write_text("[Desktop Entry]\n")

        with self._patch_platform(), \
             patch("catguard.autostart._linux_desktop_path", return_value=desktop_path):
            from catguard.autostart import is_autostart_enabled
            assert is_autostart_enabled() is True

    def test_is_enabled_false_when_desktop_missing(self, tmp_path):
        desktop_path = tmp_path / "catguard.desktop"

        with self._patch_platform(), \
             patch("catguard.autostart._linux_desktop_path", return_value=desktop_path):
            from catguard.autostart import is_autostart_enabled
            assert is_autostart_enabled() is False
