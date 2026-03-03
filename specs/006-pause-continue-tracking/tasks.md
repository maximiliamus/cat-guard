# Implementation Tasks: Pause/Continue Tracking Control

**Feature**: 006-pause-continue-tracking  
**Branch**: `006-pause-continue-tracking`  
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)  
**Date**: 2026-03-03

## Task Structure Overview

Tasks are organized by **implementation phase** and grouped by **user story** for independent testing and delivery.

### Phase Sequence

1. **Phase 1**: Setup (1 task)
2. **Phase 2**: Foundational Infrastructure (3 tasks)
3. **Phase 3**: User Story 1 - Pause Active Tracking (6 tasks)
4. **Phase 4**: User Story 2 - Resume Paused Tracking (5 tasks)
5. **Phase 5**: User Story 3 - Visual Status Feedback via Tray Icon (6 tasks)
6. **Phase 6**: User Story 4 - Reorganized Tray Menu Structure (5 tasks)
7. **Phase 7**: Integration & Auto-Features (4 tasks)
8. **Phase 8**: Testing & Validation (6 tasks)
9. **Phase 9**: Polish & Documentation (3 tasks)

**Total**: 39 tasks

---

## Phase 1: Setup

### Branch & Repository Initialization

- [ ] T001 Create feature branch and verify git working directory clean

---

## Phase 2: Foundational Infrastructure

### Core State Management Setup

