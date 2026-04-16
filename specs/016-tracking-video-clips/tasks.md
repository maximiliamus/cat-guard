# Tasks: Tracking Mode with Video Clips

**Input**: Design documents from `/specs/016-tracking-video-clips/`  
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Included — TDD required by project constitution (Principle I). Write tests first and confirm they fail before implementation.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other [P] tasks at the same phase level
- **[Story]**: User story label (`US1`, `US2`, `US3`)
- All source paths are under `src/catguard/`; all test paths are under `tests/`

---

## Phase 1: Setup

**Purpose**: Prepare the new video-tracking test surface without changing runtime behavior yet.

- [X] T001 Create or confirm the feature test scaffolds in `tests/unit/test_tracking_video.py`, `tests/integration/test_tracking_video_integration.py`, and `tests/integration/test_main_shutdown.py`, and verify the existing helpers in `tests/unit/test_config.py`, `tests/unit/test_settings_window.py`, `tests/unit/test_detection.py`, `tests/unit/test_annotation.py`, and `tests/integration/test_effectiveness_integration.py` are ready for TDD updates

**Checkpoint**: The required test files exist and are ready for red-green-refactor work.

---

## Phase 2: Foundational (Shared Building Blocks)

**Purpose**: Add the settings, snapshot, main-thread wiring, and clip-writer primitives that every user story depends on.

**⚠️ CRITICAL**: No user story work should begin until this phase is complete.

> **TDD**: Write and run T002, T003, and T004 first. Confirm they fail. Then implement T005, T006, and T007.

- [X] T002 [P] Write `@pytest.mark.unit` tests for persisted `tracking_mode` / `videoclip_fps` validation and `SettingsFormModel` round-trip behavior in `tests/unit/test_config.py` and `tests/unit/test_settings_window.py`
- [X] T003 [P] Write `@pytest.mark.unit` tests for atomic detection snapshots, capture timestamps, and verification callback payloads in `tests/unit/test_detection.py`
- [X] T004 [P] Write `@pytest.mark.unit` tests for `reserve_tracking_clip_paths()`, same-second collision suffixes, zero-frame finalize behavior, readability checks, and resize normalization in `tests/unit/test_tracking_video.py`
- [X] T005 [P] Implement persisted `tracking_mode` / `videoclip_fps` settings fields and `SettingsFormModel` round-trip support in `src/catguard/config.py` and `src/catguard/ui/settings_window.py`
- [X] T006 [P] Implement atomic processed detection snapshots, capture-time verification callback payloads, and `captured_at` propagation from detection events into tracker wiring in `src/catguard/detection.py` and `src/catguard/main.py`
- [X] T007 [P] Implement `TrackingClipPaths`, `reserve_tracking_clip_paths()`, and `TrackingClipWriter` in `src/catguard/tracking_video.py`

**Checkpoint**: Settings fields, detection snapshots, and clip-writer primitives are green and ready for story work.

---

## Phase 3: User Story 1 - Review One Cat Visit as One Video Clip (Priority: P1) 🎯 MVP

**Goal**: A completed cat session in `Videoclips` mode produces one readable annotated clip that starts with `Cat detected`, preserves remained/disappeared outcomes in order, and creates no standalone tracking JPEGs.

**Independent Test**: Set `tracking_mode="videoclips"` in a test fixture, drive a session through one or more cooldown cycles, and verify exactly one `.avi` clip exists, zero session `*.jpg` files exist, and clip readback shows the opening, remained, and final outcome frames in order.

> **TDD**: Write and run T008 and T009 first. Confirm they fail. Then implement T010 and T011.

- [X] T008 [P] [US1] Write `@pytest.mark.unit` tests for capture-time annotation, alert-sound-label propagation, video-mode session snapshots, continuity-frame sampling, direct verification writes, and opening-frame-only partial clips in `tests/unit/test_annotation.py`
- [X] T009 [P] [US1] Write `@pytest.mark.integration` tests for completed video-mode clips, zero session JPEGs, alert-sound-label and capture-time readback, remained/disappeared overlays, and low-throughput continuity behavior in `tests/integration/test_tracking_video_integration.py`
- [X] T010 [US1] Add capture-time-aware top-bar rendering, alert-sound-label propagation, and video-mode tracker session state to `src/catguard/annotation.py`
- [X] T011 [US1] Implement video-mode clip sampling, explicit verification writes, and partial `abandon()` finalization in `src/catguard/annotation.py`

**Checkpoint**: User Story 1 is independently functional. A full session is reviewable from a single clip artifact.

---

## Phase 4: User Story 2 - Choose Tracking Output in Settings (Priority: P1)

**Goal**: Users can choose `Screenshots` or `Videoclips` in Settings, edit `Videoclip FPS` only when video mode is selected, persist those values across restart, and have new values apply only to the next session.

**Independent Test**: Open Settings, switch modes, save a custom `Videoclip FPS`, restart, confirm the saved values reload, then change settings during an active video session and verify the active clip keeps its original mode/fps while the next session uses the new values.

> **TDD**: Write and run T012 and T013 first. Confirm they fail. Then implement T014 and T015.

- [X] T012 [P] [US2] Write `@pytest.mark.unit` tests for Storage-tab `Tracking mode` / `Videoclip FPS` controls, enable/disable behavior, and positive-integer entry validation in `tests/unit/test_settings_window.py`
- [X] T013 [P] [US2] Write `@pytest.mark.integration` tests for persisted mode/fps restart behavior and mid-session setting changes affecting only the next session in `tests/integration/test_tracking_video_integration.py`
- [X] T014 [US2] Add Storage-tab `Tracking mode` and `Videoclip FPS` widgets plus save/load wiring in `src/catguard/ui/settings_window.py`
- [X] T015 [US2] Ensure active sessions use snapshotted mode/fps while later sessions adopt newly saved values in `src/catguard/annotation.py`

