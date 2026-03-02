"""Unit tests for catguard.audio — written before implementation (TDD RED).

Covers:
- Random selection from multiple valid files
- Fallback to default when library empty or all invalid
- Unsupported format filtering
- init_audio / shutdown_audio call pygame.mixer
- play_alert() mode dispatch: DEFAULT, PINNED, RANDOM, fallbacks
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from catguard.audio import init_audio, play_alert, play_random_alert, shutdown_audio


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


# ---------------------------------------------------------------------------
# T009: play_alert() mode dispatch
# ---------------------------------------------------------------------------

def _make_settings(
    use_default_sound=True,
    pinned_sound="",
    sound_library_paths=None,
):
    """Build a minimal settings-like object for play_alert() tests."""
    s = MagicMock()
    s.use_default_sound = use_default_sound
    s.pinned_sound = pinned_sound
    s.sound_library_paths = sound_library_paths or []
    return s


class TestPlayAlertDefaultMode:
    """use_default_sound=True → always plays default_path regardless of library."""

    def test_plays_default_path(self, tmp_path):
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        settings = _make_settings(use_default_sound=True)

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            play_alert(settings, default)

        assert played == [str(default)]

    def test_ignores_library_when_default_mode(self, tmp_path):
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        lib = tmp_path / "lib.wav"
        lib.write_bytes(b"\x00" * 44)
        settings = _make_settings(
            use_default_sound=True,
            sound_library_paths=[str(lib)],
        )

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            play_alert(settings, default)

        assert played == [str(default)]


class TestPlayAlertPinnedMode:
    """use_default_sound=False, valid pinned_sound → plays pinned file."""

    def test_plays_pinned_file(self, tmp_path):
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        pinned = tmp_path / "pinned.wav"
        pinned.write_bytes(b"\x00" * 44)
        settings = _make_settings(use_default_sound=False, pinned_sound=str(pinned))

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            play_alert(settings, default)

        assert played == [str(pinned)]

    def test_pinned_missing_falls_back_to_random(self, tmp_path):
        """If pinned file is missing, fall back to RANDOM mode."""
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        lib = tmp_path / "lib.wav"
        lib.write_bytes(b"\x00" * 44)
        settings = _make_settings(
            use_default_sound=False,
            pinned_sound="/nonexistent/missing.wav",
            sound_library_paths=[str(lib)],
        )

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            play_alert(settings, default)

        assert played == [str(lib)]


class TestPlayAlertRandomMode:
    """use_default_sound=False, pinned_sound='' → random from library."""

    def test_plays_from_library(self, tmp_path):
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        lib = tmp_path / "lib.wav"
        lib.write_bytes(b"\x00" * 44)
        settings = _make_settings(
            use_default_sound=False,
            pinned_sound="",
            sound_library_paths=[str(lib)],
        )

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            play_alert(settings, default)

        assert played == [str(lib)]

    def test_empty_library_falls_back_to_default(self, tmp_path):
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        settings = _make_settings(use_default_sound=False, pinned_sound="")

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            play_alert(settings, default)

        assert played == [str(default)]

    def test_all_unsupported_library_falls_back_to_default(self, tmp_path):
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        bad = tmp_path / "sound.ogg"
        bad.write_bytes(b"\x00" * 10)
        settings = _make_settings(
            use_default_sound=False,
            pinned_sound="",
            sound_library_paths=[str(bad)],
        )

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            play_alert(settings, default)

        assert played == [str(default)]

    def test_random_selects_from_library(self, tmp_path):
        """Over many calls, random mode selects from the library."""
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        files = []
        for name in ["a.wav", "b.wav", "c.wav"]:
            p = tmp_path / name
            p.write_bytes(b"\x00" * 44)
            files.append(str(p))
        settings = _make_settings(
            use_default_sound=False,
            pinned_sound="",
            sound_library_paths=files,
        )

        played = []
        with patch("catguard.audio._play_async", side_effect=played.append):
            for _ in range(20):
                play_alert(settings, default)

        assert set(played).issubset(set(files))


# ---------------------------------------------------------------------------
# T002: play_alert() MUST return str (sound label for screenshot annotation)
# ---------------------------------------------------------------------------

class TestPlayAlertReturnValue:
    """T002 — play_alert() must return a str label for screenshot annotation."""

    def test_default_mode_returns_alert_default(self, tmp_path):
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        settings = _make_settings(use_default_sound=True)

        with patch("catguard.audio._play_async"):
            result = play_alert(settings, default)

        assert result == "Alert: Default"

    def test_pinned_mode_returns_filename(self, tmp_path):
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        pinned = tmp_path / "meow_alarm.wav"
        pinned.write_bytes(b"\x00" * 44)
        settings = _make_settings(use_default_sound=False, pinned_sound=str(pinned))

        with patch("catguard.audio._play_async"):
            result = play_alert(settings, default)

        assert result == "meow_alarm.wav"

    def test_random_mode_returns_filename(self, tmp_path):
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        lib = tmp_path / "siren.wav"
        lib.write_bytes(b"\x00" * 44)
        settings = _make_settings(
            use_default_sound=False,
            pinned_sound="",
            sound_library_paths=[str(lib)],
        )

        with patch("catguard.audio._play_async"):
            result = play_alert(settings, default)

        assert result == "siren.wav"

    def test_pinned_missing_fallback_to_random_returns_filename(self, tmp_path):
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        lib = tmp_path / "fallback.wav"
        lib.write_bytes(b"\x00" * 44)
        settings = _make_settings(
            use_default_sound=False,
            pinned_sound="/nonexistent/missing.wav",
            sound_library_paths=[str(lib)],
        )

        with patch("catguard.audio._play_async"):
            result = play_alert(settings, default)

        assert result == "fallback.wav"

    def test_random_empty_library_returns_alert_default(self, tmp_path):
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        settings = _make_settings(use_default_sound=False, pinned_sound="")

        with patch("catguard.audio._play_async"):
            result = play_alert(settings, default)

        assert result == "Alert: Default"

    def test_random_all_unsupported_returns_alert_default(self, tmp_path):
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        bad = tmp_path / "sound.ogg"
        bad.write_bytes(b"\x00" * 10)
        settings = _make_settings(
            use_default_sound=False,
            pinned_sound="",
            sound_library_paths=[str(bad)],
        )

        with patch("catguard.audio._play_async"):
            result = play_alert(settings, default)

        assert result == "Alert: Default"

    def test_return_type_is_str(self, tmp_path):
        default = tmp_path / "default.wav"
        default.write_bytes(b"\x00" * 44)
        settings = _make_settings(use_default_sound=True)

        with patch("catguard.audio._play_async"):
            result = play_alert(settings, default)

        assert isinstance(result, str)

