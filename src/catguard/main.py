"""CatGuard entry point — wires all modules together.

Run as:
    python -m catguard           # via __main__.py
    catguard                     # if installed via pyproject.toml entry point
"""
from __future__ import annotations

import locale
import logging
import platform
import signal
import sys
import threading
from pathlib import Path
from typing import Callable

# helpers used by on-wake callback
from catguard.time_window import _is_in_window

logger = logging.getLogger(__name__)

# Module-level file handler — replaced on logs_directory change (T020)
_file_handler: "BatchTrimFileHandler | None" = None


def _get_resource_dir() -> Path:
    """Return the root resource directory for both dev and packaged environments.

    In a PyInstaller bundle, ``sys.frozen`` is True and ``sys._MEIPASS`` points
    to the directory where bundled data files are extracted.  In development,
    fall back to three levels up from this file (the repository root).
    """
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent.parent


def _monitor_playback_done(on_done: "Callable") -> None:
    """Start a daemon thread that waits for pygame playback to finish.

    Calls *on_done* once ``pygame.mixer.get_busy()`` returns False.
    Silently no-ops if pygame is unavailable.
    """
    def _worker() -> None:
        import time
        try:
            import pygame.mixer
            time.sleep(0.15)  # let the sound start before polling
            while pygame.mixer.get_busy():
                time.sleep(0.1)
        except Exception:
            logger.debug("_monitor_playback_done: pygame unavailable.", exc_info=True)
        try:
            on_done()
        except Exception:
            logger.debug("_monitor_playback_done: on_done raised.", exc_info=True)

    threading.Thread(target=_worker, name="PlaybackMonitor", daemon=True).start()


def _recreate_tray_icon(
    root,
    stop_event,
    settings,
    on_settings_saved,
    detection_loop,
    time_window_monitor,
) -> None:
    """Rebuild the tray icon after a sleep/resume cycle.

    Windows may drop the icon when the system wakes; call this to stop
    the old icon, rebuild a new one, and restart the associated thread.
    """
    old_icon = getattr(root, "_tray_icon", None)
    if old_icon is not None:
        try:
            old_icon.stop()
        except Exception:
            logger.debug("_recreate_tray_icon: failed to stop old icon", exc_info=True)
    new_icon = _build_and_prepare_tray_icon(
        root,
        stop_event,
        settings,
        on_settings_saved,
        detection_loop,
        time_window_monitor,
    )
    root._tray_icon = new_icon
    # restart tray thread
    if platform.system() == "Darwin":
        new_icon.run_detached()
    else:
        tray_thread = threading.Thread(
            target=new_icon.run, name="TrayThread", daemon=True
        )
        tray_thread.start()


def _build_and_prepare_tray_icon(
    root,
    stop_event,
    settings,
    on_settings_saved,
    detection_loop,
    time_window_monitor,
):
    """Build a tray icon and sync its state to the current tracking status."""
    from catguard.tray import build_tray_icon, update_tray_icon_color, update_tray_menu

    new_icon = build_tray_icon(
        root, stop_event, settings, on_settings_saved,
        detection_loop, time_window_monitor,
    )
    is_tracking = detection_loop.is_tracking()
    update_tray_icon_color(new_icon, is_tracking)
    update_tray_menu(
        new_icon, is_tracking, root, settings, on_settings_saved,
        detection_loop, time_window_monitor,
    )
    return new_icon


def _make_on_wake_callback(
    root,
    stop_event,
    settings,
    on_settings_saved,
    detection_loop,
    time_window_monitor,
    was_tracking,
    on_tracking_state_changed,
) -> Callable[[], None]:
    """Return a callback suitable for :class:`SleepWatcher`.

    The returned function closes over the supplied arguments instead of
    relying on names from ``main()`` so that tests can construct a fake
    environment.
    """

    def on_wake() -> None:
        logger.info("System wake detected (SleepWatcher).")
        if not was_tracking[0]:
            logger.info("on_wake: detection was paused before sleep — not restoring.")
            return
        # FR-007: evaluate time window before restoring
        if settings.tracking_window_enabled:
            from datetime import datetime

            now = datetime.now().time()
            if not _is_in_window(
                now, settings.tracking_window_start, settings.tracking_window_end
            ):
                logger.info(
                    "on_wake: current time is outside tracking window — not restoring camera."
                )
                return
        logger.info("on_wake: restoring camera after sleep.")
        try:
            detection_loop.resume()
            on_tracking_state_changed(True)
            _recreate_tray_icon(
                root,
                stop_event,
                settings,
                on_settings_saved,
                detection_loop,
                time_window_monitor,
            )
        except Exception:
            logger.exception("on_wake: failed to resume detection loop.")

    return on_wake

