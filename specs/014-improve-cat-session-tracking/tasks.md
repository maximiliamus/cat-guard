# Tasks: Immediate Cat Session Frame Saving

**Input**: Design documents from `/specs/014-improve-cat-session-tracking/`  
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Included — TDD required by project constitution (Principle I). Write tests first and confirm they fail before implementation.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other [P] tasks at the same phase level
- **[Story]**: User story label (`US1`, `US2`, `US3`)
- All source paths are under `src/catguard/`; all test paths are under `tests/`

---

## Phase 1: Setup

**Purpose**: Confirm the existing 012-based test surface is ready to be updated for feature 014 without creating new suites.

- [X] T001 Confirm the existing session-tracking helpers and fixtures needed for this feature are present in `tests/unit/test_annotation.py`, `tests/unit/test_detection.py`, `tests/unit/test_screenshots.py`, `tests/integration/test_detection_integration.py`, and `tests/integration/test_effectiveness_integration.py`; add minimal helper stubs only where missing

**Checkpoint**: Existing test files are ready for TDD updates.

---

## Phase 2: Foundational (Shared Building Blocks)

**Purpose**: Add the shared overlay, duration-formatting, and filename helpers that all user stories depend on.

**⚠️ CRITICAL**: No user story work should begin until this phase is complete.

> **TDD**: Write and run T002 and T003 first. Confirm both fail. Then implement T004 and T005.

- [X] T002 [P] Write unit tests for neutral `detected` outcome rendering and `format_session_duration()` in `tests/unit/test_annotation.py`
- [X] T003 [P] Write unit tests for sequential saved-frame indexing in `build_session_filepath()` in `tests/unit/test_screenshots.py`
- [X] T004 Implement the neutral `detected` outcome strip and `format_session_duration()` helper in `src/catguard/annotation.py`
- [X] T005 Implement sequential saved-frame-index semantics and updated docstrings for `build_session_filepath()` in `src/catguard/screenshots.py`

**Checkpoint**: Shared overlay, duration, and session-filepath helpers are green and ready for story work.

---

## Phase 3: User Story 1 - Capture the Start of Every Cat Visit (Priority: P1) 🎯 MVP

**Goal**: Save the first session frame immediately when a new cat session starts, with the neutral `Cat detected` strip and session-aware numbering.

**Independent Test**: Trigger a new cat detection and verify a `-001.jpg` file is written before the first verification cycle completes, with a dark gray bottom strip and the text `Cat detected`.

> **TDD**: Write and run T006 and T007 first. Confirm both fail. Then implement T008 and T009.

- [X] T006 [P] [US1] Write unit tests for `EffectivenessTracker.on_detection()` immediate session-start save, `_frame_index = 1`, and no duplicate neutral save while the session is active in `tests/unit/test_annotation.py`
- [X] T007 [P] [US1] Write an integration test for immediate `-001.jpg` session-start persistence before any verification fires in `tests/integration/test_effectiveness_integration.py`
- [X] T008 [US1] Add `_frame_index` and `_active_sound_label` session metadata to `EffectivenessTracker` in `src/catguard/annotation.py`
- [X] T009 [US1] Implement the first-detection immediate neutral annotation/save flow in `EffectivenessTracker.on_detection()` in `src/catguard/annotation.py`

**Checkpoint**: A new session now creates its first persisted artifact immediately and can be validated independently.

---

## Phase 4: User Story 2 - Review Every Session Outcome Without Missing Frames (Priority: P1)

**Goal**: Save the live verification frame for every session outcome, with one saved frame per evaluation and a continuous ordered session timeline on disk.

**Independent Test**: Run a session where the cat remains for one or more checks and then leaves. Verify `001` is the neutral start frame and every later evaluation creates exactly one next sequential frame, ending with a final green outcome frame.

> **TDD**: Write and run T010, T011, T012, and T013 first. Confirm they fail. Then implement T014 and T015.

- [X] T010 [P] [US2] Write unit tests for the `DetectionLoop.set_verification_callback()` live-frame signature, deep-copied verification frame delivery, and cleared pending state in `tests/unit/test_detection.py`
- [X] T011 [P] [US2] Write unit tests for `EffectivenessTracker.on_verification(frame_bgr, has_cat, boxes)` saving exactly one next sequential session frame per evaluation in `tests/unit/test_annotation.py`
- [X] T012 [P] [US2] Write integration tests for live verification-frame delivery through the detection loop, including that the callback frame remains valid after the loop advances, in `tests/integration/test_detection_integration.py`
- [X] T013 [P] [US2] Write integration tests for one-cycle and multi-cycle ordered session timelines in `tests/integration/test_effectiveness_integration.py`
- [X] T014 [US2] Refactor verification pending state and callback delivery to pass `frame_bgr, has_cat, boxes` in `src/catguard/detection.py`
- [X] T015 [US2] Update `EffectivenessTracker.on_verification()` to save the live verification frame exactly once per evaluation, increment `_frame_index`, and close the session only on the green path in `src/catguard/annotation.py`

