"""Tracking videoclip path reservation and streamed writing helpers."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrackingClipPaths:
    """Final and temporary clip paths reserved for one session."""

    final_path: Path
    temp_path: Path


# Maps the user-facing format name to (fourcc_str, file_extension).
_FORMAT_MAP: dict[str, tuple[str, str]] = {
    "MJPG": ("MJPG", ".avi"),
    "XVID": ("XVID", ".avi"),
    "MP4V": ("mp4v", ".mp4"),
}
_DEFAULT_FORMAT = "MJPG"


def _normalise_format(fmt: object) -> str:
    """Return a supported format key, falling back to the portable default."""
    if isinstance(fmt, str):
        normalized = fmt.strip().upper()
        if normalized in _FORMAT_MAP:
            return normalized
    return _DEFAULT_FORMAT


def reserve_tracking_clip_paths(
    root: Path, session_ts: datetime, fmt: str = _DEFAULT_FORMAT
) -> TrackingClipPaths:
    """Reserve collision-safe temp/final clip paths for one session."""
    _, ext = _FORMAT_MAP[_normalise_format(fmt)]
    date_dir = root / session_ts.strftime("%Y-%m-%d")
    stem = session_ts.strftime("%Y%m%d-%H%M%S")

    counter = 0
    while True:
        suffix = "" if counter == 0 else f"-{counter:02d}"
        final_path = date_dir / f"{stem}{suffix}{ext}"
        temp_path = date_dir / f"{stem}{suffix}.partial{ext}"
        if not final_path.exists() and not temp_path.exists():
            logger.info(
                "event=tracking_clip_reserved final=%s temp=%s",
                final_path,
                temp_path,
            )
            return TrackingClipPaths(final_path=final_path, temp_path=temp_path)
        counter += 1


class TrackingClipWriter:
    """Write session frames into a temporary video file and finalize it later."""

    def __init__(self, paths: TrackingClipPaths, fps: int, fmt: str = _DEFAULT_FORMAT) -> None:
        self.paths = paths
        self.fps = max(1, int(fps))
        self.fmt = _normalise_format(fmt)
        self._writer: cv2.VideoWriter | None = None
        self._output_size: tuple[int, int] | None = None
        self._frames_written = 0
        self._write_lock = threading.Lock()
        self._closed = False
        self._finalized_path: Path | None = None

    @property
    def frames_written(self) -> int:
        return self._frames_written

    def write_frame(self, frame_bgr: np.ndarray) -> bool:
        """Write one frame, opening the writer lazily from the first frame."""
        with self._write_lock:
            if self._closed:
                logger.warning(
                    "event=tracking_clip_write_after_close path=%s",
                    self.paths.temp_path,
                )
                return False
            try:
                frame_to_write = frame_bgr
                if self._writer is None:
                    frame_h, frame_w = frame_bgr.shape[:2]
                    self._output_size = (frame_w, frame_h)
                    if not self._open_writer():
                        return False
                elif self._output_size is not None:
                    frame_to_write = self._normalise_frame(frame_bgr, self._output_size)

                assert self._writer is not None  # for type checkers
                self._writer.write(frame_to_write)
                self._frames_written += 1
                logger.debug(
                    "event=tracking_clip_frame_written path=%s frames_written=%d",
                    self.paths.temp_path,
                    self._frames_written,
                )
                return True
            except Exception:
                logger.exception(
                    "event=tracking_clip_write_failed path=%s",
                    self.paths.temp_path,
                )
                self._closed = True
                self._release_writer()
                return False

    def finalize(self, deadline_monotonic: float | None = None) -> Path | None:
        """Release the writer and promote the temp file into the final clip path."""
        if deadline_monotonic is None:
            acquired = self._write_lock.acquire()
        else:
            acquired = self._write_lock.acquire(
                timeout=max(0.0, deadline_monotonic - time.monotonic())
            )
        if not acquired:
            logger.error(
                "event=tracking_clip_finalize_lock_timeout temp=%s",
                self.paths.temp_path,
            )
            return None

        try:
            if self._finalized_path is not None:
                return self._finalized_path

            start = time.monotonic()
            self._closed = True
            self._release_writer()

            if self._frames_written == 0:
                self._remove_temp_file()
                logger.info(
                    "event=tracking_clip_finalize_empty temp=%s",
                    self.paths.temp_path,
                )
                return None

            if not self._is_readable_video(self.paths.temp_path):
                self._remove_temp_file()
                logger.warning(
                    "event=tracking_clip_finalize_unreadable temp=%s",
                    self.paths.temp_path,
                )
                return None

            try:
                self.paths.final_path.parent.mkdir(parents=True, exist_ok=True)
                result = self.paths.temp_path.replace(self.paths.final_path)
                logger.info(
                    "event=tracking_clip_finalized final=%s elapsed=%.3fs",
                    result,
                    time.monotonic() - start,
                )
                self._finalized_path = result
                return result
            except Exception:
                logger.exception(
                    "event=tracking_clip_finalize_rename_failed temp=%s final=%s",
                    self.paths.temp_path,
                    self.paths.final_path,
                )
                if self._is_readable_video(self.paths.temp_path):
                    self._finalized_path = self.paths.temp_path
                    return self.paths.temp_path
                self._remove_temp_file()
                return None
            finally:
                if deadline_monotonic is not None and time.monotonic() > deadline_monotonic:
                    logger.warning(
                        "event=tracking_clip_finalize_deadline_exceeded temp=%s deadline=%.3f",
                        self.paths.temp_path,
                        deadline_monotonic,
                    )
        finally:
            self._write_lock.release()

    def _open_writer(self) -> bool:
        assert self._output_size is not None
        self.paths.temp_path.parent.mkdir(parents=True, exist_ok=True)
        fourcc_str, _ = _FORMAT_MAP.get(self.fmt, _FORMAT_MAP[_DEFAULT_FORMAT])
        fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
        self._writer = cv2.VideoWriter(
            str(self.paths.temp_path),
            fourcc,
            float(self.fps),
            self._output_size,
        )
        if not self._writer.isOpened():
            self._release_writer()
            logger.error(
                "event=tracking_clip_open_failed temp=%s fps=%s size=%s",
                self.paths.temp_path,
                self.fps,
                self._output_size,
            )
            return False
        logger.info(
            "event=tracking_clip_opened temp=%s fps=%s size=%s",
            self.paths.temp_path,
            self.fps,
            self._output_size,
        )
        return True

    def _remove_temp_file(self) -> None:
        try:
            self.paths.temp_path.unlink(missing_ok=True)
        except OSError:
            logger.exception(
                "event=tracking_clip_temp_remove_failed temp=%s",
                self.paths.temp_path,
            )

    def _release_writer(self) -> None:
        if self._writer is None:
            return
        try:
            self._writer.release()
        finally:
            self._writer = None

    @staticmethod
    def _normalise_frame(
        frame_bgr: np.ndarray,
        output_size: tuple[int, int],
    ) -> np.ndarray:
        """Resize with aspect-preserving letterboxing into the locked writer size."""
        out_w, out_h = output_size
        frame_h, frame_w = frame_bgr.shape[:2]
        if (frame_w, frame_h) == output_size:
            return frame_bgr

        scale = min(out_w / frame_w, out_h / frame_h)
        new_w = max(1, int(round(frame_w * scale)))
        new_h = max(1, int(round(frame_h * scale)))
        resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.zeros((out_h, out_w, 3), dtype=frame_bgr.dtype)
        top = (out_h - new_h) // 2
        left = (out_w - new_w) // 2
        canvas[top : top + new_h, left : left + new_w] = resized
        return canvas

    @staticmethod
    def _is_readable_video(path: Path) -> bool:
        try:
            if not path.exists() or path.stat().st_size == 0:
                return False
            cap = cv2.VideoCapture(str(path))
        except (OSError, cv2.error):
            logger.exception("event=tracking_clip_readability_check_failed path=%s", path)
            return False
        try:
            if not cap.isOpened():
                return False
            ok, _frame = cap.read()
            return bool(ok)
        except cv2.error:
            logger.exception("event=tracking_clip_readability_check_failed path=%s", path)
            return False
        finally:
            cap.release()
