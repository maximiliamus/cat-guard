# Data Model: Tray Directory Shortcuts

**Branch**: `015-directory-menu-links` | **Date**: 2026-03-28  
**Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

## 1. Existing Settings Fields Reused

The feature introduces no new persisted entities. It reuses two existing `Settings` fields as the source of truth for tray shortcuts.

| Field | Type | Existing Source | Meaning |
|-------|------|-----------------|---------|
| `tracking_directory` | `str` | `src/catguard/config.py` | Root folder where tracking screenshots/session frames are stored |
| `photos_directory` | `str` | `src/catguard/config.py` | Root folder where manually captured photos are stored |

### Validation Already Provided

- Both fields already reject `..` path traversal in the settings model.
- Both fields may still be relative paths, so runtime normalization is required before tray launch.

## 2. Derived Runtime Entity: `TrayDirectoryShortcut`

The tray menu can be modeled as two concrete shortcut actions that share the same runtime behavior.

| Property | Type | Example | Notes |
|----------|------|---------|-------|
| `label` | `str` | `Tracking Directory` | User-facing tray label |
| `settings_field` | `str` | `tracking_directory` | Which settings field provides the target path |
| `error_label` | `str` | `tracking directory` | Lowercase phrase used in notifications/logs |
| `target_path` | `Path` | `C:\Users\...\CatGuard\tracking` | Normalized absolute directory path |
| `create_if_missing` | `bool` | `True` | Directory is created before launch |

### Concrete Instances

| Label | Settings field | Error label |
|-------|----------------|-------------|
| `Tracking Directory` | `tracking_directory` | `tracking directory` |
| `Photos Directory` | `photos_directory` | `photos directory` |

## 3. Runtime Flow: Open Directory Request

Each tray shortcut follows the same lifecycle:

```text
Configured settings path (str)
        ↓
Trim whitespace
        ↓
Expand user-home markers
        ↓
Resolve to absolute Path
        ↓
Create directory if missing
        ↓
Dispatch platform-native launcher
        ↓
Success: no further UI
Failure: log + tray notification
```

## 4. Platform Dispatch Mapping

| Platform | Launcher | Input |
|----------|----------|-------|
| Windows | `os.startfile(...)` | `str(target_path)` |
| macOS | `open` | `["open", str(target_path)]` |
| Linux | `xdg-open` | `["xdg-open", str(target_path)]` |

The platform mapping is a runtime contract, not persisted state.

## 5. Tray Menu State Model

The directory items are invariant across tray tracking states.

### Active Menu

```text
Live View
Logs
Settings…
─────────
Pause
─────────
Tracking Directory
Photos Directory
─────────
Exit
```

### Paused Menu

```text
Live View
Logs
Settings…
─────────
Continue
─────────
Tracking Directory
Photos Directory
─────────
Exit
```

### Invariants

- The only state-dependent label remains `Pause` / `Continue`.
- `Tracking Directory` and `Photos Directory` are present in both states.
- `Exit` remains the last menu item.
- A separator always appears immediately before the two directory shortcuts.

## 6. Error Outcome Model

| Stage | Failure Example | Required Outcome |
|-------|------------------|------------------|
| Path normalization | Empty/whitespace-only path | Raise an error to callback; user gets non-blocking tray notification |
| Directory creation | Permission denied | Log error and notify user; tray stays usable |
| Launcher dispatch | OS command unavailable or rejected | Log error and notify user; tray stays usable |

No failure in this feature should transition the app into a paused, exited, or otherwise degraded operating state.
