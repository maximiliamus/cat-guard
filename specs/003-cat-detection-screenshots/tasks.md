# Tasks: Screenshot on Cat Detection

**Input**: Design documents from `specs/003-cat-detection-screenshots/`  
**Prerequisites**: [plan.md](plan.md) ✓ | [spec.md](spec.md) ✓ | [data-model.md](data-model.md) ✓ | [contracts/config.md](contracts/config.md) ✓ | [quickstart.md](quickstart.md) ✓

**Tests**: Included — required by Constitution (Principle I: Test-First Development).

---

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: User story label (US1–US4) — required for all user-story phase tasks
- Exact file paths included in every task description

---

## Phase 1: Setup

**Purpose**: Create the new module stub so all subsequent test and implementation tasks have a stable import target.

- [ ] T001 Create empty `src/catguard/screenshots.py` stub (module docstring + placeholder `pass`; no logic yet)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extend the two core data structures (`DetectionEvent`, `Settings`) that every user story depends on. Tests are written first (TDD).

**⚠️ CRITICAL**: No user story work can begin until T002–T005 are complete.

- [ ] T002 [P] Write failing unit tests for `DetectionEvent.frame_bgr` optional field in `tests/unit/test_detection.py`
- [ ] T003 [P] Write failing unit tests for 4 new Settings fields (`screenshots_root_folder`, `screenshot_window_enabled`, `screenshot_window_start`, `screenshot_window_end`) in `tests/unit/test_config.py`
- [ ] T004 [P] Add `frame_bgr: Optional[np.ndarray] = None` field to `DetectionEvent` dataclass in `src/catguard/detection.py` (makes T002 pass)
- [ ] T005 [P] Add 4 new screenshot fields to `Settings` model with defaults and `HH:MM` validator in `src/catguard/config.py` (makes T003 pass)

**Checkpoint**: `pytest tests/unit/test_detection.py tests/unit/test_config.py` passes — user story work can now begin.

---

## Phase 3: User Story 1 — Automatic Screenshot on Detection (Priority: P1) 🎯 MVP

**Goal**: Every cat-detection event that plays a sound saves a max-compression JPEG frame to `<root>/<yyyy-mm-dd>/<HH-MM-SS>.jpg`, provided the main window is closed.

**Independent Test**: Trigger a detection event (main window closed, root folder configured) and verify a `.jpg` file appears at the correct path within 2 seconds.

### Tests for User Story 1

> **Write FIRST — all tests must FAIL before implementation begins**

- [ ] T006 [P] [US1] Write failing unit tests for `resolve_root()`, `build_filepath()`, and core `save_screenshot()` path (happy path + same-second collision) in `tests/unit/test_screenshots.py`
- [ ] T007 [P] [US1] Write failing integration test verifying a real `.jpg` file is created on disk for a synthetic detection event in `tests/integration/test_screenshot_integration.py`
- [ ] T010a [P] [US1] Write failing unit tests for `_main_window_visible` toggling in `tests/unit/test_main_window.py` — verify `show_or_focus()` sets the attribute to `True` and `_on_close()` sets it to `False`

### Implementation for User Story 1

- [ ] T008 [US1] Implement `resolve_root()` (default `Pictures/CatGuard` via `platformdirs.user_pictures_dir()`), `build_filepath()` (date folder + `HH-MM-SS[-N].jpg` collision-safe naming), and core `save_screenshot()` skeleton (no error handling yet, no time-window check yet) in `src/catguard/screenshots.py`
- [ ] T009 [P] [US1] Pass `frame_bgr=frame` to `DetectionEvent` for `SOUND_PLAYED` events in `DetectionLoop._run()` in `src/catguard/detection.py`
- [ ] T010 [P] [US1] Set `root._main_window_visible = False` at startup and toggle it to `True`/`False` in `MainWindow.show_or_focus()` and `MainWindow._on_close()` in `src/catguard/ui/main_window.py` ← after T010a
- [ ] T011 [US1] Wire `save_screenshot()` into `on_cat_detected()` in `src/catguard/main.py`: pass `is_window_open=lambda: getattr(root, "_main_window_visible", False)` and a no-op `on_error` placeholder; depends on T008, T009, T010

**Checkpoint**: `pytest tests/unit/test_screenshots.py tests/integration/test_screenshot_integration.py` passes. Run [quickstart.md](quickstart.md) steps 3–4 manually.

---

## Phase 4: User Story 2 — Configure Screenshots Root Folder (Priority: P1)

**Goal**: User can view and change the screenshots root folder in the Settings window via a folder-picker; the choice is persisted and takes effect on the next detection.

**Independent Test**: Change root folder in Settings, trigger a detection, confirm the screenshot appears in the new location.

### Tests for User Story 2

> **Write FIRST — tests must FAIL before implementation begins**

