# Implementation Plan: Cat Session Tracking with Evaluation Screenshots

**Branch**: `012-cat-session-tracking` | **Date**: 2026-03-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/012-cat-session-tracking/spec.md`

## Summary

Extend `EffectivenessTracker` to track a multi-cycle "cat session" from the first alert through to the cat leaving, saving an annotated evaluation JPEG at the end of every cooldown interval. Each frame is labeled with cumulative elapsed time ("Cat remained after alert: 30s" in red; "Cat disappeared after alert: 60s" in green). All session frames for one visit share a filename prefix derived from the session start timestamp, stored in the existing flat tracking folder.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: opencv-python (cv2), onnxruntime, Pillow (PIL), numpy, pydantic, platformdirs, pystray, tkinter (stdlib)
**Storage**: JPEG files on disk under `settings.tracking_directory`; settings persisted as JSON via pydantic `Settings` model
**Testing**: pytest; unit tests with `@pytest.mark.unit` (mock cv2/filesystem); integration tests with `@pytest.mark.integration` (real cv2, real tmp_path disk writes)
**Target Platform**: Windows / macOS / Linux desktop (cross-platform)
**Project Type**: Desktop application (tkinter UI + pystray system tray)
**Performance Goals**: Evaluation screenshot saves must not delay the detection loop; all disk I/O is async (daemon thread, fire-and-forget)
**Constraints**: <200ms p95 latency for detection (constitution); screenshot save errors must never crash the app (NFR-002 from spec-005)
**Scale/Scope**: Single-user desktop app; one active session at a time; session length unbounded

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Test-First Development (TDD) | PASS | All new functions and state transitions covered by unit tests written before implementation |
| II. Observability & Logging | PASS | Existing structured logging in `EffectivenessTracker` extended for session start/close/cycle events |
| III. Simplicity & Clarity (YAGNI) | PASS | No new class; session state added to existing `EffectivenessTracker`; no new settings |
| IV. Integration Testing | PASS | Integration tests verify multi-cycle end-to-end JPEG saves to `tmp_path` |
| V. Versioning & Breaking Changes | PASS | All changes are additive (new optional parameters with defaults); no breaking API changes |

**Post-design re-check**: All principles still satisfied. `annotate_frame` new `outcome_message` parameter is optional with `None` default (backward-compatible). `save_screenshot` new `filepath` parameter is optional with `None` default (backward-compatible).

## Project Structure

### Documentation (this feature)

```text
specs/012-cat-session-tracking/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (affected files only)

```text
src/catguard/
├── annotation.py        # EffectivenessTracker (session state), annotate_frame (outcome_message param), _save_annotated_async (filepath param)
└── screenshots.py       # save_screenshot (filepath param), build_session_filepath() (new)

tests/unit/
├── test_annotation.py   # New session state machine tests, timed label tests
└── test_screenshots.py  # New build_session_filepath() tests

tests/integration/
└── test_effectiveness_integration.py   # New multi-cycle session integration tests
```

**Structure Decision**: Single project layout (Option 1). Three source modules change (`annotation.py`, `screenshots.py`, `main.py`); no new modules or directories are needed.

## Complexity Tracking

*No constitution violations. Section left blank.*

---

## Spec-to-Plan Traceability

