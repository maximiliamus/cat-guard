"""Unit tests for catguard.config — written before implementation (TDD RED)."""
from __future__ import annotations

import json
import logging

import pytest
from pathlib import Path
from unittest.mock import patch

from catguard.config import Settings, load_settings, save_settings


class TestSettingsDefaults:
    def test_default_camera_index(self):
        s = Settings()
        assert s.camera_index == 0

    def test_default_confidence_threshold(self):
        s = Settings()
        assert s.confidence_threshold == 0.25

    def test_default_cooldown_seconds(self):
        s = Settings()
        assert s.cooldown_seconds == 15.0

    def test_default_sound_library_paths(self):
        s = Settings()
        assert s.sound_library_paths == []

    def test_default_autostart(self):
        s = Settings()
        assert s.autostart is False


class TestSettingsValidation:
    def test_camera_index_negative_rejected(self):
        with pytest.raises(Exception):
            Settings(camera_index=-1)

    def test_confidence_threshold_above_one_rejected(self):
        with pytest.raises(Exception):
            Settings(confidence_threshold=1.5)

    def test_confidence_threshold_below_zero_rejected(self):
        with pytest.raises(Exception):
            Settings(confidence_threshold=-0.1)

    def test_cooldown_zero_rejected(self):
        with pytest.raises(Exception):
            Settings(cooldown_seconds=0)

    def test_cooldown_negative_rejected(self):
        with pytest.raises(Exception):
            Settings(cooldown_seconds=-5)

    def test_stale_sound_paths_pruned(self):
        s = Settings(sound_library_paths=["/nonexistent/path/sound.wav"])
        assert s.sound_library_paths == []

    def test_existing_sound_path_kept(self, tmp_path):
        wav = tmp_path / "sound.wav"
        wav.write_bytes(b"\x00" * 44)
        s = Settings(sound_library_paths=[str(wav)])
        assert str(wav) in s.sound_library_paths


class TestLoadSettings:
    def test_creates_defaults_on_missing_file(self, tmp_path):
        config_file = tmp_path / "settings.json"
        with patch("catguard.config._config_file", return_value=config_file):
            s = load_settings()
        assert s.camera_index == 0
        assert config_file.exists()

    def test_missing_key_falls_back_to_default(self, tmp_path):
        config_file = tmp_path / "settings.json"
        config_file.write_text(json.dumps({"camera_index": 3}), encoding="utf-8")
        with patch("catguard.config._config_file", return_value=config_file):
            s = load_settings()
        assert s.camera_index == 3
        assert s.cooldown_seconds == 15.0

    def test_corrupt_file_resets_to_defaults(self, tmp_path, caplog):
        config_file = tmp_path / "settings.json"
        config_file.write_text("this is not json {{ bad", encoding="utf-8")
        with patch("catguard.config._config_file", return_value=config_file):
            with caplog.at_level(logging.WARNING, logger="catguard.config"):
                s = load_settings()
        assert s.camera_index == 0
        assert "corrupt" in caplog.text.lower()

    def test_logs_on_first_run(self, tmp_path, caplog):
        config_file = tmp_path / "settings.json"
        with patch("catguard.config._config_file", return_value=config_file):
            with caplog.at_level(logging.INFO, logger="catguard.config"):
                load_settings()
        assert any(
            word in caplog.text.lower()
            for word in ("default", "writing", "not found", "first")
        )


# ---------------------------------------------------------------------------
# T003: New tracking-related Settings fields
# ---------------------------------------------------------------------------

class TestTrackingSettingsDefaults:
    """T003 — tracking_directory with correct default (TDD RED before T005)."""

    def test_tracking_directory_default_is_correct(self):
        s = Settings()
        # Default should be in user's Pictures directory under CatGuard/tracking
        assert "CatGuard" in s.tracking_directory
        assert "tracking" in s.tracking_directory
        assert s.tracking_directory.endswith("tracking") or s.tracking_directory.endswith("tracking/")


class TestTrackingSettingsAssignment:
    """T003 — tracking_directory accepts valid values and persists through save/load."""

    def test_tracking_directory_accepts_path_string(self):
        s = Settings(tracking_directory="/some/path")
        assert s.tracking_directory == "/some/path"


