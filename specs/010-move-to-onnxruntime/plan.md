# Plan: Replace ultralytics/PyTorch with ONNX + onnxruntime

## Goal

Eliminate PyTorch (and the full `ultralytics` package) from the distributed build by:
1. Exporting `yolo11n.pt` to `yolo11n.onnx` once (offline, developer machine).
2. Replacing the `YOLO.predict()` inference path in `detection.py` with raw `onnxruntime` inference.
3. Removing `ultralytics` from runtime dependencies and the PyInstaller spec.

Expected outcome: distributed ZIP drops from ~500–700 MB to ~50–100 MB.

---

## Affected Files

| File | Change |
|------|--------|
| `src/catguard/detection.py` | Replace ultralytics YOLO with onnxruntime InferenceSession |
| `pyproject.toml` | Remove `ultralytics`, add `onnxruntime` |
| `catguard.spec` | Remove `collect_all('ultralytics')`, bundle `yolo11n.onnx` instead of `.pt` |
| `.github/workflows/build.yml` | No dependency on `ultralytics` install; bundle `.onnx` model |
| `tests/unit/test_detection.py` | Update mocks: mock `onnxruntime.InferenceSession` instead of `YOLO` |
| `tests/integration/test_detection_integration.py` | Adapt to new model loading path |
| `yolo11n.onnx` | New file to commit (exported once) |
| `yolo11n.pt` | Remove from repo after export is verified |

---

## Step-by-Step Implementation

### Step 1 — Export the model (developer, one-time)

On any machine with the current venv active:

```bash
python -c "
from ultralytics import YOLO
model = YOLO('yolo11n.pt')
model.export(format='onnx', imgsz=640, opset=17, simplify=True)
"
```

This produces `yolo11n.onnx` (~12 MB, still much smaller than torch).
Commit `yolo11n.onnx` and remove `yolo11n.pt` from the repo.

**Verify the export:**
```bash
python -c "
import onnxruntime as ort
import numpy as np
sess = ort.InferenceSession('yolo11n.onnx', providers=['CPUExecutionProvider'])
inp = sess.get_inputs()[0]
print(inp.name, inp.shape)  # expected: images, [1, 3, 640, 640]
out = sess.get_outputs()
print([o.name for o in out])  # expected: ['output0']
dummy = np.zeros(inp.shape, dtype=np.float32)
r = sess.run(None, {inp.name: dummy})
print(r[0].shape)  # expected: (1, 84, 8400)
"
```

---

### Step 2 — Rewrite `detection.py`

Replace the lazy-load and inference sections. No other logic changes.

#### 2a. Constants (top of file)

```python
# Before
MODEL_NAME = "yolo11n.pt"

# After
MODEL_NAME = "yolo11n.onnx"
CAT_CLASS_ID = 15  # unchanged — COCO index for 'cat'
_INPUT_SIZE = 640
_COCO_NC = 80  # number of classes in YOLO COCO model
```

#### 2b. Model loading (`_load_model`)

```python
def _load_model(self) -> None:
    if self._model is not None:
        return

    import sys
    from pathlib import Path
    import onnxruntime as ort

    if getattr(sys, "frozen", False):
        model_path = Path(sys._MEIPASS) / MODEL_NAME
    else:
        model_path = Path(MODEL_NAME)

    self._model = ort.InferenceSession(
        str(model_path),
        providers=["CPUExecutionProvider"],
    )
    self._model_input_name = self._model.get_inputs()[0].name
    logger.info("ONNX model loaded: %s", model_path)
```

#### 2c. Inference call (inside `_run` loop)

Replace `self._model.predict(...)` with a preprocessing + run + postprocessing block:

```python
# --- Preprocessing ---
import cv2
import numpy as np

blob = _preprocess_frame(small_frame, _INPUT_SIZE)

# --- ONNX inference ---
raw = self._model.run(None, {self._model_input_name: blob})[0]  # (1, 84, 8400)

# --- Postprocessing ---
boxes = _postprocess(raw, conf, CAT_CLASS_ID, small_frame.shape)
```

Helper functions to add to `detection.py` (module-level, before the class):

```python
import cv2
import numpy as np

def _preprocess_frame(frame: np.ndarray, size: int) -> np.ndarray:
    """Resize, normalize, and format a BGR frame for ONNX YOLO input.

    Returns float32 array of shape (1, 3, size, size).
    """
    h, w = frame.shape[:2]
    scale = size / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(frame, (new_w, new_h))

    # Letterbox pad to (size, size)
    canvas = np.zeros((size, size, 3), dtype=np.uint8)
    canvas[:new_h, :new_w] = resized

    # BGR → RGB, HWC → CHW, normalize
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    chw = rgb.transpose(2, 0, 1).astype(np.float32) / 255.0
    return chw[np.newaxis]  # (1, 3, 640, 640)


def _postprocess(
    raw: np.ndarray,
    conf_threshold: float,
    target_class: int,
    frame_shape: tuple[int, int, int],
) -> list["BoundingBox"]:
    """Convert raw YOLO ONNX output to BoundingBox list.

    raw shape: (1, 84, 8400) — 4 box coords + 80 class scores, 8400 anchors.
    Applies confidence filtering and NMS.
    """
    preds = raw[0].T  # (8400, 84)
    xc, yc, bw, bh = preds[:, 0], preds[:, 1], preds[:, 2], preds[:, 3]
    class_scores = preds[:, 4:]  # (8400, 80)

    cat_scores = class_scores[:, target_class]
    mask = cat_scores >= conf_threshold
    if not mask.any():
        return []

    xc, yc, bw, bh = xc[mask], yc[mask], bw[mask], bh[mask]
    scores = cat_scores[mask]

    # cx/cy/w/h → x1/y1/x2/y2 (in 640-px space)
    x1 = xc - bw / 2
    y1 = yc - bh / 2
    x2 = xc + bw / 2
    y2 = yc + bh / 2

    # OpenCV NMS expects integer boxes and float scores
    xyxy = np.stack([x1, y1, x2, y2], axis=1).astype(np.float32)
    indices = cv2.dnn.NMSBoxes(
        xyxy.tolist(), scores.tolist(), conf_threshold, iou_threshold=0.45
    )

    h_frame, w_frame = frame_shape[:2]
    scale = _INPUT_SIZE / max(h_frame, w_frame)

    results: list[BoundingBox] = []
    for i in (indices.flatten() if len(indices) else []):
        bx1 = max(0, int(x1[i] / scale))
        by1 = max(0, int(y1[i] / scale))
        bx2 = min(w_frame, int(x2[i] / scale))
        by2 = min(h_frame, int(y2[i] / scale))
        results.append(BoundingBox(bx1, by1, bx2, by2, float(scores[i])))
    return results
```

