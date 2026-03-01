# Contract: Settings Configuration Schema

**Feature**: `004-add-record-sound`
**Date**: 2026-03-01
**File**: `user_config_dir("CatGuard")/settings.json`

---

## Overview

`settings.json` is the single persisted configuration file for CatGuard. This feature
adds two new fields. All existing fields are unchanged and continue to be required
for the app to function.

---

## Schema (full, post-feature)

```json
{
  "camera_index": 0,
  "confidence_threshold": 0.25,
  "cooldown_seconds": 15.0,
  "sound_library_paths": [],
  "autostart": false,
  "screenshots_root_folder": "",
  "screenshot_window_enabled": false,
  "screenshot_window_start": "22:00",
  "screenshot_window_end": "06:00",
  "use_default_sound": true,
  "pinned_sound": ""
}
```

---

## New Fields (this feature)

### `use_default_sound`

| Property | Value |
|----------|-------|
| Type | `boolean` |
| Default | `true` |
| Required | No (missing key falls back to default on load) |
| Persisted by | `save_settings()` |

When `true`, the built-in `default.wav` plays on every detection event, regardless
of `sound_library_paths` and `pinned_sound`.

### `pinned_sound`

| Property | Value |
|----------|-------|
| Type | `string` (absolute file path, or empty string) |
| Default | `""` |
| Required | No (missing key falls back to `""`) |
| Persisted by | `save_settings()` |

Absolute path to the sound file that should always play when `use_default_sound` is
`false` and a specific sound is selected in the "Play Only This Sound" dropdown.
Empty string means "All" — random selection from `sound_library_paths`.

If the file at `pinned_sound` no longer exists on disk when `settings.json` is loaded,
the field is silently reset to `""` by the Pydantic validator (same pattern as
`sound_library_paths`).

---

## Backward Compatibility

- Existing `settings.json` files that do not contain `use_default_sound` or
  `pinned_sound` are loaded correctly; `load_settings()` merges loaded data over
  defaults, so both fields are silently populated with their defaults.
- No migration script is required.
- No breaking change to any existing field.

---

## File Location by Platform

| Platform | Path |
|----------|------|
| Windows | `%APPDATA%\CatGuard\settings.json` |
| Linux | `~/.config/CatGuard/settings.json` |
| macOS | `~/Library/Application Support/CatGuard/settings.json` |

Resolved at runtime via `platformdirs.user_config_dir("CatGuard")`.
