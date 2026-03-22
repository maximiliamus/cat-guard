# Tasks: Cat Session Tracking with Evaluation Screenshots

**Input**: Design documents from `/specs/012-cat-session-tracking/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓

**Tests**: Included — TDD required by project constitution (Principle I). Write tests first; verify they FAIL before implementing.

**Organization**: Tasks grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other [P] tasks at the same level (different files, no incomplete dependencies)
- **[Story]**: User story this task belongs to (US1, US2, US3)
- All source paths are under `src/catguard/`; test paths are under `tests/`

---

## Phase 1: Setup

**Purpose**: Verify the test infrastructure is ready before TDD phases begin.

- [X] T001 Confirm `tests/integration/test_effectiveness_integration.py` exists and contains a `@pytest.mark.integration` marker; create a minimal file skeleton with correct imports and the marker if absent

**Checkpoint**: Test infrastructure confirmed — TDD phases can begin.

---

## Phase 2: Foundational — Low-Level API Building Blocks (Plan Changes 1–4)

**Purpose**: Extend `screenshots.py` and `annotation.py` with the new optional parameters and utility function that every user-story phase depends on. All changes are additive (new `Optional` parameters with `None` defaults) and backward-compatible.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

> **TDD**: Write and run T002 and T003 first. Confirm both FAIL. Then implement T004 and T005.

- [X] T002 [P] Write `@pytest.mark.unit` tests for `build_session_filepath` (correct `<root>/<YYYY-MM-DD>/<YYYYMMDD-HHmmss>-<NNN>.jpg` format; 3-digit zero-padded cycle number; date subfolder derived from `session_ts`, not `datetime.now()`; distinct filenames for different cycle numbers) and for `save_screenshot` with explicit `filepath` (writes to the caller-supplied path bypassing `build_filepath`; bypasses both the window-open suppression check and the `is_within_time_window` suppression check) in `tests/unit/test_screenshots.py`
- [X] T003 [P] Write `@pytest.mark.unit` test for `annotate_frame` with `outcome_message` parameter: when `outcome="remained"` and `outcome_message="Cat remained after alert: 30s"`, the custom text appears in the bottom strip instead of the hardcoded default; when `outcome=None`, no strip is drawn even when `outcome_message` is provided in `tests/unit/test_annotation.py`
- [X] T004 [P] Implement `build_session_filepath(root: Path, session_ts: datetime, cycle_num: int) -> Path` and add `filepath: Optional[Path] = None` to `save_screenshot` (when provided: skip `build_filepath`, bypass both suppression checks, call `path.parent.mkdir(parents=True, exist_ok=True)`, then encode and write JPEG) in `src/catguard/screenshots.py` — run T002 tests green
- [X] T005 [P] Add `outcome_message: Optional[str] = None` to `annotate_frame` (color determined by `outcome`; text determined by `outcome_message` when provided, otherwise use existing hardcoded default; `outcome=None` still draws no strip regardless of `outcome_message`) and add `filepath: Optional[Path] = None` to `_save_annotated_async` (forwarded unchanged to `save_screenshot`) in `src/catguard/annotation.py` — run T003 tests green

**Checkpoint**: `build_session_filepath`, `save_screenshot(filepath=…)`, `annotate_frame(outcome_message=…)`, and `_save_annotated_async(filepath=…)` are all tested and green. User story phases can begin.

---

## Phase 3: User Story 1 — Full Cat Session Timeline (Priority: P1) 🎯 MVP

**Goal**: `EffectivenessTracker` tracks a multi-cycle session from the first alert through the final green outcome. A red-labeled evaluation JPEG is saved at every cooldown interval while the cat remains. A green-labeled JPEG is saved when the cat leaves, closing the session.

**Independent Test**: Simulate a cat that stays for two cooldown cycles then leaves on the third. Verify: JPEGs `<prefix>-001.jpg` (red, "Cat remained after alert: Ns"), `<prefix>-002.jpg` (red, "Cat remained after alert: 2Ns"), and `<prefix>-003.jpg` (green, "Cat disappeared after alert: 3Ns") appear in the correct date subfolder. Verify that a subsequent detection starts a fresh session at cycle `001` with a new timestamp prefix.

> **TDD**: Write and run T006 and T007 first. Confirm both FAIL. Then implement T008–T010.

- [X] T006 [P] [US1] Write `@pytest.mark.unit` tests for `EffectivenessTracker` session state machine in `tests/unit/test_annotation.py`:
  - First `on_detection` call sets `_session_start` (non-None) and `_cycle_count = 1`
  - `on_detection` while `_pending_frame is not None` is silently ignored and does NOT increment `_cycle_count`
  - `on_detection` after red verification (pending cleared, session still open) increments `_cycle_count` to 2
  - `on_detection` after green outcome (session closed) starts a new session with `_cycle_count = 1` and a new `_session_start`
  - `on_verification(has_cat=True)` saves red frame with `"Cat remained after alert: {N}s"` and leaves `_session_start` and `_cycle_count` set
  - `on_verification(has_cat=False)` saves green frame with `"Cat disappeared after alert: {N}s"` and resets `_session_start = None`, `_cycle_count = 0`
  - `on_verification` called when both `_pending_frame is None` and `_session_start is None` is a no-op
  - Elapsed time equals `int(cycle_count * settings.cooldown_seconds)` (floor truncation)
  - Session filepath matches `<root>/<YYYY-MM-DD>/<YYYYMMDD-HHmmss>-<NNN>.jpg` with date derived from `_session_start`
- [X] T007 [P] [US1] Write `@pytest.mark.integration` tests for multi-cycle session end-to-end saves in `tests/integration/test_effectiveness_integration.py`:
  - Two-cycle session (one `on_detection` + `on_verification(has_cat=True)`, then `on_detection` + `on_verification(has_cat=False)`): two JPEGs appear in the correct date subfolder with filenames `<prefix>-001.jpg` and `<prefix>-002.jpg`; both are readable JPEG files with non-zero size
  - **FR-009 annotation layers**: decode one saved JPEG with `cv2.imdecode` and assert all three spec-005 annotation layers are present: (1) top info bar — verify a non-uniform pixel region exists in the top ~10% of the image height; (2) bottom outcome strip — verify a non-uniform colored region exists in the bottom ~10% of the image height; (3) bounding box — verify at least one rectangular region differs from the raw frame (pass a frame with a known bounding box in the test)
  - Three-cycle session (two red + one green): three JPEGs; cumulative times in labels are `N`, `2N`, `3N` seconds; only the last JPEG carries a green strip
  - After green outcome, next `on_detection` produces a new JPEG with cycle suffix `001` and a distinct session timestamp prefix
  - Session JPEG date subfolder matches the session start date (set `session_start` explicitly in the test to a known date; verify the subfolder is correct even when the save occurs on a different date)
- [X] T008 [US1] Add `_session_start: Optional[datetime] = None` and `_cycle_count: int = 0` to `EffectivenessTracker.__init__` in `src/catguard/annotation.py`
- [X] T009 [US1] Implement `on_detection` three-state logic in `src/catguard/annotation.py` — check state (a) first (early return if `_pending_frame is not None`); then state (b) if `_session_start is None` (set `_session_start = datetime.now()`, `_cycle_count = 1`); then state (c) (`_cycle_count += 1`); common step: store pending frame, boxes, sound
- [X] T010 [US1] Implement `on_verification` multi-cycle logic in `src/catguard/annotation.py` in this exact order: (1) guard — no-op if `_pending_frame is None` or `_session_start is None`; (2) capture locals (frame, boxes, sound, session_start, cycle_count); (3) clear pending state (`_pending_frame = None`, `_pending_boxes = []`, `_pending_sound = None`); (4) compute `elapsed_s = int(cycle_count * self._settings.cooldown_seconds)`; (5) build timed message (`"Cat remained after alert: {elapsed_s}s"` / `"Cat disappeared after alert: {elapsed_s}s"`); (6) `filepath = build_session_filepath(resolve_root(self._settings), session_start, cycle_count)` (lazy-import from `catguard.screenshots`); (7) annotate frame with `outcome_message`; (8) dispatch `_save_annotated_async(annotated, self._settings, filepath=filepath)`; (9) if `has_cat=False`: reset `self._session_start = None`, `self._cycle_count = 0` — run T006 + T007 tests green

**Checkpoint**: US1 fully functional. Multi-cycle sessions produce correctly ordered red+green JPEG sequences in the tracking folder. The session tracking MVP is complete.

---

## Phase 4: User Story 2 — Single-Cycle Session (Priority: P2)

**Goal**: When the cat leaves after the very first alert, exactly one green-labeled evaluation JPEG is saved (cycle `001`) and the session closes. No red frames are written.

**Independent Test**: Trigger one alert → one `on_verification(has_cat=False)`. Verify exactly one JPEG exists in the session's date subfolder, it carries a green strip, its filename ends in `-001.jpg`, and no red JPEGs exist for that session prefix.

> Implementation is fully covered by Phase 3 (US1). A single integration test confirms the single-cycle happy path.

- [X] T011 [US2] Write `@pytest.mark.integration` test for single-cycle green session in `tests/integration/test_effectiveness_integration.py`: one `on_detection` + one `on_verification(has_cat=False)` → exactly one JPEG with suffix `-001.jpg` in the date subfolder; JPEG is a valid image; no red-strip JPEG exists for that session prefix

**Checkpoint**: US2 validated. Cat deterred immediately on first alert produces exactly one green frame.

---

## Phase 5: User Story 3 — Long-Running Session (Priority: P2)

**Goal**: A persistent cat triggers indefinitely accumulating red-labeled evaluation JPEGs across as many cooldown cycles as needed. No session data is lost or capped after many cycles.

**Independent Test**: Drive five consecutive alert+verification cycles with `has_cat=True`. Verify five red JPEGs exist with cumulative elapsed times equal to `N × cooldown_seconds` for N = 1 to 5, each with the correct sequential filename suffix (`-001.jpg` through `-005.jpg`), and the session remains open after the fifth cycle.

> Implementation is fully covered by Phase 3 (US1). A single integration test confirms indefinite accumulation.

- [X] T012 [US3] Write `@pytest.mark.integration` test for long-running session in `tests/integration/test_effectiveness_integration.py`: drive five `on_detection` + `on_verification(has_cat=True)` cycles; verify five red JPEGs exist with filenames `-001.jpg` through `-005.jpg`; verify cumulative elapsed times in labels equal `1×cooldown`, `2×cooldown`, … `5×cooldown`; verify `_session_start` is still set and `_cycle_count = 5` after the fifth cycle (session not prematurely closed)

**Checkpoint**: US3 validated. Long-running sessions accumulate indefinitely without data loss or premature session closure.

---

## Phase 6: Session Abandon on Pause (Plan Change 6)

**Purpose**: Any pause — manual (user), camera error (auto-pause), or time-window boundary (auto-pause) — immediately abandons the active session. No stale verification fires after resume; the next detection starts a fresh session.

> **TDD**: Write and run T013 first. Confirm it FAILS. T014 is an independent change to a different file and can be done in parallel with T013. Then implement T015 (depends on T013). Then T016.

- [X] T013 [P] Write `@pytest.mark.unit` tests for `EffectivenessTracker.abandon()` in `tests/unit/test_annotation.py`:
  - `abandon()` during an active session (with `_session_start` set, `_pending_frame` set) resets `_pending_frame = None`, `_pending_boxes = []`, `_pending_sound = None`, `_session_start = None`, `_cycle_count = 0`
  - `abandon()` when no session is active (all fields already at zero/None) raises no exception (idempotent no-op)
  - `on_detection` called immediately after `abandon()` starts a fresh session with `_cycle_count = 1` and a new non-None `_session_start`
- [X] T014 [P] Add `self._pending_frame = None` to `DetectionLoop.pause()` in `src/catguard/detection.py` (defense-in-depth: prevents a stale pending frame from triggering a spurious verification after resume if `abandon()` was not called via `main.py`)
- [X] T015 Implement `EffectivenessTracker.abandon()` in `src/catguard/annotation.py`: reset `_pending_frame = None`, `_pending_boxes = []`, `_pending_sound = None`, `_session_start = None`, `_cycle_count = 0`; log an info-level message when called with an active session (log nothing when already idle); method must be safe to call at any time — run T013 tests green
- [X] T016 Wire `tracker.abandon()` in `src/catguard/main.py`: call `tracker.abandon()` inside `on_camera_error` (before or after the existing tray notification); call `tracker.abandon()` inside `on_tracking_state_changed` when `active=False` (covers both manual pause and time-window auto-pause)

**Checkpoint**: Pause correctly abandons sessions. No stale verification screenshots are produced after resume.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T017 [P] Add structured logging for session lifecycle events in `src/catguard/annotation.py`: log session start (include `session_start` timestamp), each evaluation cycle saved (cycle number, elapsed time, red/green outcome, filepath), and session close; use the existing logger and log levels consistent with surrounding code in the file
- [X] T018 [P] Run the full test suite (`pytest -m unit` then `pytest -m integration`) and confirm all new tests pass; fix any failures before closing the feature branch

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **blocks all user story phases**
- **US1 (Phase 3)**: Depends on Phase 2 completion
- **US2 (Phase 4)**: Depends on Phase 3 completion — implementation provided by US1; test-only phase
- **US3 (Phase 5)**: Depends on Phase 3 completion — implementation provided by US1; test-only phase
- **Abandon (Phase 6)**: Depends on Phase 3 completion — requires `EffectivenessTracker` session fields from T008
- **Polish (Phase 7)**: Depends on all prior phases complete

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2 — no dependency on US2/US3
- **US2 (P2)**: Starts after Phase 3 — US2 and US3 can be done in parallel (both write to the same integration test file, so sequence the test additions within that file)
- **US3 (P2)**: Starts after Phase 3 — parallel with US2

### Within `annotation.py` (sequential — all modify the same file)

T005 → T008 → T009 → T010 → T015 → T017

### Parallel Opportunities

- T002 and T003 can be started together (different test files)
- T004 and T005 can be started together after T002 and T003 respectively (different source files)
- T006 and T007 can be started together (different test files)
- T013 and T015 can be started together (different files)

---

## Parallel Execution Examples

### Phase 2: Foundational

```text
Parallel slot A: T002 — screenshots unit tests  (tests/unit/test_screenshots.py)
Parallel slot B: T003 — annotate_frame unit test (tests/unit/test_annotation.py)
  ↓ (after both pass red-phase confirm)