| Requirement | Design Change | Test Coverage |
|---|---|---|
| FR-001: Start session on alert | Change 5 — `on_detection` steps 2–3 | Unit: first on_detection starts session |
| FR-002: Session active until green | Change 5 — `on_verification` step 9 | Unit: session remains after red; closes after green |
| FR-003: New detection absorbed into active session | Change 5 — `on_detection` step 3 (cycle increment) | Unit: second on_detection increments cycle_count |
| FR-004: Green closes session; next detection = new session | Change 5 — `on_verification` step 9; `on_detection` step 2 | Integration: after green, next session gets cycle 001 |
| FR-005: Evaluation after each cooldown | research R-001 — existing `DetectionLoop` natural re-alerting | Integration: multi-cycle sessions produce frames at each interval |
| FR-006: Red label with cumulative time | Change 5 — `on_verification` step 5 | Unit: red message text and session remaining open |
| FR-007: Green label with cumulative time | Change 5 — `on_verification` step 5 | Unit: green message text and session closing |
| FR-008: Cumulative time = cycle × cooldown | Change 5 — `on_verification` step 4 | Unit: elapsed_s formula with varied cooldown values |
| FR-009: All spec-005 annotations preserved | Change 3 — `outcome_message` added; existing bounding box / top-bar / bottom-strip layers in `annotate_frame` unchanged | Integration: saved JPEG contains boxes + top bar + bottom strip |
| FR-010: Skip cycle on camera unavailability | Change 6 — `abandon()` called on any pause; no frame saved; session closed | Unit: `abandon()` resets all session state; Integration: after pause, next detection starts a fresh session |
| FR-011: Session-prefixed filename in flat folder | Change 1 — `build_session_filepath` | Unit: filename format; Integration: file appears in correct date subfolder |
| SC-001: User can reconstruct timeline from frames | Change 1 + Change 5 — ordered filenames + monotonic cycle labels | Integration: three-cycle session produces ordered readable files |
| SC-002: Cumulative time accurate within cooldown duration | Change 5 — `int(cycle_count × cooldown_seconds)` | Unit: elapsed_s equals expected multiple |
| SC-003: One green frame as final frame of completed session | Change 5 — `on_verification` green path | Integration: exactly one green JPEG per completed session |
| SC-004: Red frames accumulate without truncation | Change 5 — no max cycle limit | Integration: long-running session test (≥3 red cycles) |
| SC-005: Saves don't block detection loop | Change 4 — `_save_annotated_async` daemon thread | Constitution NFR-001 — confirmed in plan Technical Context |

---

## Implementation Design

### Change 1 — `screenshots.py`: `build_session_filepath`

New pure function alongside existing `build_filepath`:

```
build_session_filepath(root: Path, session_ts: datetime, cycle_num: int) -> Path
```

- Output: `<root>/<yyyy-mm-dd>/<YYYYMMDD-HHmmss>-<NNN>.jpg`
- `<yyyy-mm-dd>` derived from `session_ts` (consistent date subfolder for all frames in a session)
- `<NNN>` is zero-padded to 3 digits (`f"{cycle_num:03d}"`)
- No collision suffix needed: cycle numbers are unique within a session by design
- Parent directory creation is **not** the responsibility of `build_session_filepath` — it only computes and returns the path. `save_screenshot` already calls `path.parent.mkdir(parents=True, exist_ok=True)` before writing.
- **Same-second collision prevention**: impossible by design. A session cannot start within the same second as a previous one because at least one cooldown interval (≥15 s default) must elapse between the green outcome of the previous session and a new detection. Two concurrent sessions cannot exist (single-user, single-camera app).
- **>999 cycles**: a 4-digit or longer suffix (e.g., `-1000.jpg`) is produced naturally by `f"{cycle_num:03d}"` for cycles ≥ 1000. The filename remains unique and human-readable. This edge case requires sustained detection for 4+ hours at the minimum cooldown and is accepted as-is.

### Change 2 — `screenshots.py`: `save_screenshot` filepath parameter

Add `filepath: Optional[Path] = None`:
- When `filepath` is provided: use it directly (skip `build_filepath`; still create parent dirs via `path.parent.mkdir`). **Both the window-open suppression check (`is_window_open`) and the time-window suppression check (`is_within_time_window`) are bypassed** — an explicit filepath signals a deliberate, unconditional save decision by the caller. This mirrors the existing `lambda: False` override used by `EffectivenessTracker` for window-open suppression.
- When `filepath` is None: existing behavior unchanged (both suppression checks apply)

### Change 3 — `annotation.py`: `annotate_frame` outcome_message parameter