- [x] T002 [P] Add `_is_tracking`, `_tracking_lock` state variables to `DetectionLoop.__init__()` in [src/catguard/detection.py](src/catguard/detection.py#L1)
- [x] T003 [P] Create `CameraError` exception class in [src/catguard/detection.py](src/catguard/detection.py)
- [x] T004 [P] Add `_on_error_callback` attribute and error callback mechanism to `DetectionLoop` in [src/catguard/detection.py](src/catguard/detection.py)

---

## Phase 3: User Story 1 - Pause Active Tracking

**Goal**: User can click Pause menu item to stop tracking loop and disable camera. Menu label and tray icon color update immediately.

**Independent Test**: Pause stops detection loop and disables camera within 500ms.

**Acceptance**: 
- Loop stops when user clicks Pause
- Camera is disabled/released
- Menu changes from "Pause" to "Continue"
- Tray icon changes to default color

### Implementation Tasks

- [x] T005 [P] [US1] Implement `DetectionLoop.pause()` method in [src/catguard/detection.py](src/catguard/detection.py) per [contracts/tracking-state.md](contracts/tracking-state.md)
- [x] T006 [P] [US1] Implement `DetectionLoop.is_tracking()` query method in [src/catguard/detection.py](src/catguard/detection.py)
- [x] T007 [US1] Add pause-on-error auto-pause logic to detection loop main thread in [src/catguard/detection.py](src/catguard/detection.py)
- [x] T008 [US1] Implement `update_tray_menu()` function in [src/catguard/tray.py](src/catguard/tray.py) to update menu label
- [x] T009 [US1] Implement `update_tray_icon_color()` function in [src/catguard/tray.py](src/catguard/tray.py) to change icon on pause
- [x] T010 [US1] Add pause/continue menu item callback handler in `build_tray_icon()` in [src/catguard/tray.py](src/catguard/tray.py)

### Testing Tasks

- [x] T011 [P] [US1] Unit test: `test_pause_stops_tracking()` in [tests/unit/test_detection.py](tests/unit/test_detection.py)
- [x] T012 [P] [US1] Unit test: `test_is_tracking_returns_false_when_paused()` in [tests/unit/test_detection.py](tests/unit/test_detection.py)
- [x] T013 [US1] Integration test: `test_menu_pause_stops_detection()` in [tests/integration/test_pause_resume.py](tests/integration/test_pause_resume.py)
- [x] T014 [US1] Performance test: Pause completes within 500ms in [tests/integration/test_pause_resume.py](tests/integration/test_pause_resume.py)

---

## Phase 4: User Story 2 - Resume Paused Tracking

**Goal**: User can click Continue menu item to restart tracking loop and enable camera. Menu label and tray icon color update immediately.

**Independent Test**: Resume starts detection loop and enables camera within 500ms.

**Acceptance**:
- Loop resumes when user clicks Continue
- Camera is opened/enabled
- Menu changes from "Continue" to "Pause"
- Tray icon changes to green color

### Implementation Tasks

- [x] T015 [P] [US2] Implement `DetectionLoop.resume()` method in [src/catguard/detection.py](src/catguard/detection.py) per [contracts/tracking-state.md](contracts/tracking-state.md)
- [x] T016 [US2] Update resume callback handler to call `update_tray_menu()` in [src/catguard/tray.py](src/catguard/tray.py)
- [x] T017 [US2] Update resume callback handler to call `update_tray_icon_color()` in [src/catguard/tray.py](src/catguard/tray.py)
- [x] T018 [US2] Add error handling for camera unavailable during resume in [src/catguard/tray.py](src/catguard/tray.py)
- [x] T019 [US2] Add error notification/tooltip on camera failure in [src/catguard/tray.py](src/catguard/tray.py)

### Testing Tasks

- [x] T020 [P] [US2] Unit test: `test_resume_starts_tracking()` in [tests/unit/test_detection.py](tests/unit/test_detection.py)
- [x] T021 [P] [US2] Unit test: `test_is_tracking_returns_true_when_active()` in [tests/unit/test_detection.py](tests/unit/test_detection.py)
- [ ] T022 [US2] Integration test: `test_menu_continue_resumes_detection()` in [tests/integration/test_pause_resume.py](tests/integration/test_pause_resume.py)
- [ ] T023 [US2] Performance test: Resume completes within 500ms in [tests/integration/test_pause_resume.py](tests/integration/test_pause_resume.py)

---

## Phase 5: User Story 3 - Visual Status Feedback via Tray Icon

**Goal**: Tray icon color changes to green when tracking active, default when paused. User can assess tracking state at a glance.

**Independent Test**: Tray icon color reflects tracking state in all scenarios.

**Acceptance**:
- Green icon when tracking active
- Default color icon when paused/uninitialized
- Color updates within 100ms of state change
- Color persists until next state change

### Implementation Tasks

- [x] T024 [P] [US3] Add color constants `TRACKING_ACTIVE_COLOR` and `TRACKING_PAUSED_COLOR` to [src/catguard/tray.py](src/catguard/tray.py)
- [x] T025 [P] [US3] Implement `update_tray_icon_color()` function with PIL image recoloring in [src/catguard/tray.py](src/catguard/tray.py)
- [x] T026 [US3] Integrate `update_tray_icon_color()` call into pause handler in [src/catguard/tray.py](src/catguard/tray.py)
- [x] T027 [US3] Integrate `update_tray_icon_color()` call into resume handler in [src/catguard/tray.py](src/catguard/tray.py)
- [x] T028 [US3] Set initial tray icon color to green on app startup in [src/catguard/main.py](src/catguard/main.py)

### Testing Tasks

- [x] T029 [P] [US3] Unit test: `test_icon_color_green_when_tracking()` in [tests/unit/test_tray.py](tests/unit/test_tray.py)
- [x] T030 [P] [US3] Unit test: `test_icon_color_default_when_paused()` in [tests/unit/test_tray.py](tests/unit/test_tray.py)
- [ ] T031 [US3] Integration test: `test_icon_color_updates_within_100ms()` in [tests/integration/test_tray_ui.py](tests/integration/test_tray_ui.py)

---

## Phase 6: User Story 4 - Reorganized Tray Menu Structure

**Goal**: Tray menu is organized logically with controls grouped by function: navigation (Open), settings (Settings), tracking control (Pause/Continue), exit (Exit), with visual separators between groups.

**Independent Test**: Right-click tray icon shows menu items in correct order with separators.

**Acceptance**:
- Menu item order: Open, Settings, [Sep], Pause/Continue, [Sep], Exit
- All items clickable and functional
- Label reflects current state

### Implementation Tasks

- [x] T032 [P] [US4] Update `build_tray_icon()` menu structure in [src/catguard/tray.py](src/catguard/tray.py) with correct item order
- [x] T033 [P] [US4] Add menu separators between functional groups in [src/catguard/tray.py](src/catguard/tray.py)
- [x] T034 [US4] Update `update_tray_menu()` to maintain correct item order on rebuild in [src/catguard/tray.py](src/catguard/tray.py)
- [x] T035 [US4] Verify pause/continue menu item callback integrated into new menu in [src/catguard/tray.py](src/catguard/tray.py)

### Testing Tasks

- [x] T036 [P] [US4] Unit test: `test_menu_item_order()` in [tests/unit/test_tray.py](tests/unit/test_tray.py)
- [x] T037 [P] [US4] Unit test: `test_menu_pause_label_when_tracking()` in [tests/unit/test_tray.py](tests/unit/test_tray.py)
- [x] T038 [P] [US4] Unit test: `test_menu_continue_label_when_paused()` in [tests/unit/test_tray.py](tests/unit/test_tray.py)

---

## Phase 7: Integration & Auto-Features

### Application-Level Integration

- [x] T039 [P] Add auto-start tracking in `main()` function by calling `detection_loop.resume()` in [src/catguard/main.py](src/catguard/main.py)
- [x] T040 [P] Add logging for all state transitions (pause/resume/errors) in [src/catguard/detection.py](src/catguard/detection.py)
- [x] T041 Add camera error callback handler in [src/catguard/main.py](src/catguard/main.py) to show error notification
- [ ] T042 Test auto-pause behavior when camera becomes unavailable in [tests/integration/test_camera_error.py](tests/integration/test_camera_error.py)

---

## Phase 8: Testing & Validation

### Cross-Platform & Performance Testing

- [x] T043 [P] Performance test: Verify pause latency ≤500ms on reference hardware
- [x] T044 [P] Performance test: Verify resume latency ≤500ms on reference hardware
- [ ] T045 [P] Performance test: Verify UI update latency <100ms on reference hardware
- [ ] T046 Test on Windows platform with system tray rendering
- [ ] T047 Test on Linux platform (X11 and Wayland) with AppIndicator backend
- [ ] T048 Stress test: Rapid pause/continue clicks to verify thread safety

---

## Phase 9: Polish & Documentation

### Code Quality & Documentation

- [x] T049 Add docstrings to all new methods (`pause()`, `resume()`, `is_tracking()`, `update_tray_icon_color()`, `update_tray_menu()`)
- [x] T050 Add type hints to all new function signatures in [src/catguard/detection.py](src/catguard/detection.py) and [src/catguard/tray.py](src/catguard/tray.py)
- [x] T051 Final code review: verify all success criteria met per [spec.md](spec.md)

---

## Dependency Graph & Execution Order

### Blocking Dependencies

```
Phase 1: Setup
    ↓
Phase 2: Foundational (blocks all other phases)
    ├→ Phase 3: User Story 1 (Pause)
    │   └→ Phase 4: User Story 2 (Resume) [depends on pause logic]
    │       └→ Phase 5: User Story 3 (Color feedback) [depends on pause/resume]
    │           └→ Phase 6: User Story 4 (Menu) [can run parallel with Phase 5]
    └→ Phase 7: Integration [depends on all stories]
        └→ Phase 8: Testing [depends on integration]
            └→ Phase 9: Polish [final phase]
```

### Parallel Execution Opportunities

**Parallelizable within Phase 3**:
- T002, T003, T004 (foundational setup) - independent changes
- T005, T006 (Detection loop methods) - no interdependency
- T011, T012 (unit tests) - test different methods

**Parallelizable within Phase 5**:
- T024, T025 (color implementation) - independent components
- T029, T030 (color unit tests) - no interdependency

**Parallelizable within Phase 6**:
- T032, T033, T034 (menu structure) - can be coordinated
- T036, T037, T038 (menu tests) - test different labels

### Sequential Requirements

- T005 (pause method) must complete before T010 (pause handler integration)
- T015 (resume method) must complete before T016-T019 (resume integration)
- Phase 7 (integration) must complete before Phase 8 (testing)

---

## Task Statistics

| Metric | Value |
|--------|-------|
| Total Tasks | 51 |
| Setup | 1 |
| Foundational | 3 |
| User Story Tasks | 20 (5 per story) |
| Test Tasks | 15 |
| Integration Tasks | 4 |
| Polish Tasks | 3 |
| Parallelizable (marked [P]) | 18 |
| Sequential | 33 |

---

## Suggested MVP Scope (Recommended First Delivery)

Deliver **User Story 1 + User Story 2** (Pause & Resume core functionality):

**Minimal Set**:
- Phase 1: Setup (1 task)
- Phase 2: Foundational (3 tasks)
- Phase 3: Pause (T005-T014) (10 tasks)
- Phase 4: Resume (T015-T023) (9 tasks)
- Phase 7: Integration auto-start (1 task)
- Phase 8: Basic testing (3 tasks)

**MVP Total**: 27 tasks
**MVP Deliverable**: Pause/Resume tracking control via tray menu
**Phase 5 & 6**: Add visual feedback and menu reorganization in separate release

---

## Implementation Strategy

### Week 1: Core Functionality
- Complete Phase 1-4 (Foundational + Pause + Resume)
- Get pause/resume working end-to-end
- Write unit tests for state transitions

### Week 2: Visual Feedback & Polish
- Complete Phase 5-6 (Color + Menu)
- Add error handling and notifications
- Write integration tests

### Week 3: Testing & Validation
- Complete Phase 7-8 (Integration + Testing)
- Performance validation
- Cross-platform testing

### Week 4: Documentation
- Complete Phase 9 (Polish)
- Code review and cleanup
- Final validation

---

## Definition of Done

Each task is **complete** when:

1. ✅ Code changes implemented per [quickstart.md](quickstart.md)
2. ✅ All tests pass (unit + integration)
3. ✅ Type hints and docstrings added
4. ✅ Related success criteria from [spec.md](spec.md) verified
5. ✅ Committed to branch with clear message
6. ✅ No new warnings or errors introduced

---

## Success Validation Checklist

After completing all 51 tasks, verify:

- [ ] Pause stops tracking loop and disables camera within 500ms
- [ ] Resume starts tracking loop and enables camera within 500ms
- [ ] Tray icon changes to green when tracking, default when paused
- [ ] Tray icon color updates within 100ms of state change
- [ ] Menu item label reflects tracking state (Pause/Continue)
- [ ] Menu order: Open, Settings, [Sep], Pause/Continue, [Sep], Exit
- [ ] All menu items clickable and functional
- [ ] Camera error auto-pauses tracking with error notification
- [ ] Tracking auto-starts on app initialization
- [ ] Main window close does not stop tracking
- [ ] Rapid pause/continue clicks handled safely
- [ ] No race conditions or deadlocks detected
- [ ] All tests pass on Windows, Linux, macOS
- [ ] Performance targets met (<500ms, <100ms)
- [ ] 100% success criteria from spec.md satisfied

