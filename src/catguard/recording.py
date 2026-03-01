"""Audio recording for CatGuard.

Responsibilities:
- Recorder: encapsulates a single microphone recording session (start/stop/10s cap)
- get_alerts_dir(): resolves the OS-specific alerts folder path
- save_recording(): writes a NumPy array to WAV in the alerts folder
- open_alerts_folder(): opens the alerts folder in the OS file manager
- sanitise_filename(): whitelist-based filename sanitisation + path-traversal guard
- is_silent(): zero-length / RMS silence detection

Recording thread model:
  sounddevice.rec(frames) runs on a daemon background thread.
  sounddevice.wait() blocks that thread until recording completes (cap or early stop).
  on_done is dispatched back to the tkinter main thread via root.after(0, callback).
"""
from __future__ import annotations

import logging
import os
import platform
import re
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from platformdirs import user_data_dir

logger = logging.getLogger(__name__)

_SAMPLERATE = 44_100       # Hz — fixed for all recordings
_MAX_SECONDS = 10          # automatic recording cap


def get_alerts_dir() -> Path:
    """Return the platform-specific alerts folder path.

    Windows : %APPDATA%\\CatGuard\\alerts
    Linux   : ~/.local/share/CatGuard/alerts
    macOS   : ~/Library/Application Support/CatGuard/alerts
    """
    return Path(user_data_dir("CatGuard")) / "alerts"


def sanitise_filename(raw: str) -> str:
    """Sanitise a user-supplied recording name into a safe WAV filename.

    - Whitelist: word characters, spaces, hyphens, dots
    - Spaces collapsed to underscores
    - Leading/trailing underscores and dots stripped
    - Path-traversal stripped via Path.name
    - Empty result falls back to 'recording'
    - Always appends '.wav'
    """
    name = re.sub(r"[^\w\s\-.]", "", raw, flags=re.UNICODE)
    name = re.sub(r"\s+", "_", name).strip("_.")
    name = Path(name).name          # strip any directory component / traversal
    return (name or "recording") + ".wav"


def is_silent(data: Optional[np.ndarray]) -> bool:
    """Return True if *data* is None, zero-length, or below the RMS silence threshold.

    Threshold: RMS < 100 on the int16 scale (32 767 peak).
    float32 cast prevents int16 overflow during squaring.
    """
    if data is None or len(data) == 0:
        return True
    rms = float(np.sqrt(np.mean(data.astype(np.float32) ** 2)))
    return rms < 100


def _apply_fade_out(data: np.ndarray) -> np.ndarray:
    """Apply a 20 ms linear fade-out to *data* in-place to prevent click/pop.

    Called after time-based trimming so the cut point ramps smoothly to silence.
    """
    if data is None or len(data) == 0:
        return data
    fade_frames = min(int(_SAMPLERATE * 0.020), len(data))
    if fade_frames <= 1:
        return data
    fade = np.linspace(1.0, 0.0, fade_frames, dtype=np.float32)
    if data.ndim == 2:
        data[-fade_frames:] = (data[-fade_frames:] * fade[:, np.newaxis]).astype(data.dtype)
    else:
        data[-fade_frames:] = (data[-fade_frames:] * fade).astype(data.dtype)
    return data


def save_recording(data: np.ndarray, name: str, alerts_dir: Optional[Path] = None) -> Path:
    """Write *data* as a WAV file named *name* in *alerts_dir*.

    - Creates the directory if it does not exist.
    - Returns the path of the saved file.
    - Raises OSError on disk-full / write errors (caller handles the dialog).
    """
    import soundfile as sf

    dest_dir = alerts_dir if alerts_dir is not None else get_alerts_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_name = sanitise_filename(name)
    dest_path = dest_dir / safe_name

    logger.info("Saving recording to %s (%d samples).", dest_path, len(data))
    try:
        sf.write(str(dest_path), data, _SAMPLERATE)
    except OSError as exc:
        logger.error("Failed to save recording to %s: %s", dest_path, exc)
        raise

    logger.info("Recording saved successfully: %s", dest_path)
    return dest_path