Parallel slot A: T004 — implement screenshots.py changes
Parallel slot B: T005 — implement annotation.py foundational changes
```

### Phase 3: User Story 1

```text
Parallel slot A: T006 — session state unit tests      (tests/unit/test_annotation.py)
Parallel slot B: T007 — multi-cycle integration tests (tests/integration/...)
  ↓ (after both pass red-phase confirm)
Sequential: T008 → T009 → T010  (all modify src/catguard/annotation.py)
```

### Phase 6: Abandon

```text
Parallel slot A: T013 — abandon() unit tests      (tests/unit/test_annotation.py)
Parallel slot B: T014 — detection.py defense      (src/catguard/detection.py)
  ↓ (after T013 passes red-phase confirm)
Sequential: T015 (annotation.py) → T016 (main.py)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks all stories)
3. Complete Phase 3: User Story 1 (core session state machine)
4. **STOP and VALIDATE**: Run integration tests; open saved JPEGs; verify red/green sequence and correct filenames
5. Optional: demo multi-cycle session before continuing

### Incremental Delivery

1. Phase 1 + Phase 2 → foundational API ready and tested
2. Phase 3 (US1) → MVP: live multi-cycle session tracking
3. Phase 4 (US2) + Phase 5 (US3) → scenario coverage confirmed
4. Phase 6 → pause/abandon correctness
5. Phase 7 → logging + full test suite verification

---

## Notes

- [P] tasks = different files, no incomplete dependencies — safe to parallelize
- [Story] labels map tasks to user stories for traceability and independent testing
- TDD is a constitution requirement: always confirm tests FAIL before implementing
- `annotation.py` has the longest sequential chain — it is the critical path; prioritize it
- Commit after each phase checkpoint, or after each completed task
- T015 (detection.py) is a small, low-risk one-liner addition; do it early in Phase 6 to avoid forgetting it
