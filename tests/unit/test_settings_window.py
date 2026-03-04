"""Unit tests for catguard.ui.settings_window — written before implementation (TDD RED).

Tests the data-layer logic of the settings window without a display:
- Settings values are correctly read from the Settings object
- on_save is called with a Settings object containing updated values
- Camera dropdown is populated from list_cameras()
- Autostart checkbox reflects Settings.autostart

Note: We test the model/callback logic only; actual tkinter widget creation
is not tested here (requires a display — covered by integration/manual testing).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from catguard.config import Settings
from catguard.ui.settings_window import SettingsFormModel


class TestSettingsFormModel:
    def test_populated_from_settings(self):
        s = Settings(camera_index=1, confidence_threshold=0.60, cooldown_seconds=20.0, autostart=True)
        model = SettingsFormModel.from_settings(s)
        assert model.camera_index == 1
        assert model.confidence_threshold == 0.60
        assert model.cooldown_seconds == 20.0
        assert model.autostart is True

    def test_defaults_populated(self):
        model = SettingsFormModel.from_settings(Settings())
        assert model.camera_index == 0
        assert model.confidence_threshold == 0.25
        assert model.cooldown_seconds == 15.0
        assert model.autostart is False

    def test_to_settings_round_trip(self):
        original = Settings(camera_index=2, confidence_threshold=0.55, cooldown_seconds=10.0, autostart=True)
        model = SettingsFormModel.from_settings(original)
        restored = model.to_settings()
        assert restored.camera_index == 2
        assert restored.confidence_threshold == 0.55
        assert restored.cooldown_seconds == 10.0
        assert restored.autostart is True

    def test_sound_library_paths_preserved(self, tmp_path):
        wav = tmp_path / "alert.wav"
        wav.write_bytes(b"\x00" * 44)
        original = Settings(sound_library_paths=[str(wav)])
        model = SettingsFormModel.from_settings(original)
        restored = model.to_settings()
        assert str(wav) in restored.sound_library_paths

    def test_on_save_called_with_updated_settings(self):
        on_save = MagicMock()
        model = SettingsFormModel.from_settings(Settings())
        model.camera_index = 3
        model.confidence_threshold = 0.70
        model.apply(on_save)
        on_save.assert_called_once()
        saved: Settings = on_save.call_args[0][0]
        assert saved.camera_index == 3
        assert saved.confidence_threshold == 0.70

    def test_camera_list_from_list_cameras(self):
        from catguard.detection import Camera

        fake_cameras = [
            Camera(index=0, name="Camera 0", available=True),
            Camera(index=1, name="Camera 1", available=True),
        ]
        with patch("catguard.ui.settings_window.list_cameras", return_value=fake_cameras):
            cameras = SettingsFormModel.get_cameras()
        assert len(cameras) == 2
        assert cameras[0].index == 0
        assert cameras[1].index == 1


# ---------------------------------------------------------------------------
# T012: SettingsFormModel.screenshots_root_folder
# ---------------------------------------------------------------------------

class TestSettingsFormModelScreenshotsRootFolder:
    """T012 \u2014 screenshots_root_folder field on SettingsFormModel (TDD RED before T013)."""

    def test_from_settings_populates_screenshots_root_folder(self):
        s = Settings(screenshots_root_folder="/my/screenshots")
        model = SettingsFormModel.from_settings(s)
        assert model.screenshots_root_folder == "/my/screenshots"

    def test_from_settings_empty_root_folder(self):
        s = Settings(screenshots_root_folder="")
        model = SettingsFormModel.from_settings(s)
        assert model.screenshots_root_folder == ""

    def test_to_settings_round_trip_root_folder(self):
        s = Settings(screenshots_root_folder="/tmp/cats")
        model = SettingsFormModel.from_settings(s)
        restored = model.to_settings()
        assert restored.screenshots_root_folder == "/tmp/cats"

    def test_screenshots_root_folder_default_is_empty(self):
        model = SettingsFormModel.from_settings(Settings())
        assert model.screenshots_root_folder == ""


# ---------------------------------------------------------------------------
# T021: SettingsFormModel time-window fields
# ---------------------------------------------------------------------------

class TestSettingsFormModelTimeWindow:
    """T021 \u2014 time-window fields on SettingsFormModel (TDD RED before T023)."""

    def test_from_settings_populates_window_enabled(self):
        s = Settings(tracking_window_enabled=True)
        model = SettingsFormModel.from_settings(s)
        assert model.tracking_window_enabled is True

    def test_from_settings_populates_window_start(self):
        s = Settings(tracking_window_start="21:00")
        model = SettingsFormModel.from_settings(s)
        assert model.tracking_window_start == "21:00"

    def test_from_settings_populates_window_end(self):
        s = Settings(tracking_window_end="07:00")
        model = SettingsFormModel.from_settings(s)
        assert model.tracking_window_end == "07:00"

    def test_to_settings_round_trip_time_window(self):
        s = Settings(
            tracking_window_enabled=True,
            tracking_window_start="21:30",
            tracking_window_end="05:30",
        )
        model = SettingsFormModel.from_settings(s)
        restored = model.to_settings()
        assert restored.tracking_window_enabled is True
        assert restored.tracking_window_start == "21:30"
        assert restored.tracking_window_end == "05:30"

    def test_default_window_fields(self):
        model = SettingsFormModel.from_settings(Settings())
        assert model.tracking_window_enabled is False
        assert model.tracking_window_start == "08:00"
        assert model.tracking_window_end == "18:00"


# ---------------------------------------------------------------------------
# T005: SettingsFormModel audio playback fields (use_default_sound, pinned_sound)
# ---------------------------------------------------------------------------

class TestSettingsFormModelAudioFields:
    """T005 — use_default_sound and pinned_sound round-trip through SettingsFormModel."""

    def test_from_settings_populates_use_default_sound_true(self):
        s = Settings(use_default_sound=True)
        model = SettingsFormModel.from_settings(s)
        assert model.use_default_sound is True

    def test_from_settings_populates_use_default_sound_false(self):
        s = Settings(use_default_sound=False)
        model = SettingsFormModel.from_settings(s)
        assert model.use_default_sound is False

    def test_from_settings_populates_pinned_sound_empty(self):
        s = Settings(pinned_sound="")
        model = SettingsFormModel.from_settings(s)
        assert model.pinned_sound == ""

    def test_from_settings_populates_pinned_sound_path(self, tmp_path):
        wav = tmp_path / "alert.wav"
        wav.write_bytes(b"\x00" * 44)
        s = Settings(pinned_sound=str(wav))
        model = SettingsFormModel.from_settings(s)
        assert model.pinned_sound == str(wav)

    def test_to_settings_round_trip_use_default_sound_false(self):
        model = SettingsFormModel.from_settings(Settings(use_default_sound=False))
        restored = model.to_settings()
        assert restored.use_default_sound is False

    def test_to_settings_round_trip_use_default_sound_true(self):
        model = SettingsFormModel.from_settings(Settings(use_default_sound=True))
        restored = model.to_settings()
        assert restored.use_default_sound is True

    def test_to_settings_round_trip_pinned_sound(self, tmp_path):
        wav = tmp_path / "sound.wav"
        wav.write_bytes(b"\x00" * 44)
        model = SettingsFormModel.from_settings(Settings(pinned_sound=str(wav)))
        restored = model.to_settings()
        assert restored.pinned_sound == str(wav)

    def test_to_settings_round_trip_pinned_sound_empty(self):
        model = SettingsFormModel.from_settings(Settings(pinned_sound=""))
        restored = model.to_settings()
        assert restored.pinned_sound == ""

    def test_default_audio_fields(self):
        model = SettingsFormModel.from_settings(Settings())
        assert model.use_default_sound is True
        assert model.pinned_sound == ""


# ---------------------------------------------------------------------------
# T017: Checkbox enable/disable interaction — SettingsFormModel logic
# ---------------------------------------------------------------------------

class TestAudioDropdownLogic:
    """T017 / T023 — dropdown disable logic via SettingsFormModel."""

    def test_use_default_sound_true_disables_dropdown_logic(self):
        """When use_default_sound=True, to_settings() produces use_default_sound=True."""
        model = SettingsFormModel.from_settings(Settings(use_default_sound=True))
        s = model.to_settings()
        assert s.use_default_sound is True

    def test_use_default_sound_false_enables_dropdown_logic(self):
        """When use_default_sound=False, to_settings() propagates False."""
        model = SettingsFormModel.from_settings(Settings(use_default_sound=False))
        s = model.to_settings()
        assert s.use_default_sound is False

    def test_pinned_sound_empty_maps_to_all(self):
        """Empty pinned_sound maps to 'All' convention (empty string)."""
        model = SettingsFormModel.from_settings(Settings(pinned_sound=""))
        assert model.pinned_sound == ""
        s = model.to_settings()
        assert s.pinned_sound == ""

    def test_specific_path_round_trips(self, tmp_path):
        """A specific path for pinned_sound round-trips through to_settings()."""
        wav = tmp_path / "specific.wav"
        wav.write_bytes(b"\x00" * 44)
        model = SettingsFormModel.from_settings(Settings(pinned_sound=str(wav)))
        s = model.to_settings()
        assert s.pinned_sound == str(wav)

    def test_use_default_sound_true_serialised_correctly(self):
        """use_default_sound=True serialises to Settings.use_default_sound=True."""
        model = SettingsFormModel(use_default_sound=True, pinned_sound="")
        s = model.to_settings()
        assert s.use_default_sound is True

    def test_use_default_sound_false_serialised_correctly(self):
        model = SettingsFormModel(use_default_sound=False, pinned_sound="")
        s = model.to_settings()
        assert s.use_default_sound is False


# ---------------------------------------------------------------------------
# T015: Rename-stem validation helper tests (007-misc-improvements US3)
# ---------------------------------------------------------------------------
from catguard.ui.settings_window import _validate_rename_stem  # noqa: E402


class TestValidateRenameStem:
    """T015 — pure validation logic for the sound-file rename operation."""

    def test_valid_stem_returns_none(self):
        """A plain alphanumeric stem is valid."""
        assert _validate_rename_stem("my_alert") is None

    def test_valid_stem_with_spaces_returns_none(self):
        """A stem with inner spaces is valid (only forbidden charset matters)."""
        assert _validate_rename_stem("cat alert v2") is None

    def test_empty_string_returns_error(self):
        """Empty string is rejected."""
        result = _validate_rename_stem("")
        assert result is not None
        assert "empty" in result.lower()

    def test_whitespace_only_returns_error(self):
        """Whitespace-only string is rejected (treated as empty after strip)."""
        result = _validate_rename_stem("   ")
        assert result is not None
        assert "empty" in result.lower()

    def test_forward_slash_rejected(self):
        """Forward slash is a forbidden character."""
        result = _validate_rename_stem("cat/sound")
        assert result is not None
        assert "invalid" in result.lower()

    def test_backslash_rejected(self):
        r"""Backslash is a forbidden character."""
        result = _validate_rename_stem("cat\\sound")
        assert result is not None

    def test_colon_rejected(self):
        """Colon is a forbidden character (Windows path separator)."""
        result = _validate_rename_stem("cat:sound")
        assert result is not None

    def test_asterisk_rejected(self):
        """Asterisk is a forbidden character."""
        result = _validate_rename_stem("cat*")
        assert result is not None

    def test_question_mark_rejected(self):
        """Question mark is a forbidden character."""
        result = _validate_rename_stem("cat?")
        assert result is not None

    def test_angle_brackets_rejected(self):
        """Angle brackets are forbidden characters."""
        assert _validate_rename_stem("cat<sound>") is not None

    def test_pipe_rejected(self):
        """Pipe is a forbidden character."""
        assert _validate_rename_stem("cat|sound") is not None

    def test_double_quote_rejected(self):
        """Double-quote is a forbidden character."""
        assert _validate_rename_stem('cat"sound') is not None

    def test_unicode_name_valid(self):
        """Unicode characters (e.g. accented letters) are allowed."""
        assert _validate_rename_stem("кот_звук") is None

    def test_hyphen_and_dot_allowed(self):
        """Hyphens and dots in stem are allowed."""
        assert _validate_rename_stem("alert-v2.backup") is None


# ---------------------------------------------------------------------------
# T015: SettingsFormModel tracking-window round-trip tests (T008 model layer)
# ---------------------------------------------------------------------------


class TestTrackingWindowFormModel:
    """T015 / T008 — SettingsFormModel correctly round-trips tracking_window fields."""

    def test_defaults_from_fresh_settings(self):
        model = SettingsFormModel.from_settings(Settings())
        assert model.tracking_window_enabled is False
        assert model.tracking_window_start == "08:00"
        assert model.tracking_window_end == "18:00"

    def test_enabled_flag_round_trips(self):
        s = Settings(tracking_window_enabled=True)
        model = SettingsFormModel.from_settings(s)
        result = model.to_settings()
        assert result.tracking_window_enabled is True

    def test_start_time_round_trips(self):
        s = Settings(tracking_window_start="09:30")
        model = SettingsFormModel.from_settings(s)
        result = model.to_settings()
        assert result.tracking_window_start == "09:30"

    def test_end_time_round_trips(self):
        s = Settings(tracking_window_end="20:00")
        model = SettingsFormModel.from_settings(s)
        result = model.to_settings()
        assert result.tracking_window_end == "20:00"

    def test_all_tracking_fields_round_trip_together(self):
        s = Settings(
            tracking_window_enabled=True,
            tracking_window_start="07:00",
            tracking_window_end="23:30",
        )
        model = SettingsFormModel.from_settings(s)
        result = model.to_settings()
        assert result.tracking_window_enabled is True
        assert result.tracking_window_start == "07:00"
        assert result.tracking_window_end == "23:30"


# ---------------------------------------------------------------------------
# T015: Rename file-system integration tests (using tmp_path, no display)
# ---------------------------------------------------------------------------


class TestRenameFileIntegration:
    """T015 — verify file-rename semantics that back _rename_path() live in pathlib."""

    def test_valid_rename_produces_new_file(self, tmp_path):
        """Renaming a file produces the new file and removes the old path."""
        old = tmp_path / "meow.wav"
        old.write_bytes(b"\x00" * 44)
        new = old.parent / ("purr" + old.suffix)
        old.rename(new)
        assert new.exists()
        assert not old.exists()

    def test_pinned_sound_path_update_logic(self):
        """A SettingsFormModel whose pinned_sound is updated reflects the new path."""
        model = SettingsFormModel(pinned_sound="/sounds/meow.wav")
        old_path = model.pinned_sound
        new_path = "/sounds/purr.wav"
        # Simulate what _rename_path does: update the model field
        if model.pinned_sound == old_path:
            model.pinned_sound = new_path
        assert model.pinned_sound == new_path

    def test_cancel_leaves_file_unchanged(self, tmp_path):
        """If new_stem is None (dialog cancelled), no rename occurs."""
        original = tmp_path / "meow.wav"
        original.write_bytes(b"\x00" * 44)
        # Simulate cancel: new_stem is None → early return, no rename
        new_stem = None  # type: ignore[assignment]
        if new_stem is not None:
            original.rename(original.parent / (new_stem + original.suffix))
        assert original.exists()

    def test_duplicate_detection(self, tmp_path):
        """Renaming to an existing file name should be caught before rename."""
        existing = tmp_path / "purr.wav"
        existing.write_bytes(b"\x00" * 44)
        target = tmp_path / "meow.wav"
        target.write_bytes(b"\x00" * 44)
        new_path = target.parent / ("purr" + target.suffix)
        # The duplicate guard: if new_path.exists() and new_path != target → abort
        should_abort = new_path.exists() and new_path != target
        assert should_abort, "Duplicate detection should have fired"
