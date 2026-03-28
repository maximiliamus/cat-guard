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
import subprocess
import threading
from pathlib import Path
from typing import Callable

import pystray
from PIL import Image

from catguard.config import Settings

logger = logging.getLogger(__name__)

def _assets_root() -> Path:
    """Return the assets root for both dev and packaged (PyInstaller) environments."""
    import sys
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent.parent

_ICON_PATH = _assets_root() / "assets" / "icon.png"
_ICON_ICO_PATH = _assets_root() / "assets" / "icon.ico"

# Pause/Continue tracking state colors (T024)
TRACKING_ACTIVE_COLOR = (0, 255, 0)  # Bright green RGB
TRACKING_PAUSED_COLOR = None  # System default (no recolor)


def _resolve_directory_path(path: str | Path) -> Path:
    """Return a normalized absolute directory path from a configured value."""
    raw_path = str(path).strip()
    if not raw_path:
        raise ValueError("directory path is empty")

    directory = Path(raw_path).expanduser()
    if not directory.is_absolute():
        directory = directory.resolve()
    return directory


def _open_directory(path: str | Path) -> None:
    """Create *path* if needed and open it in the platform file manager."""
    directory = _resolve_directory_path(path)
    directory.mkdir(parents=True, exist_ok=True)

    system = platform.system()
    logger.info("Opening directory: %s (platform=%s)", directory, system)
    if system == "Windows":
        os.startfile(str(directory))  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.run(["open", str(directory)], check=False)
    else:
        subprocess.run(["xdg-open", str(directory)], check=False)


def _open_directory_handler(icon: pystray.Icon, path: str | Path, label: str) -> None:
    """Open a configured directory and surface failures as tray notifications."""
    try:
        _open_directory(path)
    except Exception as exc:
        logger.error("Failed to open %s: %s", label, exc)
        notify_error(icon, f"Failed to open {label}: {exc}")


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

    tracking = detection_loop.is_tracking()
    if not tracking:
        win.clear_frame()
    win.set_capture_enabled(tracking)

    win.show_or_focus()


def _on_live_view_clicked_factory(root, detection_loop):
    """Return a pystray menu handler bound to *root* and *detection_loop*."""
    def handler(icon, item) -> None:  # pragma: no cover — runs in pystray thread
        logger.info("Live View clicked — main window requested.")
        root.after(0, lambda: _ensure_main_window(root, detection_loop))
    return handler

def build_tray_icon(
    root,
    stop_event: threading.Event,
    settings: Settings,
    on_settings_saved: Callable,
    detection_loop,
    time_window_monitor=None,
) -> pystray.Icon:
    """Build and return a pystray.Icon configured with menu items including Pause/Continue.

    Does NOT call .run() — that is the caller's responsibility (so main.py can
    choose between run_detached() on macOS and a daemon thread on other platforms).
    """
    # Store stop_event on root for later access in callbacks
    root._stop_event = stop_event
    
    # Wayland requires the AppIndicator backend
    if platform.system() == "Linux" and os.environ.get("XDG_SESSION_TYPE") == "wayland":
        os.environ.setdefault("PYSTRAY_BACKEND", "appindicator")
        logger.info("Wayland detected — using AppIndicator pystray backend.")

    image = _load_icon()

    def on_settings_clicked(icon, item):
        _on_settings(root, settings, on_settings_saved)

    def on_exit_clicked(icon, item):
        _on_exit(icon, root, stop_event)

    def on_open_tracking_directory_clicked(icon, item):
        _open_directory_handler(icon, settings.tracking_directory, "tracking directory")

    def on_open_photos_directory_clicked(icon, item):
        _open_directory_handler(icon, settings.photos_directory, "photos directory")

    def on_pause_continue_clicked(icon, item):
        """Handle pause/continue menu item click."""
        is_tracking = detection_loop.is_tracking()
        if is_tracking:
            detection_loop.pause()
            update_tray_icon_color(icon, False)
            update_tray_menu(icon, False, root, settings, on_settings_saved, detection_loop, time_window_monitor)
            _notify_state(root, False)
        else:
            try:
                if time_window_monitor is not None:
                    time_window_monitor.notify_user_resume()
                detection_loop.resume()
                update_tray_icon_color(icon, True)
                update_tray_menu(icon, True, root, settings, on_settings_saved, detection_loop, time_window_monitor)
                _notify_state(root, True)
            except Exception as exc:
                logger.error("Failed to resume tracking: %s", exc)
                notify_error(icon, f"Failed to resume: {exc}")

    on_live_view_clicked = _on_live_view_clicked_factory(root, detection_loop)

    def on_logs_clicked(icon, item):
        from catguard.ui.log_viewer import open_log_viewer
        root.after(0, lambda: open_log_viewer(root, settings))

    # Initial pause label (will show "Pause" after app starts tracking)
    pause_label = "Pause" if detection_loop.is_tracking() else "Continue"

    # Reorganized menu with separators (T032, T033, T010)
    menu = pystray.Menu(
        pystray.MenuItem("Live View", on_live_view_clicked),
        pystray.MenuItem("Logs", on_logs_clicked),
        pystray.MenuItem("Settings\u2026", on_settings_clicked),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(pause_label, on_pause_continue_clicked),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Tracking Directory", on_open_tracking_directory_clicked),
        pystray.MenuItem("Photos Directory", on_open_photos_directory_clicked),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", on_exit_clicked),
    )

    icon = pystray.Icon("CatGuard", image, "CatGuard", menu)
    logger.info("Tray icon built with pause/continue control.")
    return icon


