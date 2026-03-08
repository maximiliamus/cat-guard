# Quickstart: Alert Effectiveness Tracking & Annotated Screenshots

**Feature**: `005-alert-effectiveness`
**Date**: 2026-03-02

---

## Prerequisites

- Python 3.14+ virtual environment activated
- `pip install -e .` completed (installs `opencv-python`, `ultralytics`, `numpy`, etc.)
- Webcam connected and accessible
- `yolo11n.pt` model file present at repository root

---

## Verify the Feature Works (Manual Walkthrough)

### Step 1 — Confirm baseline tests pass before writing any implementation

```bash
pytest tests/ -x -q
```

All existing tests must be green before touching any source file.

---

### Step 2 — Run the app and confirm plain screenshots are working (pre-feature state)

```bash
python -m catguard
```

Hold a cat (or cat image on phone) in front of the webcam until an alert fires.
Open the screenshots folder (`~/Pictures/CatGuard/<today>/`) — you should see a plain
JPEG with no bounding boxes.

---

### Step 3 — Run the unit tests for the new annotation module (TDD: write tests first)

After writing `tests/unit/test_annotation.py` (before implementing `annotation.py`):

```bash
pytest tests/unit/test_annotation.py -v
# Expected: all tests FAIL (Red phase)
```

---

### Step 4 — Implement `annotation.py` and verify Green phase

```bash
pytest tests/unit/test_annotation.py -v
# Expected: all tests PASS (Green phase)
```

---

### Step 5 — Run the full test suite to confirm no regressions

```bash
pytest tests/ -x -q
```

---

### Step 6 — Manual end-to-end verification

Run the app:

```bash
python -m catguard
```

Trigger a detection event (hold a cat image in front of webcam). Then:

1. **Wait for the cooldown to elapse** (default: 15 seconds) while keeping the cat
   image **out of frame**.
2. Open the screenshots folder. You should find a new JPEG.
3. Open the JPEG in any image viewer and confirm:
   - [ ] A **green bounding box** is drawn around the cat region
   - [ ] A **confidence percentage** label (e.g. "87%") appears near the bounding box
   - [ ] The **top-left corner** shows the alert sound filename (e.g. "default.wav" or
         "Alert: Default")
   - [ ] The **bottom edge** shows a **green** outcome strip with a human-readable
         message (e.g. "Cat left – alert worked!")

4. Now trigger another detection but **keep the cat in frame** during the full cooldown.
5. After cooldown, open the new JPEG and confirm:
   - [ ] Bottom edge shows a **red** outcome strip (e.g. "Cat remained after alert")

---

### Step 7 — Verify unknown-outcome path (camera disconnect test)

1. Trigger a detection event.
2. During the cooldown, physically unplug the webcam.
3. After cooldown would have elapsed, reconnect and open the saved JPEG.
4. Confirm: **no outcome strip** is drawn (the screenshot is saved without an overlay,
   which signals "unknown outcome" per FR-012).

---

### Step 8 — Run integration tests

```bash
pytest tests/integration/test_effectiveness_integration.py -v
```

The integration test verifies the full pipeline end-to-end using a synthetic numpy
frame and mocked YOLO model, confirming:
- Bounding box pixels are the correct color at the expected coordinates
- Outcome strip pixels are green or red depending on `has_cat` at verification
- Sound label text region is present in the top-left quadrant
- No file is written to disk until `on_verification` is called

---

## Key Files

| File | Role |
|------|------|
| [src/catguard/annotation.py](../../../src/catguard/annotation.py) | NEW — frame annotation + EffectivenessTracker |
| [src/catguard/detection.py](../../../src/catguard/detection.py) | MODIFIED — BoundingBox, on_verification callback |
| [src/catguard/audio.py](../../../src/catguard/audio.py) | MODIFIED — play_alert() returns sound label |
| [src/catguard/main.py](../../../src/catguard/main.py) | MODIFIED — wires tracker into detection pipeline |
| [tests/unit/test_annotation.py](../../../tests/unit/test_annotation.py) | NEW — unit tests (write before implementing) |
| [tests/integration/test_effectiveness_integration.py](../../../tests/integration/test_effectiveness_integration.py) | NEW — integration tests |

---

## Common Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Screenshot saved immediately (no cooldown wait) | `EffectivenessTracker.on_detection()` not wired in `main.py` | Check `on_cat_detected` callback in `main.py` |
| Screenshot has no bounding boxes | `annotate_frame()` not called before save | Check `EffectivenessTracker.on_verification()` |
| Outcome strip missing on all screenshots | `set_verification_callback()` not called on `DetectionLoop` | Check `main.py` setup |
| `play_alert()` call fails type check | Caller not updated to capture return value | Update `on_cat_detected` to `sound_label = play_alert(...)` |
| `cv2.putText` coordinate error | YOLO float32 coords not converted to int | Apply `int()` + clamp in `BoundingBox` construction |
