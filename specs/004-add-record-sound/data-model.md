# Data Model: Audio Recording & Playback Controls

**Feature**: `004-add-record-sound`
**Date**: 2026-03-01

---

## Modified Entities

### `Settings` *(extended — `src/catguard/config.py`)*

Two new fields are added to the existing Pydantic model. All existing fields are
unchanged; new fields have defaults so existing `settings.json` files load without
errors.

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `use_default_sound` | `bool` | `True` | — | When `True`, the built-in default sound plays on every detection event; overrides all library/dropdown settings |
| `pinned_sound` | `str` | `""` | Path to an existing file, or empty string | Absolute path of the specific library sound to always play; empty string means "All" (random selection) |

**Validation rules (new)**:
- `pinned_sound`: if non-empty and the file no longer exists on disk, the validator
  silently resets it to `""` (consistent with the existing `prune_stale_paths`
  validator on `sound_library_paths`).

**Persistence**: Both fields round-trip through `settings.json` using the existing
`save_settings()` / `load_settings()` machinery unchanged.

---

### `SettingsFormModel` *(extended — `src/catguard/ui/settings_window.py`)*

Mirrors the two new `Settings` fields for UI binding. No display-only fields needed.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_default_sound` | `bool` | `True` | Bound to the "Use Default Sound" checkbox |
| `pinned_sound` | `str` | `""` | Bound to the "Play Only This Sound" dropdown; `""` maps to the "All" entry |

`from_settings()` and `to_settings()` must be updated to copy both fields.

---

## New Entities

### `Recorder` *(new — `src/catguard/recording.py`)*

Encapsulates a single microphone recording session. Instances are short-lived:
created when the user clicks Record, discarded after the name prompt resolves.

| Attribute / Method | Type | Description |
|--------------------|------|-------------|
| `_data` | `np.ndarray \| None` | Raw int16 samples captured by `sounddevice`; `None` before `start()` is called |
| `_samplerate` | `int` | Sample rate in Hz (44 100 Hz fixed) |
| `start(on_done)` | method | Begins capture on a daemon background thread; calls `on_done(data)` when recording ends (cap reached or `stop()` called) |
| `stop()` | method | Stops capture early; triggers the `on_done` callback via `sounddevice.stop()` |
| `is_recording()` | `bool` property | `True` while capture is active |
| `is_silent(data)` | static method | Returns `True` if the recording is zero-length or has RMS amplitude < 100 (int16 scale) |

**State transitions**:

```
[idle] --start()--> [recording] --stop() or 10s cap--> [done → on_done callback]
                                                               ↓
                                                       [idle (new instance)]
```

**Thread safety**: Only `start()` and `stop()` are called across thread boundaries.
`start()` launches a daemon thread; `stop()` delegates to `sounddevice.stop()` which
is thread-safe by library design.

---

### `PlaybackMode` *(conceptual — no separate class)*

A computed, non-persisted property of the current `Settings` state. Determines which
sound fires on a detection event:

| Mode | When Active | Sound Played |
|------|-------------|--------------|
| `DEFAULT` | `use_default_sound is True` | Built-in `default.wav` from `assets/sounds/` |
| `PINNED` | `use_default_sound is False` **and** `pinned_sound` is a non-empty path to an existing file | The file at `pinned_sound` |
| `RANDOM` | `use_default_sound is False` **and** `pinned_sound` is `""` or file is missing | A randomly selected file from `sound_library_paths`; falls back to `default.wav` if library is empty |

Priority: `DEFAULT` > `PINNED` > `RANDOM`.

This logic lives in a new `play_alert(settings, default_path)` function in
`audio.py`, replacing the direct `play_random_alert()` call in `main.py`.

---

## Derived / Runtime State

| Name | Owner | Type | Description |
|------|-------|------|-------------|
| `root._recording_event` | `main.py` | `threading.Event` | Set while recording is active; checked in `on_cat_detected` to suppress alerts; cleared when recording stops or Settings window closes |

This is not persisted. It is initialised to a cleared `threading.Event` at app startup
alongside the existing root-attribute flags.

---

## Alerts Folder

Not a data-model entity but documented here for completeness:

| Platform | Path |
|----------|------|
| Windows | `%APPDATA%\CatGuard\alerts\` |
| Linux | `~/.local/share/CatGuard/alerts/` |
| macOS | `~/Library/Application Support/CatGuard/alerts/` |

Resolved at runtime via `platformdirs.user_data_dir("CatGuard")`. Created
automatically on first save. The path is **not** stored in `settings.json`; it is
always derived. Displayed read-only in the Settings window.
