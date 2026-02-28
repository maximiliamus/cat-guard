# Implementation Plan: CatGuard App

**Branch**: `1-catguard-app` | **Date**: 2026-02-28 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/1-catguard-app/spec.md`

---

## Summary

CatGuard is a cross-platform desktop application that monitors a webcam for cats using a YOLO11n object detection model and plays a randomly selected alert sound when a cat is detected. The app runs silently in the system tray, persists settings to a platform-appropriate config directory, and supports opt-in autostart on login without using the Windows registry.

---

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**:
- `ultralytics` — YOLO11n cat detection (`yolo11n.pt`, COCO class 15)
- `opencv-python` — webcam capture (`VideoCapture`)
- `pystray` + `Pillow` — cross-platform system tray icon and menu
- `pygame` — audio playback (MP3/WAV via SDL_mixer; mixer-only init, no display)
- `platformdirs` — platform-correct config directory
- `pydantic` — settings model with validation
- `pywin32` — Windows: tray icon backend + `.lnk` shortcut creation (Windows only)

**Storage**: JSON config file in `user_config_dir("CatGuard")` (platformdirs)  
**Testing**: `pytest` with `unittest.mock` for camera/audio/YOLO stubs  
**Target Platform**: Windows 10+, macOS 12+, Linux (X11 and Wayland via AppIndicator)  
**Project Type**: desktop-app (single process, system tray, tkinter settings window)  
**Performance Goals**: <200ms p95 detection latency per frame; <100MB core service memory  
**Constraints**: No Windows registry; cross-platform; in-memory frames only; fully offline after first YOLO model download  
**Scale/Scope**: Single-user desktop app; ~5 source modules; no server component

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Test-First Development | ✅ PASS | All modules have unit tests defined before implementation; pytest |
| II. Observability & Logging | ✅ PASS | Python `logging` module; all detection events and actions logged |
| III. Simplicity & Clarity | ✅ PASS | Single-process app; no unnecessary abstraction layers |
| IV. Integration Testing | ✅ PASS | Integration tests for YOLO+camera pipeline and audio playback |
| V. Versioning & Breaking Changes | ✅ PASS | Config schema versioned; breaking changes documented in `contracts/config.md` |

**Post-design re-check**: All gates still pass. No violations.

---

## Project Structure

### Documentation (this feature)

```text
specs/1-catguard-app/
├── plan.md              ← this file
├── spec.md              ← feature specification
├── research.md          ← Phase 0 research decisions
├── data-model.md        ← entity definitions and state machine
├── quickstart.md        ← developer getting-started guide
├── contracts/
│   └── config.md        ← settings.json schema contract
├── checklists/
│   └── requirements.md  ← spec validation checklist
└── tasks.md             ← Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
src/
└── catguard/
    ├── __init__.py
    ├── main.py                  # Entry point: wires tray + detection + audio
    ├── config.py                # Settings load/save (pydantic + platformdirs + JSON)
    ├── detection.py             # YOLO11n inference loop (background daemon thread)
    ├── audio.py                 # pygame.mixer playback (random sound selection)
    ├── autostart.py             # Cross-platform autostart (startup folder / LaunchAgent / XDG)
    ├── tray.py                  # pystray system tray icon and menu
    └── ui/
        └── settings_window.py  # tkinter Settings window (camera, sensitivity, sounds, autostart)

assets/
├── icon.png                    # System tray icon (64×64 RGBA)
└── sounds/
    └── default.wav             # Built-in default alert sound

tests/
├── unit/
│   ├── test_config.py          # Settings load/save/validation/defaults/migration
│   ├── test_detection.py       # Cooldown logic, confidence filtering (mocked YOLO)
│   ├── test_audio.py           # Random selection, fallback to default, format filtering
│   └── test_autostart.py       # Enable/disable/is_enabled per platform (mocked filesystem)
└── integration/
    ├── test_detection_integration.py  # Real YOLO model + simulated cat image frame
    └── test_audio_integration.py      # Real pygame.mixer playback of test WAV/MP3
