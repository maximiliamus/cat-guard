# Tasks: Tray Directory Shortcuts

**Input**: Design documents from `/specs/015-directory-menu-links/`  
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Included — TDD required by project constitution (Principle I). Write tests first and confirm they fail before implementation.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other [P] tasks at the same phase level
- **[Story]**: User story label (`US1`, `US2`, `US3`)
- All source paths are under `src/catguard/`; all test paths are under `tests/`

---

## Phase 1: Setup

**Purpose**: Prepare the shared tray shortcut test surface without introducing new runtime modules.

- [X] T001 Create the integration test scaffold `tests/integration/test_tray_directory_shortcuts.py` with shared helpers to capture tray menu callbacks built from `src/catguard/tray.py`

**Checkpoint**: Integration test file exists and is ready for story-specific TDD work.

---

## Phase 2: Foundational (Shared Building Blocks)

**Purpose**: Add the shared path-normalization and cross-platform directory-opening helper used by all tray shortcut stories.

**⚠️ CRITICAL**: No user story work should begin until this phase is complete.

> **TDD**: Write T002 first and confirm it fails. Then implement T003.

- [X] T002 [P] Write unit tests for whitespace trimming, relative-path resolution, missing-directory creation, and Windows/macOS/Linux launcher dispatch for `_resolve_directory_path()` and `_open_directory()` in `tests/unit/test_tray.py`
- [X] T003 Implement `_resolve_directory_path()` and `_open_directory()` in `src/catguard/tray.py`

**Checkpoint**: Shared directory-opening behavior is green and reusable by all tray menu callbacks.

---

## Phase 3: User Story 1 - Open Tracking Screenshots Folder From the Tray (Priority: P1) 🎯 MVP

**Goal**: Users can click `Tracking Directory` from the tray to open the configured tracking folder, creating it first when needed and surfacing failures non-blockingly.

**Independent Test**: Launch the app, open the tray menu, click `Tracking Directory`, and verify the configured tracking folder opens in the OS file manager; if the folder does not exist, it is created first.

> **TDD**: Write T004 and T005 first. Confirm both fail. Then implement T006 and T007.

- [X] T004 [P] [US1] Write unit tests for `Tracking Directory` menu-item presence in both `build_tray_icon()` and `update_tray_menu()` in `tests/unit/test_tray.py`
- [X] T005 [P] [US1] Write an integration test for the tracking-directory tray callback creating and targeting `settings.tracking_directory` in `tests/integration/test_tray_directory_shortcuts.py`
- [X] T006 [US1] Add the `Tracking Directory` tray callback and menu item to `build_tray_icon()` in `src/catguard/tray.py`
- [X] T007 [US1] Add the tracking-directory callback to `update_tray_menu()` and route callback failures through `notify_error()` in `src/catguard/tray.py`

**Checkpoint**: The tracking directory shortcut works independently and can be demoed as the MVP.

---

## Phase 4: User Story 2 - Open Saved Photos Folder From the Tray (Priority: P2)

**Goal**: Users can click `Photos Directory` from the tray to open the configured photos folder using the same normalization, creation, and failure behavior as the tracking shortcut.

**Independent Test**: Launch the app, open the tray menu, click `Photos Directory`, and verify the configured photos folder opens in the OS file manager; if the folder does not exist, it is created first.

> **TDD**: Write T008 and T009 first. Confirm both fail. Then implement T010 and T011.

- [X] T008 [P] [US2] Write unit tests for `Photos Directory` menu-item presence in both `build_tray_icon()` and `update_tray_menu()` in `tests/unit/test_tray.py`
- [X] T009 [P] [US2] Write an integration test for the photos-directory tray callback creating and targeting `settings.photos_directory` in `tests/integration/test_tray_directory_shortcuts.py`
- [X] T010 [US2] Add the `Photos Directory` tray callback and menu item to `build_tray_icon()` in `src/catguard/tray.py`
- [X] T011 [US2] Add the photos-directory callback to `update_tray_menu()` and ensure it reuses the shared normalization/launcher path in `src/catguard/tray.py`

