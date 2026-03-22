# Plan Checklist: Cat Session Tracking with Evaluation Screenshots

**Purpose**: Validate the implementation plan for completeness, clarity, consistency with the spec, and readiness for task generation
**Created**: 2026-03-22
**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md)

## Spec-to-Plan Traceability

- [x] CHK001 - Is every functional requirement (FR-001 to FR-011) traceable to at least one named design change or decision in plan.md? [Completeness, Spec §Requirements] → **Resolved**: plan §Spec-to-Plan Traceability table now maps all FR-001–FR-011 and SC-001–SC-005 to design changes and test cases.
- [x] CHK002 - Does the plan explicitly address FR-010 (camera unavailable during evaluation → skip cycle, keep session open)? The existing `DetectionLoop` auto-pauses on camera read failure — is it clear whether session state survives a pause/resume cycle? [Gap, Spec §FR-010] → **Resolved**: any pause (camera error, manual, time-window) calls `tracker.abandon()`, which immediately resets all session state — no frame is saved for the in-progress cycle and no session continues after resume. plan §Change 6 documents `abandon()`, `DetectionLoop.pause()` defense-in-depth, and `main.py` wiring. Spec Edge Cases and §Change 5 camera note updated accordingly.
- [x] CHK003 - Are all five Success Criteria (SC-001 to SC-005) traceable to a testable design element or test case in the plan? [Traceability, Spec §Success Criteria] → **Resolved**: traceability table covers SC-001–SC-005.
- [x] CHK004 - Does the plan account for the spec-005 time window check (`is_within_time_window`) inside `save_screenshot`? Session frames must always be saved regardless of window, but the current `save_screenshot` code enforces the window. Is bypassing this gate explicitly designed? [Gap, Spec §FR-009, Assumption] → **Resolved**: plan §Change 2 now explicitly states that providing an explicit `filepath` bypasses both window-open and time-window suppression checks.
- [x] CHK005 - Does the plan address the spec assumption "existing annotation conventions from spec-005 apply to every evaluation frame"? Is it clear that `FR-009`'s bounding boxes, top bar, and bottom strip are all preserved in the new multi-cycle flow? [Completeness, Spec §FR-009] → **Resolved**: plan §Change 3 now explicitly states all other annotation layers are unchanged; `outcome_message` only affects bottom strip text.

## Design Completeness

- [x] CHK006 - Is the behavior of `build_session_filepath` fully specified for its parameters? Does the plan state whether the function creates the parent date-subfolder if it doesn't exist, or whether that responsibility stays in `save_screenshot`? [Clarity, Plan §Change 1] → **Resolved**: plan §Change 1 now states parent dir creation is `save_screenshot`'s responsibility.
- [x] CHK007 - Is a collision strategy defined for `build_session_filepath` when two sessions start within the same second (producing identical `YYYYMMDD-HHmmss` prefixes)? [Edge Case, Plan §Change 1] → **Resolved**: plan §Change 1 documents same-second collision is impossible by design (cooldown gap ≥15 s between sessions).
- [x] CHK008 - Is the upper bound of the 3-digit cycle counter (`NNN`, max 999) acknowledged? Does the plan define behavior for sessions exceeding 999 cycles? [Edge Case, Plan §Change 1] → **Resolved**: plan §Change 1 documents >999 cycles produce a 4-digit suffix; accepted edge case.
- [x] CHK009 - Does Change 5 (EffectivenessTracker session state) fully specify the `on_detection` code path for all three states: (a) no session + no pending, (b) session active + no pending, (c) session active + pending? [Clarity, Plan §Change 5] → **Resolved**: plan §Change 5 `on_detection` now has a three-state table with conditions and actions for all cases.
- [x] CHK010 - Is the `is_window_open=lambda: False` override explicitly documented as required for the session frame save call in `_save_annotated_async`? [Clarity, Plan §Change 4, research.md §R-007] → **Resolved**: plan §Change 4 now explains that the explicit `filepath` makes the `is_window_open` argument irrelevant for session frames; `lambda: False` is still passed for signature compatibility.
- [x] CHK011 - Does the plan specify who is responsible for importing `build_session_filepath` inside `EffectivenessTracker.on_verification`? Is the cross-module import from `catguard.screenshots` explicit? [Completeness, Plan §Change 5] → **Resolved**: plan §Change 3 now documents the lazy import pattern from `catguard.screenshots` and confirms no circular dependency.
- [x] CHK012 - Is the behavior of `annotate_frame` when `outcome` is neither "deterred" nor "remained" but `outcome_message` is provided fully defined? [Clarity, Plan §Change 3] → **Resolved**: plan §Change 3 now specifies that `outcome=None` means no strip is drawn regardless of `outcome_message`; `outcome` determines color, `outcome_message` determines text.

