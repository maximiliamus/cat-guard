# Implementation Plan: Tray Directory Shortcuts

**Branch**: `015-directory-menu-links` | **Date**: 2026-03-28 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/015-directory-menu-links/spec.md`

## Summary

Add two tray shortcuts, `Tracking Directory` and `Photos Directory`, immediately after the existing `Pause` / `Continue` item with a separator before them and the existing separator before `Exit` preserved. The implementation stays inside the tray layer by reusing the existing settings fields (`tracking_directory`, `photos_directory`), normalizing and creating directories before launch, opening them with the platform-native file manager, and surfacing failures via the existing non-blocking tray notification path.

## Technical Context

**Language/Version**: Python 3.14+  
**Primary Dependencies**: `pystray`, `tkinter` root dispatch, `pydantic` settings model, `Pillow`, Python standard library (`pathlib`, `os`, `subprocess`, `platform`)  
**Storage**: Existing filesystem directories configured in `Settings` (`tracking_directory`, `photos_directory`); no new persisted data  
**Testing**: `pytest` + `pytest-mock`  
**Target Platform**: Windows, macOS, Linux desktop environments  
**Project Type**: Desktop application (tray-based utility)  
**Performance Goals**: Menu rebuild remains effectively instant; directory open request is dispatched from one tray click; missing-directory creation adds no visible UI delay on local disks  
**Constraints**: No new runtime dependencies; preserve existing tray item behavior; keep `Exit` last; errors must be non-blocking; support platform-native folder launchers  
**Scale/Scope**: Small tray-only feature touching one runtime module plus tests and planning docs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✅ PASS | The feature is driven by tray unit tests that pin exact menu order and folder-opening behavior before code changes |
| II. Observability & Logging | ✅ PASS | Failures route through existing tray notifications and logger paths instead of failing silently |
| III. Simplicity & Clarity | ✅ PASS | No new settings, services, or modules are required; behavior stays localized to tray menu construction |
| IV. Integration Testing | ✅ PASS | The design includes an integration test for tray callback wiring plus manual cross-platform verification of native folder launch |
| V. Versioning & Breaking Changes | ✅ PASS | This is a backward-compatible tray enhancement with no config schema change and no migration impact |

**Post-design re-check**: All gates still pass. The design remains small, testable, and uses only established filesystem-opening patterns already present elsewhere in the codebase.

## Project Structure

### Documentation (this feature)

```text
specs/015-directory-menu-links/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── tray-menu.md
└── tasks.md             # Created later by /speckit.tasks
```

### Source Code (repository root)

```text
src/catguard/
└── tray.py                         # Add directory opener helper + new tray items

tests/unit/
└── test_tray.py                    # Exact menu order + folder opener dispatch tests

tests/integration/
└── test_tray_directory_shortcuts.py  # Planned: tray callback wiring with temp directories
```

**Structure Decision**: Single-project layout. The feature is a localized tray enhancement and should not introduce a new module unless later reuse justifies extracting a shared directory-opening utility.

## Complexity Tracking

> No Constitution Check violations requiring justification.

## Implementation Design

### A. Directory Opening Helper in `src/catguard/tray.py`

- Add a small helper that:
  - accepts a configured directory path,
  - strips surrounding whitespace,
  - expands user-home shortcuts,
  - resolves relative paths to absolute paths,
  - creates the directory when missing,
  - dispatches to the native file manager:
    - Windows: `os.startfile(...)`
    - macOS: `open`
    - Linux: `xdg-open`
- Keep launcher invocation thin and synchronous, with subprocess calls using `check=False` so platform launch failures flow back as caught exceptions rather than terminating the app.

### B. Error Handling Strategy

- Wrap tray menu callbacks around the directory-opening helper rather than embedding filesystem/launcher logic inline.
- On failure:
  - log the error with the directory label,
  - use the existing `notify_error(icon, ...)` helper for a non-blocking tray notification,
  - leave the tray icon and menu fully usable.

### C. Tray Menu Wiring

- Update both `build_tray_icon()` and `update_tray_menu()` so they emit the same menu structure:

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

- Keep the directory items visible in both tracking states.
- Preserve the existing pause/resume handlers without coupling directory actions to tracking state changes.

### D. Test Strategy

#### Unit Tests

- `tests/unit/test_tray.py`
  - exact menu order in active state,
  - exact menu order survives `update_tray_menu()` rebuilds,
  - `Tracking Directory` and `Photos Directory` appear in both initial and rebuilt menus,
  - directory opener dispatches the correct OS command on Windows/macOS/Linux,
  - missing directories are created before launch.

#### Integration Test

- `tests/integration/test_tray_directory_shortcuts.py`
  - build a tray menu with temporary tracking/photos directories,
  - invoke the captured callbacks,
  - verify the correct configured directory is targeted,
  - verify missing directories are created,
  - mock the platform launcher command while exercising real filesystem effects.

#### Manual Verification

- Use `quickstart.md` to confirm native file-manager launch on a real desktop session, since CI cannot reliably assert actual Explorer/Finder/file-manager windows.

## Delivery Notes

- No config schema changes are required because the feature reuses existing `tracking_directory` and `photos_directory` settings.
- No new user-facing windows or dialogs are added.
- This feature should remain independent from photo capture, screenshot saving, and settings UI flows except for reading the already-configured directory paths.
