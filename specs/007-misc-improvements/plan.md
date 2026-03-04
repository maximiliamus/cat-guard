# Implementation Plan: Miscellaneous UI and Behavior Improvements

**Branch**: `007-misc-improvements` | **Date**: March 4, 2026 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/007-misc-improvements/spec.md`

## Summary

Five independent improvements to CatGuard: (1) a `TimeWindowMonitor` daemon that auto-pauses/resumes the camera based on a configurable daily time window, (2) a `SleepWatcher` daemon that detects system wake events via time-jump polling and restores the camera, (3) a Rename button in the sound library UI that stops playback and renames the file on disk, (4) annotation label placement fallback when the bounding box is near a frame edge, and (5) locale-aware date/time formatting in detection frame overlays.

All five items are independent slices; each can be implemented and tested without the others.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: tkinter (UI), pystray (tray), pygame-ce (audio), OpenCV + Pillow (frame annotation), pydantic (settings), pywin32 ≥ 306 (Windows — already in deps)  
**Storage**: JSON settings file via `platformdirs.user_config_dir("CatGuard")`  
**Testing**: pytest, pytest-mock  
**Target Platform**: Windows primary (pywin32), macOS and Linux secondary  
**Project Type**: Desktop GUI application  
**Performance Goals**: <200 ms p95 latency for detection (unchanged); sleep watcher adds <1 ms CPU overhead  
**Constraints**: <100 MB memory footprint; no new runtime dependencies permitted  
**Scale/Scope**: Single-user; 5 isolated changes across 4 existing modules + 2 new modules

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✅ PASS | All new functions will have unit tests written before implementation |
| II. Observability & Logging | ✅ PASS | Each new module and modified function adds `logger.*` calls |
| III. Simplicity & Clarity | ✅ PASS | Two new modules (`sleep_watcher.py`, `time_window.py`) are small single-responsibility classes; no unnecessary abstractions |
| IV. Integration Testing | ✅ PASS | `TimeWindowMonitor` and `SleepWatcher` interact with `DetectionLoop`; integration tests required |
| V. Versioning | ✅ PASS | New settings fields are backward-compatible with defaults; MINOR version bump warranted |

**Post-design re-check**: All gates still pass. New config fields all have safe defaults (disabled). No breaking changes to existing interfaces.

## Project Structure

### Documentation (this feature)

```text
specs/007-misc-improvements/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── config.md        ← Phase 1 output
└── tasks.md             ← Phase 2 output (created by /speckit.tasks, NOT this command)
```

### Source Code Changes

```text
src/catguard/
├── config.py            MODIFY — add tracking_window_enabled/start/end fields
├── annotation.py        MODIFY — locale-aware timestamp; annotation label fallback
├── main.py              MODIFY — locale init; wire TimeWindowMonitor + SleepWatcher
├── sleep_watcher.py     NEW    — time-jump polling daemon for sleep/wake detection
├── time_window.py       NEW    — TimeWindowMonitor daemon for auto-pause/resume
└── ui/
    └── settings_window.py  MODIFY — Rename button + tracking window UI controls

tests/
├── unit/
│   ├── test_annotation.py          MODIFY — new tests for fallback logic + locale format
│   ├── test_config.py              MODIFY — new tests for tracking_window_* fields
│   ├── test_sleep_watcher.py       NEW    — unit tests for SleepWatcher
│   ├── test_time_window.py         NEW    — unit tests for TimeWindowMonitor
│   └── test_settings_window.py     MODIFY — new tests for Rename flow
└── integration/
    ├── test_pause_resume.py        MODIFY — add time-window boundary crossing tests
    └── test_sleep_resume.py        NEW    — integration test for wake→camera-restore flow
