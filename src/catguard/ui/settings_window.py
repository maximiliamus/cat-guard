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
    # Screenshot fields (T013 / T023)
    screenshots_root_folder: str = ""
    screenshot_window_enabled: bool = False
    screenshot_window_start: str = "22:00"
    screenshot_window_end: str = "06:00"
    # Audio playback fields (T004)
    use_default_sound: bool = True
    pinned_sound: str = ""

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
            screenshots_root_folder=s.screenshots_root_folder,
            screenshot_window_enabled=s.screenshot_window_enabled,
            screenshot_window_start=s.screenshot_window_start,
            screenshot_window_end=s.screenshot_window_end,
            use_default_sound=s.use_default_sound,
            pinned_sound=s.pinned_sound,
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
            screenshots_root_folder=self.screenshots_root_folder,
            screenshot_window_enabled=self.screenshot_window_enabled,
            screenshot_window_start=self.screenshot_window_start,
            screenshot_window_end=self.screenshot_window_end,
            use_default_sound=self.use_default_sound,
            pinned_sound=self.pinned_sound,
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
    from catguard.recording import (
        Recorder,
        get_alerts_dir,
        is_silent,
        open_alerts_folder,
        save_recording,
    )

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

    # (pinned_sound_var defined after combobox; _remove_path references it — forward ref resolved below)
    _pinned_var_holder: list = []  # mutable cell for forward reference

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
        # Refresh combobox values when library changes
        _refresh_sound_combobox()

    def _remove_path():
        sel = path_listbox.curselection()
        if sel:
            removed = path_listbox.get(sel[0])
            path_listbox.delete(sel[0])
            # T022: if removed path is the currently pinned sound, reset dropdown to "All"
            if _pinned_var_holder:
                pinned_var = _pinned_var_holder[0]
                if pinned_var.get() == removed:
                    pinned_var.set("All")
            _refresh_sound_combobox()

    btn_frame = tk.Frame(win)
    btn_frame.grid(row=4, column=1, sticky="w", **pad)
    tk.Button(btn_frame, text="Add…", command=_add_path).pack(side="left", padx=2)
    tk.Button(btn_frame, text="Remove", command=_remove_path).pack(side="left", padx=2)

    # ---- Sound Alerts section ------------------------------------------
    tk.Label(win, text="Sound Alerts:", font=(None, 9, "bold")).grid(
        row=5, column=0, sticky="nw", **pad
    )

    # T015: "Use Default Sound" checkbox
    use_default_var = tk.BooleanVar(value=model.use_default_sound)
    tk.Checkbutton(
        win, text="Use Default Sound", variable=use_default_var
    ).grid(row=5, column=1, sticky="w", **pad)

    # T019: "Play Only This Sound" dropdown
    tk.Label(win, text="Play Only This Sound:").grid(row=6, column=0, sticky="w", **pad)
    _initial_pinned_label = model.pinned_sound if model.pinned_sound else "All"
    _initial_values = ["All"] + list(path_listbox.get(0, tk.END))
    if model.pinned_sound and model.pinned_sound not in _initial_values:
        _initial_values.append(model.pinned_sound)
    pinned_var = tk.StringVar(value=_initial_pinned_label)
    _pinned_var_holder.append(pinned_var)  # resolve forward reference for _remove_path
    sound_combo = ttk.Combobox(
        win,
        textvariable=pinned_var,
        values=_initial_values,
        state="readonly",
        width=38,
    )
    sound_combo.grid(row=6, column=1, **pad)

    def _refresh_sound_combobox():
        """Rebuild combobox values from the current library list."""
        libs = list(path_listbox.get(0, tk.END))
        values = ["All"] + libs
        sound_combo.config(values=values)
        # If current selection is no longer valid, reset to All
        if pinned_var.get() not in values:
            pinned_var.set("All")

    # T020: _update_dropdown_state — enables/disables combobox based on checkbox
    def _update_dropdown_state(*_):
        if use_default_var.get():
            sound_combo.config(state="disabled")
        else:
            sound_combo.config(state="readonly")

    use_default_var.trace_add("write", _update_dropdown_state)
    _update_dropdown_state()  # set initial state

    # T013: Alerts folder (read-only path + Browse button on same line)
    tk.Label(win, text="Alerts folder:").grid(row=7, column=0, sticky="w", **pad)
    alerts_dir = get_alerts_dir()
    alerts_var = tk.StringVar(value=str(alerts_dir))
    alerts_row_frame = tk.Frame(win)
    alerts_row_frame.grid(row=7, column=1, sticky="w", **pad)
    tk.Entry(alerts_row_frame, textvariable=alerts_var, width=28, state="readonly").pack(side="left")
    tk.Button(
        alerts_row_frame,
        text="Browse\u2026",
        command=lambda: open_alerts_folder(alerts_dir),
    ).pack(side="left", padx=(4, 0))

    # T011: Record / Stop Recording button + state
    _recorder_holder: list = []  # mutable cell: [Recorder | None]
    _record_btn_holder: list = []  # mutable cell: [tk.Button]

    def _on_recording_done(data):
        """Called from background thread when recording ends. Dispatch to UI thread."""
        root.after(0, lambda: _show_name_prompt(data))

    def _start_recording():
        try:
            recorder = Recorder()
            _recorder_holder.clear()
            _recorder_holder.append(recorder)
            recording_event = getattr(root, "_recording_event", None)
            if recording_event is not None:
                recording_event.set()
            recorder.start(on_done=_on_recording_done)
            _record_btn_holder[0].config(text="Stop Recording")
            logger.info("Recording started from Settings window.")
        except Exception as exc:
            # T028: microphone unavailable / permission denied
            _clear_recording_state()
            logger.error("Failed to start recording: %s", exc)
            messagebox.showerror(
                "Microphone Error",
                f"Could not access microphone:\n{exc}\n\n"
                "Check that a microphone is connected and permissions are granted.",
                parent=win,
            )

    def _stop_recording():
        if _recorder_holder:
            _recorder_holder[0].stop()
        _record_btn_holder[0].config(text="Record")

    def _clear_recording_state():
        _recorder_holder.clear()
        recording_event = getattr(root, "_recording_event", None)
        if recording_event is not None:
            recording_event.clear()
        if _record_btn_holder:
            _record_btn_holder[0].config(text="Record", state="normal")

    def _on_record_btn():
        if _recorder_holder and _recorder_holder[0].is_recording:
            _stop_recording()
        else:
            _start_recording()

    record_btn = tk.Button(win, text="Record", command=_on_record_btn, width=16)
    record_btn.grid(row=8, column=1, sticky="w", **pad)
    _record_btn_holder.append(record_btn)

    # T012: Name-entry prompt (shown after recording completes)
    def _show_name_prompt(data):
        """Show name dialog after recording; save or discard based on user choice."""
        _clear_recording_state()

        if is_silent(data):
            messagebox.showwarning(
                "Silent Recording",
                "No sound was detected in the recording. The recording was discarded.",
                parent=win,
            )
            logger.info("Recording discarded: silent.")
            return

        # Disable record button while name prompt is showing
        record_btn.config(state="disabled")

        name_prompt = tk.Toplevel(win)
        name_prompt.title("Name Your Recording")
        name_prompt.resizable(False, False)
        name_prompt.grab_set()
        name_prompt.transient(win)

        tk.Label(
            name_prompt,
            text=f"Save to: {alerts_dir}",
            fg="gray",
            font=(None, 8),
        ).grid(row=0, column=0, columnspan=2, padx=8, pady=(8, 2), sticky="w")

        tk.Label(name_prompt, text="Recording name:").grid(row=1, column=0, padx=8, pady=4, sticky="w")
        name_var = tk.StringVar()
        name_entry = tk.Entry(name_prompt, textvariable=name_var, width=30)
        name_entry.grid(row=1, column=1, padx=8, pady=4)
        name_entry.focus_set()

        _saved = [False]  # one-shot guard against double-click / re-entrancy

        def _do_save():
            if _saved[0]:
                return
            _saved[0] = True
            from catguard.recording import sanitise_filename
            raw_name = name_var.get().strip()
            if not raw_name:
                _saved[0] = False  # allow retry after empty-name warning
                messagebox.showwarning("Empty Name", "Please enter a name for the recording.", parent=name_prompt)
                return

            safe_name = sanitise_filename(raw_name)
            dest_path = alerts_dir / safe_name

            # Warn on duplicate
            if dest_path.exists():
                overwrite = messagebox.askyesno(
                    "File Exists",
                    f"'{safe_name}' already exists. Overwrite?",
                    parent=name_prompt,
                )
                if not overwrite:
                    return

            try:
                saved = save_recording(data, raw_name, alerts_dir=alerts_dir)
                # Add to library if not already present
                existing_lib = list(path_listbox.get(0, tk.END))
                if str(saved) not in existing_lib:
                    path_listbox.insert(tk.END, str(saved))
                _refresh_sound_combobox()
                logger.info("Recording saved and added to library: %s", saved)
            except OSError as exc:
                messagebox.showerror(
                    "Save Error",
                    f"Could not save recording:\n{exc}",
                    parent=name_prompt,
                )
                logger.error("Failed to save recording: %s", exc)
                return

            name_prompt.destroy()
            record_btn.config(state="normal")

        def _do_cancel():
            logger.info("Recording discarded by user (cancelled name prompt).")
            name_prompt.destroy()
            record_btn.config(state="normal")

        btn_row_np = tk.Frame(name_prompt)
        btn_row_np.grid(row=2, column=0, columnspan=2, pady=8)
        tk.Button(btn_row_np, text="Save", command=_do_save, width=8).pack(side="left", padx=4)
        tk.Button(btn_row_np, text="Cancel", command=_do_cancel, width=8).pack(side="left", padx=4)

        name_prompt.protocol("WM_DELETE_WINDOW", _do_cancel)
        name_prompt.wait_window()

    # ---- Autostart -------------------------------------------------------
    auto_var = tk.BooleanVar(value=model.autostart)
    tk.Checkbutton(win, text="Start CatGuard at login", variable=auto_var).grid(row=9, column=1, sticky="w", **pad)

    # ---- Screenshots section (T014) --------------------------------------
    tk.Label(win, text="Screenshots:", font=(None, 9, "bold")).grid(
        row=10, column=0, sticky="nw", **pad
    )

    # Root folder row
    tk.Label(win, text="Root folder:").grid(row=11, column=0, sticky="w", **pad)
    folder_var = tk.StringVar(value=model.screenshots_root_folder)
    ss_folder_frame = tk.Frame(win)
    ss_folder_frame.grid(row=11, column=1, sticky="w", **pad)
    tk.Entry(ss_folder_frame, textvariable=folder_var, width=28, state="readonly").pack(side="left")

    def _browse_folder():
        chosen = filedialog.askdirectory(
            parent=win,
            title="Select screenshots root folder",
            initialdir=model.screenshots_root_folder or None,
        )
        if chosen:
            folder_var.set(chosen)

    tk.Button(ss_folder_frame, text="Browse\u2026", command=_browse_folder).pack(side="left", padx=(4, 0))

    # Resolve and display the effective (default) path when field is empty
    try:
        from catguard.screenshots import resolve_root
        from catguard.config import Settings as _S
        _tmp = _S(screenshots_root_folder="")
        _default_path = str(resolve_root(_tmp))
    except Exception:
        _default_path = "Pictures/CatGuard"

    tk.Label(
        win,
        text=f"Default: {_default_path}",
        fg="gray",
        font=(None, 8),
    ).grid(row=12, column=1, sticky="w", **pad)

    # Time window subsection (T024) ----------------------------------------
    win_enabled_var = tk.BooleanVar(value=model.screenshot_window_enabled)
    tk.Checkbutton(
        win,
        text="Only save screenshots within a daily time window",
        variable=win_enabled_var,
    ).grid(row=13, column=1, sticky="w", **pad)

    win_start_var = tk.StringVar(value=model.screenshot_window_start)
    win_end_var = tk.StringVar(value=model.screenshot_window_end)

    tw_frame = tk.Frame(win)
    tw_frame.grid(row=14, column=1, sticky="w", **pad)
    tk.Label(tw_frame, text="From:").pack(side="left")
    start_spin = tk.Spinbox(
        tw_frame, textvariable=win_start_var, values=(
            *(f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)),
        ),
        width=6,
    )
    start_spin.pack(side="left", padx=(2, 6))
    tk.Label(tw_frame, text="To:").pack(side="left")
    end_spin = tk.Spinbox(
        tw_frame, textvariable=win_end_var, values=(
            *(f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)),
        ),
        width=6,
    )
    end_spin.pack(side="left", padx=2)

    def _update_tw_state(*_):
        state = "normal" if win_enabled_var.get() else "disabled"
        start_spin.config(state=state)
        end_spin.config(state=state)

    win_enabled_var.trace_add("write", _update_tw_state)
    _update_tw_state()  # set initial state

    # ---- Buttons ---------------------------------------------------------
    def _on_close():
        # Stop any ongoing recording cleanly
        if _recorder_holder and _recorder_holder[0].is_recording:
            _recorder_holder[0].stop()
        _clear_recording_state()
        try:
            root._settings_window_open = False
            try:
                del root._settings_window
            except Exception:
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
        model.screenshots_root_folder = folder_var.get()
        model.screenshot_window_enabled = win_enabled_var.get()
        model.screenshot_window_start = win_start_var.get()
        model.screenshot_window_end = win_end_var.get()
        # T016: persist audio playback settings
        model.use_default_sound = use_default_var.get()
        # T021: persist pinned_sound ("All" → empty string)
        selected = pinned_var.get()
        model.pinned_sound = "" if selected == "All" else selected

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
    btn_row.grid(row=15, column=0, columnspan=2, pady=8)
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
