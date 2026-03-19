# Contract: Settings JSON Schema (Log Fields)

**Feature**: `011-log-viewer-search` | **Date**: 2026-03-19

This contract documents the three new fields added to `settings.json` by this feature. All other existing fields are unchanged.

---

## New Fields

```json
{
  "logs_directory": "<absolute path string>",
  "max_log_entries": 2048,
  "log_trim_batch_size": 205
}
```

| Key | JSON type | Minimum | Default | Notes |
|-----|-----------|---------|---------|-------|
| `logs_directory` | `string` | — | platform log dir | Must not contain `..`; directory is created on first write |
| `max_log_entries` | `integer` | `2048` | `2048` | Values below minimum are rejected by Pydantic and reset to default on load |
| `log_trim_batch_size` | `integer` | `205` | `205` | Values below minimum are rejected by Pydantic and reset to default on load |

## Backward Compatibility

- Existing `settings.json` files without these keys are silently upgraded: the merge-on-load pattern in `load_settings()` fills in defaults for missing keys.
- No migration script required.
- Downgrading: an older version of CatGuard will ignore unknown keys in `settings.json` (Pydantic ignores extra fields by default — `model_config` has no `extra="forbid"`).

## Validation Rules

- `logs_directory` containing `..` → `ValidationError` → reset to default on load.
- `max_log_entries < 2048` → `ValidationError` → reset to `2048` on load.
- `log_trim_batch_size < 205` → `ValidationError` → reset to `205` on load.
- UI Save guard: the Settings window validates spinbox values before calling `on_settings_saved`; values below minimum show an inline error dialog and abort the save.
