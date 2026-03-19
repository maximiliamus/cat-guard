# Research: Log Viewer with Search, Clipboard Copy, and Auto-Trim

**Branch**: `011-log-viewer-search` | **Date**: 2026-03-19

---

## 1. GUI Framework

**Decision**: tkinter + ttk (existing)
**Rationale**: The entire UI is built on tkinter Toplevel/Notebook/ttk widgets. The log viewer follows the same pattern as `MainWindow` and `SettingsWindow` — a `tk.Toplevel` with a singleton guard via `root._log_viewer_open`.
**Alternatives considered**: None — swapping GUI frameworks for a single feature is out of scope.

---

## 2. Log File Reading

**Decision**: Read raw text file directly via `Path.read_text(encoding="utf-8", errors="replace")`.
**Rationale**: The existing log file is plain UTF-8 text, one entry per line in format `%(asctime)s [%(levelname)s] %(name)s: %(message)s`. No parser is needed — lines are displayed verbatim in the `tk.Text` widget. Reverse-chronological display is achieved by reversing the lines list after reading.
**Alternatives considered**:
- Python `logging` DB handler: overkill, would require schema migration.
- `mmap` for large files: SC-004 caps display at 2,048 entries (the max trim limit), so full file reads are bounded and fast.

---

## 3. Entry-Count Trim Mechanism

**Decision**: Custom `BatchTrimFileHandler(logging.FileHandler)` in `src/catguard/log_manager.py`.
**Rationale**: Python's built-in `RotatingFileHandler` trims by file size, not entry count. A custom subclass of `FileHandler` counts emitted records in-memory (`_write_count`). Every `log_trim_batch_size` writes, it reads the file, counts lines, and rewrites it keeping only the last `max_log_entries` lines. Thread-safety is provided by the `StreamHandler` lock already held during `emit()`.
**Alternatives considered**:
- Keep `RotatingFileHandler` + separate trim daemon: adds complexity; two mechanisms for one file.
- Trim on viewer open: visible latency; viewer should be read-only without side effects.
- Count lines on every write: too expensive at high logging rates; batching amortises the cost.

**Key implementation note**: `_trim()` is called **after** `super().emit(record)`, so the triggering record is always written first. The lock (`self.lock`) is already held by the `emit()` call chain, preventing concurrent trims.

---

## 4. Logging Initialization Order

**Decision**: Swap step order in `main()` — call `load_settings()` **before** `_configure_logging(logs_dir)`.
**Rationale**: `_configure_logging()` must receive `logs_directory` from settings to open the file handler at the correct path. `load_settings()` emits `logger.info/warning` messages before handlers exist; Python's "last resort" handler silently drops INFO and prints WARNING+ to stderr. This is acceptable for the brief pre-logging startup window.
**Alternatives considered**:
- Two-phase logging (console-only → file): adds complexity for no user-visible benefit.
- Hard-code default path, reconfigure on settings load: requires handler hot-swap plumbing.

---

## 5. Log Directory Change (Runtime)

**Decision**: On `on_settings_saved`, detect `logs_directory` change, close the old `BatchTrimFileHandler`, open a new one at the new path, and replace the handler on the root logger.
**Rationale**: Matches FR-016 — new writes go to the new directory immediately after Save. The old file is left in place (spec clarification).
**Alternatives considered**:
- Restart required for directory change: poor UX; avoidable given single-handler architecture.

---

## 6. Log Viewer Search

**Decision**: In-memory line filtering — on search activation, re-read the file, filter lines by case-insensitive `substring in line.lower()`, display results in the `tk.Text` widget.
**Rationale**: Matches FR-005/FR-006. Re-reading on each search guarantees a consistent snapshot (spec clarification Q4: search result is stable until re-executed). SC-005 (<1s) is trivially met for ≤2,048 lines.
**Alternatives considered**:
- `tk.Text` tag-based highlight: keeps all text visible, harder to show "no results" message.
- Real-time incremental search: not requested; contradicts stable-snapshot requirement.

---

## 7. Copy to Clipboard

**Decision**: Check `text_widget.tag_ranges(tk.SEL)` — if a selection range exists, copy `text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)`; otherwise copy all visible text via `text_widget.get("1.0", tk.END)`. Use `root.clipboard_clear()` + `root.clipboard_append()`.
**Rationale**: Directly implements FR-012. tkinter's SEL tag tracks user text selection in the `Text` widget natively. No external clipboard library needed.
**Alternatives considered**:
- `pyperclip`: extra dependency not needed when tkinter clipboard API suffices.

---

## 8. Tray Menu Addition

**Decision**: Add `pystray.MenuItem("Logs", on_logs_clicked)` between "Open" and "Settings…" in both `build_tray_icon()` and `update_tray_menu()`. Handler: `root.after(0, lambda: open_log_viewer(root, settings))`.
**Rationale**: Follows existing pattern — `_on_open_clicked_factory` and `_on_settings()` both dispatch to the tkinter thread via `root.after(0, ...)`. The `settings` reference is already available in both functions' closure.

---

## 9. Settings Persistence for New Fields

**Decision**: Add `logs_directory`, `max_log_entries`, `log_trim_batch_size` as Pydantic `Field` entries in `Settings` with `ge=` constraints enforcing minimum values. Add `_default_logs_directory()` factory mirroring existing `_default_models_directory()` pattern.
**Rationale**: Consistent with all existing settings fields. Pydantic `ge=` constraint raises `ValidationError` on invalid values, which `load_settings()` catches and resets to defaults.

---

## 10. Settings UI — Logs Tab

**Decision**: Add `tab_logs = ttk.Frame(notebook, padding=8)` as the 7th tab, inserted after "Schedule". Use `tk.Spinbox` for `max_log_entries` and `log_trim_batch_size` (matching Detection tab pattern). Use `tk.Entry(state="readonly")` + "Browse…" button for `logs_directory` (matching Storage tab pattern).
**Validation on Save**: If spinbox value < minimum, show `messagebox.showerror` and abort save — matching pattern used for invalid inputs elsewhere.
**Rationale**: Mirrors existing tab structure exactly; no new patterns introduced.
