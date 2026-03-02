# Research: Alert Effectiveness Tracking & Annotated Screenshots

**Feature**: `005-alert-effectiveness`
**Date**: 2026-03-02

---

## 1. OpenCV Bounding Box & Confidence Label Annotation

**Decision**: Two-pass label drawing — filled rectangle background in the box colour,
white text on top. All coordinates converted to `int` (truncation) from YOLO's
`float32` tensor output, clamped to frame bounds.

**Rationale**:
- A filled backing rectangle guarantees legibility against any camera background
  (snow, night scene, high-key) without extra alpha-blend operations.
- Two-pass approach — measure text → draw background rect → draw text — is the exact
  method used by Ultralytics' own annotation code (`ultralytics.utils.plotting`).
- Shadow / outline approaches degrade at `fontScale < 0.6` (common in SD cameras) and
  require multiple `putText` calls per label with ambiguous thickness interactions.

**Key implementation parameters**:

```python
# Bounding box
BOX_COLOR     = (0, 200, 0)        # BGR — softer than pure (0,255,0)
BOX_THICKNESS = 2

# Confidence label
FONT          = cv2.FONT_HERSHEY_SIMPLEX  # built-in sans-serif, no font files
FONT_SCALE    = 0.55
FONT_THICK    = 1                  # crisp at 0.55 scale; 2 bleeds
LINE_TYPE     = cv2.LINE_AA        # anti-aliased; negligible CPU cost
LABEL_PAD     = 4                  # px padding inside the background rect

# Coordinate conversion (YOLO returns float32 tensors)
x1, y1, x2, y2 = (
    int(box.xyxy[0][0]), int(box.xyxy[0][1]),
    int(box.xyxy[0][2]), int(box.xyxy[0][3]),
)
# Clamp to frame dimensions to guard against sub-pixel out-of-bounds values
x1 = max(0, min(x1, frame.shape[1] - 1))
# … same for y1, x2, y2
```

**Alternatives considered**:
- **Shadow / double-draw**: Multiple `putText` calls with pixel offsets. Ambiguous at
  small font scales; bleed at large thickness. Rejected.
- **`cv2.addWeighted` semi-transparent rect**: Three operations (slice, blend,
  write-back) for no readability gain. Rejected.

---

## 2. Outcome Overlay Rendering (Bottom-Left Corner)

**Decision**: Full-width filled strip spanning the bottom edge of the frame, white text
drawn on top. Success strip is green; failure strip is red.

**Rationale**:
- The bottom of a typical camera frame is background (floor, furniture) — not the
  region of interest where bounding boxes appear. A full-width strip is unambiguous and
  never conflicts with bounding-box zones in the image interior.
- Colored text only (no background) fails against a matching-color camera background
  (e.g., green plant, red cushion). FR-004 requires sufficient contrast.
- A full-width strip at the bottom is visually distinct from the top-left sound label,
  satisfying the non-overlap constraint from FR-011 and FR-011a by design.

**Key implementation parameters**:

```python
SUCCESS_BG    = (0, 180, 0)        # BGR green — softer than pure (0,255,0)
FAILURE_BG    = (0, 0, 200)        # BGR red
TEXT_COLOR    = (255, 255, 255)    # white on both backgrounds
OUTCOME_FONT_SCALE = 0.7
OUTCOME_THICK = 2
OUTCOME_PAD   = 10                 # px

# Placement: full-width rect, flush to bottom
h, w = frame.shape[:2]
(tw, th), baseline = cv2.getTextSize(text, font, OUTCOME_FONT_SCALE, OUTCOME_THICK)
rect_y1 = h - th - baseline - OUTCOME_PAD * 2
cv2.rectangle(frame, (0, rect_y1), (w, h), bg_color, -1)  # -1 = filled
cv2.putText(frame, text, (OUTCOME_PAD, h - baseline - OUTCOME_PAD),
            font, OUTCOME_FONT_SCALE, TEXT_COLOR, OUTCOME_THICK, cv2.LINE_AA)
```

**Alternatives considered**:
- **Colored text only**: Fails on color-matched camera backgrounds. Rejected (FR-004).
- **`cv2.addWeighted` semi-transparent overlay**: Visually elegant but three operations
  with no readability advantage for a one-line banner. Rejected.
- **Bottom-left text-only (no strip)**: Leaves ambiguous overlap risk with low bounding
  boxes. Full-width strip eliminates ambiguity. Rejected.

---

## 3. Verification Trigger Mechanism

**Decision**: Loop-based — the existing detection loop fires an `on_verification`
callback on the first iteration where `_cooldown_elapsed()` returns `True` after a
`SOUND_PLAYED` event, using the frame already captured in that iteration.

**Rationale**:
- The camera (`cv2.VideoCapture`) is owned and held open exclusively by the detection
  loop thread for the full app session. `VideoCapture` is **not thread-safe** — a
  second thread opening the same camera index (as required by Option B) causes
  device-busy failures on Windows DSHOW.
- The loop already processes frames every ~50 ms; the verification frame is captured
  in the normal `cap.read()` call of the first post-cooldown iteration — no additional
  camera access, no model reload.
- Timing accuracy: verification fires within one frame interval (≤50 ms) of the
  cooldown expiry, which is well within the precision that matters for user-visible
  cat-detection outcomes.

**State added to `DetectionLoop`**:

```python
_pending_frame: Optional[np.ndarray] = None    # copy of detection frame
_pending_boxes: list[BoundingBox]   = []        # all boxes from detection frame
_pending_sound: Optional[str]       = None      # sound label to annotate
# Cleared after on_verification fires; prevents double-fire.
```

**Alternatives considered**:
- **`threading.Timer` + new camera open**: Opens the same physical device from a
  second thread — fails silently on Windows DSHOW. Timer lifecycle (cancellation
  on app exit) adds complexity. Rejected.
- **`threading.Timer` passing the existing cap object**: `VideoCapture` is not
  re-entrant across threads. Rejected.

---

## 4. Async Annotation & Save Pattern

**Decision**: Fire-and-forget `threading.Thread(target=_worker, daemon=True).start()`
— identical to the existing `_play_async` pattern in `audio.py`.

**Rationale**:
- Events fire at most once per cooldown (every N seconds) — thread creation overhead
  is negligible.
- Daemon mode ensures the thread does not prevent app exit.
- Errors (disk full, encode failure) are caught inside `_worker`, logged, and forwarded
  to the existing `on_error` callback (same pattern as `save_screenshot`). They never
  propagate to the detection loop.
- **Critical**: the frame buffer (`np.ndarray`) is **copied at detection time** in the
  detection loop (`frame.copy()`) before being handed to the tracker, because
  `cap.read()` overwrites the same buffer on the next iteration.

**Alternatives considered**:
- **`concurrent.futures.ThreadPoolExecutor`**: Requires `executor.shutdown(wait=True)`
  at app exit — interacts awkwardly with daemon threads. Adds no value for ≤1 event
  per cooldown. Rejected.
- **Queue-based worker thread**: Provides serialization and backpressure — but FR-005a
  already guarantees at most one pending snapshot; no queue depth > 1 needed.
  Unnecessary complexity. Rejected.
- **`asyncio`**: App is tkinter + threading-based; introducing an event loop purely
  for disk I/O is architectural mismatch. Rejected.
