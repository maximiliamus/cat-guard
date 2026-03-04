# Tasks: Miscellaneous UI and Behavior Improvements

**Input**: Design documents from `specs/007-misc-improvements/`  
**Branch**: `007-misc-improvements` | **Date**: March 4, 2026  
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Format: `[ID] [P?] [Story?] Description — file path`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[US#]**: User story label (US1–US5 map to spec.md priorities P1–P5)

---

## Phase 1: Setup

**Purpose**: Version bookkeeping before any feature work begins.

- [x] T001 Bump version to `0.2.0` in `pyproject.toml` (MINOR — new fields, new modules, no breaking changes)

---

## Phase 2: Foundational

**Purpose**: No cross-story blocking prerequisites exist — all five user stories are independent and self-contained. Proceed directly to Phase 3.

**Checkpoint**: ✅ No foundational work required — user story phases can begin immediately after T001.

---

## Phase 3: User Story 1 — Time Window Enforcement (Priority: P1) 🎯 MVP

**Goal**: Camera automatically pauses/resumes based on a configurable daily time window; user can override via tray Resume.

**Independent Test**: Configure a short time window, wait for the clock to cross the boundary, verify the camera stops; verify it restarts when the window opens. Confirm user Resume during auto-pause overrides the window.

### Config — new Settings fields

- [x] T002 [US1] Add `tracking_window_enabled` (bool, default `False`), `tracking_window_start` (str, default `"08:00"`), `tracking_window_end` (str, default `"18:00"`) fields to `Settings` in `src/catguard/config.py`
- [x] T003 [US1] Add `field_validator` for `tracking_window_start` / `tracking_window_end` enforcing `HH:MM` format in `src/catguard/config.py`
- [x] T004 [P] [US1] Write unit tests for new `Settings` fields (defaults, validator accepts valid, rejects invalid format, backward-compat load without keys) in `tests/unit/test_config.py`

### Tests — write and confirm FAIL before implementation

- [x] T005 [P] [US1] Write failing unit tests for `TimeWindowMonitor` (window active → no-op, window exits → pause, window enters → resume, user override → camera stays on, manual pause not overridden, cross-midnight window, zero-length window = disabled) in `tests/unit/test_time_window.py`
- [x] T006 [P] [US1] Write failing integration tests for time-window boundary crossings (clock crosses end → detection pauses, clock crosses start → detection resumes) in `tests/integration/test_pause_resume.py`

### Implementation

- [x] T007 [P] [US1] Implement `TimeWindowMonitor` class in `src/catguard/time_window.py`: `__init__(detection_loop, settings, on_state_changed)`, `start()`, `stop()`, `notify_user_resume()`, `_check()` poll logic, `_is_in_window()` cross-midnight helper, `_monitor_paused` / `_user_override` flags, 30 s daemon poll, `logger.*` calls per operation
- [x] T008 [P] [US1] Add "Active Monitoring Window" section to settings UI in `src/catguard/ui/settings_window.py`: `tracking_window_enabled` checkbox, `tracking_window_start` / `tracking_window_end` time Spinboxes (HH:MM, disabled when checkbox off), propagate to model on save
- [x] T009 [US1] Wire `TimeWindowMonitor` in `main()` in `src/catguard/main.py`: instantiate after `detection_loop`, register `on_state_changed` callback that calls `update_tray_icon_color` + `update_tray_menu`, call `monitor.start()` and `monitor.stop()` in shutdown
- [x] T010 [US1] In `on_pause_continue_clicked` Resume branch in `src/catguard/tray.py`: call `time_window_monitor.notify_user_resume()` (passed via closure from `main.py`) before `detection_loop.resume()`

**Checkpoint**: At this point, US1 is fully functional. Camera respects the configured time window; tray icon reflects state; user can override while outside window.

---

## Phase 4: User Story 2 — Camera Recovery After Sleep (Priority: P2)

**Goal**: Camera restores automatically after system wakes from sleep, respecting the time window and prior pause state.

**Independent Test**: Start app with camera active → sleep → wake → verify camera resumes within 10 s. Pre-condition: if outside time window at wake time, camera must NOT restore.

### Tests — write and confirm FAIL before implementation

- [x] T011 [P] [US2] Write failing unit tests for `SleepWatcher` (on_wake not called on normal 10 s tick, called when elapsed > 30 s, stop() prevents further calls, idempotent start) in `tests/unit/test_sleep_watcher.py`
- [x] T012 [P] [US2] Write failing integration test for wake → camera-restore flow (camera active before sleep → watcher fires → `detection_loop.resume()` called; paused before sleep → `resume()` NOT called; outside window at wake → remains paused) in `tests/integration/test_sleep_resume.py`

### Implementation

- [x] T013 [US2] Implement `SleepWatcher` class in `src/catguard/sleep_watcher.py`: `__init__(on_wake)`, `start()`, `stop()`, `_run()` daemon with time-jump polling (10 s sleep, >30 s elapsed → wake event), `logger.*` for detected wake and stop
- [x] T014 [US2] Wire `SleepWatcher` in `main()` in `src/catguard/main.py`: define `on_wake()` callback that checks `detection_loop.is_tracking()` was True before sleep (track via `_was_tracking_before_sleep` flag updated in `on_pause_continue_clicked`), evaluates time window (via `TimeWindowMonitor` if configured), calls `detection_loop.resume()` + tray update if conditions met; call `watcher.start()` and `watcher.stop()` in shutdown

**Checkpoint**: US2 is fully functional. App self-recovers after sleep; respects window and manual pause state.

---

## Phase 5: User Story 3 — Sound Library Rename (Priority: P3)

**Goal**: User can rename a sound file in the library via a dialog button; file is renamed on disk and config is updated atomically.

**Independent Test**: Select a file in the sound library → click Rename → enter valid name → confirm → verify list updates, file on disk renamed, `pinned_sound` updated if affected.

### Tests — write and confirm FAIL before implementation

- [x] T015 [US3] Write failing unit tests for rename flow in `tests/unit/test_settings_window.py`: valid rename updates listbox + path, rename of pinned sound updates `pinned_var`, cancel leaves file unchanged, empty name shows error, duplicate name shows error, rename during playback stops playback first

### Implementation

- [x] T016 [US3] Add `_rename_path()` closure and **Rename** button to the sound library button frame in `src/catguard/ui/settings_window.py`: button active only when a listbox entry is selected; `_rename_path()` stops playback via `pygame.mixer.stop()`, opens `simpledialog.askstring` pre-filled with current stem (no extension), validates non-empty + valid FS chars + no duplicate, calls `Path.rename()`, updates listbox entry, updates `pinned_var` if the renamed path was pinned, logs operation

**Checkpoint**: US3 fully functional. Sound rename is safe, validated, and reflected in live config.

---

## Phase 6: User Story 4 — Off-Screen Annotation Label Fallback (Priority: P4)

**Goal**: Detection bounding-box label remains visible when the box is near any frame edge, using a 5-position fallback chain.

**Independent Test**: Inject synthetic frames with boxes positioned at each of the four screen edges plus fully off-screen; verify label renders at the correct fallback position each time.

### Tests — write and confirm FAIL before implementation

- [x] T017 [US4] Write failing unit tests for `_draw_labelled_box()` fallback in `tests/unit/test_annotation.py`: normal (top on-screen) → label above box; top off-screen → label below box; top+bottom off-screen → label left; top+bottom+left off-screen → label right; all edges off-screen → label at center; existing passing tests must remain green

### Implementation

- [x] T018 [US4] Refactor `_draw_labelled_box()` in `src/catguard/annotation.py`: compute label pixel dimensions via `cv2.getTextSize`, define helper `_label_fits(bg_rect, w, h) → bool`, build ordered candidate list (above → below → left → right → center), select first fitting candidate, render background rect + text at selected position; add `logger.debug` when fallback is used

**Checkpoint**: US4 fully functional. Labels are always visible regardless of box screen position.

---

## Phase 7: User Story 5 — Locale-Aware Date/Time (Priority: P5)

**Goal**: Detection frame timestamps use the OS locale date/time format instead of the hardcoded ISO format.

**Independent Test**: Patch `locale.getlocale` / mock `datetime.strftime` to validate the format codes passed; run under a known locale and verify `%x`/`%X` produce locale-correct output.

### Tests — write and confirm FAIL before implementation

- [x] T019 [US5] Write failing unit tests for locale-aware timestamp in `tests/unit/test_annotation.py`: mock `datetime.now()` and verify `_draw_top_bar()` calls `strftime` with `'%x  %X'` (not a hardcoded format string); verify locale activation in `main()` by checking `setlocale` is called with `(LC_TIME, '')`

### Implementation

- [x] T020 [P] [US5] Add `import locale` and `locale.setlocale(locale.LC_TIME, '')` (wrapped in `try/except` with logged warning on failure) near the top of `main()` in `src/catguard/main.py`
- [x] T021 [US5] Replace `strftime("%Y-%m-%d  %H:%M:%S")` with `strftime('%x  %X')` in `_draw_top_bar()` in `src/catguard/annotation.py`

**Checkpoint**: US5 fully functional. Timestamps on screenshots and live annotations match the OS locale.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Verify observability (Constitution II), run end-to-end validation.

- [x] T022 [P] Confirm all new and modified modules contain appropriate `logger.*` calls at INFO/DEBUG/WARNING levels: `src/catguard/sleep_watcher.py`, `src/catguard/time_window.py`, modified sections of `config.py`, `annotation.py`, `settings_window.py`, `tray.py`, `main.py`
- [x] T023 Run `quickstart.md` end-to-end smoke test for all 5 user stories and confirm all pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** (Setup): No dependencies — start immediately.
- **Phase 2** (Foundational): Empty — no cross-story blockers.
- **Phases 3–7** (User Stories): All depend only on Phase 1 completing. Each story is independent of the others.
- **Phase 8** (Polish): Depends on all desired stories being implemented.

### User Story Dependencies

| Story | Depends On | Can Parallelize With |
|-------|------------|----------------------|
| US1 (P1) — Time Window | T001 only | US2, US3, US4, US5 |
| US2 (P2) — Sleep Recovery | T001 only; benefits from US1 (time window check in `on_wake`) | US3, US4, US5 |
| US3 (P3) — Rename | T001 only | US1, US2, US4, US5 |
| US4 (P4) — Annotation Fallback | T001 only | US1, US2, US3, US5 |
| US5 (P5) — Locale Date/Time | T001 only | US1, US2, US3, US4 |

> **Note on US2 + US1 interaction**: US2's `on_wake` must check the time window. If US1 is not yet implemented, US2 can skip the window check on first pass and add it once US1's `TimeWindowMonitor` exists. Both stories are independently testable.

### Within Each User Story

1. Config/model additions first (if any)
2. Tests written — confirm they **FAIL**
3. Implementation
4. Tests pass — confirm **GREEN**

---

## Parallel Execution Examples

### User Story 1 — two agents in parallel after T001

```
Agent A (Phase 3, stream 1):
  T002 → T003 → T005 → T007 → T009 → T010

Agent B (Phase 3, stream 2):
  T004 → T006 → T008
```

### User Story 2 — after US1 core is stable

```
Agent A: T011 → T013 → T014
Agent B: T012
```

### User Stories 3, 4, 5 — fully parallel with each other

```
Agent A: T015 → T016          (US3 Rename)
Agent B: T017 → T018          (US4 Annotation)
Agent C: T019 → T020 → T021  (US5 Locale)
```

---

## Implementation Strategy

**MVP scope (deliver first)**: US1 alone (Phases 3 + partial Phase 8). This is the highest-impact story — a user with a time window configured currently gets no enforcement; this delivers it completely.

**Recommended order for solo developer**:
1. T001 (5 min)
2. Phase 3 / US1 — T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009 → T010
3. Phase 4 / US2 — T011 → T012 → T013 → T014
4. Phase 5 / US3 — T015 → T016
5. Phase 6 / US4 — T017 → T018
6. Phase 7 / US5 — T019 → T020 → T021
7. Phase 8 — T022 → T023

Total tasks: **23**
