"""CatGuard entry point — wires all modules together.

Run as:
    python -m catguard           # via __main__.py
    catguard                     # if installed via pyproject.toml entry point
"""
from __future__ import annotations

import logging
import platform
import signal
import sys
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


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


def main() -> None:
    """Main entry point. Initializes all subsystems and starts the event loop."""
    import tkinter as tk

    from catguard.annotation import EffectivenessTracker
    from catguard.audio import init_audio, play_alert, shutdown_audio
    from catguard.config import load_settings, save_settings
    from catguard.detection import DetectionEvent, DetectionLoop
    from catguard.tray import build_tray_icon, notify_error

    # ------------------------------------------------------------------
    # 1. Logging
    # ------------------------------------------------------------------
    _configure_logging()

    # ------------------------------------------------------------------
    # 2. Settings (shared mutable object — all modules hold a reference)
    # ------------------------------------------------------------------
    settings = load_settings()

    # ------------------------------------------------------------------
    # 3. Audio
    # ------------------------------------------------------------------
    init_audio()
    assets_dir = Path(__file__).parent.parent.parent / "assets" / "sounds"
    default_sound = assets_dir / "default.wav"

    # ------------------------------------------------------------------
    # 4. tkinter root (created early so on_cat_detected can close over it)
    # ------------------------------------------------------------------
    root = tk.Tk()
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
    # 6. Shutdown handler (SIGINT / SIGTERM)
    # ------------------------------------------------------------------
    def on_shutdown(*_args) -> None:
        logger.info("Shutting down CatGuard…")
        detection_loop.stop()
        shutdown_audio()
        stop_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, on_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, on_shutdown)

    # ------------------------------------------------------------------
    # 7. Settings save callback (updates shared settings in-place — pull model)
    # ------------------------------------------------------------------
    def on_settings_saved(new_settings) -> None:
        save_settings(new_settings)
        for field_name in new_settings.model_fields:
            setattr(settings, field_name, getattr(new_settings, field_name))
        logger.info("Settings saved and propagated to detection loop.")

    # ------------------------------------------------------------------
    # 8. Tray + tkinter main loop
    # ------------------------------------------------------------------
    tray_icon = build_tray_icon(
        root, stop_event, settings, on_settings_saved, detection_loop
    )
    root._tray_icon = tray_icon  # expose to on_cat_detected via root reference

    # Set initial tray icon color to green (T028)
    from catguard.tray import update_tray_icon_color
    update_tray_icon_color(tray_icon, detection_loop.is_tracking())

    if platform.system() == "Darwin":
        # macOS: pystray must run detached so tkinter can own the main thread
        tray_icon.run_detached()
        root.mainloop()
    else:
        tray_thread = threading.Thread(target=tray_icon.run, name="TrayThread", daemon=True)
        tray_thread.start()
        root.mainloop()

    # Do not call on_shutdown() here; shutdown is handled by signal handler.


def _configure_logging() -> None:
    """Configure rotating file + console logging.

    Log level is INFO by default; DEBUG if --debug is in sys.argv.
    Log files are written to the platform user log directory.
    """
    import logging.handlers
    from platformdirs import user_log_dir

    log_dir = Path(user_log_dir("CatGuard"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "catguard.log"

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return  # already configured (e.g., in tests)

    level = logging.DEBUG if "--debug" in sys.argv else logging.INFO
    root_logger.setLevel(level)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    root_logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    root_logger.addHandler(ch)

    logger.info("Logging configured. Log file: %s", log_file)
    if level == logging.DEBUG:
        logger.debug("Debug logging enabled.")
