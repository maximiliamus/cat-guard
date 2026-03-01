# Quickstart: Audio Recording & Playback Controls

**Feature**: `004-add-record-sound`
**Branch**: `004-add-record-sound`

---

## Prerequisites

```bash
# Activate your virtual environment, then install new dependencies
pip install sounddevice soundfile
# Verify
python -c "import sounddevice, soundfile; print('OK')"
```

> `sounddevice` requires PortAudio. On Linux install it first:
> `sudo apt-get install libportaudio2`
> On Windows and macOS the PortAudio binary is bundled in the `sounddevice` wheel —
> no extra step needed.

---

## Running the App

```bash
python -m catguard
```

The Settings window (tray → Settings) now contains:
- **Record / Stop Recording** button with 10-second progress count-down
- **Alerts folder** read-only path field + **Browse…** button
- **Use Default Sound** checkbox (checked by default on fresh install)
- **Play Only This Sound** dropdown (disabled when "Use Default Sound" is checked)

---

## Running the Tests

```bash
# All tests
pytest

# Unit tests only (fast, no mic/camera required)
pytest tests/unit/

# New unit tests for this feature
pytest tests/unit/test_recording.py
pytest tests/unit/test_audio.py
pytest tests/unit/test_config.py
pytest tests/unit/test_settings_window.py

# Integration tests for this feature (requires real filesystem; mocks mic)
pytest tests/integration/test_recording_integration.py
pytest tests/integration/test_audio_integration.py

# Skip integration tests (e.g. in CI without audio device)
pytest -m "not integration"
```

---

## Key Files Changed / Added

| File | Change |
|------|--------|
| `src/catguard/recording.py` | **NEW** — `Recorder`, `get_alerts_dir()`, `save_recording()`, `open_alerts_folder()` |
| `src/catguard/audio.py` | **MODIFY** — add `play_alert(settings, default_path)` dispatcher |
| `src/catguard/config.py` | **MODIFY** — add `use_default_sound` and `pinned_sound` to `Settings` and `SettingsFormModel` |
| `src/catguard/main.py` | **MODIFY** — call `play_alert()`, initialise `root._recording_event` |
| `src/catguard/ui/settings_window.py` | **MODIFY** — Record button, checkbox, dropdown, alerts folder row |
| `tests/unit/test_recording.py` | **NEW** |
| `tests/integration/test_recording_integration.py` | **NEW** |

---

## Alerts Folder Location

Recorded WAV files are saved automatically to:

| Platform | Path |
|----------|------|
| Windows | `%APPDATA%\CatGuard\alerts\` |
| Linux | `~/.local/share/CatGuard/alerts\` |
| macOS | `~/Library/Application Support/CatGuard/alerts\` |

The folder is created on first save. Click **Browse…** in Settings to open it in
your file explorer.

---

## Playback Mode Quick Reference

| "Use Default Sound" | "Play Only This Sound" | Sound that plays |
|---------------------|------------------------|-----------------|
| ✅ Checked | any | Built-in `default.wav` |
| ☐ Unchecked | "All" | Random from library (existing behaviour) |
| ☐ Unchecked | specific file | That file, every time |
| ☐ Unchecked | any, library empty | Built-in `default.wav` (fallback) |

---

## TDD Workflow for Contributors

```bash
# 1. Write a failing test first
pytest tests/unit/test_recording.py::test_silence_detection  # RED

# 2. Implement the minimum code to pass
# edit src/catguard/recording.py ...

# 3. Run again to confirm green
pytest tests/unit/test_recording.py::test_silence_detection  # GREEN

# 4. Refactor, then re-run full suite
pytest
```
