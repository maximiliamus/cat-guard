# Implementation Report: Replace ultralytics/PyTorch with ONNX + onnxruntime

## Outcome

All plan objectives met. 415 unit tests pass.

---

## Changes Made

### New / removed files

| File | Action |
|------|--------|
| `yolo11n.onnx` | Added — exported from `yolo11n.pt` (10.2 MB) |
| `yolo11n.pt` | Kept on disk; remove from repo when committing |

### Source changes

#### `src/catguard/detection.py`

- `MODEL_NAME` changed from `"yolo11n.pt"` to `"yolo11n.onnx"`
- Added module constant `_INPUT_SIZE = 640`
- Added `_model_input_name: Optional[str] = None` to `DetectionLoop.__init__`
- Added two module-level helper functions before `DetectionEvent`:
  - `_preprocess_frame(frame, size)` — letterbox resize to 640×640, center-pad with gray (114), BGR→RGB, HWC→CHW, normalize to float32, returns `(1, 3, 640, 640)` blob
  - `_postprocess(raw, conf_threshold, target_class, frame_shape)` — decodes `(1, 84, 8400)` ONNX output: confidence filter on cat class (index 15), `cv2.dnn.NMSBoxes` with IoU=0.45, de-projects coordinates accounting for letterbox padding back to original frame space; returns `list[BoundingBox]`
- `_load_model()` rewritten: imports `onnxruntime`, creates `InferenceSession` with `CPUExecutionProvider`, stores input tensor name in `self._model_input_name`
- Inference block in `_run()` replaced: removed intermediate 480p resize and `YOLO.predict()` call; now calls `_preprocess_frame` → `model.run()` → `_postprocess()`
- Frame callback now passes `all_boxes` (`list[BoundingBox]`) instead of YOLO result objects
- Error message updated to "Failed to load ONNX model"

#### `src/catguard/ui/overlays.py`

- `draw_detections(frame, results)` rewritten to iterate `BoundingBox` objects directly (`.label`, `.confidence`, `.x1/.y1/.x2/.y2`) instead of YOLO result objects with `.boxes`, `.names`, `.xyxy`, `.conf`, `.cls`

#### `src/catguard/ui/main_window.py`

- `_update_no_detections_label` simplified from YOLO result iteration to `has_detections = bool(detections)`

#### `pyproject.toml`

- `"ultralytics>=8.3.0"` replaced with `"onnxruntime>=1.18.0"`

#### `catguard.spec`

- Removed `from PyInstaller.utils.hooks import collect_all` and `collect_all('ultralytics')` call
- Removed `ultralytics_binaries`, `ultralytics_datas`, `ultralytics_hiddenimports` from `Analysis`
- Changed bundled model entry from `('yolo11n.pt', '.')` to `('yolo11n.onnx', '.')`

#### `README.md`

- Replaced "On first run, CatGuard downloads the YOLO model (~6 MB) — internet access required once" with "The YOLO model is bundled inside the zip — no internet access required"
- Removed model download step from the First Run section
- Updated integration test note: `ultralytics` → `onnxruntime`

### Test changes

#### `tests/unit/test_detection.py`

- `TestNoDetectionPath.test_no_callback_when_yolo_returns_no_boxes`: changed mock from `model.predict.return_value = [mock_result]` to `model.run.return_value = [np.zeros((1, 84, 8400))]`; real frame (480×640 zeros) passed so `_preprocess_frame` runs without error; `_postprocess` returns `[]` on all-zeros input (all scores below threshold)
- `TestOneEventPerFrame._run_loop_with_boxes`: removed YOLO mock boxes; now patches `catguard.detection._postprocess` with `return_value=fake_boxes` (list of real `BoundingBox` objects); `model.run` returns zeros
- `TestVerificationCallback.test_pending_frame_set_after_sound_played`: same pattern — `_postprocess` patched to return one box
- `TestVerificationCallback.test_verification_callback_fires_after_cooldown` and `test_pending_frame_cleared_before_callback`: `model.run` returns zeros; `_postprocess` not patched — real postprocess runs and returns `[]` (no cats in blank frame)

#### `tests/unit/test_overlays.py`

- Removed `_make_mock_box` and `_make_mock_result` helper functions
- Added `_make_bbox(x1, y1, x2, y2, conf, label)` helper that returns a real `BoundingBox`
- Updated `test_single_detection_annotates_frame`, `test_multiple_detections_both_annotated`, and `test_result_with_none_boxes_handled_gracefully` to pass `BoundingBox` objects directly

#### `tests/integration/test_detection_integration.py`

- `pytest.importorskip` guard changed from `"ultralytics"` to `"onnxruntime"`
- Module docstring updated
- `test_no_callback_on_blank_frame`: replaced `model.predict()` call with `_preprocess_frame` → `model.run` → `_postprocess` pipeline
- `test_model_loads_without_error`: now also asserts `loop._model_input_name is not None`
- Other tests unchanged (they don't call the model directly)

---

## Patterns Applied

- Lazy imports retained throughout (cv2, onnxruntime imported inside functions) — consistent with existing codebase style
- Module-level helper functions `_preprocess_frame`/`_postprocess` placed before the class, following the existing `list_cameras` pattern
- Duck typing in `overlays.py` — no import of `BoundingBox` needed; accesses attributes directly
- `_postprocess` patching in unit tests instead of crafting valid ONNX tensors — keeps tests focused on loop behavior, not binary format

---

## Verified

- `yolo11n.onnx`: 10.2 MB, opset 17, input shape `[1, 3, 640, 640]`, output shape `[1, 84, 8400]`
- `onnxruntime 1.24.3` installed
- **415 tests pass, 8 skipped** (skips are pre-existing, unrelated to this change)
- `yolo11n.pt` (5.6 MB) still present on disk — delete from repo before committing

---

## Remaining step

Commit the changes and remove `yolo11n.pt` from the repository:

```bash
git rm yolo11n.pt
git add yolo11n.onnx src/catguard/detection.py src/catguard/ui/overlays.py \
        src/catguard/ui/main_window.py pyproject.toml catguard.spec README.md \
        tests/unit/test_detection.py tests/unit/test_overlays.py \
        tests/integration/test_detection_integration.py
git commit -m "Replace ultralytics/PyTorch with ONNX + onnxruntime for inference"
```
