"""Audio playback for CatGuard alert sounds.

Responsibilities:
- init_audio(): pygame.mixer.init() ONLY (never pygame.init() — avoids display dep)
- play_random_alert(paths, default_path): random selection from valid MP3/WAV files;
  falls back to default_path when list is empty or all files are unsupported format
- shutdown_audio(): pygame.mixer.quit()
- _play_async(path): non-blocking background thread playback

NOTE: pygame.mixer uses the OS audio session, which is NOT suspended when the
screen is locked — meeting FR9 (locked-screen monitoring).
"""
from __future__ import annotations

import logging
import random
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_SUPPORTED_FORMATS = frozenset({".mp3", ".wav"})


def init_audio() -> None:
    """Initialise pygame mixer only (never calls pygame.init())."""
    import pygame.mixer

    pygame.mixer.init()
    logger.info("pygame.mixer initialised.")


def shutdown_audio() -> None:
    """Shut down pygame mixer cleanly."""
    import pygame.mixer

    pygame.mixer.quit()
    logger.info("pygame.mixer shut down.")


def play_random_alert(paths: list[str], default_path: Path) -> None:
    """Select a random supported audio file from *paths* and play it.

    Falls back to *default_path* when:
    - *paths* is empty, or
    - all entries in *paths* have unsupported file extensions.

    Skips unsupported formats with a logged warning.
    """
    valid = [p for p in paths if Path(p).suffix.lower() in _SUPPORTED_FORMATS]
    skipped = len(paths) - len(valid)
    if skipped:
        logger.warning(
            "Skipped %d unsupported audio file(s) in sound library.", skipped
        )

    if valid:
        chosen = random.choice(valid)
        logger.info("Playing alert sound: %s", chosen)
        _play_async(chosen)
    else:
        logger.info("No valid library sounds — playing default: %s", default_path)
        _play_async(str(default_path))


def _play_async(path: str) -> None:
    """Play *path* in a daemon background thread (non-blocking)."""

    def _worker() -> None:
        try:
            import time

            import pygame.mixer

            sound = pygame.mixer.Sound(path)
            sound.play()
            while pygame.mixer.get_busy():
                time.sleep(0.05)
        except Exception as exc:
            logger.error("Playback error for %s: %s", path, exc)

    threading.Thread(target=_worker, name="AudioPlayback", daemon=True).start()
