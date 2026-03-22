# Research: Cat Session Tracking

**Feature**: 012-cat-session-tracking
**Date**: 2026-03-22
**Status**: Complete — no NEEDS CLARIFICATION items remain

---

## R-001: How Multi-Cycle Alerts Already Work

**Decision**: No changes needed to `DetectionLoop` for multi-cycle behavior.

**Rationale**: `DetectionLoop._run()` already naturally produces repeated alert cycles. After each verification fires, `_pending_frame` is cleared. On the next frame where `_cooldown_elapsed()` is True and a cat is detected, a new `SOUND_PLAYED` event fires, `_last_alert_time` is updated, and the cycle begins again. The loop already does exactly what multi-cycle session tracking needs at the detection level — we only need to track that consecutive cycles belong to a common session.

**Alternatives considered**: Adding an explicit "continue session" signal from the tracker back to the loop — rejected as over-engineering; the loop's natural behavior already does it.

---

## R-002: Session State Ownership

**Decision**: Extend `EffectivenessTracker` with session fields (`_session_start: Optional[datetime]`, `_cycle_count: int`). No new class is needed.

**Rationale**: `EffectivenessTracker` already owns the full pending-snapshot lifecycle. Adding session state here is minimal and keeps all effectiveness logic in one place (YAGNI / constitution Principle III). The distinction between "new session" and "new cycle" is:
- `_session_start is None` → new session (first detection or after green outcome)
- `_session_start is not None` and `_pending_frame is None` → new cycle in active session
- `_pending_frame is not None` → mid-cycle, suppress new detections (existing FR-005a guard unchanged)

**Alternatives considered**: A dedicated `SessionTracker` wrapper class — rejected; splits cohesive state across two objects with no reuse benefit.

---

## R-003: Cumulative Elapsed Time Computation

**Decision**: Compute as `int(cycle_count × settings.cooldown_seconds)`, not wall-clock measurement.

**Rationale**: The spec labels ("Cat remained after alert: 30s", "Cat remained after alert: 60s") are explicitly defined as multiples of the cooldown interval. Using `cooldown_seconds` from `Settings` makes the label exactly match the user's configured interval and avoids timing drift. Actual wall-clock elapsed time since session start would differ slightly (due to inference + I/O latency) and would produce confusing non-round numbers that disagree with the configured interval.

**Alternatives considered**: `(datetime.now() - _session_start).total_seconds()` — rejected because it adds variability and disagrees with what the user set in settings.

---

## R-004: Label Message Injection into `annotate_frame`

**Decision**: Add an `outcome_message: Optional[str] = None` parameter to `annotate_frame`. When provided, this string is used in the outcome strip instead of the hardcoded default. Color continues to be determined by `outcome` ("deterred" → green, "remained" → red).

**Rationale**: Keeps the existing color logic unchanged and tested. The only delta is the text content of the strip, which is now caller-supplied. Fully backward-compatible (all existing callers that do not supply `outcome_message` see no behavior change).

**Alternatives considered**:
- Change `outcome` to carry the full message string and encode color via a prefix — rejected; breaks existing tests and API.
- Separate `outcome_color` and `outcome_message` parameters — rejected; redundant since color is already determined by the string outcome value.

---

## R-005: Session Filename Convention

**Decision**: Add `build_session_filepath(root, session_ts, cycle_num) → Path` to `screenshots.py`. Files are stored in the existing flat date-subfolder: `<root>/<yyyy-mm-dd>/session-<YYYYMMDD-HHmmss>-frame-<NNN>.jpg`.

**Rationale**: Re-uses the existing `tracking_directory` setting and the existing date-subfolder layout. All session frames with the same session timestamp sort together when sorted lexicographically. Using a 3-digit zero-padded `NNN` supports up to 999 cycles before collision. This matches Q2: B from the spec clarification session.

Example: `tracking/2026-03-22/20260322-143000-001.jpg`

**Alternatives considered**:
- Per-session subfolder — rejected per spec Q2: B decision.
- Store session timestamp as Unix epoch integer — rejected; not human-readable.

---

## R-006: File Path Injection into the Save Pipeline

**Decision**: Add `filepath: Optional[Path] = None` to `save_screenshot` and `_save_annotated_async`. When provided, the caller-supplied path is used directly (the `build_filepath` auto-naming is bypassed). When `None`, existing behavior is preserved.

**Rationale**: Session frames require a deterministic filename derived from session state (session start timestamp + cycle number), not from the time of saving. Injecting the path at the call site is the minimal change and keeps `save_screenshot` as the single write point for all tracking images.

**Alternatives considered**: Separate `save_session_frame()` function — rejected; duplicates the JPEG encode + error-handling logic already in `save_screenshot`.

---

## R-007: Interaction with Existing spec-005 Window-Open Suppression

**Decision**: Session evaluation frames bypass window-open suppression, same as the current spec-005 annotated screenshots. The `is_window_open=lambda: False` override already in `EffectivenessTracker._save_annotated_async` call applies to session frames unchanged.

**Rationale**: Consistent with the existing rule: annotated effectiveness records (analysis artifacts) are always saved regardless of window state. Session frames are the natural continuation of this policy.

---

## R-008: No New Settings Required

**Decision**: No new `Settings` field for session tracking.

**Rationale**: The cooldown interval (`cooldown_seconds`) already drives the evaluation cadence. Session filenames use the session start timestamp (runtime state, not configuration). There is no user-configurable aspect unique to session tracking.

---

## R-009: Thread Safety

**Decision**: No new locking is needed for session state.

**Rationale**: `EffectivenessTracker.on_detection()` is called from the main thread (via `on_cat_detected` in `main.py`). `on_verification()` is called from the `DetectionLoop` daemon thread. The existing design relies on the guarantee that only one `SOUND_PLAYED` event fires per cooldown cycle (FR-005a), so `on_detection` and `on_verification` do not interleave within a single cycle. The session fields (`_session_start`, `_cycle_count`) are read/written only within those two methods and follow the same one-at-a-time access pattern. No additional synchronization is required.

---

## R-010: Testing Approach

**Decision**: TDD. Unit tests in `tests/unit/test_annotation.py` cover all new `EffectivenessTracker` session state transitions and label generation. Unit tests in `tests/unit/test_screenshots.py` cover `build_session_filepath`. Integration tests in `tests/integration/test_effectiveness_integration.py` cover the full multi-cycle save pipeline.

**Rationale**: Existing test files already cover the modules being extended. Adding to them (rather than creating new files) keeps related tests together. Integration tests verify the end-to-end flow including actual JPEG writes to `tmp_path`.
