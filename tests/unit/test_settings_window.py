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
        assert model.confidence_threshold == 0.40
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