- [ ] T012 [P] [US2] Write failing unit tests for `SettingsFormModel.screenshots_root_folder` field (`from_settings`, `to_settings`, round-trip) in `tests/unit/test_settings_window.py`

### Implementation for User Story 2

- [ ] T013 [US2] Add `screenshots_root_folder: str` field to `SettingsFormModel.from_settings()` and `to_settings()` in `src/catguard/ui/settings_window.py` (makes T012 pass)
- [ ] T014 [US2] Add **Screenshots** section to `open_settings_window()` in `src/catguard/ui/settings_window.py`: read-only entry showing the resolved effective path, **Browse…** folder-picker button, and a note showing the OS default when the field is empty; wire to `model.screenshots_root_folder`

**Checkpoint**: Open Settings → change root folder → save → trigger detection → screenshot appears in new folder.

---

## Phase 5: User Story 3 — Graceful Failure Handling (Priority: P2)

**Goal**: Any screenshot save failure logs the error and shows a tray balloon; the alert sound and detection continue unaffected.

**Independent Test**: Set a read-only root folder, trigger a detection — sound plays, tray notification appears, no crash.

### Tests for User Story 3

> **Write FIRST — tests must FAIL before implementation begins**

- [ ] T015 [P] [US3] Write failing unit tests for `save_screenshot()` error paths (`OSError`, `cv2` encoding failure) — verify `on_error` callback is invoked and exception does not propagate in `tests/unit/test_screenshots.py`
- [ ] T016 [P] [US3] Write failing unit test for `notify_error()` tray helper (verify `icon.notify()` is called with the correct message) in `tests/unit/test_tray.py`

### Implementation for User Story 3

- [ ] T017 [US3] Add `notify_error(icon, message: str)` helper to `src/catguard/tray.py` — calls `icon.notify(message, "CatGuard")` (makes T016 pass)
- [ ] T018 [US3] Wrap the JPEG-write block in `save_screenshot()` with `try/except`; on failure call `logger.error(...)` and `on_error(msg)` in `src/catguard/screenshots.py` (makes T015 pass)
- [ ] T019 [US3] Replace the no-op `on_error` placeholder in `main.py` with `lambda msg: notify_error(tray_icon, msg)`; pass `tray_icon` reference into `on_cat_detected` in `src/catguard/main.py`

**Checkpoint**: `pytest tests/unit/test_screenshots.py tests/unit/test_tray.py` passes. Run [quickstart.md](quickstart.md) step 7 manually.

---

## Phase 6: User Story 4 — Restrict Screenshots to Time Window (Priority: P2)

**Goal**: User can enable a daily time window (start + end `HH:MM`, can span midnight) in Settings; screenshots are suppressed outside the window while sounds continue to fire.

**Independent Test**: Enable window with a range excluding the current time → trigger detection → sound plays, no screenshot created; then include current time → screenshot created.

### Tests for User Story 4

> **Write FIRST — tests must FAIL before implementation begins**

- [ ] T020 [P] [US4] Write failing unit tests for `is_within_time_window()` covering: window disabled, same-day range (inside/outside), midnight-spanning range (inside/outside at 23:30/14:00), and degenerate equal-times case in `tests/unit/test_screenshots.py`
- [ ] T021 [P] [US4] Write failing unit tests for `SettingsFormModel` time-window fields (`screenshot_window_enabled`, `screenshot_window_start`, `screenshot_window_end` — `from_settings`, `to_settings`, round-trip) in `tests/unit/test_settings_window.py`

### Implementation for User Story 4

- [ ] T022 [US4] Implement `is_within_time_window(settings) -> bool` in `src/catguard/screenshots.py`: parse `HH:MM`, handle same-day and midnight-spanning ranges, degenerate equal-times case with log warning (makes T020 pass)
- [ ] T023 [US4] Add `screenshot_window_enabled`, `screenshot_window_start`, `screenshot_window_end` to `SettingsFormModel.from_settings()` and `to_settings()` in `src/catguard/ui/settings_window.py` (makes T021 pass)
- [ ] T024 [US4] Add time-window subsection to **Screenshots** section in `open_settings_window()` in `src/catguard/ui/settings_window.py`: checkbox (`screenshot_window_enabled`), two `HH:MM` spinboxes (start/end) that enable/disable with the checkbox state; wire to model fields
- [ ] T025 [US4] Add `is_within_time_window(settings)` guard to `save_screenshot()` in `src/catguard/screenshots.py` — return early (no file, no error) when outside the window (makes full T020 integration pass)

**Checkpoint**: `pytest tests/unit/test_screenshots.py tests/unit/test_settings_window.py` passes. Run [quickstart.md](quickstart.md) steps 6–7 manually.

---

## Final Phase: Polish & Cross-Cutting Concerns