class TestTrackingSettingsRoundTrip:
    """T003 — tracking_directory survives a save → load round-trip."""

    def test_tracking_directory_round_trip(self, tmp_path):
        config_file = tmp_path / "settings.json"
        original = Settings(
            tracking_directory="/tmp/cats",
        )
        with patch("catguard.config._config_file", return_value=config_file):
            save_settings(original)
            loaded = load_settings()
        assert loaded.tracking_directory == "/tmp/cats"

    def test_legacy_settings_without_tracking_directory_load_with_defaults(self, tmp_path):
        """Existing settings.json without new fields loads without error."""
        config_file = tmp_path / "settings.json"
        legacy_data = {"camera_index": 1, "cooldown_seconds": 10.0}
        config_file.write_text(json.dumps(legacy_data), encoding="utf-8")
        with patch("catguard.config._config_file", return_value=config_file):
            loaded = load_settings()
        assert loaded.camera_index == 1
        # Should load with default that includes CatGuard/tracking
        assert "CatGuard" in loaded.tracking_directory
        assert "tracking" in loaded.tracking_directory


class TestSaveSettings:
    def test_save_then_load_round_trip(self, tmp_path):
        config_file = tmp_path / "settings.json"
        with patch("catguard.config._config_file", return_value=config_file):
            original = Settings(camera_index=2, cooldown_seconds=30.0, autostart=True)
            save_settings(original)
            loaded = load_settings()
        assert loaded.camera_index == 2
        assert loaded.cooldown_seconds == 30.0
        assert loaded.autostart is True

    def test_atomic_write_no_tmp_file_after_save(self, tmp_path):
        config_file = tmp_path / "settings.json"
        with patch("catguard.config._config_file", return_value=config_file):
            save_settings(Settings())
        assert config_file.exists()
        assert not config_file.with_suffix(".tmp").exists()

    def test_save_creates_parent_dirs(self, tmp_path):
        config_file = tmp_path / "deep" / "nested" / "settings.json"
        with patch("catguard.config._config_file", return_value=config_file):
            save_settings(Settings())
        assert config_file.exists()


# ---------------------------------------------------------------------------
# T003: New audio playback Settings fields (use_default_sound, pinned_sound)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# T004: New photo-related Settings fields (Phase 2, T004)
# ---------------------------------------------------------------------------

class TestPhotoSettingsDefaults:
    def test_photos_directory_default(self):
        s = Settings()
        # Default should be in user's Pictures directory under CatGuard/photos
        assert "CatGuard" in s.photos_directory
        assert "photos" in s.photos_directory
        assert s.photos_directory.endswith("photos") or s.photos_directory.endswith("photos/")

    def test_tracking_directory_default(self):
        s = Settings()
        # Default should be in user's Pictures directory under CatGuard/tracking
        assert "CatGuard" in s.tracking_directory
        assert "tracking" in s.tracking_directory
        assert s.tracking_directory.endswith("tracking") or s.tracking_directory.endswith("tracking/")

    def test_photo_image_format_default(self):
        s = Settings()
        assert s.photo_image_format == "jpg"

    def test_photo_image_quality_default(self):
        s = Settings()
        assert s.photo_image_quality == 95

    def test_tracking_image_quality_default(self):
        s = Settings()
        assert s.tracking_image_quality == 90

    def test_photo_countdown_seconds_default(self):
        s = Settings()
        assert s.photo_countdown_seconds == 3

class TestPhotoSettingsValidation:
    def test_photo_image_quality_out_of_range(self):
        with pytest.raises(Exception):
            Settings(photo_image_quality=0)
        with pytest.raises(Exception):
            Settings(photo_image_quality=101)

    def test_tracking_image_quality_out_of_range(self):
        with pytest.raises(Exception):
            Settings(tracking_image_quality=0)
        with pytest.raises(Exception):
            Settings(tracking_image_quality=101)

    def test_photos_directory_rejects_dotdot(self):
        with pytest.raises(Exception):
            Settings(photos_directory="../badpath/photos")

class TestAudioSettingsDefaults:
    """T003 — new audio fields have correct defaults."""

    def test_use_default_sound_default_is_true(self):
        s = Settings()
        assert s.use_default_sound is True

    def test_pinned_sound_default_is_empty_string(self):
        s = Settings()
        assert s.pinned_sound == ""


class TestAudioSettingsAssignment:
    """T003 — new audio fields accept valid values."""

    def test_use_default_sound_can_be_set_false(self):
        s = Settings(use_default_sound=False)
        assert s.use_default_sound is False

    def test_pinned_sound_accepts_existing_path(self, tmp_path):
        wav = tmp_path / "alert.wav"
        wav.write_bytes(b"\x00" * 44)
        s = Settings(pinned_sound=str(wav))
        assert s.pinned_sound == str(wav)

    def test_stale_pinned_sound_reset_to_empty(self):
        """pinned_sound validator resets stale path to '' (like prune_stale_paths)."""
        s = Settings(pinned_sound="/nonexistent/path/sound.wav")
        assert s.pinned_sound == ""

    def test_empty_pinned_sound_stays_empty(self):
        s = Settings(pinned_sound="")
        assert s.pinned_sound == ""


