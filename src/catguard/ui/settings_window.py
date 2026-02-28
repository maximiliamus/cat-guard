"""Settings UI for CatGuard.

Provides:
- SettingsFormModel: a plain dataclass that mirrors Settings for UI binding.
  Intentionally free of tkinter so it can be unit-tested without a display.
- open_settings_window(): builds the actual tkinter Toplevel dialog.
"""
from __future__ import annotations

import logging
import sys
import threading
from dataclasses import dataclass, field
from typing import Callable, List

from catguard.config import Settings
from catguard.detection import Camera, list_cameras

logger = logging.getLogger(__name__)


@dataclass
class SettingsFormModel:
    """In-memory model for the Settings form.

    Decoupled from tkinter so it can be tested without a display.
    """

    camera_index: int = 0
    confidence_threshold: float = 0.25
    cooldown_seconds: float = 15.0
    sound_library_paths: List[str] = field(default_factory=list)
    autostart: bool = False

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls, s: Settings) -> "SettingsFormModel":
        """Populate a form model from a Settings object."""
        return cls(
            camera_index=s.camera_index,
            confidence_threshold=s.confidence_threshold,
            cooldown_seconds=s.cooldown_seconds,
            sound_library_paths=list(s.sound_library_paths),
            autostart=s.autostart,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_settings(self) -> Settings:
        """Convert back to a validated Settings object."""
        return Settings(
            camera_index=self.camera_index,
            confidence_threshold=self.confidence_threshold,
            cooldown_seconds=self.cooldown_seconds,
            sound_library_paths=list(self.sound_library_paths),
            autostart=self.autostart,
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def apply(self, on_save: Callable[[Settings], None]) -> None:
        """Convert to Settings and invoke the save callback."""
        on_save(self.to_settings())

    @staticmethod
    def get_cameras() -> List[Camera]:
        """Return available cameras by delegating to detection.list_cameras."""
        return list_cameras()


# ---------------------------------------------------------------------------
# tkinter window (display-dependent; not unit-tested here)
# ---------------------------------------------------------------------------

def open_settings_window(root, settings: Settings, on_settings_saved: Callable) -> None:
    """Open the Settings window as a modal tkinter Toplevel.

    Reads from *settings* in-place when the user clicks Save.
    Calls *on_settings_saved(new_settings)* after writing.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError:
        logger.error("tkinter not available; cannot open Settings window.")
        return

    from catguard.autostart import disable_autostart, enable_autostart, is_autostart_enabled

    # Prevent multiple settings windows — keep a single instance per root
    if getattr(root, "_settings_window_open", False):
        try:
            existing = getattr(root, "_settings_window", None)
            if existing is not None and existing.winfo_exists():
                existing.lift()
                return
        except Exception:
            # Fall through and allow creating a new window if something odd happened
            logger.exception("Failed to raise existing settings window")

    model = SettingsFormModel.from_settings(settings)

    win = tk.Toplevel(root)
    # mark window open on the root so subsequent clicks won't create duplicates
    root._settings_window_open = True
    root._settings_window = win
    win.title("CatGuard — Settings")
    win.resizable(False, False)
    win.grab_set()  # modal

    pad = {"padx": 8, "pady": 4}

    # ---- Camera index -------------------------------------------------
    tk.Label(win, text="Camera index:").grid(row=0, column=0, sticky="w", **pad)
    # Initially show a disabled combobox while camera enumeration runs off the UI thread
    cam_var = tk.StringVar(value="Loading…")
    cam_combo = ttk.Combobox(win, textvariable=cam_var, values=["Loading…"], state="disabled", width=30)
    cam_combo.grid(row=0, column=1, **pad)

    # ---- Detection sensitivity (inverted confidence threshold) ----------
    # Slider direction: left = HIGH sensitivity (low threshold), right = LOW sensitivity (high threshold)
    tk.Label(win, text="Detection sensitivity:").grid(row=1, column=0, sticky="w", **pad)
    # Store threshold internally; display value is inverted: display = 1 - threshold
    conf_var = tk.DoubleVar(value=model.confidence_threshold)
    sensitivity_frame = tk.Frame(win)
    sensitivity_frame.grid(row=1, column=1, sticky="w", **pad)
    threshold_label = tk.Label(sensitivity_frame, text=f"threshold={conf_var.get():.2f}")

    def _on_slider_change(val):
        # Scale goes 0.0 (high sensitivity, low threshold) to 1.0 (low sensitivity, high threshold)
        conf_var.set(round(float(val), 2))
        threshold_label.config(text=f"threshold={float(val):.2f}")

    sens_scale = tk.Scale(
        sensitivity_frame,
        from_=0.0,
        to=1.0,
        resolution=0.05,
        orient="horizontal",
        variable=conf_var,
        command=_on_slider_change,
        length=200,
        label="◄ High sensitivity         Low sensitivity ►",
    )
    sens_scale.set(model.confidence_threshold)
    sens_scale.pack(side="left")
    threshold_label.pack(side="left", padx=4)

    # ---- Cooldown -------------------------------------------------------
    tk.Label(win, text="Cooldown (seconds):").grid(row=2, column=0, sticky="w", **pad)
    cool_var = tk.DoubleVar(value=model.cooldown_seconds)
    tk.Spinbox(win, from_=1.0, to=300.0, increment=1.0, textvariable=cool_var, width=8, format="%.0f").grid(row=2, column=1, sticky="w", **pad)

    # ---- Sound library paths ------------------------------------------
    tk.Label(win, text="Sound library paths:").grid(row=3, column=0, sticky="nw", **pad)
    path_listbox = tk.Listbox(win, height=4, width=40)
    for p in model.sound_library_paths:
        path_listbox.insert(tk.END, p)
    path_listbox.grid(row=3, column=1, **pad)

    def _add_path():
        files = filedialog.askopenfilenames(
            parent=win,
            title="Select audio files",
            filetypes=[("Audio files", "*.mp3 *.wav"), ("All files", "*.*")],
        )
        for f in files:
            # Avoid duplicates
            existing = list(path_listbox.get(0, tk.END))
            if f not in existing:
                path_listbox.insert(tk.END, f)

    def _remove_path():
        sel = path_listbox.curselection()
        if sel:
            path_listbox.delete(sel[0])

    btn_frame = tk.Frame(win)
    btn_frame.grid(row=4, column=1, sticky="w", **pad)
    tk.Button(btn_frame, text="Add…", command=_add_path).pack(side="left", padx=2)
    tk.Button(btn_frame, text="Remove", command=_remove_path).pack(side="left", padx=2)

    # ---- Autostart -------------------------------------------------------
    auto_var = tk.BooleanVar(value=model.autostart)
    tk.Checkbutton(win, text="Start CatGuard at login", variable=auto_var).grid(row=5, column=1, sticky="w", **pad)

    # ---- Buttons ---------------------------------------------------------
    def _on_close():
        try:
            root._settings_window_open = False
            delattr = False
            try:
                delattr = True
                del root._settings_window
            except Exception:
                # ignore; attribute may already be removed
                pass
        finally:
            try:
                win.destroy()
            except Exception:
                pass


    def _save():
        try:
            # Extract camera index from combo value "0  Camera 0"
            cam_idx = int(cam_var.get().split()[0])
        except (ValueError, IndexError):
            cam_idx = 0

        model.camera_index = cam_idx
        model.confidence_threshold = conf_var.get()
        model.cooldown_seconds = cool_var.get()
        model.sound_library_paths = list(path_listbox.get(0, tk.END))
        new_autostart = auto_var.get()
        model.autostart = new_autostart

        # Apply autostart change if it differs from current
        if new_autostart and not is_autostart_enabled():
            enable_autostart()
        elif not new_autostart and is_autostart_enabled():
            disable_autostart()

        model.apply(on_settings_saved)
        _on_close()

    def _cancel():
        _on_close()

    btn_row = tk.Frame(win)
    btn_row.grid(row=6, column=0, columnspan=2, pady=8)
    tk.Button(btn_row, text="Save", command=_save, width=10).pack(side="left", padx=4)
    tk.Button(btn_row, text="Cancel", command=_cancel, width=10).pack(side="left", padx=4)

    # Ensure cleanup if the user closes the window via window manager
    win.protocol("WM_DELETE_WINDOW", _cancel)

    # Enumerate cameras off the UI thread to avoid blocking the GUI
    def _load_cameras_bg():
        try:
            cams = SettingsFormModel.get_cameras()
            cam_values_local = [f"{c.index}  {c.name}" for c in cams] or ["0  Default"]
        except Exception:
            logger.exception("Failed to enumerate cameras")
            cam_values_local = ["0  Default"]

        def _update():
            try:
                cam_combo.config(values=cam_values_local)
                # Select the saved camera index if it's within the list
                if model.camera_index < len(cam_values_local):
                    cam_var.set(cam_values_local[model.camera_index])
                else:
                    cam_var.set(cam_values_local[0])
                cam_combo.config(state="readonly")
            except Exception:
                logger.exception("Failed to update camera combobox")

        # Schedule combo update on the Tkinter event loop
        root.after(0, _update)

    threading.Thread(target=_load_cameras_bg, name="SettingsCameraEnum", daemon=True).start()

    win.wait_window()
