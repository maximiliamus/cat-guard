# Implementation Plan: Log Viewer with Search, Clipboard Copy, and Auto-Trim

**Branch**: `011-log-viewer-search` | **Date**: 2026-03-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/011-log-viewer-search/spec.md`

---

## Summary

Add a log viewer window (tkinter Toplevel, singleton) accessible from the tray menu via a new "Logs" item. The viewer reads the existing `catguard.log` text file, displays entries newest-first, supports case-insensitive full-line search, and provides Refresh and Copy-to-Clipboard toolbar buttons. A new `BatchTrimFileHandler` (custom `logging.FileHandler` subclass) replaces the existing `RotatingFileHandler`, enforcing entry-count-based trimming via batch writes. Three new settings (`logs_directory`, `max_log_entries`, `log_trim_batch_size`) are exposed on a new "Logs" tab in the Settings window.

---

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: tkinter + ttk (GUI), pystray (tray), pydantic (settings), platformdirs (paths) — all existing
**Storage**: Plain UTF-8 text file (`catguard.log`); JSON settings file (`settings.json`)
**Testing**: pytest + pytest-mock
**Target Platform**: Windows, macOS, Linux (desktop)
**Project Type**: Desktop application (tray-based)
**Performance Goals**: Log viewer opens <2s (SC-001); search returns <1s (SC-005); displays ≤2,048 entries without UI freeze (SC-004)
**Constraints**: No new runtime dependencies; standard library only for log_manager.py
**Scale/Scope**: Single-user local app; log bounded to `max_log_entries` (default 2,048)

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✅ PASS | Unit tests specified for `BatchTrimFileHandler` (TDD) and `SettingsFormModel` additions before implementation |
| II. Observability & Logging | ✅ PASS | This feature IS the observability improvement; `BatchTrimFileHandler` preserves structured logging |
| III. Simplicity & Clarity | ✅ PASS | No new runtime dependencies; reuses all existing patterns (Browse button, Spinbox, singleton window, `root.after` dispatch) |
| IV. Integration Testing | ✅ PASS | Settings round-trip (save/load new fields) requires integration test |
| V. Versioning & Breaking Changes | ✅ PASS | `settings.json` backward-compatible (merge-on-load fills defaults); `RotatingFileHandler` → `BatchTrimFileHandler` is internal — no public API change |

**Post-design re-check**: All gates still pass. No new violations introduced by design decisions.

---

## Project Structure

### Documentation (this feature)

```text
specs/011-log-viewer-search/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   ├── log-file-format.md
│   └── settings-schema.md
└── tasks.md             ← Phase 2 output (/speckit.tasks — not yet created)
```

### Source Code

```text
src/catguard/
├── log_manager.py           ← NEW: BatchTrimFileHandler
├── config.py                ← MODIFIED: 3 new Settings fields + validator + default factory
├── main.py                  ← MODIFIED: init order swap + _configure_logging(logs_dir, ...) + handler reconfigure on settings save
├── tray.py                  ← MODIFIED: "Logs" menu item in build_tray_icon + update_tray_menu
└── ui/
    ├── log_viewer.py        ← NEW: open_log_viewer(root, settings)
    └── settings_window.py   ← MODIFIED: SettingsFormModel + Logs tab

tests/unit/
├── test_log_manager.py      ← NEW: BatchTrimFileHandler unit tests (TDD)
├── test_log_viewer.py       ← NEW: SettingsFormModel additions (no display)
└── test_config.py           ← MODIFIED: new fields validation tests

tests/integration/
└── test_log_settings.py     ← NEW: settings round-trip for log fields
```

**Structure Decision**: Single project layout (Option 1). No new top-level directories. Two new source files (`log_manager.py`, `ui/log_viewer.py`) and one new contracts directory under specs.

---

## Complexity Tracking

> No constitution violations requiring justification.

---

## Implementation Design

### A. `src/catguard/log_manager.py` (NEW)

```python
class BatchTrimFileHandler(logging.FileHandler):
    """FileHandler that enforces entry-count trim via batched writes."""

    def __init__(self, filename, max_entries: int, batch_size: int, **kwargs):
        # max_entries receives settings.max_log_entries; batch_size receives settings.log_trim_batch_size
        super().__init__(filename, **kwargs)
        self._max_entries = max_entries
        self._batch_size = batch_size
        self._write_count = 0

    def emit(self, record) -> None:
        super().emit(record)          # lock is held by caller
        self._write_count += 1
        if self._write_count >= self._batch_size:
            self._write_count = 0
            self._trim()

    def _trim(self) -> None:
        path = Path(self.baseFilename)
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return
        if len(lines) <= self._max_entries:
            return
        keep = lines[-self._max_entries:]
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text("\n".join(keep) + "\n", encoding="utf-8")
            tmp.replace(path)
        except OSError:
            tmp.unlink(missing_ok=True)