Add `outcome_message: Optional[str] = None`:
- `outcome` continues to determine the **color** of the outcome strip ("deterred" → green, "remained" → red, `None` → no strip drawn).
- `outcome_message` determines the **text** displayed in the strip. When provided and `outcome` is "deterred" or "remained", use `outcome_message` as the strip text instead of the hardcoded default. When `outcome_message` is `None`, use the existing hardcoded defaults ("Cat disappeared after alert" / "Cat remained after alert").
- When `outcome` is `None` (unknown), no outcome strip is drawn **regardless of whether `outcome_message` is provided**. This preserves the existing spec-005 FR-012 behavior for unknown outcomes.
- **All other annotation layers** (bounding boxes with confidence scores, top info bar with sound label and timestamp) are unchanged — `outcome_message` only affects the bottom strip text. FR-009's full annotation set is preserved.

**Cross-module import**: `EffectivenessTracker.on_verification` needs `build_session_filepath` and `resolve_root` from `catguard.screenshots`. These MUST be imported inside `on_verification` (or inside `_save_annotated_async`'s `_worker`), using the same lazy-import pattern already used by `_save_annotated_async` to avoid circular imports. `catguard.screenshots` does not import from `catguard.annotation`, so no circular dependency exists.

### Change 4 — `annotation.py`: `_save_annotated_async` filepath parameter

Add `filepath: Optional[Path] = None`, forwarded to `save_screenshot`.

**`is_window_open` override**: because Change 2 specifies that providing an explicit `filepath` already bypasses both window-open and time-window suppression checks inside `save_screenshot`, the existing `lambda: False` override passed by `EffectivenessTracker` is no longer the sole mechanism for bypassing window suppression for session frames. The explicit `filepath` makes the `is_window_open` argument irrelevant for session frame saves; it is still passed (as `lambda: False`) for compatibility with the existing `save_screenshot` signature when `filepath` is None.

### Change 5 — `annotation.py`: `EffectivenessTracker` session state

Add two fields:
- `_session_start: Optional[datetime] = None`
- `_cycle_count: int = 0`

**`on_detection` updated logic** — three mutually exclusive states:

| State | Condition | Action |
|---|---|---|
| (a) Mid-cycle suppression | `_pending_frame is not None` | Silently ignore — existing FR-005a guard. `_cycle_count` is NOT incremented. |
| (b) New session | `_pending_frame is None` AND `_session_start is None` | Start session: `_session_start = datetime.now()`, `_cycle_count = 1`, then store frame. |
| (c) New cycle in active session | `_pending_frame is None` AND `_session_start is not None` | Continue session: `_cycle_count += 1`, then store frame. |

Check order: state (a) is evaluated first (early return). States (b) and (c) differ only by whether `_session_start` is set. Step 4 (store frame/boxes/sound) is common to (b) and (c).

**Thread safety note**: Both `on_detection` and `on_verification` are called from the `DetectionLoop` daemon thread (not the main thread). `on_cat_detected` in `main.py` — which calls `tracker.on_detection` — is invoked directly from `DetectionLoop._run()`. The detection loop processes frames sequentially on a single thread, guaranteeing that `on_detection` and `on_verification` never execute concurrently. No additional locking is required (research.md §R-009). See also: `DetectionLoop._pending_frame` is cleared before invoking `_verification_callback`, ensuring `on_verification` cannot be called while `on_detection` is also running for the same frame.

**`on_verification` updated logic** (operations in this exact order):
1. Guard: if `_pending_frame is None`, no-op and return (unchanged). Also no-op if `_session_start is None` (defensive guard for unexpected call with no active session).
2. Capture pending data into local variables (frame, boxes, sound, session_start, cycle_count).
3. **Clear pending state immediately**: `_pending_frame = None`, `_pending_boxes = []`, `_pending_sound = None` (before any async work — unchanged pattern).
4. Compute elapsed: `elapsed_s = int(cycle_count * self._settings.cooldown_seconds)`. Note: `int()` truncates (floor). For a 15.5 s cooldown, cycle 1 produces "15s", cycle 2 "31s".
5. Build timed message:
   - `has_cat=True` → `f"Cat remained after alert: {elapsed_s}s"` (red, outcome="remained")
   - `has_cat=False` → `f"Cat disappeared after alert: {elapsed_s}s"` (green, outcome="deterred")
6. Build session filepath: `build_session_filepath(root, session_start, cycle_count)` where `root = resolve_root(self._settings)`.
7. Annotate frame (pure function call) with `outcome_message=<timed message>`.
8. Dispatch async save via `_save_annotated_async(annotated, self._settings, filepath=filepath)`. The explicit `filepath` causes `save_screenshot` to bypass both window-open and time-window suppression checks (Change 2).
9. If `has_cat=False`: close session — `self._session_start = None`, `self._cycle_count = 0`. Both fields reset explicitly.
10. If `has_cat=True`: keep session open — `_session_start` and `_cycle_count` are preserved unchanged for the next cycle.

**App stopped between cycles**: If the application stops while a session is open but no pending frame exists (i.e., after a red verification cleared the pending state but before the next detection fires), all in-memory session state is lost on process exit. No partial file is written and no session-closing green frame is produced. This is the intended behavior per spec Assumptions ("A session pending its first evaluation is abandoned if the application stops") — the same principle applies to any mid-session app exit, regardless of cycle count.

**Camera unavailability and session abandonment**: When `DetectionLoop` auto-pauses on a camera read error, it calls `on_camera_error` in `main.py`, which calls `tracker.abandon()`. This immediately resets all session state (`_pending_frame = None`, `_session_start = None`, `_cycle_count = 0`). No evaluation frame is saved for the in-progress cycle. When the user resumes monitoring, the next cat detection starts a fresh session from scratch. See Change 6 for the full wiring.

**Session state persistence**: Session state (`_session_start`, `_cycle_count`, `_pending_frame`) is held in memory only. It is not persisted to disk and is lost if the application process exits. A session interrupted by app shutdown produces no file for its current in-progress cycle; this is the intended behavior per spec Assumptions.

**DetectionLoop re-alerting as precondition**: This design relies on `DetectionLoop` firing a new `SOUND_PLAYED` event (and calling `on_cat_detected`) after each verification cycle when the cat is still present and the cooldown has elapsed. This is a verified emergent property of the existing loop (see research.md §R-001) and is not a new behavior introduced by this feature.

**`DetectionLoop.set_verification_callback` API contract** (stable internal API from spec-005, not modified by this feature): callback signature is `cb(has_cat: bool, boxes: list[BoundingBox]) -> None`. `has_cat` is True if any cat bounding box was detected in the verification frame; `boxes` is the full list of detected regions (may be empty when `has_cat=False`). `_pending_frame` in `DetectionLoop` is cleared before the callback fires.

**Async error isolation (NFR-002)**: Session frame saves inherit the full error-isolation contract of `_save_annotated_async`: all exceptions in the background save thread are caught, logged, and forwarded to `on_error` — they never propagate to the detection loop. A save failure for one session frame does not affect the detection pipeline or subsequent frame saves. This is already implemented in the existing `_save_annotated_async`; no additional error-handling code is required for session frames specifically.

### Change 6 — Pause abandons the active session

Any pause — whether triggered by the user (manual pause), a camera read error (auto-pause), or a time-window auto-pause — must immediately abandon the active cat session. Carrying session state across a pause produces semantically meaningless verification screenshots: the cooldown timer was reset or indeterminate during the pause, and the verification frame fires at an arbitrary future time unrelated to the original alert.

**New method `EffectivenessTracker.abandon()`**:
- Resets all session and pending state: `_pending_frame = None`, `_pending_boxes = []`, `_pending_sound = None`, `_session_start = None`, `_cycle_count = 0`.
- Does NOT write any file — the in-progress cycle is silently discarded.
- Safe to call when no session is active (idempotent no-op).
- Logs an info-level message when called with an active session (for observability).

**`DetectionLoop.pause()` — defense in depth**:
- In addition to the existing behavior (stopping the thread), also explicitly clears `_pending_frame = None`. This ensures that if `abandon()` is somehow not called from `main.py`, the stale pending frame does not fire a spurious verification after resume.

**`main.py` wiring**:
- `on_camera_error` → add call to `tracker.abandon()` (before or after the existing tray notification — order does not matter).
- `on_tracking_state_changed(active: bool)` → when `active=False` (tracking paused), add call to `tracker.abandon()`.
- No changes needed for time-window auto-pause: `DetectionLoop` auto-pauses itself on time-window boundary (calls `pause()` internally), so the `on_tracking_state_changed(False)` path already covers this case.
- **Time-window auto-pause path**: `DetectionLoop._run()` calls `self.pause()` when the time window closes. `main.py` does not receive a direct callback for this — it is driven by the detection loop internally. However, `DetectionLoop.pause()` itself (Change 6 defense-in-depth edit above) clears `_pending_frame`, which prevents a stale verification. `tracker.abandon()` is also called from `on_tracking_state_changed(False)` if the UI state is updated, or can be called directly from a pause hook if one exists. Confirm the exact call site by reading `detection.py` and `main.py` during implementation.

---

## Test Plan

### Unit tests (write BEFORE implementation — TDD Red phase)

**`tests/unit/test_screenshots.py`** — new tests for `build_session_filepath` (`@pytest.mark.unit`):
- Returns correct path format for a given session timestamp and cycle number
- Zero-pads cycle number to 3 digits
- Date subfolder is derived from session timestamp (not current time)
- Different cycle numbers produce different filenames
- `save_screenshot` with explicit `filepath` writes to that path, bypassing `build_filepath` auto-naming
- `save_screenshot` with explicit `filepath` skips both the window-open and time-window suppression checks

**`tests/unit/test_annotation.py`** — new `EffectivenessTracker` session tests (`@pytest.mark.unit`):
- First `on_detection` starts a new session (`_session_start` set, `_cycle_count = 1`)
- `on_detection` while pending is still silently ignored AND `_cycle_count` is NOT incremented (FR-005a unchanged)
- `on_detection` after green outcome starts a new session (resets `_session_start`, `_cycle_count = 1`)
- `on_verification(has_cat=True)` produces red frame with correct timed message; `_session_start` and `_cycle_count` remain set after the call
- `on_verification(has_cat=False)` produces green frame with correct timed message; `_session_start = None` and `_cycle_count = 0` after the call
- `on_verification` called when `_session_start is None` and `_pending_frame is None` is a no-op (defensive guard)
- Second `on_detection` after red verification (pending cleared, session still open) increments `_cycle_count` to 2
- Elapsed time in label equals `int(cycle_count × cooldown_seconds)` — truncated to integer seconds
- Session frame filepath follows `<root>/<YYYY-MM-DD>/<YYYYMMDD-HHmmss>-<NNN>.jpg` format
- `annotate_frame` with `outcome_message="custom text"` uses that text in the outcome strip instead of the hardcoded default
- `abandon()` called during an active session resets `_pending_frame`, `_session_start`, and `_cycle_count` to their zero values (idempotent)
- `abandon()` called when no session is active is a no-op (no exception raised)
- `on_detection` called after `abandon()` starts a brand-new session with `cycle_count = 1`

### Integration tests (`@pytest.mark.integration`)

**`tests/integration/test_effectiveness_integration.py`** — new tests:
- Two-cycle session (red then green): two JPEGs appear in the correct date subfolder with correct session-prefixed filenames and strip colors
- Three-cycle session (two red then green): three JPEGs with monotonically increasing elapsed time values in their labels
- After green, next `on_detection` produces a file with cycle `001` of a new session timestamp (not cycle `004` of the old one)
- Single-cycle session (cat gone immediately): exactly one green JPEG, no red JPEGs
- Session JPEG filename date subfolder matches the session start date, not the save date (verify by controlling the session start timestamp in the test)