class TestAudioSettingsRoundTrip:
    """T003 — new audio fields survive a save → load round-trip."""

    def test_audio_fields_round_trip(self, tmp_path):
        config_file = tmp_path / "settings.json"
        wav = tmp_path / "alert.wav"
        wav.write_bytes(b"\x00" * 44)
        original = Settings(use_default_sound=False, pinned_sound=str(wav))
        with patch("catguard.config._config_file", return_value=config_file):
            save_settings(original)
            loaded = load_settings()
        assert loaded.use_default_sound is False
        assert loaded.pinned_sound == str(wav)

    def test_use_default_sound_true_round_trip(self, tmp_path):
        config_file = tmp_path / "settings.json"
        original = Settings(use_default_sound=True)
        with patch("catguard.config._config_file", return_value=config_file):
            save_settings(original)
            loaded = load_settings()
        assert loaded.use_default_sound is True

    def test_legacy_settings_without_audio_fields_load_with_defaults(self, tmp_path):
        """Existing settings.json without new audio fields loads without error."""
        config_file = tmp_path / "settings.json"
        legacy_data = {"camera_index": 1, "cooldown_seconds": 10.0}
        config_file.write_text(json.dumps(legacy_data), encoding="utf-8")
        with patch("catguard.config._config_file", return_value=config_file):
            loaded = load_settings()
        assert loaded.camera_index == 1
        assert loaded.use_default_sound is True
        assert loaded.pinned_sound == ""


# ---------------------------------------------------------------------------
# T004: tracking_window_* fields (007-misc-improvements)
# ---------------------------------------------------------------------------

class TestTrackingWindowDefaults:
    """T004 — new tracking window fields have correct defaults."""

    def test_tracking_window_enabled_default_false(self):
        s = Settings()
        assert s.tracking_window_enabled is False

    def test_tracking_window_start_default(self):
        s = Settings()
        assert s.tracking_window_start == "08:00"

    def test_tracking_window_end_default(self):
        s = Settings()
        assert s.tracking_window_end == "18:00"


class TestTrackingWindowValidation:
    """T004 — validators accept valid HH:MM and reset invalid values."""

    def test_valid_tracking_window_start_accepted(self):
        s = Settings(tracking_window_start="09:30")
        assert s.tracking_window_start == "09:30"

    def test_valid_tracking_window_end_accepted(self):
        s = Settings(tracking_window_end="23:59")
        assert s.tracking_window_end == "23:59"

    def test_invalid_tracking_window_start_reset_to_default(self):
        s = Settings(tracking_window_start="not-a-time")
        assert s.tracking_window_start == "08:00"

    def test_invalid_tracking_window_end_reset_to_default(self):
        s = Settings(tracking_window_end="99:99")
        assert s.tracking_window_end == "18:00"

    def test_midnight_spanning_window_valid(self):
        s = Settings(tracking_window_start="22:00", tracking_window_end="06:00")
        assert s.tracking_window_start == "22:00"
        assert s.tracking_window_end == "06:00"

    def test_tracking_window_enabled_true(self):
        s = Settings(tracking_window_enabled=True)
        assert s.tracking_window_enabled is True


class TestTrackingWindowBackwardCompatibility:
    """T004 — legacy settings files load cleanly with tracking_window defaults."""

    def test_legacy_file_without_tracking_window_fields(self, tmp_path):
        config_file = tmp_path / "settings.json"
        legacy_data = {"camera_index": 0, "cooldown_seconds": 15.0}
        config_file.write_text(json.dumps(legacy_data), encoding="utf-8")
        with patch("catguard.config._config_file", return_value=config_file):
            loaded = load_settings()
        assert loaded.tracking_window_enabled is False
        assert loaded.tracking_window_start == "08:00"
        assert loaded.tracking_window_end == "18:00"

    def test_tracking_window_round_trip(self, tmp_path):
        config_file = tmp_path / "settings.json"
        original = Settings(
            tracking_window_enabled=True,
            tracking_window_start="07:00",
            tracking_window_end="20:30",
        )
        with patch("catguard.config._config_file", return_value=config_file):
            save_settings(original)
            loaded = load_settings()
        assert loaded.tracking_window_enabled is True
        assert loaded.tracking_window_start == "07:00"
        assert loaded.tracking_window_end == "20:30"