def main() -> None:
    """Main entry point. Initializes all subsystems and starts the event loop."""
    import tkinter as tk

    from catguard.single_instance import ensure_single_instance
    ensure_single_instance()

    from catguard.annotation import EffectivenessTracker
    from catguard.audio import init_audio, play_alert, shutdown_audio
    from catguard.config import load_settings, save_settings
    from catguard.detection import DetectionEvent, DetectionLoop
    from catguard.sleep_watcher import SleepWatcher
    from catguard.time_window import TimeWindowMonitor
    from catguard.tray import apply_app_icon, build_tray_icon, notify_error

    # ------------------------------------------------------------------
    # 1. Settings (loaded first so logging uses configured paths)
    # ------------------------------------------------------------------
    settings = load_settings()

    # ------------------------------------------------------------------
    # 1b. Logging (uses settings.logs_directory from config)
    # ------------------------------------------------------------------
    _configure_logging(
        logs_dir=Path(settings.logs_directory),
        max_entries=settings.max_log_entries,
        batch_size=settings.log_trim_batch_size,
    )

    # ------------------------------------------------------------------
    # 1c. Locale (T020 / FR-021: read OS locale for date/time formatting)
    # ------------------------------------------------------------------
    try:
        locale.setlocale(locale.LC_TIME, "")
        logger.info("Locale set to system default: %s", locale.getlocale(locale.LC_TIME))
    except locale.Error as exc:
        logger.warning("Could not set system locale for LC_TIME: %s", exc)

    # ------------------------------------------------------------------
    # 3. Audio
    # ------------------------------------------------------------------
    init_audio()
    assets_dir = _get_resource_dir() / "assets" / "sounds"
    default_sound = assets_dir / "default.wav"

    # ------------------------------------------------------------------
    # 4. tkinter root (created early so on_cat_detected can close over it)
    # ------------------------------------------------------------------
    # Windows: when running from the Python interpreter, set an explicit
    # AppUserModelID so Toplevel windows are grouped under CatGuard rather
    # than Python.  When frozen (catguard.exe) Windows derives the grouping
    # and display name from the exe itself (FileDescription = "CatGuard"),
    # so we skip this call — otherwise Windows falls back to showing
    # "catguard.exe" in the taskbar context-menu header.
    if platform.system() == "Windows" and not getattr(sys, "frozen", False):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CatGuard.Application.1")
        except Exception:
            pass

    # Windows: clear any stale MUI cache entry for this exe so Explorer
    # re-reads FileDescription ("CatGuard") rather than showing "catguard.exe".
    if platform.system() == "Windows":
        try:
            import winreg
            _mui_key = (
                r"Software\Classes\Local Settings"
                r"\Software\Microsoft\Windows\Shell\MuiCache"
            )
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _mui_key, 0, winreg.KEY_SET_VALUE
            ) as _k:
                winreg.DeleteValue(_k, sys.executable + ".FriendlyAppName")
        except (FileNotFoundError, OSError):
            pass  # key or value absent — nothing to clear

    root = tk.Tk(className="CatGuard")
    root.title("CatGuard")
    apply_app_icon(root, is_root=True)
    root.withdraw()  # hide the root window; tray is the primary UI
    root._main_window_visible = False  # visibility flag read by save_screenshot
    root._recording_event = threading.Event()  # set while mic recording is active

    # ------------------------------------------------------------------
    # 5. Detection (pull model: loop reads settings reference each frame)
    # ------------------------------------------------------------------
    stop_event = threading.Event()

    def _on_screenshot_error(msg: str) -> None:
        """Forward screenshot save errors to the tray balloon if available."""
        icon = getattr(root, "_tray_icon", None)
        if icon is not None:
            notify_error(icon, msg)
        else:
            logger.warning("Screenshot error (tray not ready): %s", msg)

    tracker = EffectivenessTracker(
        settings=settings,
        is_window_open=lambda: getattr(root, "_main_window_visible", False),
        on_error=_on_screenshot_error,
    )

    def on_cat_detected(event: DetectionEvent) -> None:
        if root._recording_event.is_set():
            logger.debug("on_cat_detected: suppressed — recording in progress.")
            return
        sound_label = play_alert(settings, default_sound)
        tracker.on_detection(event.frame_bgr, event.boxes, sound_label)

        # Show alert label on main window while sound is playing, then clear it.
        def _apply_label(label) -> None:
            win = getattr(root, "_main_window", None)
            if win is not None and not win._closed:
                win.set_alert_label(label)

        try:
            root.after(0, lambda lbl=sound_label: _apply_label(lbl))
            _monitor_playback_done(lambda: root.after(0, lambda: _apply_label(None)))
        except Exception:
            logger.debug("on_cat_detected: could not schedule alert label update.", exc_info=True)

    detection_loop = DetectionLoop(settings, on_cat_detected)
    detection_loop.set_verification_callback(tracker.on_verification)

    # Set up camera error callback (T041)
    def on_camera_error(error_msg: str) -> None:
        """Handle camera errors by showing notification via tray."""
        tracker.abandon()  # camera error = pause → abandon active session (FR-010)
        icon = getattr(root, "_tray_icon", None)
        if icon is not None:
            notify_error(icon, f"Camera error: {error_msg}")
        else:
            logger.warning("Camera error (tray not ready): %s", error_msg)

    detection_loop.set_error_callback(on_camera_error)

    # Pre-warm camera in background before showing tray
    # This allows 20+ seconds of initialization while UI appears
    logger.info("Starting camera warm-up (this may take 20+ seconds)…")
    detection_loop.start()
    detection_loop.resume()

    # ------------------------------------------------------------------
    # 5b. Settings save callback (updates shared settings in-place — pull model)
    # ------------------------------------------------------------------
    def on_settings_saved(new_settings) -> None:
        save_settings(new_settings)
        _reconfigure_file_handler(new_settings)
        for field_name in new_settings.model_fields:
            setattr(settings, field_name, getattr(new_settings, field_name))
        logger.info("Settings saved and propagated to detection loop.")

    # ------------------------------------------------------------------
    # 5c. TimeWindowMonitor — auto-pause/resume based on time window (T009)
    # ------------------------------------------------------------------
    _was_tracking = [True]  # reflects intentional (non-error) tracking state

    def on_tracking_state_changed(is_tracking: bool) -> None:
        """Called by TimeWindowMonitor and tray state callbacks."""
        _was_tracking[0] = is_tracking
        if not is_tracking:
            tracker.abandon()  # any pause abandons the active session (FR-010)
        win = getattr(root, "_main_window", None)
        if win is not None:
            if not is_tracking:
                win.clear_frame()
            win.set_capture_enabled(is_tracking)
        icon = getattr(root, "_tray_icon", None)
        if icon is not None:
            from catguard.tray import update_tray_icon_color, update_tray_menu
            update_tray_icon_color(icon, is_tracking)
            update_tray_menu(
                icon, is_tracking, root, settings, on_settings_saved,
                detection_loop, time_window_monitor,
            )
        logger.info("Tracking state changed: is_tracking=%s", is_tracking)

    time_window_monitor = TimeWindowMonitor(
        detection_loop, settings, on_tracking_state_changed
    )
    root._on_tracking_state_changed = on_tracking_state_changed

    # ------------------------------------------------------------------
    # 5d. SleepWatcher — detect system wake and restore camera (T014)
    # ------------------------------------------------------------------
    on_wake = _make_on_wake_callback(
        root,
        stop_event,
        settings,
        on_settings_saved,
        detection_loop,
        time_window_monitor,
        _was_tracking,
        on_tracking_state_changed,
    )
    sleep_watcher = SleepWatcher(on_wake=on_wake)

    # ------------------------------------------------------------------
    # 6. Shutdown handler (SIGINT / SIGTERM)
    # ------------------------------------------------------------------
    def get_clean_frame():
        """T011: Retrieve the latest raw frame without detection overlays.

        Used by ActionPanel to capture clean photos for saving.
        Returns None when tracking is paused (camera unavailable) or when no
        frame has been captured yet.
        """
        if not detection_loop.is_tracking():
            return None
        return detection_loop.get_latest_frame()

    def minimize_to_tray():
        """Close the main window and restore the tray icon."""
        root.withdraw()
        root._main_window_visible = False
        logger.info("Main window minimized to tray.")

    # Attach these functions to root so they can be called from MainWindow
    root.get_clean_frame = get_clean_frame
    root.minimize_to_tray = minimize_to_tray
    root.settings = settings
    root._default_sound_path = default_sound

    def on_shutdown(*_args) -> None:
        logger.info("Shutting down CatGuard…")
        tracker.abandon()
        time_window_monitor.stop()
        sleep_watcher.stop()
        detection_loop.stop()
        shutdown_audio()
        stop_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, on_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, on_shutdown)

    # ------------------------------------------------------------------
    # 7. Tray + tkinter main loop
    # ------------------------------------------------------------------
    tray_icon = build_tray_icon(
        root, stop_event, settings, on_settings_saved, detection_loop, time_window_monitor
    )
    root._tray_icon = tray_icon  # expose to on_cat_detected via root reference

    # Set initial tray icon color to green (T028)
    from catguard.tray import update_tray_icon_color
    update_tray_icon_color(tray_icon, detection_loop.is_tracking())

    # Start background monitors after tray is ready
    time_window_monitor.start()
    sleep_watcher.start()

    if platform.system() == "Darwin":
        # macOS: pystray must run detached so tkinter can own the main thread
        tray_icon.run_detached()
        root.mainloop()
    else:
        tray_thread = threading.Thread(target=tray_icon.run, name="TrayThread", daemon=True)
        tray_thread.start()
        root.mainloop()

    # Do not call on_shutdown() here; shutdown is handled by signal handler.