def update_tray_icon_color(icon: pystray.Icon, is_tracking: bool) -> None:
    """Update tray icon color based on tracking state.

    Args:
        icon: pystray Icon instance
        is_tracking: True for active (green), False for paused (default)

    Applies green color overlay if is_tracking, otherwise uses default image.
    """
    try:
        base_image = _load_icon()
        
        if is_tracking:
            # Apply green color overlay
            green_image = Image.new("RGBA", base_image.size, TRACKING_ACTIVE_COLOR + (255,))
            # Blend using the base image as a mask
            colored = Image.new("RGBA", base_image.size)
            colored.paste(green_image, (0, 0), base_image)
            icon.icon = colored
        else:
            # Use default color (no overlay)
            icon.icon = base_image
        
        logger.debug("Tray icon color updated: is_tracking=%s", is_tracking)
    except Exception as exc:
        logger.warning("Could not update tray icon color: %s", exc)


def update_tray_menu(icon: pystray.Icon, is_tracking: bool, root, settings,
                    on_settings_saved, detection_loop, time_window_monitor=None) -> None:
    """Rebuild tray menu with correct Pause/Continue label.

    Args:
        icon: pystray Icon instance
        is_tracking: True to show "Pause" label, False to show "Continue"
        root: tkinter root window
        settings: Settings instance
        on_settings_saved: Callback for settings changes
        detection_loop: DetectionLoop instance
    """
    try:
        def on_settings_clicked(icon, item):
            _on_settings(root, settings, on_settings_saved)

        def on_exit_clicked(icon, item):
            # Import stop_event from main thread context via root
            stop_event = getattr(root, "_stop_event", threading.Event())
            _on_exit(icon, root, stop_event)

        def on_open_tracking_directory_clicked(icon, item):
            _open_directory_handler(icon, settings.tracking_directory, "tracking directory")

        def on_open_photos_directory_clicked(icon, item):
            _open_directory_handler(icon, settings.photos_directory, "photos directory")

        def on_pause_continue_clicked(icon, item):
            """Handle pause/continue menu item click."""
            if is_tracking:
                detection_loop.pause()
                update_tray_icon_color(icon, False)
                update_tray_menu(icon, False, root, settings, on_settings_saved, detection_loop, time_window_monitor)
                _notify_state(root, False)
            else:
                try:
                    if time_window_monitor is not None:
                        time_window_monitor.notify_user_resume()
                    detection_loop.resume()
                    update_tray_icon_color(icon, True)
                    update_tray_menu(icon, True, root, settings, on_settings_saved, detection_loop, time_window_monitor)
                    _notify_state(root, True)
                except Exception as exc:
                    logger.error("Failed to resume tracking: %s", exc)
                    notify_error(icon, f"Failed to resume: {exc}")

        on_live_view_clicked = _on_live_view_clicked_factory(root, detection_loop)

        def on_logs_clicked(icon, item):
            from catguard.ui.log_viewer import open_log_viewer
            root.after(0, lambda: open_log_viewer(root, settings))

        # Menu item label based on state
        pause_label = "Pause" if is_tracking else "Continue"

        # Reorganized menu with separators (T032, T033)
        menu = pystray.Menu(
            pystray.MenuItem("Live View", on_live_view_clicked),
            pystray.MenuItem("Logs", on_logs_clicked),
            pystray.MenuItem("Settings\u2026", on_settings_clicked),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(pause_label, on_pause_continue_clicked),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Tracking Directory", on_open_tracking_directory_clicked),
            pystray.MenuItem("Photos Directory", on_open_photos_directory_clicked),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", on_exit_clicked),
        )

        icon.menu = menu
        logger.debug("Tray menu updated: is_tracking=%s, label=%s", is_tracking, pause_label)
    except Exception as exc:
        logger.warning("Could not update tray menu: %s", exc)


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