#### 2d. Frame callback / overlay compatibility

The existing `main_window.py` and `overlays.py` receive `BoundingBox` objects already — they do **not** use ultralytics `Results` objects directly. Verify this holds and no ultralytics-specific result type is forwarded to the UI. If any overlay code calls `.boxes` on a ultralytics object, replace it with the `BoundingBox` list.

---

### Step 3 — Update `pyproject.toml`

```toml
# Remove:
"ultralytics>=8.3.0",

# Add:
"onnxruntime>=1.18.0",
```

`opencv-python` is already a direct dependency, so NMS via `cv2.dnn.NMSBoxes` is available.

---

### Step 4 — Update `catguard.spec`

```python
# Remove these lines entirely:
from PyInstaller.utils.hooks import collect_all
ultralytics_datas, ultralytics_binaries, ultralytics_hiddenimports = collect_all('ultralytics')

# In Analysis(...):
# Remove from binaries: ultralytics_binaries
# Remove from datas: *ultralytics_datas
# Remove from hiddenimports: *ultralytics_hiddenimports

# Change model bundle entry:
# Before: ('yolo11n.pt', '.')
# After:  ('yolo11n.onnx', '.')
```

onnxruntime is auto-discovered by PyInstaller; no manual hidden imports needed.

---

### Step 5 — Update CI workflow (`.github/workflows/build.yml`)

No structural changes required. `pip install -e ".[dev]"` will now install `onnxruntime` instead of `ultralytics`. The `yolo11n.onnx` file must be committed to the repository so the build job can bundle it.

If the workflow previously installed `ultralytics` separately for the export step, remove that step — the model is pre-exported and committed.

---

### Note: end-user model delivery is unchanged

Currently, `yolo11n.pt` is **bundled inside the zip** via `catguard.spec` (`('yolo11n.pt', '.')`). The exe finds it at `sys._MEIPASS/yolo11n.pt` — no download happens for end users. The README note about first-run download describes the dev install path only and is outdated.

After migration, `yolo11n.onnx` is bundled the same way. End users see no difference in behaviour. In dev mode, the `.onnx` file is committed to the repo so no download is needed there either (and there is no ultralytics auto-download fallback to rely on anyway).

---

### Step 6 — Update tests

#### Unit tests (`tests/unit/test_detection.py`)

Replace YOLO mock with onnxruntime mock:

```python
# Before
mocker.patch("catguard.detection.YOLO", return_value=mock_model)

# After
mock_session = mocker.MagicMock()
mock_session.get_inputs.return_value = [mocker.MagicMock(name="images")]
mock_session.run.return_value = [np.zeros((1, 84, 8400), dtype=np.float32)]
mocker.patch("onnxruntime.InferenceSession", return_value=mock_session)
```

#### Integration tests (`tests/integration/test_detection_integration.py`)

Ensure `yolo11n.onnx` is present in the project root (it will be committed). Update any path references from `.pt` to `.onnx`.

---

### Step 7 — Smoke test

```bash
pip install -e .
python -m catguard  # Should start normally, log "ONNX model loaded: yolo11n.onnx"
```

---

## Expected Size Impact

| Component | Before | After |
|-----------|--------|-------|
| torch + torchvision | ~700 MB | 0 MB |
| ultralytics package | ~20 MB | 0 MB |
| onnxruntime | 0 MB | ~8 MB |
| yolo11n model | 5.4 MB (.pt) | ~12 MB (.onnx) |
| **Total ZIP estimate** | ~500–700 MB | **~50–100 MB** |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| ONNX output slightly differs from ultralytics (due to different NMS) | Test with real camera frames; adjust `iou_threshold` if needed |
| `cv2.dnn.NMSBoxes` signature varies across OpenCV versions | Pin `opencv-python>=4.9.0` (already done); test locally |
| onnxruntime version mismatch with opset 17 | Require `onnxruntime>=1.18.0`; opset 17 supported since 1.16 |
| Letterbox padding changes detection accuracy | Same 640px input size, same padding — should be transparent |
| PyInstaller misses onnxruntime native libs | Run `pyinstaller --clean` and verify; add hook if needed |

---

## Definition of Done

- [ ] `yolo11n.onnx` committed, `yolo11n.pt` removed
- [ ] `detection.py` uses only `onnxruntime` + `numpy` + `cv2` for inference
- [ ] `ultralytics` removed from all dependency lists
- [ ] Unit tests pass with updated mocks
- [ ] Integration tests pass against real ONNX model
- [ ] PyInstaller build succeeds and produces a working executable
- [ ] Distributed ZIP is under 150 MB
- [ ] README updated: remove incorrect "downloads on first run" note (model is bundled in the exe)
