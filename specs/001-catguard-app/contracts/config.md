# Contract: Settings Configuration File

**Version**: 1.0  
**Format**: JSON  
**Location**:

| Platform | Path |
|---|---|
| Windows | `%APPDATA%\CatGuard\settings.json` |
| macOS | `~/Library/Application Support/CatGuard/settings.json` |
| Linux | `~/.config/CatGuard/settings.json` (respects `$XDG_CONFIG_HOME`) |

---

## Schema

```json
{
  "camera_index": 0,
  "confidence_threshold": 0.40,
  "cooldown_seconds": 15.0,
  "sound_library_paths": [
    "/home/user/sounds/hiss.mp3",
    "/home/user/sounds/spray.wav"
  ],
  "autostart": false
}
```

### Fields

| Field | Type | Required | Default | Constraints |
|---|---|---|---|---|
| `camera_index` | integer | No | `0` | ≥ 0 |
| `confidence_threshold` | number | No | `0.40` | [0.0, 1.0] |
| `cooldown_seconds` | number | No | `15.0` | > 0.0 |
| `sound_library_paths` | array of string | No | `[]` | Each element must be an absolute path to an existing MP3 or WAV file; stale paths are silently dropped on load |
| `autostart` | boolean | No | `false` | — |

---

## Compatibility Rules

1. **Missing keys**: Any missing field is silently replaced with its default value on load. Consumers MUST NOT treat missing fields as errors.
2. **Unknown keys**: Unknown fields are ignored. Consumers MUST tolerate forward-compatible additions.
3. **Type errors / corrupt file**: If the file cannot be parsed as valid JSON or a field fails type validation, the entire file is reset to defaults and re-written. A warning is emitted to the application log.
4. **Atomic writes**: The file MUST be written via a `.tmp` + atomic rename to prevent partial-write corruption.

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

## Sound Library Paths

Each entry in `sound_library_paths` is an absolute file path. Supported formats:

| Format | Extension |
|---|---|
| MP3 | `.mp3` |
| WAV | `.wav` |

Files outside these formats are silently ignored. If the list is empty or all paths are stale, the built-in default sound (`assets/sounds/default.wav`) is used.
