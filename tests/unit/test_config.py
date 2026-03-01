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
# T003: New screenshot-related Settings fields
# ---------------------------------------------------------------------------

class TestScreenshotSettingsDefaults:
    """T003 — four new Settings fields with correct defaults (TDD RED before T005)."""

    def test_screenshots_root_folder_default_is_empty_string(self):
        s = Settings()
        assert s.screenshots_root_folder == ""

    def test_screenshot_window_enabled_default_is_false(self):
        s = Settings()
        assert s.screenshot_window_enabled is False

    def test_screenshot_window_start_default(self):
        s = Settings()
        assert s.screenshot_window_start == "22:00"

    def test_screenshot_window_end_default(self):
        s = Settings()
        assert s.screenshot_window_end == "06:00"


class TestScreenshotSettingsAssignment:
    """T003 — new fields accept valid values and persist through save/load."""

    def test_screenshots_root_folder_accepts_path_string(self):
        s = Settings(screenshots_root_folder="/some/path")
        assert s.screenshots_root_folder == "/some/path"

    def test_screenshot_window_enabled_can_be_set_true(self):
        s = Settings(screenshot_window_enabled=True)
        assert s.screenshot_window_enabled is True

    def test_screenshot_window_start_accepts_valid_hhmm(self):
        s = Settings(screenshot_window_start="08:30")
        assert s.screenshot_window_start == "08:30"

    def test_screenshot_window_end_accepts_valid_hhmm(self):
        s = Settings(screenshot_window_end="23:59")
        assert s.screenshot_window_end == "23:59"

    def test_invalid_window_start_resets_to_default(self):
        """Malformed HH:MM resets to the default value."""
        s = Settings(screenshot_window_start="not-a-time")
        assert s.screenshot_window_start == "22:00"

    def test_invalid_window_end_resets_to_default(self):
        s = Settings(screenshot_window_end="99:99")
        assert s.screenshot_window_end == "06:00"


class TestScreenshotSettingsRoundTrip:
    """T003 — new fields survive a save → load round-trip."""

    def test_screenshot_fields_round_trip(self, tmp_path):
        config_file = tmp_path / "settings.json"
        original = Settings(
            screenshots_root_folder="/tmp/cats",
            screenshot_window_enabled=True,
            screenshot_window_start="21:00",
            screenshot_window_end="07:00",
        )
        with patch("catguard.config._config_file", return_value=config_file):
            save_settings(original)
            loaded = load_settings()
        assert loaded.screenshots_root_folder == "/tmp/cats"
        assert loaded.screenshot_window_enabled is True
        assert loaded.screenshot_window_start == "21:00"
        assert loaded.screenshot_window_end == "07:00"

    def test_legacy_settings_without_screenshot_fields_load_with_defaults(self, tmp_path):
        """Existing settings.json without new fields loads without error."""
        config_file = tmp_path / "settings.json"
        legacy_data = {"camera_index": 1, "cooldown_seconds": 10.0}
        config_file.write_text(json.dumps(legacy_data), encoding="utf-8")
        with patch("catguard.config._config_file", return_value=config_file):
            loaded = load_settings()
        assert loaded.camera_index == 1
        assert loaded.screenshots_root_folder == ""
        assert loaded.screenshot_window_enabled is False


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