def open_alerts_folder(alerts_dir: Optional[Path] = None) -> None:
    """Open the alerts folder in the OS file manager.

    Creates the folder if it does not already exist.
    """
    folder = alerts_dir if alerts_dir is not None else get_alerts_dir()
    folder.mkdir(parents=True, exist_ok=True)

    system = platform.system()
    logger.info("Opening alerts folder: %s (platform=%s)", folder, system)
    if system == "Windows":
        os.startfile(str(folder))  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.run(["open", str(folder)], check=False)
    else:
        subprocess.run(["xdg-open", str(folder)], check=False)


class Recorder:
    """Encapsulates a single microphone recording session.

    Uses ``sounddevice.InputStream`` with a per-frame callback so that only
    frames actually delivered during the recording window are collected.
    This eliminates the zero-padded / pipeline-flush tail that ``sd.rec()``
    produces when recording is stopped early — no trimming heuristics needed.

    Usage::

        recorder = Recorder()
        recorder.start(on_done=lambda data: ...)
        # later, optionally:
        recorder.stop()

    *on_done(data: np.ndarray)* is called (from the thread that calls
    :meth:`stop`, or from the auto-cap timer thread) with the concatenated
    int16 frames.  The caller is responsible for dispatching to the UI
    thread via ``root.after(0, lambda: process(data))``.
    """

    def __init__(self) -> None:
        self._samplerate: int = _SAMPLERATE
        self._recording: bool = False
        self._lock = threading.Lock()
        self._stream = None
        self._chunks: list = []
        self._on_done: Optional[Callable] = None
        self._cap_timer: Optional[threading.Timer] = None

    @property
    def is_recording(self) -> bool:
        """True while capture is active."""
        with self._lock:
            return self._recording

    def start(self, on_done: Callable[[np.ndarray], None]) -> None:
        """Open an input stream and begin collecting frames.

        Raises ``sounddevice.PortAudioError`` if the microphone is
        unavailable (caller should catch and show an error dialog).
        Auto-stops after ``_MAX_SECONDS``.
        """
        import sounddevice as sd

        # Validate device configuration upfront; raises PortAudioError if broken.
        try:
            sd.check_input_settings(samplerate=self._samplerate, channels=1, dtype="int16")
        except Exception as exc:
            logger.error("Microphone not available: %s", exc)
            raise

        chunks: list[np.ndarray] = []

        def _callback(indata: np.ndarray, frames: int, time_info, status) -> None:
            if status:
                logger.warning("PortAudio stream status: %s", status)
            chunks.append(indata.copy())

        stream = sd.InputStream(
            samplerate=self._samplerate,
            channels=1,
            dtype="int16",
            callback=_callback,
        )

        with self._lock:
            self._chunks = chunks
            self._on_done = on_done
            self._stream = stream
            self._recording = True

        stream.start()
        logger.info(
            "Recording started @ %d Hz (max %d s).",
            self._samplerate,
            _MAX_SECONDS,
        )

        def _cap() -> None:
            logger.info("Recording auto-capped at %d s.", _MAX_SECONDS)
            self.stop()

        cap_timer = threading.Timer(_MAX_SECONDS, _cap)
        cap_timer.daemon = True
        cap_timer.start()
        with self._lock:
            self._cap_timer = cap_timer

    def stop(self) -> None:
        """Stop capture, close the stream, and call on_done with collected data.

        Safe to call from any thread.  Re-entrant calls are silently ignored.
        """
        with self._lock:
            if not self._recording:
                return
            self._recording = False
            stream = self._stream
            chunks = list(self._chunks)
            on_done = self._on_done
            cap_timer = self._cap_timer
            self._stream = None
            self._on_done = None
            self._cap_timer = None

        if cap_timer is not None:
            cap_timer.cancel()

        try:
            stream.stop()
            stream.close()
        except Exception as exc:
            logger.warning("Error closing recording stream: %s", exc)

        if chunks:
            data = _apply_fade_out(np.concatenate(chunks, axis=0))
        else:
            data = np.array([], dtype="int16")

        logger.info(
            "Recording stopped: %d frames (%.2f s).",
            len(data),
            len(data) / self._samplerate,
        )
        on_done(data)
