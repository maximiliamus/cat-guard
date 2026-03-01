"""Integration tests for CatGuard audio playback.

These tests use real pygame-ce and a real WAV file to verify end-to-end
audio playback works without errors. They do NOT test sound output quality —
they verify the playback pipeline runs to completion.

Run with:
    pytest tests/integration/test_audio_integration.py -v
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets" / "sounds"
DEFAULT_WAV = ASSETS_DIR / "default.wav"


@pytest.mark.integration
class TestAudioIntegration:
    def setup_method(self):
        from catguard.audio import init_audio

        init_audio()

    def teardown_method(self):
        from catguard.audio import shutdown_audio

        shutdown_audio()

    def test_play_default_wav_no_error(self):
        """play_random_alert with empty library falls back to default.wav without error."""
        from catguard.audio import play_random_alert

        assert DEFAULT_WAV.exists(), f"Default WAV not found: {DEFAULT_WAV}"
        # Should not raise
        play_random_alert([], DEFAULT_WAV)
        # Give the daemon thread a moment to start playback
        time.sleep(0.3)

    def test_play_explicit_wav_file(self):
        """play_random_alert selects and plays the given WAV file."""
        from catguard.audio import play_random_alert

        assert DEFAULT_WAV.exists()
        play_random_alert([str(DEFAULT_WAV)], DEFAULT_WAV)
        time.sleep(0.3)

    def test_play_with_unsupported_format_falls_back(self, tmp_path):
        """Files with unsupported extensions are skipped; default plays."""
        from catguard.audio import play_random_alert

        bad_file = tmp_path / "test.ogg"
        bad_file.write_bytes(b"\x00" * 10)
        play_random_alert([str(bad_file)], DEFAULT_WAV)
        time.sleep(0.3)

    def test_init_and_shutdown_idempotent(self):
        """Calling init/shutdown multiple times should not raise."""
        from catguard.audio import init_audio, shutdown_audio

        init_audio()   # extra init while already initialised
        shutdown_audio()
        init_audio()   # re-init after shutdown
        shutdown_audio()
        # Re-initialise for teardown_method
        init_audio()


# ---------------------------------------------------------------------------
# T018: play_alert() mode dispatch — default-sound toggle persistence
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestPlayAlertModeDispatchIntegration:
    """T018 / T024 — end-to-end play_alert() mode selection with saved settings."""

    def _make_settings(self, tmp_path, use_default_sound=True, pinned_sound="", library=None):
        s = MagicMock()
        s.use_default_sound = use_default_sound
        s.pinned_sound = pinned_sound
        s.sound_library_paths = library or []
        return s

    def test_use_default_sound_true_calls_play_async_with_default(self, tmp_path):
        """T018: use_default_sound=True → _play_async receives default_path."""
        from catguard.audio import play_alert

        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        settings = self._make_settings(tmp_path, use_default_sound=True)

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            play_alert(settings, default)

        assert played == [str(default)]

    def test_use_default_sound_false_with_library_plays_library(self, tmp_path):
        """T018: use_default_sound=False → library sound is used."""
        from catguard.audio import play_alert

        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        lib = tmp_path / "lib.wav"
        lib.write_bytes(b"\x00" * 44)
        settings = self._make_settings(
            tmp_path,
            use_default_sound=False,
            library=[str(lib)],
        )

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            play_alert(settings, default)

        assert played == [str(lib)]

    # T024: pinned-sound playback integration tests
    def test_pinned_sound_always_plays_same_file(self, tmp_path):
        """T024: pinned_sound set → play_alert always plays that file."""
        from catguard.audio import play_alert

        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        pinned = tmp_path / "pinned.wav"
        pinned.write_bytes(b"\x00" * 44)
        settings = self._make_settings(
            tmp_path,
            use_default_sound=False,
            pinned_sound=str(pinned),
        )

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            for _ in range(3):
                play_alert(settings, default)

        assert all(p == str(pinned) for p in played)
        assert len(played) == 3

    def test_pinned_sound_missing_falls_back_to_random(self, tmp_path):
        """T024: pinned_sound path removed → fallback to random selection."""
        from catguard.audio import play_alert

        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        lib = tmp_path / "lib.wav"
        lib.write_bytes(b"\x00" * 44)
        settings = self._make_settings(
            tmp_path,
            use_default_sound=False,
            pinned_sound="/nonexistent/removed.wav",
        )
        settings.sound_library_paths = [str(lib)]

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            play_alert(settings, default)

        assert played == [str(lib)]

    def test_pinned_sound_empty_random_from_library(self, tmp_path):
        """T024: pinned_sound='' → random selection from library."""
        from catguard.audio import play_alert

        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        files = []
        for name in ["a.wav", "b.wav", "c.wav"]:
            p = tmp_path / name
            p.write_bytes(b"\x00" * 44)
            files.append(str(p))
        settings = self._make_settings(
            tmp_path,
            use_default_sound=False,
            pinned_sound="",
        )
        settings.sound_library_paths = files

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            for _ in range(10):
                play_alert(settings, default)

        assert set(played).issubset(set(files))
