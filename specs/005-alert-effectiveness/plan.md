# Implementation Plan: Alert Effectiveness Tracking & Annotated Screenshots

**Branch**: `005-alert-effectiveness` | **Date**: 2026-03-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-alert-effectiveness/spec.md`

## Summary

Replace plain screenshot saves with fully annotated JPEG captures that show:
1. **Bounding boxes** with confidence percentages drawn on every detected cat region.
2. **Alert sound label** in the top-left corner (filename or "Alert: Default").
3. **Outcome overlay** in the bottom-left corner — green "cat left" or red "cat remained" — determined by a post-cooldown verification check using the existing detection loop.

The screenshot is held in memory at detection time and saved only after the cooldown
elapses and a verification frame is evaluated. Annotation and disk-write run
asynchronously on a daemon thread so the detection loop is never blocked.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: `opencv-python` / `cv2` (annotation), `numpy` (frame buffer),
`ultralytics` YOLO (detection + verification), `platformdirs` (save paths),
`pydantic` (settings), `pygame-ce` (audio), `pytest` + `pytest-mock` (testing)
**Storage**: Annotated JPEG files written to the existing screenshots root folder
(`<root>/<yyyy-mm-dd>/<HH-MM-SS>.jpg`); no new storage location introduced
**Testing**: pytest, pytest-mock; unit tests mock `cv2` and `numpy`; integration tests
use temporary filesystem directories
**Target Platform**: Windows 10+, Ubuntu 20.04+, macOS 12+ (desktop, single-user)
**Project Type**: Desktop application (tkinter + pystray)
**Performance Goals**: Detection loop latency ≤200ms p95 (unchanged — NFR-001:
annotation runs asynchronously off the detection thread)
**Constraints**: <100MB memory; single pending snapshot per cooldown (FR-005a); frame
copy taken at detection time to prevent race conditions with the detection loop's
`cap.read()` overwrite; no new settings fields required; no new UI components

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Status |
|-----------|-------------|--------|
| I. Test-First Development | `annotation.py` and all modified modules MUST have failing tests written before implementation; Red-Green-Refactor enforced | ✅ PASS |
| II. Observability & Logging | `annotation.py` MUST log annotation start/outcome/save/error; `detection.py` MUST log verification trigger and result | ✅ PASS |
| III. Simplicity & Clarity | One new module (`annotation.py`); detection loop extended minimally with three state fields + one callback; no new UI, no new settings; fire-and-forget daemon thread (reuses existing `_play_async` pattern) | ✅ PASS |
| IV. Integration Testing | Detection→annotation→save pipeline and the verification trigger require integration tests | ✅ PASS |
| V. Versioning & Breaking Changes | `DetectionEvent` gains new optional field `boxes` (default `[]`) — backward-compatible; `play_alert()` return type changes from `None` to `str` — callers in `main.py` updated; no settings fields renamed or removed | ✅ PASS |

**Post-design re-check**: ✅ All gates still pass after Phase 1 design.

## Project Structure

### Documentation (this feature)

```text
specs/005-alert-effectiveness/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── config.md        ← Phase 1 output (no settings schema changes — documents that)
└── tasks.md             ← Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code

```text
src/catguard/
├── annotation.py             ← NEW: annotate_frame(), build_sound_label(),
│                                    EffectivenessTracker, _save_annotated_async()
├── detection.py              ← MODIFY: add BoundingBox dataclass; DetectionEvent.boxes
│                                    field; refactor inner loop to fire ONE SOUND_PLAYED
│                                    per frame (not one per box); add _pending_* state
│                                    and on_verification callback to DetectionLoop
├── audio.py                  ← MODIFY: play_alert() returns str (sound label displayed
│                                    on screenshot); DEFAULT → "Alert: Default",
│                                    PINNED/RANDOM → Path(chosen).name
└── main.py                   ← MODIFY: capture sound_label from play_alert(); pass to
│                                    EffectivenessTracker.on_detection(); wire
│                                    tracker.on_verification to DetectionLoop

tests/unit/
├── test_annotation.py        ← NEW: annotate_frame() rendering, build_sound_label(),
│                                    EffectivenessTracker state machine (pending/clear),
│                                    outcome color/text mapping, unknown-outcome path
├── test_detection.py         ← EXTEND: BoundingBox construction; DetectionEvent.boxes;
│                                    one-event-per-frame refactor; on_verification fires
│                                    at first cooldown expiry; pending state cleared
│                                    after verification
└── test_audio.py             ← EXTEND: play_alert() return value for all three modes
                                       (DEFAULT, PINNED, RANDOM) and fallback paths

tests/integration/
└── test_effectiveness_integration.py  ← NEW: full pipeline — detection event fires,
                                              EffectivenessTracker stores snapshot,
                                              on_verification called, annotated JPEG
                                              written to tmp_path; verify pixel colors
                                              in outcome strip; verify bounding box
                                              pixel; verify sound label text region
```

**Structure Decision**: Single-project layout (existing). One new module `annotation.py`
owns all frame-annotation and delayed-save concerns, keeping `detection.py` focused on
inference and `screenshots.py` focused on I/O. `screenshots.py` is reused as the
underlying save backend — `EffectivenessTracker` calls it with an already-annotated
frame.