- [ ] T026 [P] Run full test suite and fix any regressions: `pytest` (all unit + integration)
- [ ] T027 [P] Verify [contracts/config.md](contracts/config.md) schema v1.1 matches actual `Settings` fields in `src/catguard/config.py` (field names, types, defaults, constraints)
- [ ] T028 Run complete [quickstart.md](quickstart.md) manual validation (all 7 steps)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 (needs `DetectionEvent.frame_bgr` + `Settings` fields)
- **US2 (Phase 4)**: Depends on Phase 2 (needs `Settings` fields); independent of US1
- **US3 (Phase 5)**: Depends on Phase 3 (needs `screenshots.py` core from US1)
- **US4 (Phase 6)**: Depends on Phase 2 (needs `Settings` fields) and Phase 3 (needs `screenshots.py`)
- **Polish (Final)**: Depends on all desired stories being complete

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|-----------|-------------------|
| US1 (P1) | Phase 2 complete | US2 (after Phase 2) |
| US2 (P1) | Phase 2 complete | US1 (after Phase 2) |
| US3 (P2) | US1 complete | US4 (after Phase 2 + US1) |
| US4 (P2) | Phase 2 + US1 `screenshots.py` exists | US3 |

### Within Each User Story

1. Tests written first (must FAIL)
2. Implementation makes tests pass (Green)
3. Refactor if needed (Refactor)
4. Checkpoint validation before moving to next story

---

## Parallel Execution Examples

### Phase 2 — Foundational

```
Parallel batch 1 (write tests):
  T002  Write failing tests for DetectionEvent.frame_bgr
  T003  Write failing tests for 4 new Settings fields

Parallel batch 2 (implement, after batch 1):
  T004  Add frame_bgr to DetectionEvent
  T005  Add 4 new Settings fields
```

### Phase 3 — User Story 1

```
Parallel batch 1 (write tests):
  T006   Unit tests for screenshots.py (happy path)
  T007   Integration test for detection→file path
  T010a  Unit tests for _main_window_visible toggle (test_main_window.py)

Sequential (implementation depends on all tests failing):
  T008  Implement resolve_root, build_filepath, save_screenshot core
  T009  Pass frame_bgr to DetectionEvent in DetectionLoop      ← parallel with T010
  T010  Track main-window visibility flag                      ← after T010a; parallel with T009
  T011  Wire save_screenshot in main.py                        ← after T008, T009, T010
```

### Phase 4 — User Story 2 (can overlap with Phase 3 implementation)

```
  T012  Write failing tests for SettingsFormModel (parallel with Phase 3 T009/T010)
  T013  Add screenshots_root_folder to SettingsFormModel   ← after T012
  T014  Add Screenshots UI section                          ← after T013
```

### Phase 5 + 6 — US3 and US4 (can overlap after Phase 3 complete)

```
Parallel batch 1:
  T015  Failing tests: save_screenshot error paths         (US3)
  T016  Failing tests: notify_error tray helper            (US3)
  T020  Failing tests: is_within_time_window               (US4)
  T021  Failing tests: SettingsFormModel time-window fields (US4)

Parallel batch 2 (after batch 1):
  T017  Implement notify_error in tray.py                  (US3)
  T018  Add try/except to save_screenshot                  (US3) ← after T015, T017
  T022  Implement is_within_time_window                    (US4) ← after T020

Sequential:
  T019  Wire on_error to tray notify in main.py            (US3) ← after T018
  T023  Add time-window fields to SettingsFormModel        (US4) ← after T021
  T024  Add time-window UI section                         (US4) ← after T023
  T025  Add is_within_time_window guard to save_screenshot (US4) ← after T022
```

---

## Implementation Strategy

### MVP Scope (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational (T002–T005) — **required gate**
3. Complete Phase 3: US1 — Automatic Screenshot (T006–T011)
4. Complete Phase 4: US2 — Configure Root Folder (T012–T014)
5. **STOP and VALIDATE**: Run quickstart steps 1–5; screenshots appear in configured folder
6. Demo / deploy MVP

### Full Delivery

Continue with Phase 5 (US3 — failure handling) and Phase 6 (US4 — time window) after MVP validation.

### Task Count Summary

| Phase | Tasks | User Story |
|-------|-------|-----------|
| Phase 1: Setup | 1 | — |
| Phase 2: Foundational | 4 | — |
| Phase 3: US1 | 6 | US1 (P1) |
| Phase 4: US2 | 3 | US2 (P1) |
| Phase 5: US3 | 5 | US3 (P2) |
| Phase 6: US4 | 6 | US4 (P2) |
| Final: Polish | 3 | — |
| **Total** | **28** | |

| Story | Task count | Parallel opportunities |
|-------|-----------|----------------------|
| US1 | 6 | Tests (T006/T007), then impl (T009/T010) |
| US2 | 3 | T012 can overlap with US1 T009/T010 |
| US3 | 5 | Tests (T015/T016), then impl (T017/T018) |
| US4 | 6 | Tests (T020/T021), then impl (T022/T023) |
