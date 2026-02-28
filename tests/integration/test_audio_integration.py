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