def _configure_logging(
    logs_dir: Path | None = None,
    max_entries: int = 2048,
    batch_size: int = 205,
) -> None:
    """Configure BatchTrimFileHandler + console logging.

    Log level is INFO by default; DEBUG if --debug is in sys.argv.
    Log files are written to *logs_dir* (defaults to the platform user log directory).
    Creates the directory if it does not exist.
    """
    global _file_handler
    from catguard.log_manager import BatchTrimFileHandler

    if logs_dir is None:
        from platformdirs import user_data_dir
        logs_dir = Path(user_data_dir("CatGuard")) / "logs"

    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "catguard.log"

    root_logger = logging.getLogger()
    # Only skip if our file handler is already attached.
    # Don't bail on StreamHandlers added by third-party libs (e.g. ultralytics).
    if _file_handler is not None and _file_handler in root_logger.handlers:
        return

    level = logging.DEBUG if "--debug" in sys.argv else logging.INFO
    root_logger.setLevel(level)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    fh = BatchTrimFileHandler(
        str(log_file),
        max_entries=max_entries,
        batch_size=batch_size,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root_logger.addHandler(fh)
    _file_handler = fh

    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    root_logger.addHandler(ch)

    logger.info("Logging configured. Log file: %s", log_file)
    if level == logging.DEBUG:
        logger.debug("Debug logging enabled.")


def _reconfigure_file_handler(settings) -> None:
    """Swap the file handler if *settings.logs_directory* has changed (T020)."""
    global _file_handler
    from catguard.log_manager import BatchTrimFileHandler

    if _file_handler is None:
        return

    new_dir = Path(settings.logs_directory)
    current_dir = Path(_file_handler.baseFilename).parent

    if new_dir.resolve() == current_dir.resolve():
        return  # unchanged — nothing to do

    new_dir.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()

    # Remove and close old handler
    root_logger.removeHandler(_file_handler)
    _file_handler.close()

    # Create new handler at the new location
    new_log_file = new_dir / "catguard.log"
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    new_fh = BatchTrimFileHandler(
        str(new_log_file),
        max_entries=settings.max_log_entries,
        batch_size=settings.log_trim_batch_size,
        encoding="utf-8",
    )
    new_fh.setFormatter(fmt)
    root_logger.addHandler(new_fh)
    _file_handler = new_fh
    logger.info("Log file handler reconfigured to: %s", new_log_file)
