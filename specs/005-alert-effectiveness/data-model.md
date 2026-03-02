# Data Model: Alert Effectiveness Tracking & Annotated Screenshots

**Feature**: `005-alert-effectiveness`
**Date**: 2026-03-02

---

## Modified Entities

### `BoundingBox` *(new dataclass — `src/catguard/detection.py`)*

A lightweight, serialisation-friendly record of a single detected region within a
camera frame. Replaces the ad-hoc per-box iteration in `DetectionLoop._run()`.

| Field | Type | Description |
|-------|------|-------------|
| `x1` | `int` | Left edge of the bounding box in pixels (clamped to frame width) |
| `y1` | `int` | Top edge of the bounding box in pixels (clamped to frame height) |
| `x2` | `int` | Right edge of the bounding box in pixels |
| `y2` | `int` | Bottom edge of the bounding box in pixels |
| `confidence` | `float` | Detection confidence score in [0.0, 1.0] |

**Validation rules**:
- Coordinates are converted from YOLO's `float32` tensor output using `int()`
  (truncation) and clamped to `[0, frame_dimension − 1]` before storage.
- `confidence` is the raw float from `box.conf[0]`; displayed as `f"{int(c * 100)}%"`.

---

### `DetectionEvent` *(modified — `src/catguard/detection.py`)*

Two fields are changed or added. All existing fields are preserved and their defaults
are unchanged, so code paths that do not read `boxes` continue to work without
modification.

| Field | Change | Type | Default | Description |
|-------|--------|------|---------|-------------|
| `confidence` | *unchanged* | `float` | — | Max confidence across all detected boxes (kept for backward compatibility) |
| `sound_file` | *unchanged* | `Optional[str]` | `None` | Sound label; now populated by `main.py` after calling `play_alert()` |
| `frame_bgr` | *unchanged* | `Optional[np.ndarray]` | `None` | Raw BGR frame at detection moment |
| `boxes` | **NEW** | `list[BoundingBox]` | `field(default_factory=list)` | All detected bounding boxes in the frame at detection time |

**Behavioral change**: `DetectionLoop._run()` is refactored to fire exactly **one**
`SOUND_PLAYED` event per frame (containing all detected boxes), rather than one event
per detected box. The previous per-box iteration caused the callback to be invoked
multiple times per frame; only the first call fired SOUND_PLAYED and the rest were
COOLDOWN_SUPPRESSED. The new behavior is equivalent from a user perspective (one alert
per cooldown cycle) but is semantically cleaner and required for all-box annotation.

---

### `DetectionLoop` *(modified — `src/catguard/detection.py`)*

Three internal state fields and one optional callback are added. All existing public
API (`start()`, `stop()`, `set_frame_callback()`) is unchanged.

**New state fields** (internal):

| Field | Type | Initial | Description |
|-------|------|---------|-------------|
| `_pending_frame` | `Optional[np.ndarray]` | `None` | Deep copy of frame captured at detection time; `None` when no verification is pending. Sole pending-state sentinel — detection-time boxes and sound label are owned by `EffectivenessTracker` (YAGNI: no `_pending_boxes`/`_pending_sound` in `DetectionLoop`) |

**New public setter**:

| Method | Signature | Description |
|--------|-----------|-------------|
| `set_verification_callback` | `(cb: Optional[Callable[[bool, list[BoundingBox]], None]]) -> None` | Register or clear the callback invoked at cooldown expiry. Called as `cb(has_cat, boxes)` where `has_cat` is `True` if ≥1 cat box detected in the verification frame. Cleared with `None`. |

**Verification trigger logic** (added to `_run()` inner loop):
```
Before normal detection on each frame:
  if _pending_frame is not None and _cooldown_elapsed():
      has_cat = len(cat_boxes_in_current_frame) > 0
      call on_verification(has_cat, cat_boxes_in_current_frame)
      _pending_frame = None   ← clears pending state (sole sentinel)
```
Note: the pending state is cleared *before* calling the callback to avoid re-entrance
if the callback triggers a detection event synchronously.

---