```

### B. `src/catguard/config.py` changes

- Add `_default_logs_directory()` factory.
- Add three fields to `Settings`: `logs_directory`, `max_log_entries`, `log_trim_batch_size`.
- Add `validate_logs_directory` field validator (no `..`).

### C. `src/catguard/main.py` changes

- `_configure_logging(logs_dir: Path, max_entries: int, batch_size: int)` — accepts runtime values; calls `logs_dir.mkdir(parents=True, exist_ok=True)` before creating `BatchTrimFileHandler`; stores handler in module-level `_file_handler`.
- In `main()`: call `load_settings()` first (step 1), then `_configure_logging(Path(settings.logs_directory), ...)` (step 2). Swap current order.
- In `on_settings_saved`: detect `logs_directory` change; if changed, remove old handler, create new `BatchTrimFileHandler` at new path, add to root logger.

### D. `src/catguard/tray.py` changes

- Add `on_logs_clicked` factory (mirrors `_on_open_clicked_factory`): dispatches `open_log_viewer(root, settings)` via `root.after(0, ...)`.
- Insert `pystray.MenuItem("Logs", on_logs_clicked)` after "Open" in both `build_tray_icon()` and `update_tray_menu()` menu construction.

### E. `src/catguard/ui/log_viewer.py` (NEW)

```
open_log_viewer(root, settings)
  ├── singleton guard: root._log_viewer_open
  ├── win = tk.Toplevel(root)
  ├── apply_app_icon(win)              — consistent with all other Toplevel windows
  ├── geometry: load_win_geometry("log_viewer") on open; save_win_geometry("log_viewer", ...) on close
  ├── Top panel (tk.Frame):
  │   ├── tk.Entry (search_var)       — fills available width
  │   ├── tk.Button "Search"          — triggers _do_search()
  │   └── <Return> binding on entry
  ├── Main area:
  │   └── tk.Text (state=DISABLED, font=monospace, wrap=NONE)
  │       + ttk.Scrollbar (vertical + horizontal)
  └── Toolbar (tk.Frame, right-aligned):
      ├── tk.Button "Copy to Clipboard"  — triggers _do_copy()
      └── tk.Button "Refresh"            — triggers _do_refresh()

_do_refresh():
  reads Path(settings.logs_directory) / "catguard.log" (encoding="utf-8", errors="replace")
  clears search_var; resets to full view

_do_search():
  reads current file; filters lines by search_var (case-insensitive)
  updates Text widget; shows "No results." if empty

_do_copy():
  if text_widget.tag_ranges(tk.SEL): copy selected
  else: copy text_widget.get("1.0", tk.END)
  uses root.clipboard_clear() + root.clipboard_append()
```

### F. `src/catguard/ui/settings_window.py` changes

- `SettingsFormModel`: add `logs_directory: str`, `max_log_entries: int = 2048`, `log_trim_batch_size: int = 205`.
- `from_settings()` / `to_settings()`: include three new fields.
- `_save()`: extract new field values from UI vars; validate minimums before calling `model.apply()`.
- New `tab_logs = ttk.Frame(notebook, padding=8)`: `logs_directory` row (Entry + Browse), `max_log_entries` Spinbox, `log_trim_batch_size` Spinbox.

---

## Test Plan

### Unit Tests — `tests/unit/test_log_manager.py`

> All tests use `tmp_path` pytest fixture for filesystem isolation — no real user directories touched.

| Test | Behaviour verified |
|------|--------------------|
| `test_trim_not_triggered_before_batch` | No trim until `batch_size` writes |
| `test_trim_triggered_at_batch_boundary` | File trimmed after exactly `batch_size` writes when over limit |
| `test_trim_keeps_last_n_entries` | Oldest lines removed; newest retained |
| `test_trim_no_op_when_within_limit` | File unchanged when count ≤ `max_entries` |
| `test_trim_atomic_write` | `.tmp` file used; original replaced |
| `test_trim_handles_missing_file` | No exception if file does not exist yet |
| `test_write_count_resets_after_batch` | Counter resets to 0 after each trim check |

### Unit Tests — `tests/unit/test_log_viewer.py`

> Scope: `SettingsFormModel` additions only — no tkinter display required. Log viewer window singleton behaviour, geometry persistence, and widget interactions are display-dependent and are intentionally excluded from unit tests; they are covered by manual acceptance testing against the spec scenarios.

| Test | Behaviour verified |
|------|--------------------|
| `test_settings_form_model_defaults` | New fields have correct defaults |
| `test_from_settings_roundtrip` | `from_settings` + `to_settings` preserves new fields |
| `test_to_settings_validates_minimums` | Values below minimum raise `ValidationError` |

### Unit Tests — `tests/unit/test_main.py` (additions)

| Test | Behaviour verified |
|------|--------------------|
| `test_on_settings_saved_reconfigures_handler_on_dir_change` | When `logs_directory` changes, old `BatchTrimFileHandler` is removed from root logger and new one is added at the new path |
| `test_on_settings_saved_no_handler_change_when_dir_unchanged` | Handler is not replaced when `logs_directory` is unchanged |

### Unit Tests — `tests/unit/test_tray.py` (additions)

| Test | Behaviour verified |
|------|--------------------|
| `test_build_tray_icon_includes_logs_item` | "Logs" `MenuItem` is present in menu built by `build_tray_icon()` |
| `test_update_tray_menu_includes_logs_item` | "Logs" `MenuItem` is present in menu built by `update_tray_menu()` |

### Unit Tests — `tests/unit/test_config.py` (additions)

| Test | Behaviour verified |
|------|--------------------|
| `test_logs_directory_default` | Default resolves to platform data dir |
| `test_logs_directory_rejects_traversal` | `..` in path raises `ValidationError` |
| `test_max_log_entries_minimum` | Values < 2048 raise `ValidationError` |
| `test_log_trim_batch_size_minimum` | Values < 205 raise `ValidationError` |
| `test_load_settings_migrates_missing_log_fields` | Old JSON without new keys loads with defaults |

### Integration Tests — `tests/integration/test_log_settings.py`

> Real filesystem writes required — no mocks (Constitution §IV: integration tests must hit real shared state).

| Test | Behaviour verified |
|------|--------------------|
| `test_settings_round_trip_log_fields` | Save + reload preserves `logs_directory`, `max_log_entries`, `log_trim_batch_size` |
