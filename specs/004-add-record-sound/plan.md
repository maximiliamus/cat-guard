# Implementation Plan: Audio Recording & Playback Controls

**Branch**: `004-add-record-sound` | **Date**: 2026-03-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-add-record-sound/spec.md`

## Summary

Add microphone recording to the Settings window (Record/Stop button, 10-second cap,
name prompt on stop, WAV save to the OS alerts folder). Add a "Use Default Sound"
checkbox (default: checked) and a "Play Only This Sound" dropdown to control which
sound fires on each detection event. All new settings persist in `settings.json`.
The detection engine suppresses alert sounds while recording is active.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: tkinter (UI), pydantic + platformdirs (config/paths),
pygame-ce (playback), `sounddevice` + `soundfile` *(NEW — mic capture & WAV I/O)*,
pytest + pytest-mock (testing)
**Storage**: Existing JSON settings file at `user_config_dir("CatGuard")/settings.json`;
recorded WAV files at `user_data_dir("CatGuard")/alerts/`
**Testing**: pytest, pytest-mock; unit tests mock `sounddevice`; integration tests
use real filesystem with temporary directories
**Target Platform**: Windows 10+, Ubuntu 20.04+, macOS 12+ (desktop)
**Project Type**: Desktop application (tkinter + pystray)
**Performance Goals**: ≤200ms p95 detection latency (unchanged); recording is
user-initiated (10 s max); playback-mode dispatch <5 ms
**Constraints**: <100MB memory; no network calls; no new UI framework; tkinter main
thread must never block; bool flag on `root` for recording-suppression signal
(consistent with existing `_main_window_visible` pattern)
**Scale/Scope**: Single-user desktop app; typically ≤ hundreds of WAV files in
the alerts folder

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Status |
|-----------|-------------|--------|
| I. Test-First Development | `recording.py` and all Settings/audio changes MUST have failing tests written before implementation; Red-Green-Refactor enforced | ✅ PASS |
| II. Observability & Logging | `recording.py` MUST log session start/stop/save/discard/error; `audio.py` playback-mode selection MUST log which mode fired and why | ✅ PASS |
| III. Simplicity & Clarity | One new module (`recording.py`); existing modules extended minimally; boolean flag for recording-suppression signal; no new UI framework | ✅ PASS |
| IV. Integration Testing | Playback-mode dispatch, Settings persistence, and record→save→library flow each require integration tests | ✅ PASS |
| V. Versioning & Breaking Changes | All `Settings` changes are additive new fields with defaults; no existing field renamed or removed; backward-compatible with existing `settings.json` | ✅ PASS |

**Post-design re-check**: ✅ All gates still pass after Phase 1 design.

## Project Structure

### Documentation (this feature)

```text
specs/004-add-record-sound/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── config.md        ← Phase 1 output (updated settings.json schema)
└── tasks.md             ← Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code

```text
src/catguard/
├── recording.py              ← NEW: Recorder class, get_alerts_dir(), save_recording(),
│                                    open_alerts_folder()
├── audio.py                  ← MODIFY: add play_alert() mode dispatcher; keep
│                                    play_random_alert() as internal helper
├── config.py                 ← MODIFY: add use_default_sound (bool, default True)
│                                    and pinned_sound (str, default "") to Settings;
│                                    mirror in SettingsFormModel
├── main.py                   ← MODIFY: call play_alert() instead of play_random_alert();
│                                    expose root._recording_active flag
└── ui/
    └── settings_window.py    ← MODIFY: add Record/Stop button with 10 s progress,
                                     Use Default Sound checkbox, Play Only This Sound
                                     dropdown, alerts folder read-only field + Browse…

tests/unit/
├── test_recording.py         ← NEW: Recorder, save_recording, silence detection,
│                                    filename sanitisation, get_alerts_dir
├── test_audio.py             ← EXTEND: play_alert() mode dispatch (default/pinned/random)
├── test_config.py            ← EXTEND: new fields, defaults, round-trip persistence
└── test_settings_window.py   ← EXTEND: SettingsFormModel new fields, to_settings(),
                                      from_settings(), dropdown enable/disable logic

tests/integration/
├── test_audio_integration.py      ← EXTEND: recording-suppression; mode dispatch
│                                          end-to-end with saved settings
└── test_recording_integration.py  ← NEW: full record→stop→name→save→library flow
                                          with mocked sounddevice
```

**Structure Decision**: Single-project layout (existing). One new module `recording.py`
owns all mic-capture and WAV-I/O concerns, keeping `audio.py` focused on playback only.
Settings changes are additive fields on the existing Pydantic model.
