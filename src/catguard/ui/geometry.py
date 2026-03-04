"""Window geometry persistence for CatGuard.

Stores per-window position/size strings in:
  %APPDATA%/CatGuard/windows.json  (Windows)
  ~/.local/share/CatGuard/windows.json  (Linux/macOS)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from platformdirs import user_data_dir

logger = logging.getLogger(__name__)

_GEOMETRY_FILE = Path(user_data_dir("CatGuard")) / "windows.json"


def load_win_geometry(key: str) -> str:
    """Return saved geometry string for *key*, or empty string on any error."""
    try:
        data = json.loads(_GEOMETRY_FILE.read_text(encoding="utf-8"))
        return data.get(key, "")
    except Exception:
        return ""


def save_win_geometry(key: str, value: str) -> None:
    """Persist *value* geometry string for *key* to disk."""
    try:
        try:
            data = json.loads(_GEOMETRY_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        data[key] = value
        _GEOMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _GEOMETRY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to save window geometry for '%s': %s", key, exc)
