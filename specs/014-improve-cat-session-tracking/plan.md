# Implementation Plan: Immediate Cat Session Frame Saving

**Branch**: `014-improve-cat-session-tracking` | **Date**: 2026-03-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/014-improve-cat-session-tracking/spec.md`

## Summary

Replace the current cross-cooldown screenshot buffering with a fully persisted session timeline. The first detected-cat frame is annotated with a neutral `Cat detected` strip and saved immediately as the first session artifact. Later session outcomes are saved from the live verification frame, not from a delayed in-memory copy. Session filenames remain grouped by the session start timestamp, but the suffix becomes a sequential saved-frame index so the user sees `001` for the start frame, then `002`, `003`, and so on. A shared formatter produces human-readable session times such as `30s`, `2m 15s`, and `1h 2m 45s` for both overlays and logs.

## Technical Context

**Language/Version**: Python 3.14+  
**Primary Dependencies**: opencv-python (`cv2`), Pillow (`PIL`), numpy, onnxruntime, pydantic, tkinter (stdlib), pystray  
**Storage**: JPEG files on disk under `settings.tracking_directory`; JSON settings persisted through the existing `Settings` model  
**Testing**: `pytest` unit and integration tests using `tmp_path`, mocks, and real JPEG writes  
**Target Platform**: Windows / macOS / Linux desktop  
**Project Type**: Desktop application (`tkinter` UI + background detection loop + tray integration)  
**Performance Goals**: Preserve constitution target of `<200ms` p95 detection latency; all session frame writes remain async and non-blocking  
**Constraints**: No new user settings; no duplicate session frames for one evaluation; keep current date-folder storage layout; structured logs must expose human-readable session durations  
**Scale/Scope**: Single-user desktop app, one active cat session at a time, session length unbounded

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Test-First Development | PASS | Plan adds failing unit and integration tests first for immediate start-frame save, verification callback contract, sequential session numbering, and human-readable durations. |
| II. Observability & Logging | PASS | Session lifecycle logs will include human-readable elapsed time, frame index, outcome, and filepath. |
| III. Simplicity & Clarity | PASS | Extend existing `DetectionLoop`, `EffectivenessTracker`, and `annotate_frame`; no new subsystem or settings surface. |
| IV. Integration Testing | PASS | Contract change in the verification callback and end-to-end JPEG output are covered by integration tests. |
| V. Versioning & Breaking Changes | PASS | No user-facing config or file-location break; filenames remain under the existing session prefix convention with only the suffix semantics changing inside one feature branch. |

**Post-design re-check**: PASS. The design keeps the implementation inside the existing screenshot/annotation pipeline, preserves async saves, and adds only one internal callback contract change needed to stop buffering frames across cooldowns.
**Merge gate note**: Constitution compliance remains conditional on implementation-phase completion of full automated regression and at least one peer review approval before merge.

## Project Structure

### Documentation (this feature)

```text
specs/014-improve-cat-session-tracking/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── session-frame-output.md
└── tasks.md
```

### Source Code (affected files only)

```text
src/catguard/
├── annotation.py        # Neutral session-start overlay, duration formatter, tracker refactor
├── detection.py         # Verification callback carries current frame; pending state becomes metadata-only
└── screenshots.py       # Sequential session-frame filepath helper

tests/unit/
├── test_annotation.py   # Start-frame save, duration formatting, tracker state transitions
├── test_detection.py    # Verification callback signature and pending-state behavior
└── test_screenshots.py  # Sequential session-frame numbering