**Checkpoint**: Users can reconstruct the full session from disk without any discarded evaluation screenshots.

---

## Phase 5: User Story 3 - Read Session Duration Quickly (Priority: P2)

**Goal**: Show session durations in compact human-readable format on saved outcome frames and in session-related logs.

**Independent Test**: Verify overlay and log output renders durations as `30s`, `2m 15s`, and `1h 2m 45s` instead of raw second counts.

> **TDD**: Write and run T016 and T017 first. Confirm they fail. Then implement T018.

- [X] T016 [P] [US3] Write unit tests for human-readable duration strings in session overlay messages and log text in `tests/unit/test_annotation.py`
- [X] T017 [P] [US3] Write an integration test that saved session outcomes and session lifecycle logs use human-readable durations in `tests/integration/test_effectiveness_integration.py`
- [X] T018 [US3] Apply `format_session_duration()` to session overlay messages and lifecycle logging in `src/catguard/annotation.py`

**Checkpoint**: Duration information is readable at a glance across both saved images and logs.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finish pause/error abandonment behavior and run the documented validation flow across all stories.

> **TDD**: Write and run T019 and T020 first. Confirm they fail. Then implement T021 and run T022.

- [X] T019 [P] Write unit tests for `EffectivenessTracker.abandon()` resetting session metadata without affecting already-saved files in `tests/unit/test_annotation.py`
- [X] T020 [P] Write an integration test for pause or camera-error session abandonment with no synthetic closing frame in `tests/integration/test_effectiveness_integration.py`
- [X] T021 Implement session abandonment resets and pause/error wiring in `src/catguard/annotation.py`, `src/catguard/detection.py`, and `src/catguard/main.py`
- [ ] T022 Run the focused validation commands from `specs/014-improve-cat-session-tracking/quickstart.md`, the full automated regression suite with `pytest`, and the documented manual smoke steps
- [ ] T023 Record peer-review sign-off and acceptance-criteria verification against `specs/014-improve-cat-session-tracking/spec.md` before merge

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup completion; blocks all story work
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 2 (Phase 4)**: Depends on User Story 1 because it builds on `_frame_index` and immediate start-frame persistence
- **User Story 3 (Phase 5)**: Depends on User Story 2 because it formats the already-correct outcome timeline
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1**: First independently deliverable increment; recommended MVP
- **US2**: Extends the US1 session-start flow into a complete session timeline
- **US3**: Refines the US2 timeline presentation without changing the underlying save order

### Within Each User Story

- Tests MUST be written and observed failing before implementation
- Detection-loop callback changes precede tracker verification refactor in US2
- Annotation changes in `src/catguard/annotation.py` are the critical sequential path across the feature

### Parallel Opportunities

- T002 and T003 can run in parallel
- T006 and T007 can run in parallel
- T010, T011, T012, and T013 can run in parallel
- T016 and T017 can run in parallel
- T019 and T020 can run in parallel

---

## Parallel Example: User Story 2

```text
Parallel slot A: T010 — update detection-loop unit tests in tests/unit/test_detection.py
Parallel slot B: T011 — update tracker unit tests in tests/unit/test_annotation.py
Parallel slot C: T012 — add detection integration coverage in tests/integration/test_detection_integration.py
Parallel slot D: T013 — add end-to-end timeline coverage in tests/integration/test_effectiveness_integration.py
  ↓
Sequential: T014 — detection.py callback refactor
  ↓
Sequential: T015 — annotation.py verification-save refactor
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. Stop and validate that `-001.jpg` is created immediately with the neutral `Cat detected` strip

### Incremental Delivery

1. Add shared helpers in Phase 2
2. Deliver immediate session-start persistence in US1
3. Deliver full ordered session timelines in US2
4. Add human-readable duration formatting in US3
5. Finish abandonment and run quickstart validation in Phase 6

### Parallel Team Strategy

1. One engineer handles foundational overlay/path helpers
2. One engineer prepares US2 detection-loop tests while another prepares tracker/integration tests
3. Merge on the detection callback contract before the tracker verification refactor

---

## Notes

- [P] tasks are parallelizable because they touch different files or independent test layers
- `src/catguard/annotation.py` is the critical path file across this feature
- Reuse the existing session-tracking test files instead of creating new suites
- Keep every saved session frame under the existing timestamp-prefix grouping contract from `specs/014-improve-cat-session-tracking/contracts/session-frame-output.md`
