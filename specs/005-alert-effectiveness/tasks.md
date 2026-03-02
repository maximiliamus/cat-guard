# Tasks: Alert Effectiveness Tracking & Annotated Screenshots

**Feature**: `005-alert-effectiveness`
**Branch**: `005-alert-effectiveness`
**Input**: Design documents from `/specs/005-alert-effectiveness/`
**Prerequisites**: [plan.md](plan.md) · [spec.md](spec.md) · [data-model.md](data-model.md) · [contracts/config.md](contracts/config.md) · [research.md](research.md) · [quickstart.md](quickstart.md)

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[US1]**: Visual Detection Evidence — bounding boxes + sound label on every screenshot
- **[US2]**: Alert Outcome Labeling — delayed save, post-cooldown verification, green/red outcome overlay

---

## Phase 1: Setup

**Purpose**: Verify project dependencies are declared before writing new code.

- [X] T001 Verify `opencv-python` is declared in `pyproject.toml` and `requirements.txt`; add if missing

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Structural changes shared by both user stories — `BoundingBox` dataclass,
`DetectionEvent.boxes` field, one-SOUND_PLAYED-per-frame refactor, and `play_alert()`
return type. MUST be complete before any user story work begins.

> ⚠️ **CRITICAL**: No user story implementation can begin until this phase is complete.

### Tests — write first, confirm RED before implementing

- [X] T002 [P] Write failing tests for `play_alert()` return values (DEFAULT / PINNED / RANDOM / fallback paths) in `tests/unit/test_audio.py`
- [X] T003 [P] Write failing tests for `BoundingBox` dataclass, `DetectionEvent.boxes` field, and one-`SOUND_PLAYED`-per-frame behavior in `tests/unit/test_detection.py`

### Implementation

- [X] T004 Add `BoundingBox` dataclass (x1, y1, x2, y2, confidence) to `src/catguard/detection.py`
- [X] T005 Add `boxes: list[BoundingBox]` field (`default_factory=list`) to `DetectionEvent` in `src/catguard/detection.py`
- [X] T006 Refactor `DetectionLoop._run()` inner loop to collect all cat boxes first and emit exactly one `SOUND_PLAYED` event per frame in `src/catguard/detection.py`; on the `SOUND_PLAYED` path set `self._pending_frame = frame.copy()` (`.copy()` is mandatory — `cap.read()` overwrites the buffer each iteration); sound label is not set here — it flows from `play_alert()` via `tracker.on_detection()` in `main.py`
- [X] T007 [P] Change `play_alert()` return type from `None` to `str`; return `"Alert: Default"` for DEFAULT/fallback and `Path(chosen).name` for PINNED/RANDOM in `src/catguard/audio.py`

**Checkpoint**: `pytest tests/unit/test_audio.py tests/unit/test_detection.py -q` — all new tests pass.

---

## Phase 3: User Story 1 — Visual Detection Evidence (Priority: P1) 🎯 MVP

**Goal**: Implement and verify `annotate_frame()` and `build_sound_label()` as standalone tested pure functions that produce correct bounding-box, confidence-label, and sound-label annotation layers. (End-to-end disk writes require T023 in Phase 4.)

**Independent Test**: Unit-test `annotate_frame()` directly with a synthetic BGR array
and a list of `BoundingBox` objects — verify that pixels at the expected box corners
differ from the original frame (rectangle drawn) and that the top-left region is
modified (sound label rendered).

### Tests — write first, confirm RED before implementing

- [X] T008 [US1] Write failing unit tests for `build_sound_label()` — `None` → `"Alert: Default"`, absolute path → filename only, `"Alert: Default"` pass-through — in `tests/unit/test_annotation.py`
- [X] T009 [US1] Write failing unit tests for `annotate_frame()` bounding box layer (rectangle pixels at box edges changed) and sound label layer (top-left region modified) in `tests/unit/test_annotation.py`

### Implementation

- [X] T010 [US1] Create `src/catguard/annotation.py` with module scaffold: imports (`cv2`, `numpy`, `pathlib`, `logging`, `threading`), visual constants (`BOX_COLOR`, `FONT`, `FONT_SCALE`, `SUCCESS_BG`, `FAILURE_BG`, `TEXT_COLOR`, `OUTCOME_FONT_SCALE`), and `logger = logging.getLogger(__name__)`
- [X] T011 [US1] Implement `build_sound_label(value: Optional[str]) -> str` in `src/catguard/annotation.py`
- [X] T012 [US1] Implement bounding box + confidence label annotation layer in `annotate_frame()` using two-pass approach (measure text → draw background rect → draw text) in `src/catguard/annotation.py`
- [X] T013 [US1] Implement sound label top-left corner layer in `annotate_frame()` (filled background rect at x=10, text on top) in `src/catguard/annotation.py`