```

**Structure Decision**: Single-project layout. No web/mobile components. All source under `src/catguard/` for clean imports and packaging.

---

## Dependency List

```
# requirements.txt
ultralytics>=8.3.0       # YOLO model; pulls in torch, torchvision, pydantic, platformdirs
opencv-python>=4.9.0
pystray>=0.19.4
Pillow>=10.0.0
pygame>=2.5.0
pywin32>=306;sys_platform=="win32"

# dev / test
pytest>=8.0.0
pytest-mock>=3.12.0
```

---

## Module Responsibilities

### `config.py`
- `load_settings() → Settings`: Load from disk; write defaults on first run; reset on corruption.
- `save_settings(settings: Settings)`: Atomic write via `.tmp` rename.
- `Settings`: pydantic `BaseModel` with all fields, validators, and defaults.

### `detection.py`
- `DetectionLoop(settings, on_cat_detected_callback)`: Background daemon thread.
- `run()`: Opens webcam → captures frames → runs YOLO inference → fires callback if cat detected and cooldown elapsed.
- Cooldown managed internally; emits `DetectionEvent` to logger on every detection.

### `audio.py`
- `init_audio()`: `pygame.mixer.init()` only (no display).
- `play_random_alert(paths: list[str], default_path: Path)`: Selects random file; falls back to default if list empty.
- `shutdown_audio()`: `pygame.mixer.quit()`.

### `autostart.py`
- `enable_autostart()`, `disable_autostart()`, `is_autostart_enabled() → bool`.
- Platform dispatch via `platform.system()`.

### `tray.py`
- `build_tray_icon(root, stop_event) → pystray.Icon`: Constructs icon with `Settings...` and `Exit` menu items.
- `on_settings(root)`: Dispatches to tkinter main thread via `root.after(0, ...)`.
- `on_exit(icon, root, stop_event)`: Stops tray + sets stop event + destroys root.

### `ui/settings_window.py`
- `open_settings_window(root, settings, on_save)`: Creates/raises `tk.Toplevel`.
- Fields: camera dropdown, sensitivity slider, cooldown spinbox, sound library list (add/remove), autostart checkbox.
- `on_save`: persists via `save_settings`; propagates changes to running detection loop.

### `main.py`
- Wires all modules together.
- Starts detection thread.
- Builds tray icon.
- Runs tkinter `mainloop()` on main thread (platform-safe pattern).

---

## Cross-Platform Notes

| Concern | Approach |
|---|---|
| macOS tray | `icon.run_detached()` before `root.mainloop()` |
| Linux Wayland tray | `PYSTRAY_BACKEND=appindicator` when `XDG_SESSION_TYPE=wayland` |
| Autostart — Windows | `.lnk` in `%APPDATA%\...\Startup\` via `win32com` |
| Autostart — macOS | `~/Library/LaunchAgents/com.catguard.app.plist` via `plistlib` |
| Autostart — Linux | `~/.config/autostart/catguard.desktop` (XDG spec) |
| Config directory | `platformdirs.user_config_dir("CatGuard")` |
| Audio on locked screen | `pygame.mixer` uses OS audio session; not suspended on lock |

---

## Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| YOLO11n accuracy insufficient for edge cases (cat obscured, unusual angle) | Medium | Expose confidence threshold in settings; upgrade path to `yolo11s` |
| `pystray` AppIndicator not available on some Linux distros | Low | Graceful fallback to `xorg` backend with a logged warning |
| `pygame.mixer` conflicts with other audio libs in the process | Low | Initialize mixer once at startup; never call `pygame.init()` |
| PyTorch process RAM exceeds 100MB on low-memory systems | Medium | ONNX export (`yolo11n.onnx`) reduces RAM; document as optimization step |
| `pywin32` missing on Windows | Low | Add to `requirements.txt` with `sys_platform=="win32"` guard |
