"""Cross-platform autostart management for CatGuard.

Provides:
- enable_autostart()    Register CatGuard to run at login (platform-specific)
- disable_autostart()   Unregister CatGuard from login (platform-specific)
- is_autostart_enabled() True if currently registered

Platform strategies
-------------------
Windows  - Startup-folder .lnk shortcut  (no registry, no admin required)
macOS    - LaunchAgent plist in ~/Library/LaunchAgents/
Linux    - XDG .desktop file in ~/.config/autostart/
"""
from __future__ import annotations

import logging
import platform
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enable_autostart() -> None:
    """Register CatGuard for autostart on the current OS."""
    os_name = platform.system()
    if os_name == "Windows":
        path = _windows_startup_path()
        _create_windows_shortcut(path)
        logger.info("Autostart enabled (Windows .lnk): %s", path)
    elif os_name == "Darwin":
        path = _macos_plist_path()
        _write_macos_plist(path)
        logger.info("Autostart enabled (macOS LaunchAgent): %s", path)
    else:
        path = _linux_desktop_path()
        _write_linux_desktop(path)
        logger.info("Autostart enabled (Linux .desktop): %s", path)


def disable_autostart() -> None:
    """Remove the autostart entry for the current OS."""
    os_name = platform.system()
    if os_name == "Windows":
        path = _windows_startup_path()
    elif os_name == "Darwin":
        path = _macos_plist_path()
    else:
        path = _linux_desktop_path()

    if path.exists():
        path.unlink()
        logger.info("Autostart disabled: %s", path)
    else:
        logger.debug("Autostart entry not found (already disabled): %s", path)


def is_autostart_enabled() -> bool:
    """Return True if the autostart entry exists for the current OS."""
    os_name = platform.system()
    if os_name == "Windows":
        return _windows_startup_path().exists()
    elif os_name == "Darwin":
        return _macos_plist_path().exists()
    else:
        return _linux_desktop_path().exists()


# ---------------------------------------------------------------------------
# Windows helpers
# ---------------------------------------------------------------------------

def _windows_startup_path() -> Path:
    """Return the path for the Startup-folder .lnk shortcut."""
    import os
    startup = Path(os.environ.get("APPDATA", "~")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return startup / "CatGuard.lnk"


def _create_windows_shortcut(path: Path) -> None:
    """Create a .lnk shortcut at *path* pointing to the installed catguard entry point.

    Tries win32com.shell first (pywin32); falls back to writing a stub file so
    that the integration can be tested without pywin32 installed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import win32com.client  # type: ignore[import]
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(path))
        shortcut.Targetpath = sys.executable
        shortcut.Arguments = "-m catguard"
        shortcut.WorkingDirectory = str(Path(sys.executable).parent)
        shortcut.Description = "CatGuard — cat deterrent"
        shortcut.save()
        logger.debug("Created Windows shortcut via win32com: %s", path)
    except ImportError:
        logger.warning("pywin32 not available; writing stub .lnk at %s", path)
        path.write_text(f"[stub]\ntarget={sys.executable}\nargs=-m catguard\n")


# ---------------------------------------------------------------------------
# macOS helpers
# ---------------------------------------------------------------------------

def _macos_plist_path() -> Path:
    """Return the LaunchAgent plist path."""
    return Path.home() / "Library" / "LaunchAgents" / "com.catguard.app.plist"


def _write_macos_plist(path: Path) -> None:
    """Write a launchd LaunchAgent plist for CatGuard."""
    import plistlib

    plist_data: dict = {
        "Label": "com.catguard.app",
        "ProgramArguments": [sys.executable, "-m", "catguard"],
        "RunAtLoad": True,
        "KeepAlive": False,
        "StandardOutPath": str(Path.home() / "Library" / "Logs" / "CatGuard.log"),
        "StandardErrorPath": str(Path.home() / "Library" / "Logs" / "CatGuard.err.log"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        plistlib.dump(plist_data, fh)


# ---------------------------------------------------------------------------
# Linux helpers
# ---------------------------------------------------------------------------

def _linux_desktop_path() -> Path:
    """Return the XDG autostart .desktop file path."""
    return Path.home() / ".config" / "autostart" / "catguard.desktop"


def _write_linux_desktop(path: Path) -> None:
    """Write an XDG autostart .desktop file for CatGuard."""
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=CatGuard\n"
        "Comment=Cat deterrent — runs at login\n"
        f"Exec={sys.executable} -m catguard\n"
        "Hidden=false\n"
        "NoDisplay=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