**Checkpoint**: `pytest tests/unit/test_annotation.py -q` — all US1 tests pass. `annotate_frame()` and `build_sound_label()` work correctly as standalone pure functions.

---

## Phase 4: User Story 2 — Alert Outcome Labeling (Priority: P1)

**Goal**: Screenshots are held in memory until the cooldown elapses; a verification
check determines whether the cat left or stayed; a green or red outcome strip is
applied; the annotated JPEG is saved asynchronously. No screenshot is written
to disk before the outcome is known.

**Independent Test**: Feed a `DetectionEvent` into `EffectivenessTracker.on_detection()`,
then call `on_verification(has_cat=False, boxes=[])`, and assert that a JPEG file
exists in `tmp_path` with green pixels in the bottom strip.

### Tests — write first, confirm RED before implementing

- [X] T014 [US2] Extend `tests/unit/test_annotation.py` with failing tests for `EffectivenessTracker` state machine: `on_detection()` stores frame, FR-005a ignore-if-pending, `_is_pending` property, `on_verification()` clears pending state
- [X] T015 [US2] Extend `tests/unit/test_annotation.py` with failing tests for outcome overlay: green strip for `outcome="deterred"`, red strip for `outcome="remained"`, no strip for `outcome=None` in `annotate_frame()`
- [X] T016 [P] [US2] Write failing unit tests for `DetectionLoop.set_verification_callback()` and verification trigger logic (fires callback on first frame after `_cooldown_elapsed()` with pending state, clears pending state before invoking callback) in `tests/unit/test_detection.py`
- [X] T017 [P] [US2] Write failing integration test for full pipeline (detection event → `EffectivenessTracker` stores snapshot → `on_verification` called → annotated JPEG written to `tmp_path` → verify green/red pixel in outcome strip and bounding box pixel) in `tests/integration/test_effectiveness_integration.py`

### Implementation

- [X] T018 [US2] Implement outcome overlay annotation layer (`outcome="deterred"` → green full-width strip, `outcome="remained"` → red strip, `outcome=None` → no-op) in `annotate_frame()` in `src/catguard/annotation.py`
- [X] T019 [US2] Implement `_save_annotated_async(frame, settings, is_window_open, on_error)` fire-and-forget daemon thread in `src/catguard/annotation.py` (mirrors `_play_async` pattern; wraps `save_screenshot()` call; log INFO on successful save with file path; log ERROR + invoke `on_error` on all exceptions — NFR-002; constitution II requires logging here, not deferred to Phase 5)
- [X] T020 [US2] Implement `EffectivenessTracker` class in `src/catguard/annotation.py`: `on_detection()` with FR-005a guard (log DEBUG on store, DEBUG on ignore-if-pending); `on_verification()` (log INFO on outcome + save dispatched, WARNING on no-outcome/camera-unavailable save); `_is_pending` property; logging is part of this task per constitution II
- [X] T021 [P] [US2] Add `_pending_frame: Optional[np.ndarray] = None` state field and `set_verification_callback()` public method to `DetectionLoop` in `src/catguard/detection.py`; `_pending_frame` is the sole pending-state sentinel — `_pending_boxes`/`_pending_sound` are not stored here (YAGNI; detection-time data is owned by `EffectivenessTracker`)
- [X] T022 [US2] Add verification trigger block to `DetectionLoop._run()` in `src/catguard/detection.py`: check `_pending_frame is not None` and `_cooldown_elapsed()` before normal detection; clear `_pending_frame = None` **before** invoking callback (prevents re-entrance); also handle camera-unavailable fallback — if `cap.read()` returns `ret=False` while pending and cooldown has elapsed, invoke the callback with `has_cat=False, boxes=[]` and clear `_pending_frame` (satisfies FR-012: saves without outcome overlay rather than holding the frame in memory indefinitely)
- [X] T023 [US2] In `src/catguard/main.py`: (1) instantiate `EffectivenessTracker(settings=settings, is_window_open=<lambda checking main_window exists>, on_error=<tray notification callback>)` at app setup; (2) register `detection_loop.set_verification_callback(tracker.on_verification)`; (3) in `on_cat_detected`, capture `sound_label = play_alert(settings, default_sound)` and call `tracker.on_detection(event.frame_bgr, event.boxes, sound_label)`

