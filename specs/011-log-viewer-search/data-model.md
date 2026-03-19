# Data Model: Log Viewer with Search, Clipboard Copy, and Auto-Trim

**Branch**: `011-log-viewer-search` | **Date**: 2026-03-19

---

## 1. Settings Model Extensions

New fields added to `src/catguard/config.py` — `Settings(BaseModel)`:

| Field | Type | Default | Constraint | Description |
|-------|------|---------|-----------|-------------|
| `logs_directory` | `str` | `_default_logs_directory()` | no `..` (path traversal) | Directory where `catguard.log` is written and read |
| `max_log_entries` | `int` | `2048` | `ge=2048` | Maximum retained log entries; trim removes oldest when exceeded |
| `log_trim_batch_size` | `int` | `205` | `ge=205` | Number of writes between trim checks (~10% of default `max_log_entries`) |

**Default factory**:
```python
def _default_logs_directory() -> str:
    return str(Path(user_data_dir("CatGuard")) / "logs")
```

**Validator** (mirrors existing directory validators):
```python
@field_validator("logs_directory")
@classmethod
def validate_logs_directory(cls, path: str) -> str:
    if ".." in path:
        raise ValueError(f"logs_directory must not contain '..' (got {path!r})")
    return path
```

**JSON persistence** (`settings.json`): new keys `logs_directory`, `max_log_entries`, `log_trim_batch_size` added alongside existing keys. Existing installs without these keys get defaults via the merge-on-load pattern in `load_settings()`.

---

## 2. SettingsFormModel Extensions

New fields added to `src/catguard/ui/settings_window.py` — `SettingsFormModel(dataclass)`:

| Field | Type | Default |
|-------|------|---------|
| `logs_directory` | `str` | `_default_logs_directory()` |
| `max_log_entries` | `int` | `2048` |
| `log_trim_batch_size` | `int` | `205` |

Both `from_settings()` and `to_settings()` extended to include these three fields.

---

## 3. Log Entry (File Format)

Log entries are written by Python's `logging` module using the format:

```
%(asctime)s [%(levelname)s] %(name)s: %(message)s
```

**Example line**:
```
2026-03-19 14:32:01,123 [INFO] catguard.detection: Cat detected (confidence=0.87)
```

- One entry per line.
- UTF-8 encoded.
- Lines are terminated with `\n`.
- The log viewer treats each non-empty line as one entry.
- Reverse-chronological display: lines are reversed after reading.

**File location**: `{settings.logs_directory}/catguard.log`

**Invariant enforced by trim**: line count ≤ `max_log_entries` after each trim cycle.

---

## 4. BatchTrimFileHandler

Defined in `src/catguard/log_manager.py`.

```
BatchTrimFileHandler
├── __init__(filename, max_entries, batch_size, **kwargs)
│   ├── _max_entries: int         # from settings.max_log_entries
│   ├── _batch_size: int          # from settings.log_trim_batch_size
│   └── _write_count: int = 0     # in-memory counter; reset after each trim check
├── emit(record)
│   ├── calls super().emit(record)  # writes to file (lock held)
│   ├── increments _write_count
│   └── if _write_count >= _batch_size: _write_count = 0; _trim()
└── _trim()
    ├── reads all lines from self.baseFilename
    ├── if len(lines) <= _max_entries: return (no-op)
    └── rewrites file keeping last _max_entries lines (atomic: write to .tmp, rename)
```

**Thread safety**: `emit()` is called inside the `StreamHandler` lock (acquired by the logging framework before calling `emit`). `_trim()` is called from within that lock, so file reads and atomic rewrites are serialised.

**Handler lifecycle**:
- Created in `_configure_logging(logs_dir, max_entries, batch_size)`.
- Stored as module-level `_file_handler: BatchTrimFileHandler | None` in `main.py` for access by `on_settings_saved`.
- When `logs_directory` changes: old handler is closed and removed from root logger; new handler is created at the new path and added.

---

## 5. State Transitions — Log Viewer Window

```
[Closed]
    │  user clicks "Logs" in tray menu
    ▼
[Open — Unfiltered]
    │  user types in search input + clicks Search / presses Enter
    ▼
[Open — Filtered]  ◄──── user clicks Search with empty input ────► [Open — Unfiltered]
    │
    │  user clicks Refresh (either state)
    ▼
[Reloads from file — active search cleared, shows full log]
    │
    │  user closes window
    ▼
[Closed]
```

**Singleton guard**: `root._log_viewer_open: bool`. If True and window exists, `window.lift()` is called instead of creating a new one.

---

## 6. Relationships

```
Settings ──────────────────────────────────► BatchTrimFileHandler
 .logs_directory                               (file path)
 .max_log_entries                              (_max_entries)
 .log_trim_batch_size                          (_batch_size)

Settings ──────────────────────────────────► LogViewerWindow
 .logs_directory                               (reads catguard.log from this dir)

TrayIcon ──── "Logs" click ────────────────► open_log_viewer(root, settings)

SettingsWindow["Logs tab"] ─── Save ───────► on_settings_saved(new_settings)
                                               ├── saves settings.json
                                               ├── propagates fields to shared Settings
                                               └── if logs_directory changed:
                                                    reconfigures BatchTrimFileHandler
```
