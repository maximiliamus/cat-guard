"""Unit tests for catguard.audio — written before implementation (TDD RED).

Covers:
- Random selection from multiple valid files
- Fallback to default when library empty or all invalid
- Unsupported format filtering
- init_audio / shutdown_audio call pygame.mixer
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from catguard.audio import init_audio, play_random_alert, shutdown_audio


class TestRandomSelection:
    def test_plays_from_library_not_default(self, tmp_path):
        paths = []
        for name in ["a.wav", "b.wav", "c.wav"]:
            p = tmp_path / name
            p.write_bytes(b"\x00" * 44)
            paths.append(str(p))

        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            play_random_alert(paths, default)

        assert len(played) == 1
        assert played[0] in paths  # chose from library, not default

    def test_random_across_multiple_calls(self, tmp_path):
        paths = []
        for name in ["a.wav", "b.wav", "c.wav"]:
            p = tmp_path / name
            p.write_bytes(b"\x00" * 44)
            paths.append(str(p))

        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            for _ in range(20):
                play_random_alert(paths, default)

        # With 3 files and 20 calls, randomness should produce >1 unique selection
        unique = set(played)
        assert len(unique) >= 1
        assert unique.issubset(set(paths))


class TestFallback:
    def test_fallback_to_default_when_empty_library(self, tmp_path):
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            play_random_alert([], default)

        assert played == [str(default)]

    def test_fallback_to_default_when_all_unsupported(self, tmp_path):
        bad = tmp_path / "sound.ogg"
        bad.write_bytes(b"\x00" * 10)

        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            play_random_alert([str(bad)], default)

        assert played == [str(default)]


class TestFormatFiltering:
    def test_unsupported_format_excluded(self, tmp_path):
        valid = tmp_path / "ok.mp3"
        valid.write_bytes(b"\x00" * 10)
        invalid = tmp_path / "bad.ogg"
        invalid.write_bytes(b"\x00" * 10)
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            play_random_alert([str(valid), str(invalid)], default)

        assert played == [str(valid)]

    def test_wav_and_mp3_both_accepted(self, tmp_path):
        wav = tmp_path / "a.wav"
        wav.write_bytes(b"\x00" * 44)
        mp3 = tmp_path / "b.mp3"
        mp3.write_bytes(b"\x00" * 10)
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            for _ in range(10):
                play_random_alert([str(wav), str(mp3)], default)

        unique = set(played)
        assert unique.issubset({str(wav), str(mp3)})
        assert len(unique) >= 1


class TestInitShutdown:
    def test_init_calls_mixer_init(self):
        import pygame.mixer as mixer_mod
        with patch.object(mixer_mod, "init") as mock_init:
            init_audio()
            mock_init.assert_called_once()

    def test_shutdown_calls_mixer_quit(self):
        import pygame.mixer as mixer_mod
        with patch.object(mixer_mod, "quit") as mock_quit:
            shutdown_audio()
            mock_quit.assert_called_once()