## Design Clarity

- [x] CHK013 - Is the elapsed time formula `int(cycle_count × cooldown_seconds)` precise enough to be unambiguous? For a cooldown of 15.0 s, cycle 1 produces "15s", cycle 2 "30s" — is this rounding behavior (floor via `int()`) explicitly stated and intentional? [Clarity, Plan §Change 5, research.md §R-003] → **Resolved**: plan §Change 5 `on_verification` step 4 now states `int()` truncates (floor) with example.
- [x] CHK014 - Is the distinction between "new session" (session_start is None) and "new cycle in active session" (session_start is not None, pending_frame is None) stated clearly enough to be unambiguous for an implementer seeing these states for the first time? [Clarity, Plan §Change 5] → **Resolved**: plan §Change 5 `on_detection` now has an explicit three-row state table with conditions, making state (b) vs (c) unambiguous.
- [x] CHK015 - Is the term "close the session" precisely defined? Specifically, are the exact fields reset (`_session_start = None`, `_cycle_count = 0`) listed explicitly in the plan, or left implicit? [Clarity, Plan §Change 5] → **Resolved**: plan §Change 5 step 9 now lists both fields explicitly.
- [x] CHK016 - Does the plan clearly state that `_cycle_count` is incremented BEFORE the filepath is computed (so cycle 1 saves as `-001.jpg`, not `-000.jpg`)? [Clarity, Plan §Change 5] → **Resolved**: plan §Change 5 `on_detection` step 2/3 sets/increments cycle_count; `on_verification` uses it in step 6 — ordering is now explicit.
- [x] CHK017 - Is the ordering of operations in `on_verification` unambiguous? Specifically: clear pending state first, then compute filepath, then annotate, then dispatch async save — or a different order? [Clarity, Plan §Change 5] → **Resolved**: plan §Change 5 `on_verification` is now a numbered ordered list with "in this exact order" preamble.

## Edge Case Design Coverage

- [x] CHK018 - Does the plan design address what happens to session state (`_session_start`, `_cycle_count`, `_pending_frame`) when the application is stopped while a session is active but between cycles (pending cleared, session still open)? [Edge Case, Spec §Assumptions] → **Resolved**: plan §Change 5 "App stopped between cycles" note added — all in-memory session state lost on exit, no partial file written, no green frame produced; consistent with spec Assumptions.
- [x] CHK019 - Does the plan address the spec edge case "camera unavailable during evaluation"? Specifically, when `DetectionLoop` auto-pauses and exits its thread, does `on_verification` ever fire? If not, how does the session eventually resume or close? [Gap, Spec §Edge Cases] → **Resolved**: `on_verification` does NOT fire after auto-pause. Instead, `on_camera_error` in `main.py` immediately calls `tracker.abandon()`, resetting all session state. On resume, the next detection starts a fresh session. Plan §Change 6 and spec Edge Cases both reflect this design (pause = abandon, not preserve).
- [x] CHK020 - Is the behavior defined for `on_detection` being called while `_pending_frame is not None` during a running session (the FR-005a guard)? Does the guard prevent cycle count increment in this case? [Clarity, Plan §Change 5, Spec §FR-003] → **Resolved**: plan §Change 5 `on_detection` step 1 fires first; `_cycle_count` is not incremented when the guard fires (step 2/3 is skipped).
- [x] CHK021 - Does the plan address what happens if `on_verification` fires but `_session_start` is None (defensive guard)? Is this no-op behavior explicitly designed? [Edge Case, Plan §Change 5] → **Resolved**: plan §Change 5 `on_verification` step 1 now includes the `_session_start is None` defensive no-op guard.

## Test Plan Completeness