**Checkpoint**: `pytest tests/ -q` — all tests pass including integration pipeline. Bounding boxes, sound label, and outcome overlay all render correctly end-to-end.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Observability (constitution requirement II), error resilience, and manual validation.

- [X] T024 [P] Review observability in `src/catguard/annotation.py`: verify all log statements added in T019/T020 are present (DEBUG on detection/ignore, INFO on outcome, WARNING on no-outcome, ERROR on save failure); add any missing statements
- [X] T025 [P] Add observability logging to `src/catguard/detection.py`: log at DEBUG on verification trigger fired, DEBUG on has_cat result, DEBUG on pending state cleared
- [ ] T026 Run quickstart.md manual validation: trigger detection, wait cooldown with cat gone → verify green-strip JPEG in screenshots folder; trigger again, keep cat in frame → verify red-strip JPEG

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)        → no dependencies
Phase 2 (Foundational) → depends on Phase 1 — BLOCKS both user stories
Phase 3 (US1)          → depends on Phase 2
Phase 4 (US2)          → depends on Phase 2 (US1 not strictly required but recommended first)
Phase 5 (Polish)       → depends on Phase 3 + Phase 4
```

### User Story Dependencies

- **US1**: Depends only on Phase 2 (Foundational). No dependency on US2.
- **US2**: Depends on Phase 2. Builds on `annotate_frame()` and `annotation.py` scaffold from US1 — recommend completing US1 first.

### Within Each Phase (ordering)

```
Phase 2:
  T002, T003 (parallel) → T004 → T005 → T006
                           T007 (parallel with T004–T006)

Phase 3:
  T008 → T009 → T010 → T011 → T012 → T013

Phase 4:
  T014 → T015          (test_annotation.py, sequential)
  T016                 (test_detection.py, parallel with T014)
  T017                 (test_effectiveness_integration.py, parallel with T014)
  ─── all tests written ───
  T018 → T019 → T020   (annotation.py, sequential)
  T021 → T022          (detection.py, parallel with T018–T020)
  T023                 (main.py, depends on T020 + T022)

Phase 5:
  T024, T025 (parallel) → T026
```

---

## Parallel Execution Examples

### Phase 2 — Audio and detection tests in parallel

```
Thread A: T002 — failing tests for play_alert() in test_audio.py
Thread B: T003 — failing tests for BoundingBox + DetectionEvent.boxes in test_detection.py
```

### Phase 4 — All four test-writing tasks can start together

```
Thread A: T014 → T015  (test_annotation.py: EffectivenessTracker + outcome overlay)
Thread B: T016          (test_detection.py: verification trigger)
Thread C: T017          (test_effectiveness_integration.py: full pipeline)
```

### Phase 4 — Implementation split across annotation.py and detection.py

```
Thread A: T018 → T019 → T020  (annotation.py — outcome overlay, async save, tracker)
Thread B: T021 → T022          (detection.py — pending state, verification trigger)
# T023 (main.py) starts only after T020 and T022 complete
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Complete Phase 1 + Phase 2
2. Complete Phase 3 (US1)
3. **Stop and validate**: `pytest tests/unit/test_annotation.py tests/unit/test_detection.py tests/unit/test_audio.py -q`
4. Confirm `annotate_frame()` unit tests pass — bounding boxes and sound label render correctly on synthetic frames
5. **Note**: End-to-end annotated screenshots require T023 (Phase 4 wiring); Phase 3 alone delivers tested annotation functions, not wired production behaviour
6. Ship or continue to US2

### Incremental Delivery

1. Phase 1 + 2 → foundational types verified
2. Phase 3 (US1) → annotated screenshots with bounding boxes + sound label → **demo-able**
3. Phase 4 (US2) → delayed save + outcome overlays → **full feature complete**
4. Phase 5 → observability + manual sign-off

### Notes

- `[P]` tasks touch different files — safe to parallelize
- Tests MUST fail before implementation — verify RED before writing source code
- `annotation.py` is the only new source module; `detection.py`, `audio.py`, `main.py` are modified
- `screenshots.py` is **not modified** — `EffectivenessTracker` calls it as-is with an already-annotated frame
- Commit after each checkpoint or logical group (e.g., after T006, after T013, after T023)