### `play_alert()` return value *(modified — `src/catguard/audio.py`)*

Return type changes from `None` to `str`. The returned string is the sound label used
in the screenshot annotation (FR-011a).

| Playback mode | Condition | Return value |
|---------------|-----------|--------------|
| DEFAULT | `settings.use_default_sound is True` | `"Alert: Default"` |
| PINNED | `use_default_sound is False` and `pinned_sound` is a valid file | `Path(pinned_sound).name` |
| PINNED fallback | Pinned file missing — falls back to RANDOM | `Path(chosen).name` or `"Alert: Default"` |
| RANDOM | Library has valid files | `Path(chosen).name` |
| RANDOM fallback | Library empty or all invalid — falls back to default | `"Alert: Default"` |

---

## New Entities

### `EffectivenessTracker` *(new — `src/catguard/annotation.py`)*

Manages the pending snapshot lifecycle: stores the detection frame in memory, receives
the verification result, annotates the frame, and dispatches the async save.

| Attribute / Method | Type | Description |
|--------------------|------|-------------|
| `_pending_frame` | `Optional[np.ndarray]` | Deep copy of the detection frame held in memory |
| `_pending_boxes` | `list[BoundingBox]` | Bounding boxes from the detection frame |
| `_pending_sound` | `Optional[str]` | Sound label string |
| `_settings` | `Settings` | Reference to the shared settings object (for save path, time window) |
| `_is_window_open` | `Callable[[], bool]` | Delegate for the "main window is open" check |
| `_on_error` | `Callable[[str], None]` | Error forwarding callback (to tray notification) |
| `on_detection(frame, boxes, sound_label)` | method | Called by `main.py` on `SOUND_PLAYED`. Stores a deep copy of the frame and metadata. If already tracking (FR-005a), silently ignores the new event. |
| `on_verification(has_cat, boxes)` | method | Called by `DetectionLoop` at cooldown expiry. Determines outcome, annotates the pending frame, dispatches async save, clears pending state. |
| `_is_pending` | `bool` property | `True` while a frame is held in memory awaiting verification. |

**State machine**:

```
[idle]
  ──on_detection()──▶ [pending: frame held in memory]
                            │
                      on_detection() while pending → silently ignored (FR-005a)
                            │
                      on_verification(has_cat)
                            │
                    ┌───────┴──────────┐
               has_cat=False       has_cat=True
                    │                  │
             outcome="deterred"  outcome="remained"
                    └───────┬──────────┘
                    annotate_frame(outcome)
                    _save_annotated_async()
                    clear pending state
                            │
                         [idle]
```

---

### `annotate_frame()` *(new pure function — `src/catguard/annotation.py`)*

Applies all three annotation layers to a copy of the input frame and returns the
result. Does not modify the input array.

| Parameter | Type | Description |
|-----------|------|-------------|
| `frame_bgr` | `np.ndarray` | Source frame; a copy is made internally |
| `boxes` | `list[BoundingBox]` | Detected regions to annotate with bounding boxes |
| `sound_label` | `str` | Text for the top-left corner (filename or "Alert: Default") |
| `outcome` | `Optional[str]` | `"deterred"`, `"remained"`, or `None` (unknown) |
| **returns** | `np.ndarray` | New annotated BGR ndarray |

**Annotation zones** (non-overlapping by design):

| Zone | Content | Position |
|------|---------|----------|
| Bounding boxes | Rectangle + confidence % label on filled rect | On detected regions within the frame |
| Sound label | Filename text on filled background rect | Top-left corner (x=10, y=10 + text height) |
| Outcome overlay | Full-width filled strip with outcome message | Bottom edge of frame |

---

### `build_sound_label()` *(new pure function — `src/catguard/annotation.py`)*

Normalises the raw string returned by `play_alert()` for display on the screenshot.

| Input | Output |
|-------|--------|
| `"Alert: Default"` | `"Alert: Default"` (pass-through) |
| Absolute path string | `Path(value).name` (filename only, no directory) |
| `None` | `"Alert: Default"` (defensive fallback) |
