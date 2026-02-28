# Implementation Plan: Screenshot on Cat Detection

**Branch**: `003-cat-detection-screenshots` | **Date**: 2026-03-01 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/003-cat-detection-screenshots/spec.md`

---

## Summary

When a cat is detected and the alert sound fires, capture the camera frame and save it as a maximum-compression JPEG inside `<root>/<yyyy-mm-dd>/<HH-MM-SS[-N]>.jpg`. The root folder defaults to `Pictures/CatGuard` (resolved at runtime per OS) and is user-configurable in Settings. Screenshots are skipped when the main window is open or when an optional daily time window (start/end HH:MM, can span midnight) is enabled and the current time falls outside it. Save failures are logged and surfaced as a brief tray balloon notification; they never block the alert sound. A new single-responsibility module (`screenshots.py`) encapsulates all save logic with no tkinter dependency, making it fully unit-testable.

---

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: OpenCV `cv2` (JPEG encoding — already a runtime dependency), `platformdirs` (transitive via ultralytics — `user_pictures_dir()`), `pystray` (tray `notify()` for failure notifications — already a runtime dependency), `pydantic` (Settings model extension), `tkinter` (settings UI — stdlib)  
**Storage**: JPEG files on local disk (`<root>/<yyyy-mm-dd>/<HH-MM-SS[-N]>.jpg`)  
**Testing**: pytest 8+, pytest-mock  
**Target Platform**: Windows (primary), Linux, macOS (same as existing app)  
**Project Type**: Desktop GUI application  
**Performance Goals**: Screenshot save completes within 200 ms p95; zero additional latency introduced to the alert sound path (save is called after the sound callback returns, on the same detection thread)  
**Constraints**: All tkinter calls MUST remain on the main thread; screenshot I/O runs on the `DetectionLoop` daemon thread and MUST NOT call any tkinter API. No new heavyweight dependencies. `platformdirs` is already available transitively.  
**Scale/Scope**: Single user, single camera stream, local disk only

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — all gates pass.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✓ REQUIRED | `tests/unit/test_screenshots.py` and `tests/integration/test_screenshot_integration.py` written before implementation. All new logic in `screenshots.py` is pure-function testable with no display required. |
| II. Observability & Logging | ✓ REQUIRED | Structured `logging` calls in `screenshots.py` for every save attempt, success, and failure (with exception info). Tray notification on failure. |
| III. Simplicity & Clarity | ✓ ENFORCED | New logic isolated in one new module (`screenshots.py`). No new GUI framework. Reuse `cv2.imencode` for JPEG (already imported in detection path). No new top-level dependencies. |
| IV. Integration Testing | ✓ REQUIRED | Integration test exercises full detection → screenshot save path with a synthetic frame. |
| V. Versioning & Breaking Changes | ✓ NOTED | Settings schema gains 4 new optional fields (non-breaking); `DetectionEvent` gains an optional `frame_bgr` field (non-breaking, `None` default). Version stays at `0.1.0`. |

---

## Architecture & Data Flow

```
DetectionLoop (daemon thread)
  └─ _run() loop:
       ├─ cap.read()  → raw BGR frame (numpy ndarray)
       ├─ model.predict()
       └─ on_cat_detected(DetectionEvent(frame_bgr=frame))   ← frame attached to event

main.py  on_cat_detected(event):
  ├─ play_random_alert(...)                                   ← existing
  └─ screenshots.save_screenshot(                             ← NEW
         frame_bgr   = event.frame_bgr,
         settings    = settings,
         is_window_open = lambda: _is_main_window_open(root),
         on_error    = lambda msg: _tray_notify(tray_icon, msg)
     )

screenshots.py  save_screenshot(frame_bgr, settings, is_window_open, on_error):
  ├─ if is_window_open() → return (FR-012)
  ├─ if not is_within_time_window(settings) → return (FR-015)
  ├─ root = resolve_root(settings)
  ├─ path = build_filepath(root, datetime.now())
  ├─ path.parent.mkdir(parents=True, exist_ok=True)   (FR-005)
  ├─ cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 1])
  └─ on exception → logger.error + on_error(msg)

tray.py  _tray_notify(icon, msg):
  └─ icon.notify(msg, "CatGuard")                            (FR-010)
```

**Thread safety**: `save_screenshot` runs on the `DetectionLoop` daemon thread. It never touches tkinter objects directly. The `is_window_open()` lambda reads a plain Python bool attribute (`root._main_window_visible`) that is set by the main thread — reading a Python bool under the GIL is safe without an explicit lock. The `on_error` lambda calls `pystray.Icon.notify()` which is documented as thread-safe in pystray.

**Main-window visibility tracking**: `MainWindow.show_or_focus()` sets `root._main_window_visible = True`; `MainWindow._on_close()` sets it to `False`. The attribute is initialised to `False` in `main.py` before the detection loop starts.

---

## Project Structure

### Documentation (this feature)

```text
specs/003-cat-detection-screenshots/
├── spec.md
├── plan.md              ← this file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── config.md        ← updated settings schema (4 new fields)
└── tasks.md             ← Phase 2 output (/speckit.tasks command)
```

### Source Code Changes

```text
src/catguard/
├── screenshots.py           (NEW) save logic — pure functions, no tkinter
├── config.py                (UPDATE) 4 new Settings fields
├── detection.py             (UPDATE) DetectionEvent.frame_bgr optional field
├── main.py                  (UPDATE) on_cat_detected calls save_screenshot; tracks main-window visibility
├── tray.py                  (UPDATE) expose _tray_notify helper; pass icon ref to main.py
└── ui/
    ├── main_window.py       (UPDATE) _main_window_visible bool toggle
    └── settings_window.py   (UPDATE) SettingsFormModel + UI for screenshots section

tests/
├── unit/
│   ├── test_screenshots.py          (NEW) unit tests for screenshots.py pure functions
│   ├── test_config.py               (UPDATE) new Settings fields
│   ├── test_settings_window.py      (UPDATE) SettingsFormModel new fields
│   ├── test_detection.py            (UPDATE) DetectionEvent.frame_bgr field
│   ├── test_main_window.py          (UPDATE) _main_window_visible toggling
│   └── test_tray.py                 (UPDATE) notify_error helper
└── integration/
    └── test_screenshot_integration.py  (NEW) end-to-end: detection → file saved on disk
```

**Structure Decision**: Single-project layout (Option 1). All changes are additive to the existing `src/catguard/` tree.