def _notify_state(root, is_tracking: bool) -> None:
    """Call root._on_tracking_state_changed if registered (for main.py state tracking)."""
    cb = getattr(root, "_on_tracking_state_changed", None)
    if cb is not None:
        try:
            cb(is_tracking)
        except Exception:
            logger.debug("_notify_state: callback raised.", exc_info=True)


def _set_window_taskbar_name(hwnd: int, name: str) -> None:
    """Set AppUserModel display-name properties on a HWND via Win32 IPropertyStore.

    Sets both PKEY_AppUserModel_RelaunchCommand (pid=2) and
    PKEY_AppUserModel_RelaunchDisplayNameResource (pid=4).  Windows requires
    both to be present together — setting only the display-name property is
    silently ignored.  No-op if any step fails.
    """
    try:
        import ctypes
        import sys

        class _GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_uint8 * 8),
            ]

        class _PROPERTYKEY(ctypes.Structure):
            _fields_ = [("fmtid", _GUID), ("pid", ctypes.c_uint32)]

        def _appusermodel_pkey(pid: int) -> _PROPERTYKEY:
            # {9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}
            pk = _PROPERTYKEY()
            pk.fmtid.Data1, pk.fmtid.Data2, pk.fmtid.Data3 = 0x9F4C2855, 0x9F79, 0x4B39
            pk.fmtid.Data4[:] = [0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3]
            pk.pid = pid
            return pk

        # IID_IPropertyStore {886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}
        riid = _GUID()
        riid.Data1, riid.Data2, riid.Data3 = 0x886D8EEB, 0x8CF2, 0x4446
        riid.Data4[:] = [0x8D, 0x02, 0xCD, 0xBA, 0x1D, 0xBD, 0xCF, 0x99]

        pps = ctypes.c_void_p()
        hr = ctypes.windll.shell32.SHGetPropertyStoreForWindow(
            ctypes.c_size_t(hwnd), ctypes.byref(riid), ctypes.byref(pps)
        )
        if hr != 0 or not pps.value:
            return

        vt = ctypes.cast(
            ctypes.cast(pps, ctypes.POINTER(ctypes.c_void_p))[0],
            ctypes.POINTER(ctypes.c_void_p),
        )
        # IPropertyStore vtable: QI(0) AddRef(1) Release(2) GetCount(3)
        #                        GetAt(4) GetValue(5) SetValue(6) Commit(7)
        _SetValue = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, ctypes.c_void_p,
            ctypes.POINTER(_PROPERTYKEY), ctypes.c_void_p,
        )(vt[6])

        def _set_string(pid: int, value: str) -> None:
            pv = (ctypes.c_byte * 24)()
            if ctypes.windll.propsys.InitPropVariantFromString(
                ctypes.c_wchar_p(value), ctypes.byref(pv)
            ) == 0:
                _SetValue(pps, ctypes.byref(_appusermodel_pkey(pid)), ctypes.byref(pv))
                ctypes.windll.ole32.PropVariantClear(ctypes.byref(pv))

        # pid=2: RelaunchCommand — required partner; Windows ignores pid=4 without it
        _set_string(2, sys.executable)
        # pid=4: RelaunchDisplayNameResource — friendly name in taskbar context menu
        _set_string(4, name)

        _Commit = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p)(vt[7])
        _Commit(pps)

        _Release = ctypes.WINFUNCTYPE(ctypes.ULONG, ctypes.c_void_p)(vt[2])
        _Release(pps)
    except Exception as exc:
        logger.debug("Could not set taskbar display name: %s", exc)


def apply_app_icon(win, *, is_root: bool = False) -> None:
    """Set the application .ico on a tkinter window (no-op if icon not found).

    Pass ``is_root=True`` when *win* is the ``tk.Tk()`` root — this uses the
    ``default=`` argument which registers the icon as the application-class icon
    so all Toplevel taskbar buttons inherit it automatically on Windows.
    """
    try:
        ico = _ICON_ICO_PATH
        if ico.exists():
            if is_root:
                win.iconbitmap(default=str(ico))
            else:
                win.iconbitmap(str(ico))
    except Exception as exc:
        logger.debug("Could not set window icon: %s", exc)

    if platform.system() == "Windows":
        try:
            _set_window_taskbar_name(win.winfo_id(), "CatGuard")
        except Exception as exc:
            logger.debug("Could not set taskbar name: %s", exc)


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
    # Build source image from PNG asset, ICO asset, or placeholder
    if _ICON_PATH.exists():
        img = Image.open(_ICON_PATH).convert("RGBA")
    elif _ICON_ICO_PATH.exists():
        img = Image.open(_ICON_ICO_PATH).convert("RGBA")
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
