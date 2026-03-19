# Quickstart: Log Viewer with Search, Clipboard Copy, and Auto-Trim

**Branch**: `011-log-viewer-search` | **Date**: 2026-03-19

---

## What This Feature Adds

| Component | Where | What changes |
|-----------|-------|--------------|
| `BatchTrimFileHandler` | `src/catguard/log_manager.py` *(new)* | Replaces `RotatingFileHandler`; trims by entry count |
| Log viewer window | `src/catguard/ui/log_viewer.py` *(new)* | Toplevel with search, copy, refresh |
| Tray menu "Logs" item | `src/catguard/tray.py` | New menu item between Open and Settings… |
| Settings "Logs" tab | `src/catguard/ui/settings_window.py` | New tab with 3 settings |
| New Settings fields | `src/catguard/config.py` | `logs_directory`, `max_log_entries`, `log_trim_batch_size` |
| Init order swap | `src/catguard/main.py` | `load_settings()` before `_configure_logging(logs_dir)` |

---

## Running Locally

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the app (log viewer accessible from tray icon)
python -m catguard

# Run with debug logging
python -m catguard --debug
```

---

## Running Tests

```bash
# All unit tests
pytest tests/unit/

# New tests for this feature
pytest tests/unit/test_log_manager.py
pytest tests/unit/test_log_viewer.py

# All tests (unit + integration)
pytest
```

---

## Key Files for This Feature

```
src/catguard/
├── log_manager.py          ← NEW: BatchTrimFileHandler
├── config.py               ← MODIFIED: 3 new settings fields
├── main.py                 ← MODIFIED: init order + log dir reconfigure
├── tray.py                 ← MODIFIED: Logs menu item
└── ui/
    ├── log_viewer.py       ← NEW: log viewer Toplevel
    └── settings_window.py  ← MODIFIED: Logs tab + SettingsFormModel

tests/unit/
├── test_log_manager.py     ← NEW
└── test_log_viewer.py      ← NEW (SettingsFormModel additions)

specs/011-log-viewer-search/
├── contracts/
│   ├── log-file-format.md
│   └── settings-schema.md
├── data-model.md
├── research.md
└── quickstart.md           ← this file
```

---

## Configuration Defaults

| Setting | Default | Minimum | Where |
|---------|---------|---------|-------|
| `logs_directory` | `{user_data_dir}/logs` | — | Settings → Logs tab |
| `max_log_entries` | `2048` | `2048` | Settings → Logs tab |
| `log_trim_batch_size` | `205` | `205` | Settings → Logs tab |

---

## How Trim Works

1. Every log write increments an in-memory counter in `BatchTrimFileHandler`.
2. When the counter reaches `log_trim_batch_size` (default 205), it resets and a trim check runs.
3. If the file has more than `max_log_entries` lines, the oldest lines are removed and the file is rewritten atomically.
4. The log viewer is unaffected mid-session; changes appear on next Refresh.

---

## How the Log Viewer Works

1. Click "Logs" in the tray icon menu.
2. The viewer opens and loads `catguard.log` from `logs_directory`, displaying entries newest-first.
3. Type in the search box and press Enter or click "Search" to filter by substring (case-insensitive, full line including timestamp).
4. Clear the search and press Enter / click "Search" to restore the full view.
5. Click "Refresh" to reload the file (picks up new entries written since open).
6. Click "Copy to Clipboard" to copy: selected text (if any) or all visible entries.
