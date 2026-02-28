---

description: "Tasks for feature: Tray Open - Main Window"

---

# Tasks: Tray Open - Main Window

**Input**: Design documents from `/specs/2-tray-open-mainwindow/`
**Prerequisites**: `spec.md`, `plan.md` (both required).

> ⚠️ **Constitution enforcement**: Tests MUST be written and FAIL before the implementation they cover. The Red-Green-Refactor cycle is mandatory per the project constitution.

## Path Conventions
All paths relative to repository root (`source/`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create file stubs so all modules can be imported and wired without compile errors.

- [X] T001 [P] Create `src/catguard/ui/main_window.py` with an empty `MainWindow` class stub (pass-body only, no logic)
- [X] T002 [P] Create `src/catguard/ui/overlays.py` with empty stub functions: `draw_bounding_box`, `draw_label`, `draw_detections` (each raises `NotImplementedError`)
- [X] T003 [P] Add `Open` menu item stub to `pystray.Menu` in `src/catguard/tray.py` wired to a no-op handler `_on_open_clicked`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that all user story implementations depend on. Includes observability (constitution requirement).

- [X] T004 Add `_frame_callback` field and `set_frame_callback(cb)` method to `DetectionLoop` in `src/catguard/detection.py`; callback signature: `(frame_bgr: np.ndarray, detections: list) -> None`; protected by `threading.Lock`; call it at end of each inference cycle (after existing alert logic)
- [X] T005 Add structured `logging` calls in `src/catguard/ui/main_window.py` for window open, close, frame-update, and no-source events (required by constitution principle II)
- [X] T006 Add structured `logging` calls in `src/catguard/tray.py` for the new Open menu action

**Checkpoint**: Stubs importable, `DetectionLoop` frame callback wired, logging in place. User story work can now begin.

---

## Phase 3: User Story 1 — Open Main Window from Tray (Priority: P1) 🎯 MVP

**Goal**: `Open` in tray opens a window sized to the captured frame with detection overlays (bounding boxes + class labels).

**Independent Test**: Right-click tray → `Open` → window appears sized to camera frame; cat detection shows green bounding box and `cat` label.

### Tests FIRST — write these before any implementation below (must FAIL initially)

- [X] T007 [US1] Write failing unit tests in `tests/unit/test_overlays.py` for `draw_bounding_box` (modifies frame pixels in bbox region), `draw_label` (modifies frame pixels at position), and `draw_detections` (returns annotated copy; no-op on empty results)
- [X] T008 [US1] Write failing unit tests in `tests/unit/test_main_window.py` for: `MainWindow` instantiation without display (mock `tk.Toplevel`), `show_or_focus` guard (creates once, focuses on re-call), `update_frame` sizes window geometry to frame `w×h`, `_show_no_source_message` renders a message when frame is `None`

### Implementation (make tests green)

- [X] T009 [US1] Implement `draw_bounding_box(frame, bbox, color=(0,255,0), thickness=2)` in `src/catguard/ui/overlays.py` using `cv2.rectangle`
- [X] T010 [US1] Implement `draw_label(frame, text, position, font_scale=0.6, color=(0,255,0), thickness=2)` in `src/catguard/ui/overlays.py` using `cv2.putText`
- [X] T011 [US1] Implement `draw_detections(frame, results) -> np.ndarray` in `src/catguard/ui/overlays.py`; iterates `result.boxes`, calls `draw_bounding_box` + `draw_label` per detection; returns frame copy unchanged if results empty/None
- [X] T012 [US1] Implement `MainWindow.__init__(self, root)` in `src/catguard/ui/main_window.py`: creates hidden `tk.Toplevel`, binds `_on_close` to `WM_DELETE_WINDOW`, stores reference as `root._main_window`
- [X] T013 [US1] Implement `MainWindow.show_or_focus(self)` in `src/catguard/ui/main_window.py`: deiconifies and raises window; safe to call multiple times
- [X] T014 [US1] Implement `MainWindow.update_frame(self, frame_bgr, detections)` in `src/catguard/ui/main_window.py`: on first call sets `Toplevel` geometry to `{w}x{h}` (scale to screen if frame exceeds screen bounds); converts BGR frame → `PIL.ImageTk.PhotoImage` via Pillow; updates `tk.Canvas` image; calls `draw_detections`; shows "No detections" label when detections list is empty
- [X] T015 [US1] Implement `MainWindow._on_close(self)` and `MainWindow._show_no_source_message(self)` in `src/catguard/ui/main_window.py`; `_on_close` destroys window and clears `root._main_window`; `_show_no_source_message` shows a `tk.Label` with Retry/Close buttons
- [X] T016 [US1] Implement `_ensure_main_window(root)` and `_on_open_clicked(icon, item)` in `src/catguard/tray.py`; `_ensure_main_window` creates `MainWindow` if absent, then calls `show_or_focus()`; wire `Open` menu item to this handler via `root.after(0, ...)`
- [X] T017 [US1] Wire frame callback in `src/catguard/main.py`: pass `detection_loop` reference into `build_tray_icon`; inside `_ensure_main_window` call `detection_loop.set_frame_callback(lambda f, d: root.after(0, lambda: main_window.update_frame(f, d)))`; call `detection_loop.set_frame_callback(None)` inside `MainWindow._on_close`

**Checkpoint**: US1 complete — `Open` opens a correctly sized window with live overlays.

---

## Phase 4: User Story 2 — Tray Presence & Existing Items (Priority: P2)

**Goal**: Tray menu contains exactly `Settings…`, `Open`, `Exit` in that order; `Exit` still quits the app.

**Independent Test**: Right-click tray icon; confirm all three items present; click `Exit` and app quits.

### Tests FIRST

- [X] T018 [US2] Write failing unit tests in `tests/unit/test_tray.py` asserting: (1) menu item labels include `Settings…`, `Open`, `Exit`; (2) `Exit` calls `stop_event.set()`

### Implementation

- [X] T019 [US2] Verify/update `pystray.Menu` in `src/catguard/tray.py` so item order is `Settings…`, `Open`, `Exit`; confirm `Exit` handler unchanged; make T018 green

**Checkpoint**: US2 complete — all three tray items verified by tests.

---

## Phase 5: User Story 3 — Detection Visualization (Priority: P2)

**Goal**: Overlays are robust for 0, 1, and multiple detections; styling constants defined; no label collisions.

**Independent Test**: Inject test frame with two cats; confirm two bounding boxes and two `cat` labels rendered; inject frame with no detections; confirm "No detections" message displayed.

### Tests FIRST

- [X] T020 [US3] Add failing tests in `tests/unit/test_overlays.py` for: multiple detections (two boxes on one frame), empty results (frame returned unchanged), styling constants exported from `src/catguard/ui/overlays.py`
- [X] T021 [US3] Add failing test in `tests/unit/test_main_window.py` for `update_frame` with empty detections showing "No detections" text on canvas

### Implementation

- [X] T022 [US3] Add styling constants `BOX_COLOR`, `LABEL_FONT_SCALE`, `LABEL_THICKNESS`, `LABEL_PADDING` at module level in `src/catguard/ui/overlays.py`; update `draw_bounding_box` and `draw_label` to use them as defaults
- [X] T023 [US3] Ensure `draw_detections` uses class name from YOLO result (`result.names[int(box.cls[0])]`) as label text and positions label above bounding box top-left corner; offset labels to avoid overlap when multiple detections share similar y-coordinates

**Checkpoint**: US3 complete — overlays robust and styled; all unit tests green.

---

## Phase 6: Integration Test (Required by Constitution)

- [X] T024 Write `tests/integration/test_tray_open_mainwindow.py`: create a synthetic BGR numpy frame (e.g. 640×480), create a mock detection result with one `cat` box, instantiate `MainWindow` with a mock `tk.Tk`, call `update_frame(frame, [detection])`, assert window geometry set to `640x480` and `draw_detections` called with correct args
- [X] T025 Run full test suite `python -m pytest tests/` and resolve any regressions

---

## Phase 7: Polish

- [X] T026 [P] Add `specs/2-tray-open-mainwindow/quickstart.md` with step-by-step manual verification instructions (start app → open tray → click Open → verify window size + overlays)
- [X] T027 [P] Review all tkinter calls in `src/catguard/ui/main_window.py` and `src/catguard/tray.py`; confirm every UI call runs on the main thread (never from `DetectionLoop` thread directly)

---

## Dependencies & Execution Order

```
Phase 1 (stubs) → Phase 2 (foundational) → Phase 3 (US1, P1) → Phase 4 (US2) + Phase 5 (US3) → Phase 6 (integration) → Phase 7 (polish)
```

- Within each user story phase: **tests MUST be written before implementation** (constitution rule)
- Within US1: T007/T008 (tests) → T009–T011 (overlays impl) → T012–T015 (MainWindow impl) → T016 (tray wiring) → T017 (main.py wiring)
- T024 integration test depends on T017 (all US1 implementation complete)

## Parallel Opportunities

- T001, T002, T003 (Phase 1 stubs) — different files, all parallel
- T007, T008 (US1 test files) — different files, parallel
- T009, T010 (overlay functions) — same file but independent functions; can be written together
- T018, T020, T021 (test additions in Phase 4/5) — parallel with each other
- T026, T027 (polish) — parallel

---

## File Reference Summary

| File | Status | Changed by |
|------|--------|-----------|
| `src/catguard/tray.py` | Modify | T003, T006, T016, T019 |
| `src/catguard/detection.py` | Modify | T004 |
| `src/catguard/main.py` | Modify | T017 |
| `src/catguard/ui/main_window.py` | **New** | T001, T005, T012–T015 |
| `src/catguard/ui/overlays.py` | **New** | T002, T009–T011, T022–T023 |
| `tests/unit/test_overlays.py` | **New** | T007, T020 |
| `tests/unit/test_main_window.py` | **New** | T008, T021 |
| `tests/unit/test_tray.py` | Modify | T018 |
| `tests/integration/test_tray_open_mainwindow.py` | **New** | T024 |
| `specs/2-tray-open-mainwindow/quickstart.md` | **New** | T026 |

<!-- End of generated tasks.md -->
