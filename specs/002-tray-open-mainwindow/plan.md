# Implementation Plan: Tray Open - Main Window

**Branch**: `2-tray-open-mainwindow` | **Date**: 2026-03-01 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/2-tray-open-mainwindow/spec.md`

---

## Summary

Add an **`Open`** item to the CatGuard system tray menu. Clicking it opens a new tkinter `Toplevel` window (`MainWindow`) sized to the current capture frame. The window renders the live camera feed and draws YOLO detection overlays (bounding boxes + class labels) on top of each detected object in real time, matching the existing detection frame rate.

---

## Technical Context

**Language/Version**: Python 3.14+  
**Primary Dependencies**: tkinter (stdlib, main-thread UI), OpenCV (`cv2` — frame capture & image rendering), Pillow (frame → tkinter-compatible `PhotoImage`), pystray (tray menu), ultralytics YOLO (detection inference, already running in `DetectionLoop`)  
**Storage**: N/A (no new persistence required)  
**Testing**: pytest 8+, pytest-mock  
**Target Platform**: Windows (primary), Linux, macOS (same as existing app)  
**Project Type**: Desktop GUI application  
**Performance Goals**: Detection overlays rendered within 200 ms p95; window open within 1 second p95; display frame rate matches `DetectionLoop` inference rate (~20 FPS with `imgsz=320` on CPU)  
**Constraints**: All tkinter calls MUST run on the tkinter main thread (via `root.after`). No additional heavyweight dependencies. `MainWindow` must not block the tray event loop.  
**Scale/Scope**: Single user, single window, single camera stream

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✓ REQUIRED | Unit tests for `MainWindow` logic and overlay helpers written before implementation. Integration test for window open + overlay flow required. |
| II. Observability & Logging | ✓ REQUIRED | Structured `logging` calls in `MainWindow` open/close events and overlay rendering errors. |
| III. Simplicity & Clarity | ✓ ENFORCED | Reuse tkinter (already a dependency). No new GUI framework. Reuse existing `DetectionLoop` frame/result pipeline — do not duplicate detection. |
| IV. Integration Testing | ✓ REQUIRED | Integration test simulates a live frame with detections and verifies window size + overlay draw calls. |
| V. Versioning | ✓ NOTED | No API-surface or breaking changes; version stays at `0.1.0` (patch-level feature). |

---

## Architecture & Data Flow

```
main.py
  └─ build_tray_icon(root, stop_event, settings, ...)
       └─ tray.py: pystray.Menu
            ├─ Settings…  (existing)
            ├─ Open        (NEW) ──→ root.after(0, MainWindow.show_or_focus)
            └─ Exit        (existing)

DetectionLoop (daemon thread)
  └─ _run() loop:
       ├─ cap.read()          → raw BGR frame (numpy ndarray, h×w×3)
       ├─ model.predict()     → results with boxes, conf, cls
       └─ on_cat_detected()   (existing alert callback)
       └─ on_frame_ready()    (NEW callback) → posts (frame, detections) to MainWindow

MainWindow (tkinter Toplevel, main thread only)
  ├─ show_or_focus()    — create if not open, focus if already open
  ├─ _update_frame(frame_bgr, detections)
  │    ├─ overlays.draw_detections(frame_bgr, detections) → annotated frame
  │    ├─ Convert BGR → PIL Image → PhotoImage
  │    └─ canvas.itemconfig(img_handle, image=photo_image)
  └─ _on_close()        — destroys window, clears reference
```

**Thread safety**: `DetectionLoop` runs on its own daemon thread. It posts frames to the main thread using `root.after(0, callback)` — the same pattern already used by `_on_settings`. `MainWindow` never touches tkinter objects from the background thread.

**Frame delivery**: `DetectionLoop._run()` is extended with an optional `on_frame_ready` callback that fires on every inference cycle, passing the raw frame and the full results list. The callback is only set when `MainWindow` is open, so there is zero overhead when the window is closed.

---

## Project Structure

### Documentation (this feature)

```text
specs/2-tray-open-mainwindow/
├── spec.md
├── plan.md              ← this file
├── tasks.md
└── checklists/
    └── requirements.md
```

### Source Code Changes

```text
src/catguard/
├── tray.py                      ← ADD Open menu item + show_main_window handler
├── detection.py                 ← ADD on_frame_ready optional callback to DetectionLoop
└── ui/
    ├── __init__.py              (unchanged)
    ├── settings_window.py       (unchanged)
    ├── main_window.py           (NEW) MainWindow class
    └── overlays.py              (NEW) draw_detections / draw_bounding_box / draw_label

tests/
├── unit/
│   ├── test_tray.py             ← ADD test: menu contains Open item; existing items preserved
│   ├── test_main_window.py      (NEW) unit tests for MainWindow logic (no display required)
│   └── test_overlays.py         (NEW) unit tests for overlay drawing functions
└── integration/
    └── test_tray_open_mainwindow.py  (NEW) integration test: open window → overlays rendered
