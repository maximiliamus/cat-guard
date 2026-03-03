"""Cat detection module using YOLO11n.

Responsibilities:
- DetectionLoop: background daemon thread running YOLO inference on webcam frames
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
MODEL_NAME = "yolo11n.pt"


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
        self._frame_callback: Optional[Callable] = None
        self._frame_callback_lock = threading.Lock()
        self._pending_frame: Optional["np.ndarray"] = None
        """Deep copy of detection frame held until verification fires.

        ``None`` when no verification is pending.  Acts as the sole
        pending-state sentinel (YAGNI: detection-time boxes and sound label
        are owned by EffectivenessTracker, not this loop).
        """
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

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Lazy-load the YOLO model (runs once inside the daemon thread).
        
        Cached in memory across pause/resume cycles for efficiency.
        """
        if self._model is not None:
            return  # Model already loaded, reuse it
        
        from ultralytics import YOLO

        self._model = YOLO(MODEL_NAME)
        logger.info("YOLO model loaded: %s", MODEL_NAME)

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

        self._load_model()

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
            logger.warning(
                "Could not open camera at index %d. Detection loop exiting.",
                self._settings.camera_index,
            )
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

                # Pull current threshold from shared settings (live updates for free)
                conf = self._settings.confidence_threshold

                # --- Verification trigger (T006/T022) ----------------------------
                # Before running inference: if a pending frame is held and the
                # cooldown has elapsed, fire the verification callback with the
                # current live frame's inference results.
                # We run inference first below and store results; the trigger
                # check is done AFTER inference so we have the current boxes.

                # Resize frame for faster inference (480p) but keep original for display
                try:
                    h, w = frame.shape[:2]
                except (AttributeError, ValueError):
                    # Mock frame or invalid shape in tests
                    h, w = 480, 640
                    
                if h > 0 and w > 0:
                    scale = min(480.0 / h, 640.0 / w)
                else:
                    scale = 1.0
                    
                if scale < 1.0:
                    small_frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
                else:
                    small_frame = frame
                    scale = 1.0  # No scaling needed

                results = self._model.predict(
                    small_frame,
                    conf=conf,
                    classes=[CAT_CLASS_ID],
                    device="cpu",
                    imgsz=640,
                    verbose=False,
                )

                # Collect all bounding boxes from this frame's results.
                # Scale boxes back to original frame size if we resized
                all_boxes: list[BoundingBox] = []
                max_conf = 0.0
                for result in results:
                    raw_boxes = result.boxes
                    if raw_boxes is None or len(raw_boxes) == 0:
                        continue
                    names: dict = getattr(result, "names", {})
                    for box in raw_boxes:
                        _conf = float(box.conf[0])
                        _cls = int(box.cls[0])
                        _label = names.get(_cls, str(_cls))
                        # Scale coordinates back to original frame size
                        if scale < 1.0:
                            x1 = max(0, min(int(box.xyxy[0][0] / scale), w - 1))
                            y1 = max(0, min(int(box.xyxy[0][1] / scale), h - 1))
                            x2 = max(0, min(int(box.xyxy[0][2] / scale), w - 1))
                            y2 = max(0, min(int(box.xyxy[0][3] / scale), h - 1))
                        else:
                            x1 = max(0, min(int(box.xyxy[0][0]), w - 1))
                            y1 = max(0, min(int(box.xyxy[0][1]), h - 1))
                            x2 = max(0, min(int(box.xyxy[0][2]), w - 1))
                            y2 = max(0, min(int(box.xyxy[0][3]), h - 1))
                        all_boxes.append(
                            BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=_conf, label=_label)
                        )
                        max_conf = max(max_conf, _conf)

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
                        cb(frame, results)
                    except Exception:  # pragma: no cover
                        logger.exception("Frame callback raised an exception.")
        finally:
            cap.release()
            logger.info("Camera %d released.", self._settings.camera_index)
