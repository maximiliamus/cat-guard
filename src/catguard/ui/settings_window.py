"""Settings UI for CatGuard.

Provides:
- SettingsFormModel: a plain dataclass that mirrors Settings for UI binding.
  Intentionally free of tkinter so it can be unit-tested without a display.
- open_settings_window(): builds the actual tkinter Toplevel dialog.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List

from catguard.config import Settings, _default_models_directory, _default_photos_directory, _default_tracking_directory
from catguard.ui.geometry import load_win_geometry, save_win_geometry
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
    detection_fps: float = 3.0
    sound_library_paths: List[str] = field(default_factory=list)
    autostart: bool = False
    # Tracking fields (T013 / T023 / 008)
    models_directory: str = field(default_factory=_default_models_directory)
    tracking_directory: str = field(default_factory=_default_tracking_directory)
    photos_directory: str = field(default_factory=_default_photos_directory)
    photo_countdown_seconds: int = 3
    # Audio playback fields (T004)
    use_default_sound: bool = True
    pinned_sound: str = ""
    # Tracking time window fields (T002 / 007-misc-improvements)
    tracking_window_enabled: bool = False
    tracking_window_start: str = "08:00"
    tracking_window_end: str = "18:00"

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
            detection_fps=s.detection_fps,
            sound_library_paths=list(s.sound_library_paths),
            autostart=s.autostart,
            models_directory=s.models_directory,
            tracking_directory=s.tracking_directory,
            photos_directory=s.photos_directory,
            photo_countdown_seconds=s.photo_countdown_seconds,
            use_default_sound=s.use_default_sound,
            pinned_sound=s.pinned_sound,
            tracking_window_enabled=s.tracking_window_enabled,
            tracking_window_start=s.tracking_window_start,
            tracking_window_end=s.tracking_window_end,
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
            detection_fps=self.detection_fps,
            sound_library_paths=list(self.sound_library_paths),
            autostart=self.autostart,
            models_directory=self.models_directory,
            tracking_directory=self.tracking_directory,
            photos_directory=self.photos_directory,
            photo_countdown_seconds=self.photo_countdown_seconds,
            use_default_sound=self.use_default_sound,
            pinned_sound=self.pinned_sound,
            tracking_window_enabled=self.tracking_window_enabled,
            tracking_window_start=self.tracking_window_start,
            tracking_window_end=self.tracking_window_end,
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
# Pure helpers (unit-testable without a display)
# ---------------------------------------------------------------------------

_FORBIDDEN_STEM_CHARS: frozenset[str] = frozenset(r'\/:*?"<>|')


def _validate_rename_stem(new_stem: str) -> str | None:
    """Validate a proposed file stem for a rename operation.

    Returns ``None`` if the stem is valid, or a human-readable error string
    if it is not.  Intentionally free of tkinter so it can be unit-tested.
    """
    stripped = new_stem.strip()
    if not stripped:
        return "Name cannot be empty."
    if any(c in _FORBIDDEN_STEM_CHARS for c in stripped):
        bad = ", ".join(sorted(c for c in stripped if c in _FORBIDDEN_STEM_CHARS))
        return f"Name contains invalid characters: {bad}"
    return None


# ---------------------------------------------------------------------------
# tkinter window (display-dependent; not unit-tested here)
# ---------------------------------------------------------------------------

# Mutable cell — persists saved geometry across multiple settings-window sessions
# within a process; initialised from disk so it survives restarts.
_settings_win_geometry: list[str] = [load_win_geometry("settings_window")]


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
    from catguard.tray import apply_app_icon
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
    apply_app_icon(win)
    # mark window open on the root so subsequent clicks won't create duplicates
    root._settings_window_open = True
    root._settings_window = win
    win.title("CatGuard — Settings")
    win.resizable(True, True)
    win.grab_set()  # modal

    win.minsize(500, 360)

    # Restore saved position, or centre on root
    win.update_idletasks()
    if _settings_win_geometry[0]:
        win.geometry(_settings_win_geometry[0])
    else:
        rw = root.winfo_rootx() + root.winfo_width() // 2
        rh = root.winfo_rooty() + root.winfo_height() // 2
        win.geometry(f"+{rw - win.winfo_reqwidth() // 2}+{rh - win.winfo_reqheight() // 2}")

    pad = {"padx": 8, "pady": 4}

    # ---- Notebook -------------------------------------------------------
    notebook = ttk.Notebook(win)
    notebook.pack(fill="both", expand=True, padx=8, pady=(8, 0))

    tab_detection = ttk.Frame(notebook, padding=8)
    tab_models    = ttk.Frame(notebook, padding=8)
    tab_sound     = ttk.Frame(notebook, padding=8)
    tab_storage   = ttk.Frame(notebook, padding=8)
    tab_schedule  = ttk.Frame(notebook, padding=8)
    tab_general   = ttk.Frame(notebook, padding=8)

    notebook.add(tab_general,   text="General")
    notebook.add(tab_detection, text="Detection")
    notebook.add(tab_models,    text="Models")
    notebook.add(tab_sound,     text="Alerts")
    notebook.add(tab_storage,   text="Storage")
    notebook.add(tab_schedule,  text="Schedule")

    # Allow column 1 to grow when the window is resized
    tab_general.columnconfigure(1, weight=1)
    tab_detection.columnconfigure(1, weight=1)
    tab_models.columnconfigure(1, weight=1)
    tab_sound.columnconfigure(1, weight=1)
    tab_sound.rowconfigure(2, weight=1)   # listbox row grows vertically
    tab_storage.columnconfigure(1, weight=1)
    tab_schedule.columnconfigure(1, weight=1)

    # ==== Detection tab ==================================================

    # ---- Camera index ---------------------------------------------------
    tk.Label(tab_detection, text="Camera index:").grid(row=0, column=0, sticky="e", **pad)
    cam_var = tk.StringVar(value="Loading…")
    cam_combo = ttk.Combobox(tab_detection, textvariable=cam_var, values=["Loading…"], state="disabled", width=30)
    cam_combo.grid(row=0, column=1, sticky="ew", **pad)

    # ---- Detection sensitivity ------------------------------------------
    tk.Label(tab_detection, text="Detection sensitivity:").grid(row=1, column=0, sticky="e", **pad)
    conf_var = tk.DoubleVar(value=model.confidence_threshold)
    sensitivity_frame = tk.Frame(tab_detection)
    sensitivity_frame.grid(row=1, column=1, sticky="ew", **pad)
    threshold_label = tk.Label(sensitivity_frame, text=f"{conf_var.get():.2f}")

    def _on_slider_change(val):
        conf_var.set(round(float(val), 2))
        threshold_label.config(text=f"{float(val):.2f}")

    sens_scale = tk.Scale(
        sensitivity_frame,
        from_=0.0,
        to=1.0,
        resolution=0.05,
        orient="horizontal",
        showvalue=False,
        variable=conf_var,
        command=_on_slider_change,
        length=200,
    )
    sens_scale.set(model.confidence_threshold)
    sens_scale.pack(side="left")
    threshold_label.pack(side="left", padx=(4, 0))

    # ---- Cooldown -------------------------------------------------------
    tk.Label(tab_detection, text="Cooldown (seconds):").grid(row=2, column=0, sticky="e", **pad)
    cool_var = tk.DoubleVar(value=model.cooldown_seconds)
    tk.Spinbox(tab_detection, from_=1.0, to=300.0, increment=1.0, textvariable=cool_var, width=8, format="%.0f").grid(row=2, column=1, sticky="w", **pad)

    # ---- Detection FPS --------------------------------------------------
    tk.Label(tab_detection, text="Detection FPS:").grid(row=3, column=0, sticky="e", **pad)
    fps_var = tk.DoubleVar(value=model.detection_fps)
    tk.Spinbox(tab_detection, from_=1.0, to=30.0, increment=1.0, textvariable=fps_var, width=8, format="%.0f").grid(row=3, column=1, sticky="w", **pad)

    # ==== Models tab ======================================================

    # ---- Models directory -----------------------------------------------
    tk.Label(tab_models, text="Models directory:").grid(row=0, column=0, sticky="e", **pad)
    models_folder_var = tk.StringVar(value=model.models_directory)
    models_folder_frame = tk.Frame(tab_models)
    models_folder_frame.grid(row=0, column=1, sticky="ew", **pad)

    def _browse_models_folder():
        chosen = filedialog.askdirectory(
            parent=win,
            title="Select models directory",
            initialdir=model.models_directory,
        )
        if chosen:
            models_folder_var.set(chosen)

    tk.Button(models_folder_frame, text="Browse\u2026", command=_browse_models_folder).pack(side="right", padx=(4, 0))
    tk.Entry(models_folder_frame, textvariable=models_folder_var, state="readonly").pack(side="left", fill="x", expand=True)

    # ==== Alerts tab ======================================================

    alerts_dir = get_alerts_dir()

    def _display_label(full_path: str) -> str:
        """Return filename only if inside alerts_dir, else full path."""
        p = Path(full_path)
        try:
            p.relative_to(alerts_dir)
            return p.name
        except ValueError:
            return full_path

    # ---- Alerts library --------------------------------------------------
    tk.Label(tab_sound, text="Alerts library:").grid(row=2, column=0, sticky="ne", **pad)
    path_listbox = tk.Listbox(tab_sound, height=5, width=40)
    _paths_list: list[str] = []  # full paths, parallel to listbox entries
    for p in model.sound_library_paths:
        _paths_list.append(p)
        path_listbox.insert(tk.END, _display_label(p))
    path_listbox.grid(row=2, column=1, sticky="nsew", **pad)

    # (pinned_sound_var defined after combobox; _remove_path references it — forward ref resolved below)
    _pinned_var_holder: list = []  # mutable cell for forward reference

    def _add_path():
        files = filedialog.askopenfilenames(
            parent=win,
            title="Select audio files",
            filetypes=[("Audio files", "*.mp3 *.wav"), ("All files", "*.*")],
        )
        for f in files:
            if f not in _paths_list:
                _paths_list.append(f)
                path_listbox.insert(tk.END, _display_label(f))
        # Refresh combobox values when library changes
        _refresh_sound_combobox()

    def _remove_path():
        sel = path_listbox.curselection()
        if sel:
            idx = sel[0]
            removed = _paths_list[idx]
            path_listbox.delete(idx)
            del _paths_list[idx]
            # T022: if removed path is the currently pinned sound, reset dropdown to "All (in random order)"
            if _pinned_var_holder:
                pinned_var = _pinned_var_holder[0]
                if pinned_var.get() == _display_label(removed):
                    pinned_var.set("All (in random order)")
            _refresh_sound_combobox()

    def _play_selected():
        sel = path_listbox.curselection()
        if not sel:
            return
        path = _paths_list[sel[0]]
        from catguard.audio import _play_async
        _play_async(path)

    # Mutable cell to persist rename dialog geometry across invocations;
    # seed from disk so position is remembered across restarts.
    _rename_dlg_geometry = [load_win_geometry("rename_dialog") or None]

    def _rename_path():
        """Rename the selected sound file on disk and update the UI. (T016)"""
        sel = path_listbox.curselection()
        if not sel:
            return
        path = _paths_list[sel[0]]
        # Stop any active playback before showing dialog
        try:
            import pygame.mixer  # noqa: PLC0415
            pygame.mixer.stop()
            logger.debug("_rename_path: stopped pygame mixer before dialog.")
        except Exception:
            logger.debug("_rename_path: pygame.mixer.stop() not available.")
        current_stem = Path(path).stem

        # Custom resizable rename dialog — Entry expands with the window
        _result = [None]
        dlg = tk.Toplevel(win)
        apply_app_icon(dlg)
        dlg.title("Rename Sound")
        dlg.resizable(True, False)
        dlg.grab_set()
        dlg.transient(win)

        tk.Label(dlg, text="New name:").grid(row=0, column=0, padx=(8, 4), pady=(12, 4), sticky="w")
        name_var = tk.StringVar(value=current_stem)
        name_entry = tk.Entry(dlg, textvariable=name_var)
        name_entry.grid(row=0, column=1, padx=(0, 8), pady=(12, 4), sticky="ew")
        name_entry.icursor(tk.END)
        name_entry.select_range(0, tk.END)

        dlg.columnconfigure(1, weight=1)

        def _ok(event=None):
            _result[0] = name_var.get()
            _rename_dlg_geometry[0] = dlg.geometry()
            save_win_geometry("rename_dialog", _rename_dlg_geometry[0])
            dlg.destroy()

        def _cancel(event=None):
            _rename_dlg_geometry[0] = dlg.geometry()
            save_win_geometry("rename_dialog", _rename_dlg_geometry[0])
            dlg.destroy()

        btn_row_dlg = tk.Frame(dlg)
        btn_row_dlg.grid(row=1, column=0, columnspan=2, pady=(4, 10))
        tk.Button(btn_row_dlg, text="OK", command=_ok, width=8).pack(side="left", padx=4)
        tk.Button(btn_row_dlg, text="Cancel", command=_cancel, width=8).pack(side="left", padx=4)

        dlg.bind("<Return>", _ok)
        dlg.bind("<Escape>", _cancel)
        dlg.protocol("WM_DELETE_WINDOW", _cancel)

        # Restore saved geometry, or let tkinter size naturally then centre on parent
        if _rename_dlg_geometry[0]:
            dlg.geometry(_rename_dlg_geometry[0])
        else:
            dlg.update_idletasks()
            pw = win.winfo_rootx() + win.winfo_width() // 2
            ph = win.winfo_rooty() + win.winfo_height() // 2
            dlg.geometry(f"+{pw - dlg.winfo_reqwidth() // 2}+{ph - dlg.winfo_reqheight() // 2}")

        name_entry.focus_set()
        dlg.wait_window()

        # Always return focus to the listbox and restore the selection.
        # selection_set() does not fire <<ListboxSelect>>, so update the
        # rename button state manually afterwards.
        path_listbox.focus_set()
        path_listbox.selection_set(sel[0])
        path_listbox.see(sel[0])
        _update_selection_btn_states()

        new_stem = _result[0]
        if new_stem is None:  # user cancelled
            return
        err = _validate_rename_stem(new_stem)
        if err:
            messagebox.showerror("Invalid Name", err, parent=win)
            return
        new_stem = new_stem.strip()
        new_path = Path(path).parent / (new_stem + Path(path).suffix)
        if new_path == Path(path):
            logger.debug("_rename_path: name unchanged ('%s') — skipping.", new_stem)
            return
        if new_path.exists() and new_path != Path(path):
            messagebox.showerror(
                "Duplicate Name", f"'{new_stem}' already exists.", parent=win
            )
            return
        try:
            Path(path).rename(new_path)
        except OSError as exc:
            messagebox.showerror("Rename Error", str(exc), parent=win)
            logger.error("_rename_path: failed to rename %s → %s: %s", path, new_path, exc)
            return
        # Update listbox entry in-place
        new_path_str = str(new_path)
        path_listbox.delete(sel[0])
        path_listbox.insert(sel[0], _display_label(new_path_str))
        _paths_list[sel[0]] = new_path_str
        path_listbox.selection_set(sel[0])
        path_listbox.see(sel[0])
        # Update pinned_var if this sound was the pinned selection
        if _pinned_var_holder and _pinned_var_holder[0].get() == _display_label(path):
            _pinned_var_holder[0].set(_display_label(new_path_str))
        _refresh_sound_combobox()
        logger.info("Sound file renamed: %s → %s", path, new_path)

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

    btn_frame = tk.Frame(tab_sound)
    btn_frame.grid(row=3, column=1, sticky="ew", **pad)
    btn_frame.columnconfigure(0, weight=1)
    btn_frame.columnconfigure(1, weight=1)
    btn_frame.columnconfigure(2, weight=1)

    left_grp = tk.Frame(btn_frame)
    left_grp.grid(row=0, column=0, sticky="w")
    tk.Button(left_grp, text="Add…", command=_add_path).pack(side="left", padx=2)
    rename_btn = tk.Button(left_grp, text="Rename", command=_rename_path, state="disabled")
    rename_btn.pack(side="left", padx=2)

    center_grp = tk.Frame(btn_frame)
    center_grp.grid(row=0, column=1)
    record_btn = tk.Button(center_grp, text="Record", command=_on_record_btn)
    record_btn.pack(side="left", padx=2)
    _record_btn_holder.append(record_btn)
    play_btn = tk.Button(center_grp, text="▶ Play", command=_play_selected, state="disabled")
    play_btn.pack(side="left", padx=2)

    right_grp = tk.Frame(btn_frame)
    right_grp.grid(row=0, column=2, sticky="e")
    remove_btn = tk.Button(right_grp, text="Remove", command=_remove_path, fg="red", state="disabled")
    remove_btn.pack(side="left", padx=2)

    def _update_selection_btn_states(*_):
        state = "normal" if path_listbox.curselection() else "disabled"
        rename_btn.config(state=state)
        play_btn.config(state=state)
        remove_btn.config(state=state)

    def _on_listbox_click(event):
        idx = path_listbox.nearest(event.y)
        if idx in path_listbox.curselection():
            path_listbox.selection_clear(idx)
            _update_selection_btn_states()
            return "break"

    path_listbox.bind("<Button-1>", _on_listbox_click)
    path_listbox.bind("<<ListboxSelect>>", _update_selection_btn_states)

    # ---- Sound tab: alerts ----------------------------------------------
    # T015: "Use default alert" checkbox
    use_default_var = tk.BooleanVar(value=model.use_default_sound)
    tk.Label(tab_sound, text="Use default alert:").grid(row=5, column=0, sticky="e", **pad)
    _use_default_frame = tk.Frame(tab_sound)
    _use_default_frame.grid(row=5, column=1, sticky="ew", **pad)
    _use_default_cb = tk.Checkbutton(_use_default_frame, variable=use_default_var, takefocus=0)
    _use_default_cb.pack(side="left")
    _use_default_frame.bind("<Button-1>", lambda _e: use_default_var.set(not use_default_var.get()))

    def _play_default_sound():
        _default_sound = getattr(root, "_default_sound_path", None)
        if _default_sound and Path(_default_sound).is_file():
            try:
                import pygame.mixer
                pygame.mixer.stop()
            except Exception:
                pass
            from catguard.audio import _play_async
            _play_async(str(_default_sound))

    tk.Button(_use_default_frame, text="\u25b6 Play", command=_play_default_sound).pack(side="left", padx=(6, 0))

    # T019: "Play Only This Sound" dropdown
    tk.Label(tab_sound, text="Play alert:").grid(row=4, column=0, sticky="e", **pad)
    _initial_pinned_label = _display_label(model.pinned_sound) if model.pinned_sound else "All (in random order)"
    _initial_values = ["All (in random order)"] + [_display_label(p) for p in _paths_list]
    if model.pinned_sound and _initial_pinned_label not in _initial_values:
        _initial_values.append(_initial_pinned_label)
    pinned_var = tk.StringVar(value=_initial_pinned_label)
    _pinned_var_holder.append(pinned_var)  # resolve forward reference for _remove_path
    sound_combo = ttk.Combobox(
        tab_sound,
        textvariable=pinned_var,
        values=_initial_values,
        state="readonly",
        width=38,
    )
    sound_combo.grid(row=4, column=1, sticky="ew", **pad)

    def _refresh_sound_combobox():
        """Rebuild combobox values from the current library list."""
        values = ["All (in random order)"] + [_display_label(p) for p in _paths_list]
        sound_combo.config(values=values)
        # If current selection is no longer valid, reset to All
        if pinned_var.get() not in values:
            pinned_var.set("All (in random order)")

    # T020: _update_dropdown_state — enables/disables combobox based on checkbox
    def _update_dropdown_state(*_):
        sound_combo.config(state="disabled" if use_default_var.get() else "readonly")

    use_default_var.trace_add("write", _update_dropdown_state)
    _update_dropdown_state()  # set initial state without playing

    # T013: Alerts directory (read-only path + Browse button on same line)
    tk.Label(tab_sound, text="Alerts directory:").grid(row=0, column=0, sticky="e", **pad)
    alerts_var = tk.StringVar(value=str(alerts_dir))
    alerts_row_frame = tk.Frame(tab_sound)
    alerts_row_frame.grid(row=0, column=1, sticky="ew", **pad)
    tk.Button(
        alerts_row_frame,
        text="Browse\u2026",
        command=lambda: open_alerts_folder(alerts_dir),
    ).pack(side="right", padx=(4, 0))
    tk.Entry(alerts_row_frame, textvariable=alerts_var, state="readonly").pack(side="left", fill="x", expand=True)

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
        apply_app_icon(name_prompt)
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
                if str(saved) not in _paths_list:
                    _paths_list.append(str(saved))
                    path_listbox.insert(tk.END, _display_label(str(saved)))
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

    # ==== Storage tab ====================================================

    # ---- Tracking directory ---------------------------------------------
    tk.Label(tab_storage, text="Tracking directory:").grid(row=0, column=0, sticky="w", **pad)
    folder_var = tk.StringVar(value=model.tracking_directory)
    ss_folder_frame = tk.Frame(tab_storage)
    ss_folder_frame.grid(row=0, column=1, sticky="ew", **pad)

    def _browse_folder():
        chosen = filedialog.askdirectory(
            parent=win,
            title="Select tracking directory",
            initialdir=model.tracking_directory,
        )
        if chosen:
            folder_var.set(chosen)

    tk.Button(ss_folder_frame, text="Browse\u2026", command=_browse_folder).pack(side="right", padx=(4, 0))
    tk.Entry(ss_folder_frame, textvariable=folder_var, state="readonly").pack(side="left", fill="x", expand=True)

    # ---- Photos directory -----------------------------------------------
    tk.Label(tab_storage, text="Photos directory:").grid(row=1, column=0, sticky="w", **pad)
    photos_folder_var = tk.StringVar(value=model.photos_directory)
    photos_folder_frame = tk.Frame(tab_storage)
    photos_folder_frame.grid(row=1, column=1, sticky="ew", **pad)

    def _browse_photos_folder():
        chosen = filedialog.askdirectory(
            parent=win,
            title="Select photos directory",
            initialdir=model.photos_directory,
        )
        if chosen:
            photos_folder_var.set(chosen)

    tk.Button(photos_folder_frame, text="Browse\u2026", command=_browse_photos_folder).pack(side="right", padx=(4, 0))
    tk.Entry(photos_folder_frame, textvariable=photos_folder_var, state="readonly").pack(side="left", fill="x", expand=True)

    # ==== Schedule tab ===================================================

    track_win_enabled_var = tk.BooleanVar(value=model.tracking_window_enabled)
    tk.Checkbutton(
        tab_schedule,
        text="Only monitor within a daily time window",
        variable=track_win_enabled_var,
    ).grid(row=0, column=0, columnspan=2, sticky="w", **pad)

    track_win_start_var = tk.StringVar(value=model.tracking_window_start)
    track_win_end_var = tk.StringVar(value=model.tracking_window_end)

    tw_track_frame = tk.Frame(tab_schedule)
    tw_track_frame.grid(row=1, column=0, columnspan=2, sticky="w", **pad)
    tk.Label(tw_track_frame, text="From:").pack(side="left")
    track_start_spin = tk.Spinbox(
        tw_track_frame,
        textvariable=track_win_start_var,
        values=(*(f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)),),
        width=6,
    )
    track_start_spin.pack(side="left", padx=(2, 6))
    tk.Label(tw_track_frame, text="To:").pack(side="left")
    track_end_spin = tk.Spinbox(
        tw_track_frame,
        textvariable=track_win_end_var,
        values=(*(f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)),),
        width=6,
    )
    track_end_spin.pack(side="left", padx=2)

    def _update_track_tw_state(*_):
        state = "normal" if track_win_enabled_var.get() else "disabled"
        track_start_spin.config(state=state)
        track_end_spin.config(state=state)

    track_win_enabled_var.trace_add("write", _update_track_tw_state)
    _update_track_tw_state()  # set initial state

    # ==== General tab ====================================================

    # ---- Photo countdown ------------------------------------------------
    tk.Label(tab_general, text="Photo countdown (sec):").grid(row=0, column=0, sticky="e", **pad)
    photo_countdown_var = tk.IntVar(value=model.photo_countdown_seconds)
    photo_countdown_spin = tk.Spinbox(tab_general, from_=1, to=30, increment=1, textvariable=photo_countdown_var, width=8)
    photo_countdown_spin.grid(row=0, column=1, sticky="w", **pad)

    auto_var = tk.BooleanVar(value=model.autostart)
    tk.Label(tab_general, text="Start CatGuard at login:").grid(row=1, column=0, sticky="e", **pad)
    _auto_frame = tk.Frame(tab_general)
    _auto_frame.grid(row=1, column=1, sticky="ew", **pad)
    auto_check = tk.Checkbutton(_auto_frame, variable=auto_var, takefocus=0)
    auto_check.pack(side="left")
    _auto_frame.bind("<Button-1>", lambda _: auto_var.set(not auto_var.get()))

    # ---- Buttons (outside notebook) -------------------------------------
    def _on_close():
        # Persist window geometry before destroying — save to both in-process
        # cell and on-disk file so position/size survives restarts.
        try:
            _settings_win_geometry[0] = win.geometry()
            save_win_geometry("settings_window", _settings_win_geometry[0])
        except Exception:
            pass
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
        model.detection_fps = fps_var.get()
        model.sound_library_paths = list(_paths_list)
        new_autostart = auto_var.get()
        model.autostart = new_autostart
        model.models_directory = models_folder_var.get()
        model.tracking_directory = folder_var.get()
        model.photos_directory = photos_folder_var.get()
        model.photo_countdown_seconds = photo_countdown_var.get()
        # T016: persist audio playback settings
        model.use_default_sound = use_default_var.get()
        # T021: persist pinned_sound ("All (in random order)" → empty string; display label → full path)
        selected_label = pinned_var.get()
        if selected_label == "All (in random order)":
            model.pinned_sound = ""
        else:
            model.pinned_sound = next(
                (p for p in _paths_list if _display_label(p) == selected_label), ""
            )
        # T008: persist tracking window settings
        model.tracking_window_enabled = track_win_enabled_var.get()
        model.tracking_window_start = track_win_start_var.get()
        model.tracking_window_end = track_win_end_var.get()

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
    btn_row.pack(anchor="e", padx=8, pady=8)
    tk.Button(btn_row, text="Save", command=_save, width=10).pack(side="left", padx=4)
    tk.Button(btn_row, text="Cancel", command=_cancel, width=10).pack(side="left", padx=4)

    # Ensure cleanup if the user closes the window via window manager
    win.protocol("WM_DELETE_WINDOW", _cancel)

    # Enumerate cameras off the UI thread to avoid blocking the GUI
    def _load_cameras_bg():
        try:
            cams = list_cameras(active_indices={model.camera_index})
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

    win.lift()
    win.focus_force()
    photo_countdown_spin.focus_set()

    win.wait_window()
