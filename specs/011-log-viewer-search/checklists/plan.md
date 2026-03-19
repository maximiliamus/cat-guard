# Plan Review Checklist: Log Viewer with Search, Clipboard Copy, and Auto-Trim

**Purpose**: Lightweight author self-review — validate plan quality, clarity, and completeness before task generation
**Created**: 2026-03-19
**Feature**: [plan.md](../plan.md)
**Focus**: Design decisions (A–F) and test plan — equally weighted; plan-internal quality only

---

## Design Decisions — Completeness

- [x] CHK001 - Are all five modified files (`config.py`, `main.py`, `tray.py`, `settings_window.py`) and two new files (`log_manager.py`, `ui/log_viewer.py`) listed in the Project Structure source tree? [Completeness, Plan §Project Structure]
- [x] CHK002 - Is the `on_settings_saved` extension (detect `logs_directory` change → close old handler → open new `BatchTrimFileHandler`) fully specified in the plan, not just implied? [Completeness, Plan §Design C]
- [x] CHK003 - Is `SettingsFormModel` explicitly listed as requiring `from_settings()` and `to_settings()` extension for the three new fields? [Completeness, Plan §Design F]
- [x] CHK004 - Is the `apply_app_icon(win)` call for the log viewer `Toplevel` mentioned in the plan, consistent with how all other windows in the codebase receive the app icon? [Gap, Plan §Design E] — **Fixed**: added to Design E
- [x] CHK005 - Is log viewer window geometry persistence (save/restore position via `save_win_geometry` / `load_win_geometry`) addressed in the plan? [Gap, Plan §Design E] — **Fixed**: added to Design E

---

## Design Decisions — Clarity

- [x] CHK006 - Is the `BatchTrimFileHandler._trim()` locking strategy described precisely enough — specifically, is it clear that `self.lock` is already held by the time `_trim()` is called from within `emit()`? [Clarity, Plan §Design A]
- [x] CHK007 - Is the module-level `_file_handler` variable (used to access the handler from `on_settings_saved`) named and placed clearly in the plan's description of `main.py` changes? [Clarity, Plan §Design C]
- [x] CHK008 - Are both locations where the tray menu is constructed (`build_tray_icon` and `update_tray_menu`) explicitly called out as requiring the "Logs" item addition? [Clarity, Plan §Design D]
- [x] CHK009 - Is the exact position of the "Logs" `pystray.MenuItem` within the menu order stated (e.g., after "Open", before "Settings…") in the plan? [Clarity, Plan §Design D]
- [x] CHK010 - Is the `init order swap` change described with a clear before/after in `main.py` — specifically that `load_settings()` moves above `_configure_logging()`? [Clarity, Plan §Design C]
- [x] CHK011 - Is the `errors="replace"` encoding parameter for log file reading specified in the plan (Design E) rather than only in the contracts document? [Completeness, Plan §Design E] — **Fixed**: added to `_do_refresh()` in Design E

---

## Design Decisions — Consistency

- [x] CHK012 - Is the `root.after(0, ...)` dispatch pattern for the "Logs" tray handler consistent with how "Open" and "Settings…" handlers are dispatched, as described in the plan? [Consistency, Plan §Design D]
- [x] CHK013 - Do the `BatchTrimFileHandler` constructor parameter names in the plan (`max_entries`, `batch_size`) match the settings field names (`max_log_entries`, `log_trim_batch_size`) used throughout the spec and data model? [Consistency, Plan §Design A, Data Model §1] — **Fixed**: mapping comment added to constructor in Design A

---

## Test Plan — Coverage

- [x] CHK014 - Is there a test case for the `on_settings_saved` handler reconfiguration path (i.e., when `logs_directory` changes, old handler is removed and new one is added)? [Gap, Plan §Test Plan] — **Fixed**: added `test_main.py` additions section with 2 tests
- [x] CHK015 - Is the log viewer window singleton behaviour (focus existing window if already open) covered by a test, or explicitly excluded with rationale? [Gap, Plan §Test Plan] — **Fixed**: explicit exclusion note added to `test_log_viewer.py` section
- [x] CHK016 - Is there a test case for the tray menu "Logs" item presence in both `build_tray_icon` and `update_tray_menu`? [Gap, Plan §Test Plan] — **Fixed**: added `test_tray.py` additions section with 2 tests
- [x] CHK017 - Are the seven `test_log_manager.py` cases sufficient to cover the batch boundary (exactly at `batch_size`, one before, one after)? [Coverage, Plan §Test Plan]

---

## Test Plan — Isolation & Quality

- [x] CHK018 - Is the test isolation strategy for `BatchTrimFileHandler` specified — does it use `tmp_path` (pytest fixture) to avoid real filesystem side effects? [Clarity, Gap, Plan §Test Plan] — **Fixed**: `tmp_path` note added above `test_log_manager.py` table
- [x] CHK019 - Are the prerequisites for the integration test `test_log_settings.py` defined — specifically, does it require a real filesystem write (no mocks) per the constitution? [Clarity, Plan §Test Plan, Constitution §IV] — **Fixed**: explicit note added above integration test table
- [x] CHK020 - Is the `test_log_viewer.py` scope explicitly bounded to `SettingsFormModel` (no-display tests), with a note on what UI behaviour is intentionally not unit-tested here? [Clarity, Plan §Test Plan] — **Fixed**: scope boundary note added above `test_log_viewer.py` table

---

## Notes

- All 20 items resolved: 10 passed as-is, 10 fixed via plan.md updates
- CHK004, CHK005, CHK011 — Design E gaps closed (icon, geometry, encoding)
- CHK013 — constructor param mapping clarified in Design A
- CHK014, CHK015, CHK016 — test plan extended with `test_main.py` and `test_tray.py` additions; singleton explicitly excluded from unit tests
- CHK018, CHK019, CHK020 — isolation and scope notes added to all affected test sections
