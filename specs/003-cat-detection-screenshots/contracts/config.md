# Contract: Settings Configuration File (v1.1)

**Version**: 1.1 *(non-breaking extension of v1.0)*  
**Format**: JSON  
**Location**:

| Platform | Path |
|---|---|
| Windows | `%APPDATA%\CatGuard\settings.json` |
| macOS | `~/Library/Application Support/CatGuard/settings.json` |
| Linux | `~/.config/CatGuard/settings.json` (respects `$XDG_CONFIG_HOME`) |

**Change from v1.0**: Four new optional fields added for the screenshot feature. All have defaults; existing `settings.json` files without these fields continue to work without migration.

---

## Schema

```json
{
  "camera_index": 0,
  "confidence_threshold": 0.25,
  "cooldown_seconds": 15.0,
  "sound_library_paths": [
    "/home/user/sounds/hiss.mp3"
  ],
  "autostart": false,
  "screenshots_root_folder": "",
  "screenshot_window_enabled": false,
  "screenshot_window_start": "22:00",
  "screenshot_window_end": "06:00"
}
```

### Fields

| Field | Type | Required | Default | Constraints |
|---|---|---|---|---|
| `camera_index` | integer | No | `0` | ≥ 0 |
| `confidence_threshold` | number | No | `0.25` | [0.0, 1.0] |
| `cooldown_seconds` | number | No | `15.0` | > 0.0 |
| `sound_library_paths` | array of string | No | `[]` | Each element must be an absolute path to an existing MP3 or WAV file; stale paths are silently dropped on load |
| `autostart` | boolean | No | `false` | — |
| `screenshots_root_folder` | string | No | `""` | Absolute path to the screenshots root folder. Empty string means use the OS default (`Pictures/CatGuard`). Non-existent paths are accepted; folders are created on first save. |
| `screenshot_window_enabled` | boolean | No | `false` | When `true`, screenshots are only saved within the `screenshot_window_start`–`screenshot_window_end` time range. |
| `screenshot_window_start` | string | No | `"22:00"` | `HH:MM` format (00:00–23:59). Start of the daily screenshot time window. |
| `screenshot_window_end` | string | No | `"06:00"` | `HH:MM` format (00:00–23:59). End of the daily screenshot time window. May be earlier than `screenshot_window_start` to span midnight (e.g., `"22:00"` → `"06:00"`). |

---

## Time Window Semantics

When `screenshot_window_enabled` is `true`:

| Condition | Window type | Screenshot saved when |
|---|---|---|
| `start < end` | Same-day (e.g., 08:00–18:00) | `start ≤ now < end` |
| `start > end` | Midnight-spanning (e.g., 22:00–06:00) | `now ≥ start OR now < end` |
| `start == end` | Degenerate | Treated as disabled (screenshots at any hour); warning logged |

All comparisons use the local wall-clock time at the moment of the detection event.

---

## Compatibility Rules

1. **Missing keys**: Any missing field is silently replaced with its default value on load. Consumers MUST NOT treat missing fields as errors.
2. **Unknown keys**: Unknown fields are ignored. Consumers MUST tolerate forward-compatible additions.
3. **Type errors / corrupt file**: If the file cannot be parsed as valid JSON or a field fails type validation, the entire file is reset to defaults and re-written. A warning is emitted to the application log.
4. **Atomic writes**: The file MUST be written via a `.tmp` + atomic rename to prevent partial-write corruption.
5. **Invalid `HH:MM` values**: If `screenshot_window_start` or `screenshot_window_end` cannot be parsed as `HH:MM`, the field resets to its default and a warning is logged. The rest of the config is unaffected.

---

## Breaking vs. Non-Breaking Changes

| Change | Type | Required action |
|---|---|---|
| Add a new optional field with a default | Non-breaking | Update schema docs only |
| Remove a field | **Breaking** | Bump schema version, write migration |
| Rename a field | **Breaking** | Bump schema version, write migration |
| Change a field's type | **Breaking** | Bump schema version, write migration |
| Tighten a constraint (e.g., min value) | **Breaking** | Bump schema version, write migration |

For any breaking change: add `"schema_version": N` to the schema, add a migration function in `config.py`, and update this document.

---

## Change Log

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-02-28 | Initial schema (`camera_index`, `confidence_threshold`, `cooldown_seconds`, `sound_library_paths`, `autostart`) |
| 1.1 | 2026-03-01 | Added `screenshots_root_folder`, `screenshot_window_enabled`, `screenshot_window_start`, `screenshot_window_end` (non-breaking) |
