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
import re
from pathlib import Path
from typing import List

from platformdirs import user_config_dir, user_pictures_dir
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(user_config_dir("CatGuard"))
_CONFIG_FILE = _CONFIG_DIR / "settings.json"


def _default_tracking_directory() -> str:
    """Return the default tracking directory path."""
    return str(Path(user_pictures_dir()) / "CatGuard" / "tracking")


def _default_photos_directory() -> str:
    """Return the default photos directory path."""
    return str(Path(user_pictures_dir()) / "CatGuard" / "photos")


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
        default=0.25,
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
    use_default_sound: bool = Field(
        default=True,
        description=(
            "When True, the built-in default sound plays on every detection event, "
            "regardless of sound_library_paths and pinned_sound."
        ),
    )
    pinned_sound: str = Field(
        default="",
        description=(
            "Absolute path to the specific library sound to always play. "
            "Empty string means random selection from sound_library_paths."
        ),
    )
    tracking_window_enabled: bool = Field(
        default=False,
        description=(
            "When True, the camera is active only during the window defined by "
            "tracking_window_start and tracking_window_end. "
            "When False, the camera runs continuously (existing behavior)."
        ),
    )
    tracking_window_start: str = Field(
        default="08:00",
        description="Start of the daily active monitoring period (HH:MM, local 24-hour time).",
    )
    tracking_window_end: str = Field(
        default="18:00",
        description=(
            "End of the daily active monitoring period (HH:MM, local 24-hour time). "
            "May precede start to span midnight (e.g. '22:00' → '06:00')."
        ),
    )
    photos_directory: str = Field(
        default_factory=_default_photos_directory,
        description="Directory where captured photos are saved (date-organised into YYYY-MM-DD subfolders). Defaults to system Pictures directory.",
    )
    tracking_directory: str = Field(
        default_factory=_default_tracking_directory,
        description="Directory where tracking screenshots are saved. Defaults to system Pictures directory.",
    )
    photo_image_format: str = Field(
        default="jpg",
        description="Image format for saved photos (currently 'jpg' only; future: 'png', 'webp').",
    )
    photo_image_quality: int = Field(
        default=95,
        ge=1,
        le=100,
        description="JPEG quality for saved photos (1–100, where 100 is best fidelity).",
    )
    tracking_image_quality: int = Field(
        default=90,
        ge=1,
        le=100,
        description="JPEG quality for tracking/detection screenshots (1–100).",
    )
    photo_countdown_seconds: int = Field(
        default=3,
        gt=0,
        description="Countdown duration (in seconds) for 'Take photo with delay' button.",
    )

    @field_validator("photos_directory")
    @classmethod
    def validate_photos_directory(cls, path: str) -> str:
        """Reject paths containing '..' for security (NFR-SEC-001)."""
        if ".." in path:
            raise ValueError(f"photos_directory must not contain '..' (got {path!r})")
        return path

    @field_validator("tracking_directory")
    @classmethod
    def validate_tracking_directory(cls, path: str) -> str:
        """Reject paths containing '..' for security (NFR-SEC-001)."""
        if ".." in path:
            raise ValueError(f"tracking_directory must not contain '..' (got {path!r})")
        return path

    @field_validator("pinned_sound")
    @classmethod
    def reset_stale_pinned_sound(cls, path: str) -> str:
        """Silently reset pinned_sound to '' if the file no longer exists."""
        if path and not Path(path).is_file():
            logger.warning(
                "pinned_sound path no longer exists (%r) — resetting to empty.",
                path,
            )
            return ""
        return path

    @field_validator("sound_library_paths")
    @classmethod
    def prune_stale_paths(cls, paths: List[str]) -> List[str]:
        """Silently drop paths that no longer exist on disk."""
        return [p for p in paths if Path(p).is_file()]

    @field_validator("tracking_window_start", mode="before")
    @classmethod
    def validate_tracking_window_start(cls, value: object) -> str:
        """Accept HH:MM strings; reset invalid values to '08:00'."""
        _HHMM_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
        if isinstance(value, str) and _HHMM_RE.match(value):
            return value
        logger.warning(
            "Invalid HH:MM value for tracking_window_start (%r) — resetting to '08:00'.",
            value,
        )
        return "08:00"

    @field_validator("tracking_window_end", mode="before")
    @classmethod
    def validate_tracking_window_end(cls, value: object) -> str:
        """Accept HH:MM strings; reset invalid values to '18:00'."""
        _HHMM_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
        if isinstance(value, str) and _HHMM_RE.match(value):
            return value
        logger.warning(
            "Invalid HH:MM value for tracking_window_end (%r) — resetting to '18:00'.",
            value,
        )
        return "18:00"


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