```

**Structure Decision**: Single-project layout. All changes stay within `src/catguard/`. Two new small modules added. No new packages, no new top-level directories.

## Phase 0: Research — Resolved

See [research.md](research.md) for full findings. Summary of decisions:

| ID | Question | Resolution |
|----|----------|------------|
| R-001 | Sleep/wake cross-platform detection | Time-jump polling daemon (10 s sleep, >30 s gap = wake) — zero new deps |
| R-002 | Locale-aware datetime | `locale.setlocale(LC_TIME, '')` at startup + `strftime('%x  %X')` |
| R-003 | Off-screen label placement | Refactor `_draw_labelled_box()` to test 5 candidate positions in spec order |
| R-004 | Rename during active playback | `pygame.mixer.stop()` before dialog; file not held open after stop |
| R-005 | Time window polling & state | 30 s poll; `_monitor_paused` flag guards against overriding manual pause |
| R-006 | Separate tracking vs screenshot window | `tracking_window_*` fields added; `screenshot_window_*` subsequently removed — `tracking_window_*` now governs both screenshot and detection windows (post-implementation consolidation) |

## Phase 1: Design

### 1.1 Data Model

See [data-model.md](data-model.md) for full entity definitions.

Key additions to `Settings`:

```python
tracking_window_enabled: bool = False
tracking_window_start: str = "08:00"    # HH:MM local time
tracking_window_end: str = "18:00"      # HH:MM; supports cross-midnight
```

### 1.2 New Modules

**`sleep_watcher.py`** — `SleepWatcher(on_wake: Callable[[], None])`

- `start()` → spawns daemon thread
- `stop()` → signals thread to exit
- Thread: sleeps 10 s, checks if wall-clock elapsed > 30 s; calls `on_wake()` if yes

**`time_window.py`** — `TimeWindowMonitor(detection_loop, settings, on_state_changed)`

- `start()` / `stop()`  
- `notify_user_resume()` → sets `_user_override` flag (called by tray Resume handler)
- Internal 30 s poll: evaluate `_is_in_window()` → trigger pause/resume as needed
- `_is_in_window(now, start, end)` handles cross-midnight ranges

### 1.3 Modified Functions

| File | Function | Change |
|------|----------|--------|
| `annotation.py` | `_draw_top_bar()` | Replace `strftime("%Y-%m-%d  %H:%M:%S")` → `strftime('%x  %X')` |
| `annotation.py` | `_draw_labelled_box()` | Add 5-candidate fallback loop; use `frame.shape[:2]` for bounds |
| `settings_window.py` | `btn_frame` block | Add `Rename` button; add `_rename_path()` closure |
| `settings_window.py` | tracking window section | Add `tracking_window_enabled` checkbox + start/end time Spinboxes |
| `main.py` | `main()` | Add `locale.setlocale(locale.LC_TIME, '')` + wire `TimeWindowMonitor` + `SleepWatcher` |
| `tray.py` | `on_pause_continue_clicked` | Call `time_window_monitor.notify_user_resume()` on resume |

### 1.4 Interface Contracts

See [contracts/config.md](contracts/config.md) for updated Settings schema.

## Complexity Tracking

No constitution violations. All changes are straightforward extensions of existing patterns.

---

## Amendments (post-implementation polish)

Changes made after the original spec was completed:

### A-001 — `screenshot_window_*` fields removed
`screenshot_window_enabled/start/end` were removed from `Settings` and from the UI. `tracking_window_*` now governs both detection and screenshot time-gating. Existing settings files with the old keys silently ignore them on load.

### A-002 — Window geometry persistence
New module `src/catguard/ui/geometry.py` provides `load_win_geometry(key)` / `save_win_geometry(key, value)`. Geometry is stored in `%APPDATA%\CatGuard\windows.json` (one JSON dict keyed by window name). Three windows persist geometry across restarts:

| Key | Window |
|-----|--------|
| `settings_window` | Settings Toplevel (position + size) |
| `rename_dialog` | Rename sound dialog (position + size) |
| `main_window` | Live-view window (position only; size is always set from the camera frame) |

### A-003 — Main window unresizable, always fits frame
`MainWindow` now calls `resizable(False, False)`. The window and canvas are resized to match the camera frame dimensions on **every** `update_frame()` call (not just the first). On startup, only the saved position (`+X+Y`) is restored from disk; size is never cached.

### A-004 — Log directory
Application log moved from `platformdirs.user_log_dir("CatGuard")` to `user_data_dir("CatGuard") / "logs"` so all runtime data (settings, geometry, alerts, logs) lives under a single `%APPDATA%\CatGuard\` directory on Windows.

### A-005 — Rename UX polish
- Dialog is resizable horizontally (Entry field grows with window width).
- After the dialog closes (OK, Cancel, ESC, or X), focus always returns to the sound-library listbox, the renamed item is re-selected, and the Rename button is re-enabled.
- Dialog position/size persists between invocations via A-002.
