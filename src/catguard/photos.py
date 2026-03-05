"""Photo capture and storage for CatGuard.

Responsibilities:
- Photo dataclass (in-memory representation)
- build_photo_filepath: generate collision-safe filenames for photos
- encode_photo: JPEG encoding with configurable quality
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import cv2  # noqa: F401 — imported here so tests can patch catguard.photos.cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Photo:
    """An in-memory photograph captured from the detection frame.

    Attributes:
        timestamp: datetime when the photo was captured (local system time).
        bytes: JPEG-encoded image bytes.
        source: indicator of where the photo came from (e.g., 'clean-capture').
    """

    timestamp: datetime
    bytes: bytes
    source: str = "clean-capture"


def build_photo_filepath(root: Path, ts: datetime, ext: str) -> Path:
    """Return a collision-safe JPEG file path for *ts* inside *root*.

    Structure: ``<root>/<yyyy-mm-dd>/<HH-MM-SS[-N]>.<ext>``

    If ``<HH-MM-SS>.<ext>`` already exists, a counter suffix is appended:
    ``<HH-MM-SS-1>.<ext>``, ``<HH-MM-SS-2>.<ext>``, … until an unused name is found.

    Args:
        root: Root directory for photos (typically `settings.photos_directory`).
        ts: Timestamp of the photo (local system time).
        ext: File extension, e.g., 'jpg' (without leading dot).

    Returns:
        A Path object for the collision-safe filename.
    """
    # Create date subfolder
    date_folder = root / ts.strftime("%Y-%m-%d")
    date_folder.mkdir(parents=True, exist_ok=True)

    # Base filename: HH-MM-SS
    base_name = ts.strftime("%H-%M-%S")
    file_ext = f".{ext}" if ext else ""

    # Check for collisions
    filepath = date_folder / f"{base_name}{file_ext}"
    if not filepath.exists():
        return filepath

    # Append collision suffix: -1, -2, ...
    counter = 1
    while True:
        collision_name = f"{base_name}-{counter}{file_ext}"
        filepath = date_folder / collision_name
        if not filepath.exists():
            return filepath
        counter += 1


def encode_photo(frame: "np.ndarray", quality: int) -> bytes:
    """Encode a single video frame to JPEG bytes.

    Args:
        frame: OpenCV frame in BGR format (H, W, 3).
        quality: JPEG quality (1–100, where 100 is best fidelity).

    Returns:
        JPEG-encoded bytes.

    Raises:
        ValueError: If quality is out of range or cv2.imencode fails.
    """
    if not (1 <= quality <= 100):
        raise ValueError(f"photo_image_quality must be 1–100, got {quality}")

    if cv2 is None:  # pragma: no cover
        raise RuntimeError("cv2 is not available; cannot encode photo.")

    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("cv2.imencode returned False — could not encode frame.")

    return buf.tobytes()
