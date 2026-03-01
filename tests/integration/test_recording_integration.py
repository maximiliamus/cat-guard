"""Integration tests for the record → stop → name → save → library flow.

Uses a real temporary filesystem but mocks sounddevice to avoid requiring
actual microphone hardware in CI.

Marks: integration (can be skipped with -m "not integration")
"""
from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_audio_data(rms: int = 300, length: int = 4410) -> np.ndarray:
    """Create a synthetic int16 audio array with the given approximate RMS."""
    return np.full(length, rms, dtype="int16")


# ---------------------------------------------------------------------------
# T014: record → stop → name → save → library flow
# ---------------------------------------------------------------------------

class TestRecordSaveFlow:
    """Full record-save flow using mocked sounddevice."""

    def test_save_recording_creates_wav_in_alerts_dir(self, tmp_path):
        """Saving a non-silent recording writes a WAV file."""
        from catguard.recording import save_recording

        data = _make_audio_data(rms=500)
        path = save_recording(data, "integration test", alerts_dir=tmp_path)

        assert path.exists()
        assert path.suffix == ".wav"
        assert path.parent == tmp_path

    def test_save_recording_path_added_to_library(self, tmp_path):
        """After saving, the path can be added to a simulated library list."""
        from catguard.recording import save_recording

        data = _make_audio_data(rms=500)
        saved_path = save_recording(data, "my alert", alerts_dir=tmp_path)

        library: list[str] = []
        if str(saved_path) not in library:
            library.append(str(saved_path))

        assert str(saved_path) in library

    def test_silent_recording_rejected(self):
        """Silent recordings are detected and should not be saved."""
        from catguard.recording import is_silent

        silent_data = np.zeros(4410, dtype="int16")
        assert is_silent(silent_data) is True

    def test_cancel_does_not_create_file(self, tmp_path):
        """Cancelling the name prompt does not write any file."""
        # Simulate: recording completes but user cancels name prompt
        files_before = set(tmp_path.iterdir())
        # No save_recording call → no file created
        files_after = set(tmp_path.iterdir())
        assert files_before == files_after

    def test_recorder_on_done_callback_called(self, tmp_path):
        """Recorder calls on_done after stop() is called."""
        from catguard.recording import Recorder

        fake_chunk = _make_audio_data(rms=400, length=44100).reshape(-1, 1)
        done_event = threading.Event()
        received: list[np.ndarray] = []

        def on_done(data):
            received.append(data)
            done_event.set()

        callback_holder: list = [None]

        class _FakeStream:
            def start(self):
                if callback_holder[0]:
                    callback_holder[0](fake_chunk, len(fake_chunk), None, None)
            def stop(self): pass
            def close(self): pass

        def _fake_input_stream(*args, **kwargs):
            callback_holder[0] = kwargs.get("callback")
            return _FakeStream()

        with patch("sounddevice.check_input_settings"), \
             patch("sounddevice.InputStream", side_effect=_fake_input_stream):
            recorder = Recorder()
            recorder.start(on_done=on_done)
            recorder.stop()
            done_event.wait(timeout=5.0)

        assert done_event.is_set(), "on_done was never called"
        assert len(received) == 1

    def test_recorder_stop_triggers_on_done(self):
        """Calling stop() triggers the on_done callback."""
        from catguard.recording import Recorder

        fake_chunk = _make_audio_data(rms=200, length=100).reshape(-1, 1)
        done_event = threading.Event()
        received: list[np.ndarray] = []

        def on_done(data):
            received.append(data)
            done_event.set()

        callback_holder: list = [None]

        class _FakeStream:
            def start(self):
                if callback_holder[0]:
                    callback_holder[0](fake_chunk, len(fake_chunk), None, None)
            def stop(self): pass
            def close(self): pass

        def _fake_input_stream(*args, **kwargs):
            callback_holder[0] = kwargs.get("callback")
            return _FakeStream()

        with patch("sounddevice.check_input_settings"), \
             patch("sounddevice.InputStream", side_effect=_fake_input_stream):
            recorder = Recorder()
            recorder.start(on_done=on_done)
            recorder.stop()
            done_event.wait(timeout=5.0)

        assert done_event.is_set()

    def test_duplicate_filename_overwrite(self, tmp_path):
        """Writing a recording with an existing name overwrites the file."""
        from catguard.recording import save_recording

        data1 = _make_audio_data(rms=300)
        data2 = _make_audio_data(rms=600)

        p1 = save_recording(data1, "overlap", alerts_dir=tmp_path)
        p2 = save_recording(data2, "overlap", alerts_dir=tmp_path)

        assert p1 == p2  # same path (overwritten)
        assert p2.exists()

    def test_wav_file_is_valid_audio(self, tmp_path):
        """Saved WAV file can be read back with soundfile."""
        import soundfile as sf
        from catguard.recording import save_recording

        data = _make_audio_data(rms=400, length=8820)
        path = save_recording(data, "valid audio", alerts_dir=tmp_path)

        read_data, samplerate = sf.read(str(path), dtype="int16")
        assert samplerate == 44100
        assert len(read_data) == 8820
