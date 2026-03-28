# Quickstart: Tray Directory Shortcuts

**Branch**: `015-directory-menu-links` | **Date**: 2026-03-28  
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Prerequisites

1. Activate the project virtual environment.
2. Install dependencies if needed: `pip install -e ".[dev]"`.
3. Start CatGuard from the repository root:

```bash
python -m catguard
```

## Manual Validation

### 1. Confirm tray menu order

1. Open the tray menu.
2. Verify the order is:

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

3. Click `Pause`, reopen the menu, and verify the order is unchanged except `Pause` becomes `Continue`.

### 2. Open tracking directory

1. In `Settings…`, configure `tracking_directory` to a test folder that does not yet exist.
2. Close Settings and click `Tracking Directory` from the tray.
3. Verify:
   - the directory is created,
   - the system file manager opens to that folder,
   - the app remains responsive.

### 3. Open photos directory

1. In `Settings…`, configure `photos_directory` to a second test folder that does not yet exist.
2. Click `Photos Directory` from the tray.
3. Verify:
   - the directory is created,
   - the system file manager opens to that folder,
   - the app remains responsive.

### 4. Failure path smoke test

1. Configure one of the directory settings to a location the current user cannot create or open.
2. Click the corresponding tray item.
3. Verify:
   - CatGuard stays running,
   - a non-blocking tray error notification appears,
   - other tray actions still work afterward.

## Suggested Automated Checks

Run the tray-focused tests:

```bash
.venv\Scripts\python.exe -m pytest tests\unit\test_tray.py -q
```

When the integration test is added, run:

```bash
.venv\Scripts\python.exe -m pytest tests\integration\test_tray_directory_shortcuts.py -q
```