```

**Structure Decision**: Single-project layout, matching existing `src/catguard/` and `tests/` structure. `ui/` sub-package already exists (`settings_window.py`). Two new files added under `ui/`. No new top-level packages.

---

## Component Design

### `src/catguard/ui/overlays.py`

Pure functions; no tkinter or pystray imports. Operates on numpy arrays (OpenCV BGR).

```python
def draw_bounding_box(frame, bbox, color=(0,255,0), thickness=2) -> None
    # bbox: (x1, y1, x2, y2) integers

def draw_label(frame, text, position, font_scale=0.6, color=(0,255,0), thickness=2) -> None
    # position: (x, y) top-left of label text

def draw_detections(frame, results) -> numpy.ndarray
    # Iterates result.boxes; calls draw_bounding_box + draw_label for each detection
    # Returns a copy of frame with overlays applied
    # Handles empty/None results gracefully (returns frame unchanged)
```

### `src/catguard/ui/main_window.py`

```python
class MainWindow:
    def __init__(self, root: tk.Tk) -> None
        # Creates a hidden Toplevel; stores reference on root as root._main_window

    def show_or_focus(self) -> None
        # Called from main thread via root.after(); deiconify + raise if already exists

    def update_frame(self, frame_bgr: numpy.ndarray, detections) -> None
        # Called via root.after(0, ...) from DetectionLoop callback
        # Sizes window to frame on first call; updates canvas image thereafter
        # Draws "No detections" label when detections list is empty

    def _on_close(self) -> None
        # Destroys window; clears root._main_window; stops frame delivery

    def _show_no_source_message(self) -> None
        # Shows a label "No capture source available" with Retry / Close buttons
```

### `src/catguard/detection.py` additions

```python
# DetectionLoop gains an optional on_frame_ready callback:
def set_frame_callback(self, cb: Callable[[ndarray, list], None] | None) -> None
    # Thread-safe setter (protected by a threading.Lock)
    # Called with (frame_bgr, detections) after each inference cycle
    # cb=None disables delivery with zero overhead
```

### `src/catguard/tray.py` additions

```python
def on_open_clicked(icon, item):
    # Calls root.after(0, lambda: _ensure_main_window(root, detection_loop))

def _ensure_main_window(root, detection_loop):
    # Creates MainWindow if not present, then calls show_or_focus()
    # Registers main_window.update_frame as the DetectionLoop frame callback
```

---

## Key Decisions & Tradeoffs

| Decision | Choice | Rationale |
|----------|--------|-----------|
| UI toolkit | tkinter (existing) | Already a dependency; adds zero weight; runs on all target platforms. |
| Frame delivery | Callback + `root.after` | Avoids inter-thread tkinter calls; matches existing `_on_settings` pattern. |
| Overlay rendering | OpenCV `cv2.rectangle` / `cv2.putText` on BGR frame copy | cv2 already loaded in `DetectionLoop`; no new dependency; fast in-memory op. |
| Frame → tkinter image | `PIL.ImageTk.PhotoImage` via Pillow (existing dep) | Standard cross-platform approach; Pillow already in `pyproject.toml`. |
| Window sizing | Set `Toplevel` geometry to `{w}x{h}` on first frame | Exact frame size per FR-003; falls back to scale-to-screen if frame exceeds screen bounds. |
| Single instance | Guard via `root._main_window` attribute | Simple, idiomatic tkinter pattern; no global state needed. |
| No `plan.md` impact on tasks | tasks.md already drafted | Tasks aligned; only task ordering needs updating to enforce TDD-first (tests before implementation). |

---

## TDD Execution Order

Per the project constitution, tests are written and **fail** before implementation.

1. `tests/unit/test_overlays.py` — test `draw_bounding_box`, `draw_label`, `draw_detections` return correct frame shapes and annotate expected pixel regions
2. `tests/unit/test_main_window.py` — test `MainWindow` initialization, `show_or_focus` guard, `update_frame` sizing logic (mock tkinter/cv2)
3. `tests/unit/test_tray.py` — assert tray menu contains `Open`, `Settings…`, `Exit`
4. **Implement** `overlays.py` → tests go green
5. **Implement** `main_window.py` → tests go green
6. **Implement** tray `Open` handler → tray unit test goes green
7. **Implement** `DetectionLoop.set_frame_callback` + wire in `main.py`
8. `tests/integration/test_tray_open_mainwindow.py` — end-to-end: fake frame + detection → verify window resized + overlay draw called

---

## Out of Scope

- Audio/alert changes (existing `on_cat_detected` unchanged)
- Settings window changes
- Multi-window support (single `MainWindow` instance)
- Recording or saving frames
- Remote/network camera sources