**Checkpoint**: Both directory shortcuts work, and each can be validated independently from the tray.

---

## Phase 5: User Story 3 - Keep Tray Menu Layout Predictable (Priority: P3)

**Goal**: The tray menu keeps a stable order in both active and paused states: `Live View`, `Logs`, `Settings…`, separator, `Pause` / `Continue`, separator, `Tracking Directory`, `Photos Directory`, separator, `Exit`.

**Independent Test**: Build the tray menu in active and paused states, then verify the exact item order and confirm pause/resume rebuilds preserve the two directory items and the final `Exit` position.

> **TDD**: Write T012 and T013 first. Confirm both fail. Then implement T014.

- [X] T012 [P] [US3] Write unit tests for exact active/paused tray menu order and separator placement in `tests/unit/test_tray.py`
- [X] T013 [P] [US3] Write an integration test that tray menu rebuilds after pause/resume preserve both directory items and keep `Exit` last in `tests/integration/test_tray_directory_shortcuts.py`
- [X] T014 [US3] Refactor tray menu construction so `build_tray_icon()` and `update_tray_menu()` emit the identical ordered menu structure in `src/catguard/tray.py`

**Checkpoint**: Menu layout is stable across tracking-state changes and matches the tray-menu contract exactly.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Run the documented validation flow and confirm the feature satisfies the spec and contract.

- [ ] T015 [P] Run the manual acceptance scenarios and failure-path checks documented in `specs/015-directory-menu-links/quickstart.md`
- [X] T016 Run the focused automated validation commands for `tests/unit/test_tray.py` and `tests/integration/test_tray_directory_shortcuts.py`, then verify success criteria against `specs/015-directory-menu-links/spec.md` and `specs/015-directory-menu-links/contracts/tray-menu.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup completion; blocks all story work
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 2 (Phase 4)**: Depends on Foundational completion; independent of US1 aside from using the same tray helper
- **User Story 3 (Phase 5)**: Depends on US1 and US2 because the final menu order includes both directory items
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1**: First independently deliverable increment; recommended MVP
- **US2**: Independent folder shortcut built on the same foundational opener helper
- **US3**: Final ordering and rebuild consistency pass once both shortcuts exist

### Within Each User Story

- Tests MUST be written and observed failing before implementation
- Menu-presence tests precede callback wiring
- Callback wiring precedes final menu-order refactor

### Parallel Opportunities

- T004 and T005 can run in parallel
- T008 and T009 can run in parallel
- T012 and T013 can run in parallel
- US1 and US2 can proceed in parallel after Foundational completion if different engineers own separate test and callback changes

---

## Parallel Example: User Story 1

```text
Parallel slot A: T004 — add tracking menu presence assertions in tests/unit/test_tray.py
Parallel slot B: T005 — add tracking callback integration coverage in tests/integration/test_tray_directory_shortcuts.py
  ↓
Sequential: T006 — wire build_tray_icon() tracking callback in src/catguard/tray.py
  ↓
Sequential: T007 — preserve tracking shortcut through update_tray_menu() and notify_error() in src/catguard/tray.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. Stop and validate that `Tracking Directory` works end-to-end from the tray

### Incremental Delivery

1. Add shared directory-opening helper in Phase 2
2. Deliver the tracking shortcut in US1
3. Deliver the photos shortcut in US2
4. Finalize exact ordering and rebuild consistency in US3
5. Run quickstart/manual validation and focused automated tests in Phase 6

### Parallel Team Strategy

1. One engineer handles the foundational tray opener helper
2. After Phase 2, one engineer can own US1 while another owns US2
3. Merge both shortcuts before a final US3 pass on exact menu ordering

---

## Notes

- [P] tasks are parallelizable because they touch different files or independent test layers
- `src/catguard/tray.py` is the critical-path runtime file for the entire feature
- Native Explorer/Finder/file-manager window opening remains a manual validation concern even when callback wiring is covered by tests
- Keep tray failures non-blocking and reuse the existing `notify_error()` user-feedback path
