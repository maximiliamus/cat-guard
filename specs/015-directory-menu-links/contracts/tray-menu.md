# Contract: Tray Menu Directory Shortcuts

**Location**: `src/catguard/tray.py`  
**Responsibility**: Define the tray menu structure and behavioral guarantees for the two directory shortcut items

## Menu Structure Contract

Both `build_tray_icon()` and `update_tray_menu()` MUST produce the same menu structure:

```text
1. Live View
2. Logs
3. Settings…
4. ─────────
5. Pause / Continue
6. ─────────
7. Tracking Directory
8. Photos Directory
9. ─────────
10. Exit
```

### Invariants

- `Pause` / `Continue` is the only state-dependent label.
- `Tracking Directory` and `Photos Directory` are present in both active and paused tracking states.
- `Exit` remains the last item.
- A separator appears immediately before the directory shortcut pair.

## Shortcut Behavior Contract

### `Tracking Directory`

- Target source: `settings.tracking_directory`
- Required behavior:
  - normalize the configured path,
  - create the directory if it does not exist,
  - open the directory in the platform-native file manager,
  - if launch fails, log the error and show a non-blocking tray notification.

### `Photos Directory`

- Target source: `settings.photos_directory`
- Required behavior:
  - normalize the configured path,
  - create the directory if it does not exist,
  - open the directory in the platform-native file manager,
  - if launch fails, log the error and show a non-blocking tray notification.

## Platform Dispatch Contract

| Platform | Expected launcher |
|----------|-------------------|
| Windows | `os.startfile(path)` |
| macOS | `subprocess.run(["open", path], check=False)` |
| Linux | `subprocess.run(["xdg-open", path], check=False)` |

## Error Handling Contract

- Directory shortcut failures MUST NOT:
  - exit the app,
  - disable the tray icon,
  - alter pause/resume state,
  - remove any tray menu items.
- Directory shortcut failures MUST:
  - be logged,
  - notify the user through the existing tray-notification mechanism,
  - leave the tray fully usable for subsequent actions.