tests/integration/
├── test_detection_integration.py      # Verification callback frame delivery
└── test_effectiveness_integration.py  # End-to-end session timeline saves
```

**Structure Decision**: Single-project desktop app. The feature stays within the existing `catguard` package and the current unit/integration test layout.

## Complexity Tracking

*No constitution violations. Section left blank.*

---

## Spec-to-Plan Traceability

| Requirement | Design Change | Planned Tests |
|---|---|---|
| FR-001, FR-004 | Change 5: save neutral start frame immediately on first `on_detection()` | Unit: first detection writes `-001`; Integration: start frame exists before first verification |
| FR-002, FR-003 | Change 2: add neutral `detected` overlay style in `annotate_frame()` | Unit: neutral strip color/text assertion |
| FR-005, FR-008 | Change 1 + Change 5: verification callback receives live frame and tracker saves exactly one frame per evaluation | Unit: callback contract; Integration: no missing evaluation frame |
| FR-006, FR-007 | Change 5: verification save path produces red/green outcome frames with human-readable duration | Unit: remained/disappeared messages; Integration: red then green timeline |
| FR-009 | Change 5: active session detection advances cycle state without creating another neutral start frame | Unit: active-session detection does not save duplicate start frame |
| FR-010, FR-011, FR-012 | Change 4: shared human-duration formatter used by overlays and logs | Unit: `30s`, `2m 15s`, `1h 2m 45s` formatting |
| FR-013 | Change 3 + Change 5: sequential session-frame suffixes keep one readable timeline per session | Unit: filepath suffixes `001`, `002`, `003`; Integration: session files sort correctly |
| FR-014 | Change 5: `abandon()` resets metadata only and does not create synthetic closing frames | Unit: abandon resets session; Integration: pause leaves saved files intact and adds no final frame |
| SC-001, SC-004 | Change 5: persisted start frame plus sequential evaluation saves reconstruct the entire session from disk | Integration: full-session timeline reconstruction |
| SC-002 | Change 1 + Change 5: one saved frame per evaluation result | Integration: exact saved-frame count matches event count |
| SC-003 | Change 4: formatter shared across overlays and logs | Unit: formatter examples; Integration: session log assertions |

---

## Implementation Design

### Change 1 - `detection.py`: deliver the live verification frame

Update the internal verification callback contract from:

```python
cb(has_cat, boxes)
```

to:

```python
cb(frame_bgr, has_cat, boxes)
```

Design details:

- Replace the long-lived `DetectionLoop._pending_frame` image buffer with a metadata-only pending flag such as `_verification_pending: bool`.
- When an alerting detection fires, `DetectionEvent.frame_bgr` still carries a deep copy of that current detection frame for the immediate session-start save.
- When the post-cooldown verification fires, the detection loop deep-copies the current live frame and passes it to the verification callback before the next loop iteration can overwrite the capture buffer.
- The pending flag is cleared before invoking the callback, preserving the existing no-reentrancy guarantee.
- `pause()` clears the pending flag so no stale verification fires after resume.

Why this change:

- It removes the cross-cooldown screenshot buffering that the feature is explicitly replacing.
- It preserves the evaluation frame that is currently discarded.
- It reduces duplicated runtime state between `DetectionLoop` and `EffectivenessTracker`.

### Change 2 - `annotation.py`: support a neutral session-start overlay

Extend `annotate_frame()` so `outcome` supports a new `detected` state:

- `detected` -> dark gray bottom strip, white text, default message `Cat detected`
- `remained` -> existing red strip
- `deterred` -> existing green strip
- `None` -> no strip

Design details:

- Add a neutral strip background constant near the existing red/green constants.
- Keep the full-width bottom-bar layout identical to the existing outcome strip so the session-start frame visually matches later session frames.
- Continue to honor `outcome_message` overrides for all non-`None` outcomes.

This lets the first session artifact use the same annotation path as later outcome frames instead of introducing a one-off drawing code path.

### Change 3 - `screenshots.py`: sequential session-frame numbering

Keep `build_session_filepath()` but change its suffix semantics from "cycle number" to "saved frame index within the session":

```python
build_session_filepath(root: Path, session_ts: datetime, frame_index: int) -> Path
```

Filename contract:

- `001` -> neutral session-start frame
- `002+` -> chronological evaluation outcome frames
- Prefix remains `YYYYMMDD-HHmmss` derived from `session_start`
- Date folder remains derived from `session_start`

Example:

```text
20260323-101500-001.jpg   # Cat detected
20260323-101500-002.jpg   # Cat remained after alert: 30s
20260323-101500-003.jpg   # Cat disappeared after alert: 1m 0s
```

This keeps lexical sort order aligned with the user's mental timeline.

### Change 4 - `annotation.py`: shared human-readable duration formatter

Add a pure helper for session duration formatting, used by both overlay text and logs:

```python
format_session_duration(total_seconds: float | int) -> str
```

Formatting rules:

- `< 60` seconds -> `Xs`
- `>= 60` and `< 3600` -> `Xm Ys`
- `>= 3600` -> `Xh Ym Zs`
- Input is floored to a non-negative integer before formatting

Examples:

- `30` -> `30s`
- `135` -> `2m 15s`
- `3765` -> `1h 2m 45s`

Elapsed time calculation remains the cooldown-based session value from feature `012`:

```python
elapsed_s = int(cycle_count * settings.cooldown_seconds)
```

Only the presentation changes.

### Change 5 - `annotation.py`: refactor `EffectivenessTracker` to session metadata only

`EffectivenessTracker` no longer holds a pending image copy. It tracks only session metadata:

- `_session_start: Optional[datetime]`
- `_cycle_count: int` - alert cycles in the active session
- `_frame_index: int` - saved frame count in the active session
- `_active_sound_label: Optional[str]` - sound tied to the current alert cycle

Updated flow:

1. `on_detection(frame, boxes, sound_label)`
   - If no session is active:
     - start session
     - set `_cycle_count = 1`
     - set `_frame_index = 1`
     - set `_active_sound_label = sound_label`
     - annotate the current detection frame with `outcome="detected"` and save `-001` immediately
   - If a session is already active:
     - increment `_cycle_count`
     - update `_active_sound_label`
     - do not save a frame yet; the next saved artifact will be the live verification frame for this cycle

2. `on_verification(frame_bgr, has_cat, boxes)`
   - Guard and no-op if no session is active
   - increment `_frame_index`
   - compute `elapsed_s = int(_cycle_count * cooldown_seconds)`
   - format `elapsed_text = format_session_duration(elapsed_s)`
   - annotate the live verification frame with:
     - `Cat remained after alert: <elapsed_text>` when `has_cat=True`
     - `Cat disappeared after alert: <elapsed_text>` when `has_cat=False`
   - save the frame immediately to the next sequential session filepath
   - close the session only on the green `has_cat=False` path

3. `abandon()`
   - reset `_session_start`, `_cycle_count`, `_frame_index`, `_active_sound_label`
   - never writes a synthetic final frame
   - keeps previously saved session files untouched

Logging changes:

- log session start with the initial filepath
- log each evaluation save with `cycle_count`, `frame_index`, outcome, and human-readable `elapsed`
- log session close with total saved frames and total human-readable elapsed duration

## Test Plan

### Unit tests (write first)

**`tests/unit/test_annotation.py`**

- First `on_detection()` starts a session and dispatches an immediate save of `-001` with neutral strip text `Cat detected`
- Active-session `on_detection()` increments `_cycle_count` without saving a duplicate neutral frame
- `on_verification(frame, has_cat=True, boxes)` saves a red frame with a human-readable duration and keeps the session open
- `on_verification(frame, has_cat=False, boxes)` saves a green frame with a human-readable duration and closes the session
- `format_session_duration()` returns `30s`, `2m 15s`, `1h 2m 45s`, `1m 0s`, and `1h 0m 0s` for the expected inputs
- `annotate_frame(..., outcome="detected")` renders the neutral strip with white text
- `abandon()` resets session metadata and does not raise when called idempotently

**`tests/unit/test_detection.py`**

- `set_verification_callback()` stores a callback with the new `(frame_bgr, has_cat, boxes)` signature
- verification clears the pending flag before invoking the callback
- verification passes a deep-copied live frame to the callback
- `pause()` clears the verification-pending flag

**`tests/unit/test_screenshots.py`**

- `build_session_filepath()` uses `frame_index` suffixes `001`, `002`, `003`
- the date folder still comes from `session_start`
- frame indices above `999` are not truncated

### Integration tests

**`tests/integration/test_effectiveness_integration.py`**

- first detection writes `-001` immediately before any verification fires
- one-cycle session produces:
  - `-001` neutral `Cat detected`
  - `-002` green `Cat disappeared after alert: <duration>`
- multi-cycle session produces:
  - `-001` neutral start frame
  - one red verification frame per failed cycle
  - one final green verification frame
- pause or camera-error abandonment leaves existing files intact and adds no synthetic closing frame
- session logs include human-readable elapsed durations

**`tests/integration/test_detection_integration.py`**

- verification callback receives the live verification frame and current boxes from the detection loop
- the pending flag is cleared before callback execution, preventing duplicate verification delivery
