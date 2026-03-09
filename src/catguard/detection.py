"""Cat detection module using YOLO11n (ONNX runtime).

Responsibilities:
- DetectionLoop: background daemon thread running ONNX inference on webcam frames
- list_cameras(): enumerate available camera indices via OpenCV
- DetectionEvent / DetectionAction: data model for detection outcomes
- Cooldown logic to suppress rapid-repeat alerts
- Confidence threshold read from shared Settings (pull model — no callback needed)
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional

# cv2 imported lazily inside functions so the module loads without opencv-python
# installed (e.g. in CI environments where only pure-Python packages are available).

from catguard.config import Settings

try:
    import numpy as np  # available when opencv-python is installed
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# YOLO COCO class index for 'cat'
CAT_CLASS_ID = 15
MODEL_NAME = "yolo11n.onnx"
_INPUT_SIZE = 640  # ONNX model input resolution


class CameraError(Exception):
    """Raised when camera operations fail (open, read, release)."""

    pass


class DetectionAction(Enum):
    """Outcome of a single detection event."""

    SOUND_PLAYED = "SOUND_PLAYED"
    """Alert triggered and a sound was played."""

    COOLDOWN_SUPPRESSED = "COOLDOWN_SUPPRESSED"
    """Cat detected but cooldown had not elapsed; no sound played."""


@dataclass
class BoundingBox:
    """A single detected region within a camera frame.

    Coordinates are pixel-space integers, clamped to frame dimensions.
    *confidence* is the raw YOLO score in [0.0, 1.0].
    *label* is the human-readable class name (e.g. "cat").
    """

    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    label: str = "cat"


def _preprocess_frame(frame: "np.ndarray", size: int) -> "np.ndarray":
    """Letterbox a BGR frame to *size*×*size* and return a float32 (1,3,H,W) blob."""
    import cv2

    h, w = frame.shape[:2]
    scale = size / max(h, w)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # Center-pad with gray (114) to produce a square canvas
    pad_top = (size - new_h) // 2
    pad_left = (size - new_w) // 2
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[pad_top : pad_top + new_h, pad_left : pad_left + new_w] = resized

    # BGR → RGB, HWC → CHW, [0,255] → [0,1]
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    chw = rgb.transpose(2, 0, 1).astype(np.float32) / 255.0
    return chw[np.newaxis]  # (1, 3, size, size)


def _postprocess(
    raw: "np.ndarray",
    conf_threshold: float,
    target_class: int,
    frame_shape: tuple,
) -> "list[BoundingBox]":
    """Decode raw YOLO11 ONNX output into BoundingBox objects.

    *raw* has shape (1, 84, 8400): 4 box coords + 80 class scores × 8400 anchors.
    Applies confidence filtering and NMS; scales boxes back to original frame size.
    """
    import cv2

    h_frame, w_frame = frame_shape[:2]
    scale = _INPUT_SIZE / max(h_frame, w_frame)
    new_h = int(round(h_frame * scale))
    new_w = int(round(w_frame * scale))
    pad_top = (_INPUT_SIZE - new_h) // 2
    pad_left = (_INPUT_SIZE - new_w) // 2

    preds = raw[0].T  # (8400, 84)
    xc, yc, bw, bh = preds[:, 0], preds[:, 1], preds[:, 2], preds[:, 3]
    cat_scores = preds[:, 4 + target_class]

    mask = cat_scores >= conf_threshold
    if not mask.any():
        return []

    xc, yc, bw, bh = xc[mask], yc[mask], bw[mask], bh[mask]
    scores = cat_scores[mask]
    x1 = xc - bw / 2
    y1 = yc - bh / 2

    # NMS expects (x, y, w, h) format
    bboxes_xywh = np.stack([x1, y1, bw, bh], axis=1).astype(np.float32).tolist()
    indices = cv2.dnn.NMSBoxes(bboxes_xywh, scores.tolist(), conf_threshold, 0.45)

    flat: list[int] = (
        indices.flatten().tolist()
        if hasattr(indices, "flatten") and len(indices) > 0
        else []
    )
    result: list[BoundingBox] = []
    for i in flat:
        bx1 = max(0, int((x1[i] - pad_left) / scale))
        by1 = max(0, int((y1[i] - pad_top) / scale))
        bx2 = min(w_frame, int((x1[i] + bw[i] - pad_left) / scale))
        by2 = min(h_frame, int((y1[i] + bh[i] - pad_top) / scale))
        result.append(BoundingBox(bx1, by1, bx2, by2, float(scores[i])))
    return result


@dataclass
class DetectionEvent:
    """Immutable record of a single detection occurrence (in-memory only)."""

    timestamp: datetime
    confidence: float
    action: DetectionAction
    sound_file: Optional[str] = None
    frame_bgr: Optional["np.ndarray"] = None
    """Raw BGR camera frame captured at the moment of detection.

    Set only for ``SOUND_PLAYED`` events so the screenshot module can save it
    without a second capture. ``None`` for ``COOLDOWN_SUPPRESSED`` events.
    Never written to disk; lives only for the duration of the callback.
    """
    boxes: "list[BoundingBox]" = field(default_factory=list)
    """All bounding boxes detected in the frame at the moment of the event.

    Empty list for ``COOLDOWN_SUPPRESSED`` events or when no boxes are
    available.  Set to all detected regions for ``SOUND_PLAYED`` events.
    """


@dataclass
class Camera:
    """Represents a detected webcam device."""

    index: int
    name: str
    available: bool


def list_cameras(max_index: int = 7) -> list[Camera]:
    """Enumerate available cameras by trying VideoCapture indices 0..max_index.

    Returns a list of Camera objects for every index that successfully opens.
    """
    import cv2  # lazy — opencv-python may not be installed in all environments
    import platform

    # Reduce noisy OpenCV native logs when probing devices (best-effort).
    try:
        # Prefer quieter log level when available
        if hasattr(cv2, "utils") and hasattr(cv2.utils, "logging"):
            cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        # Ignore failures — this is non-critical
        pass

    cameras: list[Camera] = []
    use_dshow = platform.system() == "Windows"

    for i in range(max_index + 1):
        # On Windows, prefer the DirectShow backend to avoid FFmpeg probing messages
        try:
            if use_dshow:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            else:
                cap = cv2.VideoCapture(i)

            if cap is not None and cap.isOpened():
                cameras.append(Camera(index=i, name=f"Camera {i}", available=True))
        except Exception:
            logger.debug("Exception while probing camera index %d", i, exc_info=True)
        finally:
            try:
                if 'cap' in locals() and cap is not None:
                    cap.release()
            except Exception:
                pass

    return cameras


class DetectionLoop:
    """Background daemon thread that runs YOLO11n inference on webcam frames.

    Settings are read on each frame iteration (pull model), so changes made to
    the shared Settings object by the settings window are immediately reflected
    without any thread-to-thread callbacks.
    """

    def __init__(
        self,
        settings: Settings,
        on_cat_detected: Callable[[DetectionEvent], None],
    ) -> None:
        self._settings = settings
        self._on_cat_detected = on_cat_detected
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_alert_time: Optional[datetime] = None
        self._model = None
        self._model_input_name: Optional[str] = None
        self._frame_callback: Optional[Callable] = None
        self._frame_callback_lock = threading.Lock()
        self._pending_frame: Optional["np.ndarray"] = None
        """Deep copy of detection frame held until verification fires.

        ``None`` when no verification is pending.  Acts as the sole
        pending-state sentinel (YAGNI: detection-time boxes and sound label
        are owned by EffectivenessTracker, not this loop).
        """
        self._latest_frame: Optional["np.ndarray"] = None
        """Latest raw BGR frame from the camera (for photo capture, etc).
        
        Updated on every frame iteration; used by ActionPanel to capture
        clean photos without detection overlays.
        """
        self._frame_lock = threading.Lock()
        self._verification_callback: Optional[Callable] = None
        # Pause/resume state management (T002, T003, T004)
        self._is_tracking = False
        self._tracking_lock = threading.Lock()
        self._on_error_callback: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the detection loop in a daemon thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="DetectionLoop", daemon=True
        )
        self._thread.start()
        logger.info("DetectionLoop started (camera=%d).", self._settings.camera_index)

    def stop(self) -> None:
        """Signal the loop to stop and wait up to 5 s for it to finish."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        logger.info("DetectionLoop stopped.")

    def set_frame_callback(
        self, cb: Optional[Callable[["np.ndarray", list], None]]
    ) -> None:
        """Set or clear the per-frame callback invoked after each inference cycle.

        Thread-safe: the callback is swapped atomically under a lock.
        Pass *cb=None* to disable delivery (zero overhead when window is closed).

        The callback is invoked as ``cb(frame_bgr, detections)`` where
        *frame_bgr* is the raw BGR numpy ndarray and *detections* is the
        list of YOLO result objects from that inference cycle.
        """
        with self._frame_callback_lock:
            self._frame_callback = cb
        logger.debug("Frame callback %s.", "registered" if cb is not None else "cleared")

    def set_verification_callback(
        self, cb: Optional[Callable[[bool, "list[BoundingBox]"], None]]
    ) -> None:
        """Register or clear the post-cooldown verification callback.

        Called as ``cb(has_cat, boxes)`` from the detection loop thread
        on the first iteration where ``_cooldown_elapsed()`` is True and
        a pending frame is held in memory.  Implementations MUST NOT
        perform blocking I/O directly; dispatch to a background thread.
        Pass *cb=None* to disable.
        """
        self._verification_callback = cb
        logger.debug(
            "Verification callback %s.",
            "registered" if cb is not None else "cleared",
        )

    def set_error_callback(self, cb: Optional[Callable[[str], None]]) -> None:
        """Register or clear the camera error callback.

        Called as ``cb(error_message)`` from the detection loop thread
        when a camera error occurs and auto-pause is triggered.
        Pass *cb=None* to disable.
        """
        self._on_error_callback = cb
        logger.debug(
            "Error callback %s.",
            "registered" if cb is not None else "cleared",
        )

    def pause(self) -> bool:
        """Stop the detection loop and disable camera.

        Returns:
            bool: True if pause was executed, False if already paused

        Thread-safe: Can be called from any thread
        Idempotent: Safe to call multiple times
        """
        with self._tracking_lock:
            if not self._is_tracking:
                return False  # Already paused
            self._is_tracking = False
        # Signal loop to stop (existing mechanism)
        self._stop_event.set()
        logger.info("Tracking paused.")
        return True

    def resume(self) -> bool:
        """Start the detection loop and enable camera.

        Returns:
            bool: True if resume was executed, False if already active

        Raises:
            CameraError: If camera cannot be opened

        Thread-safe: Can be called from any thread
        Idempotent: Safe to call multiple times
        """
        with self._tracking_lock:
            if self._is_tracking:
                return False  # Already running
            self._is_tracking = True
            self._stop_event.clear()  # Clear stop signal
        
        # Restart the detection thread since it exits when paused
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(
                target=self._run, name="DetectionLoop", daemon=True
            )
            self._thread.start()
        
        logger.info("Tracking resumed.")
        return True

    def is_tracking(self) -> bool:
        """Return whether tracking is currently active.

        Returns:
            bool: True if tracking active, False if paused/stopped

        Thread-safe: Read-only lock
        """
        with self._tracking_lock:
            return self._is_tracking

    def get_latest_frame(self) -> Optional["np.ndarray"]:
        """Return a copy of the latest captured frame, or None if unavailable.

        Thread-safe: Returns a copy to avoid race conditions with the
        detection loop updating the frame.

        Returns:
            np.ndarray or None: Latest BGR frame, or None if no frame
            has been captured yet (e.g., during startup).
        """
        with self._frame_lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Lazy-load the ONNX model (runs once inside the daemon thread).

        Cached in memory across pause/resume cycles for efficiency.
        In PyInstaller frozen builds, resolves the model path from sys._MEIPASS
        so the bundled yolo11n.onnx is found regardless of the working directory.
        """
        if self._model is not None:
            return  # Model already loaded, reuse it

        import sys
        from pathlib import Path

        import onnxruntime as ort

        if getattr(sys, "frozen", False):
            model_path = Path(sys._MEIPASS) / MODEL_NAME
        else:
            model_path = Path(MODEL_NAME)

        self._model = ort.InferenceSession(
            str(model_path), providers=["CPUExecutionProvider"]
        )
        self._model_input_name = self._model.get_inputs()[0].name
        logger.info("ONNX model loaded: %s", model_path)

    def _cooldown_elapsed(self) -> bool:
        """Return True if enough time has passed since the last alert."""
        if self._last_alert_time is None:
            return True
        elapsed = (
            datetime.now(timezone.utc) - self._last_alert_time
        ).total_seconds()
        return elapsed >= self._settings.cooldown_seconds

    def _run(self) -> None:
        """Main detection loop — runs inside the daemon thread."""
        import cv2  # lazy import
        import platform as _platform

        try:
            self._load_model()
        except Exception:
            error_msg = f"Failed to load ONNX model ({MODEL_NAME})."
            logger.exception(error_msg)
            self.pause()
            if self._on_error_callback:
                try:
                    self._on_error_callback(error_msg)
                except Exception:
                    logger.exception("Error callback raised an exception.")
            return

        # On Windows use DirectShow (consistent with list_cameras()); the
        # default MSMF backend is unreliable in PyInstaller-packaged builds.
        if _platform.system() == "Windows":
            cap = cv2.VideoCapture(self._settings.camera_index, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(self._settings.camera_index)
        # Limit the internal OpenCV buffer to 1 frame so we always process
        # the most recent camera frame rather than stale buffered ones.
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Increase field of view by minimizing zoom (if supported by camera)
        try:
            cap.set(cv2.CAP_PROP_ZOOM, 1)  # Minimize zoom for widest FOV
        except Exception:
            pass  # Camera may not support zoom control
            
        if not cap.isOpened():
            error_msg = f"Could not open camera at index {self._settings.camera_index}."
            logger.warning("%s Detection loop exiting.", error_msg)
            self.pause()
            if self._on_error_callback:
                try:
                    self._on_error_callback(error_msg)
                except Exception:
                    logger.exception("Error callback raised an exception.")
            return

        logger.info("Camera %d opened. Monitoring started.", self._settings.camera_index)

        try:
            while not self._stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    error_msg = f"Failed to read frame from camera {self._settings.camera_index}."
                    logger.warning(error_msg)
                    # Auto-pause on camera error (T007)
                    self.pause()
                    # Notify error callback if registered
                    if self._on_error_callback:
                        try:
                            self._on_error_callback(error_msg)
                        except Exception:  # pragma: no cover
                            logger.exception("Error callback raised an exception.")
                    break  # Exit detection loop

                # Store the latest frame for remote access (e.g., photo capture)
                with self._frame_lock:
                    self._latest_frame = frame.copy()

                # Pull current threshold from shared settings (live updates for free)
                conf = self._settings.confidence_threshold

                # --- Verification trigger (T006/T022) ----------------------------
                # Before running inference: if a pending frame is held and the
                # cooldown has elapsed, fire the verification callback with the
                # current live frame's inference results.
                # We run inference first below and store results; the trigger
                # check is done AFTER inference so we have the current boxes.

                # Run ONNX inference on the full frame (letterbox + normalize inside)
                blob = _preprocess_frame(frame, _INPUT_SIZE)
                raw_out = self._model.run(None, {self._model_input_name: blob})[0]
                all_boxes = _postprocess(raw_out, conf, CAT_CLASS_ID, frame.shape)
                max_conf = max((b.confidence for b in all_boxes), default=0.0)

                # Verification trigger: fires once per pending cycle on the first
                # post-cooldown frame.  Pending state is cleared BEFORE invoking
                # the callback to prevent re-entrance.
                if self._pending_frame is not None and self._cooldown_elapsed():
                    has_cat = len(all_boxes) > 0
                    cb = self._verification_callback
                    self._pending_frame = None  # clear before callback
                    logger.debug(
                        "Verification trigger fired: has_cat=%s, boxes=%d",
                        has_cat,
                        len(all_boxes),
                    )
                    if cb is not None:
                        try:
                            cb(has_cat, all_boxes)
                        except Exception:
                            logger.exception("Verification callback raised an exception.")

                # Emit exactly ONE event per frame (not one per box).
                if all_boxes:
                    now = datetime.now(timezone.utc)
                    if self._cooldown_elapsed():
                        self._last_alert_time = now
                        # Mandatory copy: cap.read() overwrites the buffer
                        # on the next iteration.
                        self._pending_frame = frame.copy()
                        event = DetectionEvent(
                            timestamp=now,
                            confidence=max_conf,
                            action=DetectionAction.SOUND_PLAYED,
                            frame_bgr=self._pending_frame,
                            boxes=all_boxes,
                        )
                        logger.info(
                            "Cat detected (conf=%.2f, %d box(es)) — ALERTING",
                            max_conf,
                            len(all_boxes),
                        )
                        self._on_cat_detected(event)
                    else:
                        event = DetectionEvent(
                            timestamp=now,
                            confidence=max_conf,
                            action=DetectionAction.COOLDOWN_SUPPRESSED,
                            boxes=all_boxes,
                        )
                        logger.debug(
                            "Cat detected (conf=%.2f) — COOLDOWN_SUPPRESSED",
                            max_conf,
                        )

                # Yield the CPU briefly between inferences so the process
                # doesn't pin a core at 100 %.  Using stop_event.wait means
                # the thread wakes up immediately when stop() is called.
                if self._stop_event.wait(timeout=0.05):
                    break

                # Deliver frame + results to optional UI callback (MainWindow).
                # Snapshot the callback reference atomically to avoid TOCTOU.
                with self._frame_callback_lock:
                    cb = self._frame_callback
                if cb is not None:
                    try:
                        cb(frame, all_boxes)
                    except Exception:  # pragma: no cover
                        logger.exception("Frame callback raised an exception.")
        finally:
            cap.release()
            logger.info("Camera %d released.", self._settings.camera_index)
