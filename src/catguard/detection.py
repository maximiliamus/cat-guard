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


class DetectionAction(Enum):
    """Outcome of a single detection event."""

    SOUND_PLAYED = "SOUND_PLAYED"
    """Alert triggered and a sound was played."""

    COOLDOWN_SUPPRESSED = "COOLDOWN_SUPPRESSED"
    """Cat detected but cooldown had not elapsed; no sound played."""


@dataclass
class DetectionEvent:
    """Immutable record of a single detection occurrence (in-memory only)."""

    timestamp: datetime
    confidence: float
    action: DetectionAction
    sound_file: Optional[str] = None


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

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Lazy-load the YOLO model (runs once inside the daemon thread)."""
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
                    logger.warning(
                        "Failed to read frame from camera %d.",
                        self._settings.camera_index,
                    )
                    # Brief pause before retrying to avoid a tight error loop
                    if self._stop_event.wait(timeout=0.5):
                        break
                    continue

                # Pull current threshold from shared settings (live updates for free)
                conf = self._settings.confidence_threshold

                results = self._model.predict(
                    frame,
                    conf=conf,
                    classes=[CAT_CLASS_ID],
                    device="cpu",
                    imgsz=640,  # 640px: needed to reliably detect cats further from the camera
                    verbose=False,
                )

                for result in results:
                    boxes = result.boxes
                    if boxes is None or len(boxes) == 0:
                        continue

                    for box in boxes:
                        confidence = float(box.conf[0])
                        now = datetime.now(timezone.utc)

                        if self._cooldown_elapsed():
                            self._last_alert_time = now
                            event = DetectionEvent(
                                timestamp=now,
                                confidence=confidence,
                                action=DetectionAction.SOUND_PLAYED,
                            )
                            logger.info(
                                "Cat detected (conf=%.2f) — ALERTING", confidence
                            )
                            self._on_cat_detected(event)
                        else:
                            event = DetectionEvent(
                                timestamp=now,
                                confidence=confidence,
                                action=DetectionAction.COOLDOWN_SUPPRESSED,
                            )
                            logger.debug(
                                "Cat detected (conf=%.2f) — COOLDOWN_SUPPRESSED",
                                confidence,
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
