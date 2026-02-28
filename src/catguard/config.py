"""Settings management for CatGuard.

Responsibilities:
- Settings pydantic model with all fields, validators, and defaults
- load_settings(): load from disk; write defaults on first run; reset on corruption
- save_settings(): atomic write via .tmp rename
- Structured logging for first-run and corrupt-file events
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from platformdirs import user_config_dir
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(user_config_dir("CatGuard"))
_CONFIG_FILE = _CONFIG_DIR / "settings.json"


def _config_file() -> Path:
    """Return the config file path (overridable in tests via patch)."""
    return _CONFIG_FILE


class Settings(BaseModel):
    """Persisted application settings.

    All fields include defaults so the app works out of the box.
    Writes are atomic to prevent corrupt state on crash.
    """

    model_config = ConfigDict(validate_assignment=True)

    camera_index: int = Field(
        default=0,
        ge=0,
        description="Index of the webcam to use (OpenCV VideoCapture index).",
    )
    confidence_threshold: float = Field(
        default=0.40,
        ge=0.0,
        le=1.0,
        description=(
            "YOLO detection confidence threshold. "
            "NOTE: inverse to 'sensitivity' — high sensitivity = low threshold "
            "(e.g. 0.20); low sensitivity = high threshold (e.g. 0.70)."
        ),
    )
    cooldown_seconds: float = Field(
        default=15.0,
        gt=0,
        description="Minimum seconds between consecutive alert sounds.",
    )
    sound_library_paths: List[str] = Field(
        default_factory=list,
        description="Absolute paths to user-uploaded MP3/WAV alert sounds.",
    )
    autostart: bool = Field(
        default=False,
        description="Whether the app starts automatically on user login.",
    )

    @field_validator("sound_library_paths")
    @classmethod
    def prune_stale_paths(cls, paths: List[str]) -> List[str]:
        """Silently drop paths that no longer exist on disk."""
        return [p for p in paths if Path(p).is_file()]


def load_settings() -> Settings:
    """Load settings from disk.

    - If the file is missing: write defaults and return them (first-run).
    - If a key is missing: merge with defaults so partial configs work.
    - If the file is corrupt: log a warning, reset to defaults.
    """
    config_file = _config_file()

    if not config_file.exists():
        logger.info(
            "Config file not found at %s — writing defaults on first run.", config_file
        )
        settings = Settings()
        save_settings(settings)
        return settings

    try:
        with config_file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        # Merge loaded data over defaults so missing keys get defaults
        defaults = Settings().model_dump()
        defaults.update(data)
        return Settings.model_validate(defaults)

    except (json.JSONDecodeError, ValueError, TypeError, OSError) as exc:
        logger.warning(
            "Config file is corrupt (%s) — resetting to defaults: %s",
            config_file,
            exc,
        )
        settings = Settings()
        save_settings(settings)
        return settings


def save_settings(settings: Settings) -> None:
    """Atomically write settings to disk via .tmp rename.

    Creates the parent directory if it does not exist.
    """
    config_file = _config_file()
    config_file.parent.mkdir(parents=True, exist_ok=True)

    tmp_file = config_file.with_suffix(".tmp")
    try:
        with tmp_file.open("w", encoding="utf-8") as fh:
            json.dump(settings.model_dump(), fh, indent=2)
        tmp_file.replace(config_file)
    except Exception:
        tmp_file.unlink(missing_ok=True)
        raise
