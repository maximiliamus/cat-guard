# Contract: Log File Format

**Feature**: `011-log-viewer-search` | **Date**: 2026-03-19

This contract describes the log file format that both the writer (`BatchTrimFileHandler`) and the reader (log viewer) must agree on.

---

## File Location

```
{settings.logs_directory}/catguard.log
```

Default path (platform-specific):
- **Windows**: `C:\Users\<user>\AppData\Local\CatGuard\catguard.log`
- **macOS**: `~/Library/Application Support/CatGuard/logs/catguard.log`
- **Linux**: `~/.local/share/CatGuard/logs/catguard.log`

---

## Line Format

```
YYYY-MM-DD HH:MM:SS,mmm [LEVEL] logger.name: message text
```

**Example**:
```
2026-03-19 14:32:01,123 [INFO] catguard.detection: Cat detected (confidence=0.87)
2026-03-19 14:32:05,456 [WARNING] catguard.audio: Sound file not found: /path/to/alert.mp3
2026-03-19 14:32:10,789 [ERROR] catguard.main: Camera initialisation failed
```

**Encoding**: UTF-8
**Line ending**: `\n`
**Entry count**: ≤ `max_log_entries` at all times (enforced by `BatchTrimFileHandler._trim()`)

---

## Reader Contract

The log viewer MUST:
1. Read the file as UTF-8 with `errors="replace"` (handles any corrupt bytes).
2. Split on `\n`; skip empty lines.
3. Display lines in reverse order (newest first) by default.
4. Apply case-insensitive substring search across the full line (including timestamp).
5. Not write to or modify the file in any way.

---

## Writer Contract

`BatchTrimFileHandler` MUST:
1. Write one record per line using the format string `%(asctime)s [%(levelname)s] %(name)s: %(message)s`.
2. After every `log_trim_batch_size` emitted records, check total line count.
3. If line count exceeds `max_log_entries`, rewrite the file keeping only the **last** `max_log_entries` lines (preserve most recent entries).
4. Perform the rewrite atomically: write to `catguard.log.tmp`, then `os.replace()` over `catguard.log`.
5. Never truncate the file mid-write (the lock is held throughout `emit()` and `_trim()`).
