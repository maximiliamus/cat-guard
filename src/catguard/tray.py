"""System tray icon and menu for CatGuard.

Responsibilities:
- build_tray_icon(): create a pystray.Icon with Settings… and Exit menu items
- _on_settings(): dispatch to tkinter main thread via root.after(0, ...)
- _on_exit(): stop tray, set stop_event, destroy root
- Platform branching: macOS run_detached, Wayland AppIndicator backend
"""
from __future__ import annotations

import logging
import os
import platform
import threading
from pathlib import Path
from typing import Callable

import pystray
from PIL import Image

from catguard.config import Settings

logger = logging.getLogger(__name__)

_ICON_PATH = Path(__file__).parent.parent.parent / "assets" / "icon.png"
_ICON_ICO_PATH = Path(__file__).parent.parent.parent / "assets" / "icon.ico"


def _ensure_main_window(root, detection_loop) -> None:
    """Create MainWindow if absent, register frame callback, then show/focus."""
    from catguard.ui.main_window import MainWindow

    win = getattr(root, "_main_window", None)
    if win is None:
        win = MainWindow(root)
        # Clear the callback when the user closes the window
        win._on_close_extra = lambda: detection_loop.set_frame_callback(None)

    # Register frame delivery callback so the window receives live frames.
    # The lambda posts to the main thread via root.after for thread safety.
    def _on_frame(frame_bgr, detections) -> None:
        try:
            root.after(0, lambda f=frame_bgr, d=detections: win.update_frame(f, d))
        except Exception:
            pass  # root may be destroyed during shutdown

    detection_loop.set_frame_callback(_on_frame)
    logger.info("Main window frame callback registered.")
    win.show_or_focus()


def _on_open_clicked_factory(root, detection_loop):
    """Return a pystray menu handler bound to *root* and *detection_loop*."""
    def handler(icon, item) -> None:  # pragma: no cover — runs in pystray thread
        logger.info("Open clicked — main window requested.")
        root.after(0, lambda: _ensure_main_window(root, detection_loop))
    return handler

def build_tray_icon(
    root,
    stop_event: threading.Event,
    settings: Settings,
    on_settings_saved: Callable,
    detection_loop,
) -> pystray.Icon:
    """Build and return a pystray.Icon configured with Settings… and Exit items.

    Does NOT call .run() — that is the caller's responsibility (so main.py can
    choose between run_detached() on macOS and a daemon thread on other platforms).
    """
    # Wayland requires the AppIndicator backend
    if platform.system() == "Linux" and os.environ.get("XDG_SESSION_TYPE") == "wayland":
        os.environ.setdefault("PYSTRAY_BACKEND", "appindicator")
        logger.info("Wayland detected — using AppIndicator pystray backend.")

    image = _load_icon()

    def on_settings_clicked(icon, item):
        _on_settings(root, settings, on_settings_saved)

    def on_exit_clicked(icon, item):
        _on_exit(icon, root, stop_event)

    on_open_clicked = _on_open_clicked_factory(root, detection_loop)

    menu = pystray.Menu(
        pystray.MenuItem("Settings\u2026", on_settings_clicked),
        pystray.MenuItem("Open", on_open_clicked),
        pystray.MenuItem("Exit", on_exit_clicked),
    )

    icon = pystray.Icon("CatGuard", image, "CatGuard", menu)
    logger.info("Tray icon built.")
    return icon


def notify_error(icon: pystray.Icon, message: str) -> None:
    """Show a brief non-blocking tray balloon notification for save failures.

    Swallows all exceptions so detection and audio are never interrupted.
    """
    try:
        icon.notify(message, "CatGuard")
    except Exception:
        logger.warning("Could not show tray notification: %s", message)


def _on_settings(root, settings: Settings, on_settings_saved: Callable) -> None:
    """Open the Settings window on the tkinter main thread."""
    from catguard.ui.settings_window import open_settings_window

    root.after(0, lambda: open_settings_window(root, settings, on_settings_saved))


def _on_exit(icon: pystray.Icon, root, stop_event: threading.Event) -> None:
    """Stop the tray icon, signal the stop event, and destroy the tkinter root."""
    logger.info("Exit requested via tray menu.")
    stop_event.set()
    icon.stop()
    try:
        root.after(0, root.destroy)
    except Exception:
        pass


def _load_icon() -> Image.Image:
    """Load the tray icon image; fall back to a plain coloured square.

    On Windows, pystray's Win32 backend saves the PIL image to a temporary
    .ico file and calls LoadImage.  If the PIL image has no ICO format
    metadata (e.g. came from Image.new or a PNG), Pillow's ICO encoder can
    produce a file that LoadImage rejects with WinError 0.  The fix is to
    pre-cache a proper .ico on disk and return it opened via Image.open so
    that Pillow carries full ICO format info for the subsequent save.
    """
    # Build source image from PNG asset or placeholder
    if _ICON_PATH.exists():
        img = Image.open(_ICON_PATH).convert("RGBA")
    else:
        logger.warning("Icon file not found at %s — using placeholder.", _ICON_PATH)
        img = Image.new("RGBA", (48, 48), (100, 149, 237, 255))

    if platform.system() != "Windows":
        return img

    # Windows: ensure a valid .ico file exists, then load from it so pystray
    # gets a PIL image whose format is already ICO.
    try:
        if not _ICON_ICO_PATH.exists():
            _ICON_ICO_PATH.parent.mkdir(parents=True, exist_ok=True)
            img.save(
                str(_ICON_ICO_PATH),
                format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48)],
            )
            logger.debug("Cached tray icon at %s.", _ICON_ICO_PATH)
        return Image.open(str(_ICON_ICO_PATH))
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "Could not create/load icon.ico (%s) — falling back to PNG image.", exc
        )
        return img
