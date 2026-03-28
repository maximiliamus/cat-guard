"""Integration tests for tray directory shortcut callbacks and menu rebuilds."""
from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from catguard.config import Settings
from catguard.tray import build_tray_icon


EXPECTED_ACTIVE_LABELS = [
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

EXPECTED_PAUSED_LABELS = [
    "Live View",
    "Logs",
    "Settings…",
    "SEPARATOR",
    "Continue",
    "SEPARATOR",
    "Tracking Directory",
    "Photos Directory",
    "SEPARATOR",
    "Exit",
]


class _FakeDetectionLoop:
    def __init__(self, tracking: bool = True) -> None:
        self._tracking = tracking

    def is_tracking(self) -> bool:
        return self._tracking

    def pause(self) -> bool:
        self._tracking = False
        return True

    def resume(self) -> bool:
        self._tracking = True
        return True


def _configure_pystray_capture(mock_pystray, captured_menus: list[list[object]], icon):
    def capture_item(label, callback, *args, **kwargs):
        return {"label": label, "callback": callback}

    def capture_menu(*items):
        captured_menus.append(list(items))
        return list(items)

    mock_pystray.Icon.return_value = icon
    mock_pystray.MenuItem = capture_item
    mock_pystray.Menu = capture_menu
    mock_pystray.Menu.SEPARATOR = "SEPARATOR"


def _build_tray_with_capture(settings: Settings, detection_loop: _FakeDetectionLoop):
    root = MagicMock()
    stop_event = threading.Event()
    on_save = MagicMock()
    captured_menus: list[list[object]] = []

    with patch("catguard.tray.pystray") as mock_pystray:
        icon = MagicMock()
        _configure_pystray_capture(mock_pystray, captured_menus, icon)

        build_tray_icon(root, stop_event, settings, on_save, detection_loop)

    return icon, captured_menus


def _labels(menu_items: list[object]) -> list[str]:
    result: list[str] = []
    for item in menu_items:
        if isinstance(item, dict):
            result.append(item["label"])
        else:
            result.append(str(item))
    return result


def _callback(menu_items: list[object], label: str):
    for item in menu_items:
        if isinstance(item, dict) and item["label"] == label:
            return item["callback"]
    raise AssertionError(f"Callback for {label!r} not found in menu: {_labels(menu_items)}")


class TestTrayDirectoryShortcutsIntegration:
    def test_tracking_directory_callback_creates_and_opens_configured_directory(self, tmp_path):
        tracking_dir = tmp_path / "tracking-output"
        settings = Settings(tracking_directory=str(tracking_dir))
        loop = _FakeDetectionLoop(tracking=True)

        icon, captured_menus = _build_tray_with_capture(settings, loop)
        callback = _callback(captured_menus[0], "Tracking Directory")

        with patch("catguard.tray.platform.system", return_value="Linux"), \
             patch("catguard.tray.subprocess.run") as mock_run:
            callback(icon, None)

        assert tracking_dir.exists()
        mock_run.assert_called_once_with(["xdg-open", str(tracking_dir)], check=False)

    def test_photos_directory_callback_creates_and_opens_configured_directory(self, tmp_path):
        photos_dir = tmp_path / "photos-output"
        settings = Settings(photos_directory=str(photos_dir))
        loop = _FakeDetectionLoop(tracking=True)

        icon, captured_menus = _build_tray_with_capture(settings, loop)
        callback = _callback(captured_menus[0], "Photos Directory")

        with patch("catguard.tray.platform.system", return_value="Linux"), \
             patch("catguard.tray.subprocess.run") as mock_run:
            callback(icon, None)

        assert photos_dir.exists()
        mock_run.assert_called_once_with(["xdg-open", str(photos_dir)], check=False)

    def test_pause_resume_menu_rebuild_preserves_directory_items_and_exit_last(self, tmp_path):
        settings = Settings(
            tracking_directory=str(tmp_path / "tracking"),
            photos_directory=str(tmp_path / "photos"),
        )
        loop = _FakeDetectionLoop(tracking=True)
        root = MagicMock()
        stop_event = threading.Event()
        on_save = MagicMock()
        captured_menus: list[list[object]] = []

        with patch("catguard.tray.pystray") as mock_pystray:
            icon = MagicMock()
            _configure_pystray_capture(mock_pystray, captured_menus, icon)

            build_tray_icon(root, stop_event, settings, on_save, loop)
            assert _labels(captured_menus[0]) == EXPECTED_ACTIVE_LABELS

            pause_callback = _callback(captured_menus[0], "Pause")
            with patch("catguard.tray.update_tray_icon_color"):
                pause_callback(icon, None)

            assert _labels(captured_menus[-1]) == EXPECTED_PAUSED_LABELS
            assert _labels(icon.menu)[-1] == "Exit"

            continue_callback = _callback(icon.menu, "Continue")
            with patch("catguard.tray.update_tray_icon_color"):
                continue_callback(icon, None)

            assert _labels(captured_menus[-1]) == EXPECTED_ACTIVE_LABELS
            assert _labels(icon.menu)[-1] == "Exit"
