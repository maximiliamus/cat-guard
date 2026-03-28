# Research: Tray Directory Shortcuts

**Branch**: `015-directory-menu-links` | **Date**: 2026-03-28

## 1. Source of Truth for Directory Targets

**Decision**: Reuse `Settings.tracking_directory` and `Settings.photos_directory` directly; do not add new settings or duplicate path state in the tray layer.  
**Rationale**: The feature is purely a shortcut to folders that already exist in the app model. Reusing the existing settings keeps behavior aligned with the Storage settings UI and avoids introducing a second configuration path.  
**Alternatives considered**:
- Hard-code default CatGuard folders in tray callbacks: rejected because it would ignore user-configured directories.
- Add dedicated tray-only path fields: rejected because it creates redundant configuration for the same folders.

## 2. Missing Directory Behavior

**Decision**: Create the target directory before attempting to open it.  
**Rationale**: This matches the existing pattern already used by `open_alerts_folder()` in `src/catguard/recording.py`, where the folder is created on demand before launching the file manager. It also satisfies the spec requirement that the tray shortcut should work even before the first file has been saved there.  
**Alternatives considered**:
- Fail if the folder does not exist: rejected because it adds friction and makes the tray shortcuts unreliable on first use.
- Prompt the user before creating the folder: rejected because the feature should remain one-click and non-blocking.

## 3. Path Normalization

**Decision**: Normalize configured paths by trimming whitespace, expanding `~`, and resolving relative paths to absolute paths before creating/opening the folder.  
**Rationale**: Existing settings validation blocks `..` traversal but still permits relative paths. Normalization in the tray opener keeps the runtime behavior predictable and prevents the launcher commands from receiving ambiguous paths.  
**Alternatives considered**:
- Pass configured strings directly to the launcher: rejected because relative or whitespace-padded paths can behave inconsistently across platforms.
- Normalize paths on save in the settings model: rejected for this feature because it would broaden scope into settings persistence semantics.

## 4. Platform Launcher Pattern

**Decision**: Use the same cross-platform launcher pattern already present elsewhere in the codebase:
- Windows: `os.startfile(...)`
- macOS: `subprocess.run(["open", ...], check=False)`
- Linux: `subprocess.run(["xdg-open", ...], check=False)`  
**Rationale**: This pattern already exists in `src/catguard/recording.py` and in the local `_open_dir()` helper inside `src/catguard/ui/settings_window.py`. Reusing the same launcher choices preserves platform behavior and avoids new dependencies.  
**Alternatives considered**:
- `webbrowser.open()` for directories: rejected because it is not the right abstraction for native folder windows.
- A third-party desktop integration library: rejected because the standard library and existing patterns are already sufficient.

## 5. Error Surfacing

**Decision**: Catch directory-open failures in the tray callback and surface them through the existing `notify_error(icon, message)` tray notification path.  
**Rationale**: The tray feature should behave like other non-blocking CatGuard failures: log the issue, tell the user briefly, and keep the app running. `notify_error()` already exists for this style of UX.  
**Alternatives considered**:
- Silent logging only: rejected because the user would get no feedback after clicking a tray shortcut.
- Modal dialog: rejected because tray actions should not pull focus or block the app.

## 6. Menu Construction Strategy

**Decision**: Add the two directory items to both `build_tray_icon()` and `update_tray_menu()` using the same order and separator layout.  
**Rationale**: `pystray` menu rebuilds are already the project pattern for state changes, so both code paths must produce the same structure or the new items will disappear after a pause/resume transition.  
**Alternatives considered**:
- Add the items only in the initial build path: rejected because `update_tray_menu()` would overwrite them after the first state change.
- Extract full menu construction into a separate builder immediately: deferred because the current feature is small and does not require a larger tray refactor.

## 7. Test Coverage Shape

**Decision**: Cover the feature with tray-focused unit tests plus one planned integration test for callback wiring and real directory creation.  
**Rationale**: Unit tests are sufficient to pin the exact menu structure and OS-dispatch logic. An integration test should still exercise the tray callbacks against real temporary directories to satisfy the constitution’s emphasis on boundary verification. Native file-manager windows themselves remain a manual verification concern.  
**Alternatives considered**:
- Unit tests only: rejected because the feature crosses the tray-callback/filesystem boundary.
- Full end-to-end OS automation: rejected because native Explorer/Finder/file-manager windows are not practical or stable for CI.
