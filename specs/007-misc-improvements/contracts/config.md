# Contract: Settings Configuration Schema

**Feature**: 007-misc-improvements  
**Date**: March 4, 2026  
**File**: `%APPDATA%\CatGuard\settings.json` (Windows) | `~/.config/CatGuard/settings.json` (Linux/macOS)

---

## Schema (full — including new fields)

```json
{
  "camera_index": 0,
  "confidence_threshold": 0.25,
  "cooldown_seconds": 15.0,
  "sound_library_paths": [],
  "autostart": false,
  "screenshots_root_folder": "",
  "use_default_sound": true,
  "pinned_sound": "",
  "tracking_window_enabled": false,
  "tracking_window_start": "08:00",
  "tracking_window_end": "18:00"
}
```

## New Fields (007-misc-improvements)

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `tracking_window_enabled` | `boolean` | `false` | — | Enables daily active monitoring time window. When `false`, all other `tracking_window_*` fields are ignored and the camera runs continuously. |
| `tracking_window_start` | `string` | `"08:00"` | Format: `HH:MM` (00:00–23:59) | Start of the daily window (local 24-hour time). Camera turns on at this time. |
| `tracking_window_end` | `string` | `"18:00"` | Format: `HH:MM` (00:00–23:59) | End of the daily window (local 24-hour time). Camera turns off at this time. If `end < start`, the window spans midnight. |

## Existing Fields (unchanged)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `camera_index` | `integer` | `0` | OpenCV VideoCapture index |
| `confidence_threshold` | `number` | `0.25` | YOLO detection threshold [0.0–1.0] |
| `cooldown_seconds` | `number` | `15.0` | Minimum seconds between alerts |
| `sound_library_paths` | `array[string]` | `[]` | Absolute paths to MP3/WAV files. File rename updates entries in-place. |
| `autostart` | `boolean` | `false` | Start with OS login |
| `screenshots_root_folder` | `string` | `""` | Empty = OS default Pictures/CatGuard |
| `use_default_sound` | `boolean` | `true` | Always play built-in default sound |
| `pinned_sound` | `string` | `""` | Path to always-play sound; empty = random. Updated automatically after file rename. |

## Behavioral Notes

- **Rename side-effects**: When a sound file is renamed via the UI, the settings file is immediately re-saved with the updated paths in `sound_library_paths` and `pinned_sound` (if affected).
- **Backward compatibility**: Existing settings files without `tracking_window_*` keys load cleanly; pydantic applies the documented defaults. The `screenshot_window_*` fields (present in settings files written by features 003–005) are silently ignored on load.
- **Validation errors**: If `tracking_window_start` or `tracking_window_end` do not match `HH:MM`, the settings file is treated as corrupt and reset to defaults (existing behavior for all corrupted settings files).
- **Supplementary files** (same directory as `settings.json`):
  - `windows.json` — persists per-window geometry strings (position + size); written on each window close.
  - `logs/catguard.log` — rotating application log (max 5 MB × 3 backups).
