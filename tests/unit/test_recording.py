"""Unit tests for catguard.recording — written before implementation (TDD RED).

Covers:
- get_alerts_dir: correct platform-derived path
- sanitise_filename: special chars, spaces, path traversal, empty string
- is_silent: zero-length, None, RMS below/above threshold
- save_recording: file written to tmp dir with correct name
- open_alerts_folder: correct OS command dispatched (mocked)
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from catguard.recording import (
    Recorder,
    get_alerts_dir,
    is_silent,
    open_alerts_folder,
    sanitise_filename,
    save_recording,
)


# ---------------------------------------------------------------------------
# get_alerts_dir
# ---------------------------------------------------------------------------

class TestGetAlertsDir:
    def test_returns_path_object(self):
        d = get_alerts_dir()
        assert isinstance(d, Path)

    def test_ends_with_alerts(self):
        d = get_alerts_dir()
        assert d.name == "alerts"

    def test_parent_dir_is_catguard(self):
        d = get_alerts_dir()
        assert d.parent.name == "CatGuard"


# ---------------------------------------------------------------------------
# sanitise_filename
# ---------------------------------------------------------------------------

class TestSanitiseFilename:
    def test_basic_name(self):
        assert sanitise_filename("my recording") == "my_recording.wav"

    def test_special_chars_stripped(self):
        result = sanitise_filename("alert!@#$%^&*()")
        # Only word chars, spaces, hyphens, dots survive
        assert "!" not in result
        assert "@" not in result
        assert result.endswith(".wav")

    def test_spaces_converted_to_underscores(self):
        assert sanitise_filename("hello world") == "hello_world.wav"

    def test_path_traversal_stripped(self):
        result = sanitise_filename("../../etc/passwd")
        assert "/" not in result
        assert ".." not in result.replace(".wav", "")
        assert result.endswith(".wav")

    def test_path_traversal_with_backslash(self):
        result = sanitise_filename("..\\windows\\system32\\evil")
        # Path.name on Windows strips directory; on Linux too via Path
        assert result.endswith(".wav")

    def test_empty_string_falls_back_to_recording(self):
        assert sanitise_filename("") == "recording.wav"

    def test_only_special_chars_falls_back_to_recording(self):
        assert sanitise_filename("!@#$%") == "recording.wav"

    def test_unicode_preserved(self):
        result = sanitise_filename("Привет мир")
        assert result.endswith(".wav")
        # Unicode word chars should be preserved
        assert len(result) > len(".wav")

    def test_leading_dots_stripped(self):
        result = sanitise_filename("...hidden")
        assert not result.startswith(".")

    def test_already_has_wav_extension(self):
        # Should not double-add .wav; the .wav in the name becomes part of base
        result = sanitise_filename("sound.wav")
        assert result.endswith(".wav")

    def test_hyphens_preserved(self):
        assert sanitise_filename("my-sound") == "my-sound.wav"


# ---------------------------------------------------------------------------
# is_silent
# ---------------------------------------------------------------------------

class TestIsSilent:
    def test_none_is_silent(self):
        assert is_silent(None) is True

    def test_zero_length_array_is_silent(self):
        assert is_silent(np.array([], dtype="int16")) is True

    def test_all_zeros_is_silent(self):
        data = np.zeros(44100, dtype="int16")
        assert is_silent(data) is True

    def test_rms_below_threshold_is_silent(self):
        # RMS ≈ 50 — well below 100 threshold
        data = np.full(44100, 50, dtype="int16")
        rms = float(np.sqrt(np.mean(data.astype(np.float32) ** 2)))
        assert rms < 100
        assert is_silent(data) is True

    def test_rms_above_threshold_not_silent(self):
        # RMS ≈ 1000 — well above 100 threshold
        data = np.full(44100, 1000, dtype="int16")
        rms = float(np.sqrt(np.mean(data.astype(np.float32) ** 2)))
        assert rms > 100
        assert is_silent(data) is False

    def test_threshold_boundary_below(self):
        # RMS exactly 99 → silent
        val = 99
        data = np.full(100, val, dtype="int16")
        assert is_silent(data) is True

    def test_threshold_boundary_above(self):
        # RMS exactly 101 → not silent
        val = 101
        data = np.full(100, val, dtype="int16")
        assert is_silent(data) is False


# ---------------------------------------------------------------------------
# save_recording
# ---------------------------------------------------------------------------

class TestSaveRecording:
    def test_file_written_to_alerts_dir(self, tmp_path):
        data = np.full(4410, 200, dtype="int16")
        path = save_recording(data, "test sound", alerts_dir=tmp_path)
        assert path.exists()
        assert path.suffix == ".wav"
        assert path.parent == tmp_path

    def test_filename_sanitised(self, tmp_path):
        data = np.full(4410, 200, dtype="int16")
        path = save_recording(data, "hello world!", alerts_dir=tmp_path)
        assert " " not in path.name
        assert "!" not in path.name

    def test_creates_alerts_dir_if_missing(self, tmp_path):
        alerts_dir = tmp_path / "new_subdir"
        assert not alerts_dir.exists()
        data = np.full(4410, 200, dtype="int16")
        save_recording(data, "test", alerts_dir=alerts_dir)
        assert alerts_dir.exists()

    def test_returns_path(self, tmp_path):
        data = np.full(4410, 200, dtype="int16")
        result = save_recording(data, "my rec", alerts_dir=tmp_path)
        assert isinstance(result, Path)

    def test_wav_file_readable(self, tmp_path):
        """Written WAV is readable back with soundfile."""
        import soundfile as sf
        data = np.full(4410, 300, dtype="int16")
        path = save_recording(data, "readable", alerts_dir=tmp_path)
        read_data, samplerate = sf.read(str(path), dtype="int16")
        assert samplerate == 44100
        assert len(read_data) == 4410


# ---------------------------------------------------------------------------
# open_alerts_folder
# ---------------------------------------------------------------------------

class TestOpenAlertsFolder:
    def test_windows_uses_startfile(self, tmp_path):
        with patch("platform.system", return_value="Windows"), \
             patch("os.startfile", create=True) as mock_start:
            open_alerts_folder(alerts_dir=tmp_path)
        mock_start.assert_called_once_with(str(tmp_path))

    def test_macos_uses_open(self, tmp_path):
        with patch("platform.system", return_value="Darwin"), \
             patch("subprocess.run") as mock_run:
            open_alerts_folder(alerts_dir=tmp_path)
        mock_run.assert_called_once_with(["open", str(tmp_path)], check=False)

    def test_linux_uses_xdg_open(self, tmp_path):
        with patch("platform.system", return_value="Linux"), \
             patch("subprocess.run") as mock_run:
            open_alerts_folder(alerts_dir=tmp_path)
        mock_run.assert_called_once_with(["xdg-open", str(tmp_path)], check=False)

    def test_creates_folder_if_missing(self, tmp_path):
        new_dir = tmp_path / "missing_alerts"
        assert not new_dir.exists()
        with patch("platform.system", return_value="Linux"), \
             patch("subprocess.run"):
            open_alerts_folder(alerts_dir=new_dir)
        assert new_dir.exists()