**Checkpoint**: User Story 2 is independently functional. Users can select and persist tracking output behavior through Settings.

---

## Phase 5: User Story 3 - Keep Screenshot Tracking Available (Priority: P2)

**Goal**: `Screenshots` mode continues to produce the existing JPEG session timeline only, even after the video-mode branch and settings changes are added.

**Independent Test**: Run a screenshot-mode session after switching back from `Videoclips` and verify the normal `-001.jpg`, `-002.jpg`, ... timeline is produced with no `.avi` artifact.

> **TDD**: Write and run T016 and T017 first. Confirm they fail. Then implement T018.

- [X] T016 [P] [US3] Write `@pytest.mark.unit` tests for screenshot-mode tracker branching with no clip creation in `tests/unit/test_annotation.py`
- [X] T017 [P] [US3] Write `@pytest.mark.integration` tests for screenshot-only output after switching back from video mode in `tests/integration/test_effectiveness_integration.py`
- [X] T018 [US3] Preserve screenshot-mode JPEG flow and no-clip behavior while the video-mode branch is active in `src/catguard/annotation.py`

**Checkpoint**: User Story 3 is independently functional. Screenshot tracking remains unchanged.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finalize real shutdown/error paths, structured logging, failure recovery, and end-to-end validation across all stories.

> **TDD**: Write and run T019 and T020 first. Confirm they fail. Then implement T021 and T022 before validation.

- [X] T019 [P] Write `@pytest.mark.integration` tests for tray-exit, camera-error, and schedule-stop cleanup preserving readable partial clips and bounded finalize/shutdown timing in `tests/integration/test_main_shutdown.py`
- [X] T020 [P] Write `@pytest.mark.integration` tests for readable `.partial.avi` rename recovery, non-blocking error reporting, and completed-session finalize timing in `tests/integration/test_tracking_video_integration.py`
- [X] T021 Implement unified `shutdown_app()` cleanup plus shutdown/finalize lifecycle logging in `src/catguard/main.py`
- [X] T022 Implement writer-failure recovery, readable `.partial.avi` preservation, and structured session/clip lifecycle logging in `src/catguard/annotation.py` and `src/catguard/tracking_video.py`
- [ ] T023 Run the focused validation commands and manual smoke steps documented in `specs/016-tracking-video-clips/quickstart.md`, including the 10-second finalize expectation and lifecycle log inspection
- [ ] T024 Record peer-review sign-off and acceptance-criteria verification against `specs/016-tracking-video-clips/spec.md` and `specs/016-tracking-video-clips/checklists/plan.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup completion; blocks all story work
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 2 (Phase 4)**: Depends on Foundational completion and builds on the video-mode runtime added for US1
- **User Story 3 (Phase 5)**: Depends on US1 and US2 because it validates screenshot-mode behavior after the video-mode and settings branches exist
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1**: First independently deliverable increment; recommended MVP
- **US2**: Depends on the shared settings/runtime primitives and validates that the video-mode feature is user-accessible
- **US3**: Regression story confirming the pre-existing screenshot path still works after US1 and US2

### Within Each User Story

- Tests MUST be written and observed failing before implementation
- Shared runtime primitives from Phase 2 precede all story code
- `src/catguard/annotation.py` is the critical-path file across US1, US2, and US3
- Real shutdown/error-path work waits for the core tracker behavior to be stable

### Parallel Opportunities

- T002, T003, and T004 can run in parallel
- T005, T006, and T007 can run in parallel after the Phase 2 tests are failing
- T008 and T009 can run in parallel
- T012 and T013 can run in parallel
- T016 and T017 can run in parallel
- T019 and T020 can run in parallel

---

## Parallel Example: Foundational Phase

```text
Parallel slot A: T002 — config/settings-form tests in tests/unit/test_config.py and tests/unit/test_settings_window.py
Parallel slot B: T003 — detection snapshot tests in tests/unit/test_detection.py
Parallel slot C: T004 — clip-writer tests in tests/unit/test_tracking_video.py
  ↓
Parallel slot A: T005 — config.py + SettingsFormModel plumbing
Parallel slot B: T006 — detection.py snapshot plumbing
Parallel slot C: T007 — tracking_video.py writer implementation
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. Stop and validate that one completed session produces exactly one readable clip and zero session JPEGs

### Incremental Delivery

1. Add shared settings, snapshot, and clip-writer primitives in Phase 2
2. Deliver single-clip session review in US1
3. Deliver the Settings workflow in US2
4. Confirm screenshot-mode regression safety in US3
5. Finish real shutdown/failure recovery and full validation in Phase 6

### Parallel Team Strategy

1. One engineer owns Phase 2 settings plumbing while another owns detection snapshots and a third owns clip-writer primitives
2. After Phase 2, one engineer can drive `annotation.py` for US1 while another prepares US2 settings tests
3. Complete US3 and Phase 6 only after the core tracker path is stable

---

## Notes

- [P] tasks are parallelizable because they touch different files or independent test layers
- `src/catguard/annotation.py` is the critical-path runtime file for the feature
- `tests/integration/test_tracking_video_integration.py` is the main end-to-end validation surface; keep it readable as stories layer on behavior
- `MJPG` + `.avi` packaged-player compatibility remains a manual validation concern even when OpenCV readback is green
