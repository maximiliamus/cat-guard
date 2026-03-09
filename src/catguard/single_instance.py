"""Single-instance guard — ensures only one CatGuard process runs at a time.

Usage::

    from catguard.single_instance import ensure_single_instance
    ensure_single_instance()   # exits with code 1 if another instance is running
"""
from __future__ import annotations

import logging
import platform
import sys

logger = logging.getLogger(__name__)

_MUTEX_NAME = "Global\\CatGuard_SingleInstance"
_LOCK_FILE_NAME = "catguard.lock"

# Module-level handles kept alive for the process lifetime.
_win_mutex = None
_lock_file = None


def ensure_single_instance() -> None:
    """Exit the process if another instance of CatGuard is already running."""
    if platform.system() == "Windows":
        _acquire_windows_mutex()
    else:
        _acquire_unix_lock()


# ---------------------------------------------------------------------------
# Windows — named mutex
# ---------------------------------------------------------------------------

def _acquire_windows_mutex() -> None:
    global _win_mutex
    import ctypes
    import ctypes.wintypes

    ERROR_ALREADY_EXISTS = 183

    _win_mutex = ctypes.windll.kernel32.CreateMutexW(None, True, _MUTEX_NAME)
    last_error = ctypes.windll.kernel32.GetLastError()

    if last_error == ERROR_ALREADY_EXISTS:
        logger.warning("Another CatGuard instance is already running. Exiting.")
        sys.exit(1)

    logger.debug("Single-instance mutex acquired.")


# ---------------------------------------------------------------------------
# Unix — lock file
# ---------------------------------------------------------------------------

def _acquire_unix_lock() -> None:
    global _lock_file
    import fcntl
    from pathlib import Path
    from platformdirs import user_data_dir

    lock_path = Path(user_data_dir("CatGuard")) / _LOCK_FILE_NAME
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    _lock_file = open(lock_path, "w")
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        _lock_file.close()
        logger.warning("Another CatGuard instance is already running. Exiting.")
        sys.exit(1)

    logger.debug("Single-instance lock file acquired: %s", lock_path)