- [x] CHK022 - Does the test plan include a case for `save_screenshot` with `filepath=<explicit Path>` bypassing `build_filepath` auto-naming? [Completeness, Plan §Test Plan] → **Resolved**: added to unit test plan for `test_screenshots.py`.
- [x] CHK023 - Does the test plan include a case verifying that the time window bypass (`is_window_open=lambda: False`) is applied to session frame saves? [Gap, Plan §Test Plan] → **Resolved**: added as `save_screenshot` with explicit filepath skips both suppression checks.
- [x] CHK024 - Is there a test case for `on_detection` being called with `_pending_frame is not None` during an active session — confirming it is silently ignored AND `_cycle_count` is NOT incremented? [Completeness, Plan §Test Plan] → **Resolved**: added explicitly to `test_annotation.py` unit tests.
- [x] CHK025 - Is there a test case for `on_verification` being called when no session is active (`_session_start is None`)? [Edge Case, Plan §Test Plan] → **Resolved**: added as "`on_verification` called when `_session_start is None` and `_pending_frame is None` is a no-op".
- [x] CHK026 - Does the integration test plan verify that the session-prefixed filename (`YYYYMMDD-HHmmss-NNN.jpg`) appears in the correct date-subfolder (the session start date, not the save date)? [Completeness, Plan §Test Plan] → **Resolved**: added as final integration test case.
- [x] CHK027 - Is there a test case for the complete "after green outcome, next detection starts a fresh session with cycle 001 and a new session timestamp"? [Completeness, Plan §Test Plan] → **Resolved**: already covered in integration tests.
- [x] CHK028 - Does the test plan specify which tests are unit (`@pytest.mark.unit`) vs integration (`@pytest.mark.integration`)? [Clarity, Plan §Test Plan] → **Resolved**: both test sections now carry explicit marker labels.

## Non-Functional Requirements

- [x] CHK029 - Does the plan confirm that no new threading locks are introduced, and is the rationale for this decision (single-event-per-cycle guarantee) documented and traceable to a research decision? [Consistency, Plan §Technical Context, research.md §R-009] → **Resolved**: plan §Change 5 `on_detection` thread safety note now documents that both callbacks run on the detection daemon thread sequentially, with explicit reference to research.md §R-009.
- [x] CHK030 - Does the plan address the async error isolation requirement (NFR-002 from spec-005): that a session frame save failure must never crash the app or interrupt subsequent detection events? [Completeness, Spec §SC-005] → **Resolved**: plan §Change 5 "Async error isolation (NFR-002)" note added — session frames inherit full error-isolation contract from existing `_save_annotated_async`.
- [x] CHK031 - Is it specified that the session state (`_session_start`, `_cycle_count`) is NOT persisted to disk and is lost on app restart — and that this is intentional per the spec assumption? [Clarity, Spec §Assumptions] → **Resolved**: plan §Change 5 now includes explicit "Session state persistence" note.

## Dependencies & Assumptions

- [x] CHK032 - Is the dependency on `DetectionLoop`'s natural re-alerting behavior (producing a new `SOUND_PLAYED` event after each verification cycle) explicitly documented as a required precondition, not just described in research? [Dependency, research.md §R-001] → **Resolved**: plan §Change 5 now includes "DetectionLoop re-alerting as precondition" note.
- [x] CHK033 - Does the plan specify the minimum version or API contract of `DetectionLoop.set_verification_callback` that this feature depends on? [Dependency, Plan §Technical Context] → **Resolved**: plan §Change 5 now documents the stable internal API contract: `cb(has_cat: bool, boxes: list[BoundingBox]) -> None`.
- [x] CHK034 - Is the assumption that `on_detection` is always called from the main thread (and `on_verification` from the daemon thread) explicitly stated in the plan's thread safety section? [Assumption, research.md §R-009] → **Resolved**: plan §Change 5 `on_detection` thread safety note now corrects this — both callbacks are called from the DetectionLoop daemon thread; thread safety is guaranteed by the sequential single-threaded detection loop, not by thread identity.

## Notes

- All 34 items resolved as of 2026-03-22.
- CHK002/CHK019 resolution notes updated 2026-03-22: corrected design — pause abandons the session (calls `tracker.abandon()`), not preserves it. Plan §Change 6 added. Data-model.md state machine updated with abandon paths.
- Plan is ready for `/speckit.tasks`.
