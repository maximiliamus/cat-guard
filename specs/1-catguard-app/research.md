# Research: CatGuard App

**Phase**: 0 — Pre-design research  
**Date**: 2026-02-28  
**Feature**: [specs/1-catguard-app/spec.md](spec.md)

---

## R1 — Cat Detection: YOLO Model

**Decision**: `ultralytics` Python package with `yolo11n.pt` (YOLO11 Nano)

**Rationale**:
- YOLO11n has the best accuracy-per-parameter in the ultralytics family: 39.5 mAP50-95, ~17–56ms CPU inference, <10MB weights, <250MB total process RAM.
- Passes both spec constraints: <200ms p95 latency and <100MB core footprint.
- `classes=[15]` in `predict()` filters to cats server-side (COCO class 15 = "cat").
- Fully offline after first download; weights cached in `~/.ultralytics/assets/`.
- API: `model.predict(frame_bgr, classes=[15], conf=threshold, device="cpu", verbose=False)`.
- Optional: export to ONNX for ~2–3× CPU speedup with no code change.

**Confidence threshold**: Start at `0.40`; expose as `confidence_threshold` setting (range 0.0–1.0).

**Upgrade path**: `yolo11s.pt` (+8 mAP, ~90ms CPU); `yolo26n.pt` (~39ms CPU, NMS-free, Jan 2026).

**Alternatives considered**:
- YOLOv8: identical API, strictly worse efficiency — acceptable fallback.
- Darknet/YOLOv4: unmaintained, no Python-first API.
- YOLOv5: superseded by YOLO11 in all metrics.

---

## R2 — System Tray: Cross-Platform

**Decision**: `pystray` with `Pillow` for icon rendering

**Rationale**:
- Only purpose-built cross-platform tray library (Win32 / Cocoa / GTK / AppIndicator backends).
- Minimal dependency surface alongside PyTorch/OpenCV/YOLO.
- Threading model: detection loop → daemon thread; tray → daemon thread (Win/Linux) or `icon.run_detached()` (macOS); tkinter → main thread.
- Settings window opened via `root.after(0, ...)` from pystray's callback thread (thread-safe).

**Linux Wayland**: Set `PYSTRAY_BACKEND=appindicator` when `XDG_SESSION_TYPE=wayland`. Requires `python3-gi gir1.2-ayatanaappindicator3-0.1` (present on most GNOME/KDE installs).

**Alternatives considered**:
- PyQt6 `QSystemTrayIcon`: truly cross-platform including native Wayland, but adds ~50MB and forces a full Qt event loop — only preferred if the entire UI is already Qt-based.
- `rumps`: macOS only.
- `infi.systray`: Windows only.

---

## R3 — Autostart on Login: Cross-Platform, No Registry

**Decision**: Hand-rolled stdlib implementation (3 platform branches, ~25 lines each). No third-party library.

**Rationale**: All available autostart libraries (`startup`, `auto-start`) are abandoned (< 4 stars, 3–6 years without commits). A hand-rolled implementation using stdlib is simpler and has no stale dependency risk.

| Platform | Mechanism | File | Dependencies |
|---|---|---|---|
| Windows | User Startup folder shortcut | `%APPDATA%\...\Startup\CatGuard.lnk` | `pywin32` (already needed by pystray) |
| macOS | LaunchAgent plist | `~/Library/LaunchAgents/com.catguard.app.plist` | `plistlib` (stdlib) |
| Linux | XDG Autostart .desktop | `~/.config/autostart/catguard.desktop` | stdlib only |

- Detection state: `Path.exists()` on all three platforms — no OS API calls needed.
- Windows: `.lnk` shortcut (no registry); visible in Task Manager Startup tab.
- macOS: `plistlib.dump()` to write; `launchctl load/unload` to activate current session.
- Linux: freedesktop XDG autostart spec; supported by GNOME, KDE, XFCE, MATE, Cinnamon.

**Alternatives considered**:
- Windows registry `HKCU\Run`: explicitly prohibited by spec.
- `winshell`: wraps `win32com` but is an extra dependency with no benefit.
- `systemd --user` service: more powerful but doesn't integrate with display managers on non-systemd distros; XDG is more portable.

---

## R4 — Settings Storage: Config File Format

**Decision**: `platformdirs.user_config_dir("CatGuard")` + JSON + `pydantic.BaseModel`

**Rationale**:
- `platformdirs` (4.9.2, Feb 2026): actively maintained fork of `appdirs`; already a transitive dep of `ultralytics` — zero new dep cost. Correct paths on all platforms.
- JSON: stdlib read+write; supports `list[str]` (sound library paths) natively. TOML would require `tomli_w` for writing.
- `pydantic.BaseModel` (v2): already a hard dep of `ultralytics`. Provides typed defaults, range validation (`Field(ge=0, le=1)`), partial-dict loading (`model_validate`), and atomic write via `.tmp` + `Path.replace()`.

**Config file location**:
| Platform | Path |
|---|---|
| Windows | `%APPDATA%\CatGuard\settings.json` |
| macOS | `~/Library/Application Support/CatGuard/settings.json` |
| Linux | `~/.config/CatGuard/settings.json` |

**Alternatives considered**:
- TOML: better human-editable, but `tomllib` is read-only in stdlib.
- INI: no native list support — sound library paths require workarounds.
- `pydantic-settings`: env-var layering unneeded for a desktop GUI app.
- `dynaconf`: multi-environment server tool; wrong abstraction level.

---

## R5 — Audio Playback: Cross-Platform MP3/WAV

**Decision**: `pygame.mixer` (initialize mixer only, never `pygame.init()`)

**Rationale**:
- Native MP3 + WAV via bundled SDL_mixer; no system packages required on Windows or macOS.
- Screen-lock safe: OS audio session (WASAPI/CoreAudio/PulseAudio) is never suspended on lock.
- Non-blocking: `Sound.play()` dispatches to SDL's internal audio thread and returns immediately.
- Self-contained: SDL2 + SDL_mixer ship inside the pip wheel.
- Key: use `pygame.mixer.init()` only — never `pygame.init()` — to bypass all SDL video requirements.

**Alternatives considered**:
- `playsound3`: zero Python audio deps, but Linux requires GStreamer or `mpg123` — less hermetic.
- `sounddevice + soundfile`: excellent for WAV; MP3 support is unreliable from pip on Linux.
- `pydub`: requires external `ffmpeg` binary — unacceptable for zero-friction install.
- `python-vlc`: requires VLC installed on user's machine — too heavy.

---

## Resolution Summary

| Clarification in spec | Resolved by |
|---|---|
| YOLO model choice | R1: `ultralytics` + `yolo11n.pt` |
| Cross-platform tray | R2: `pystray` |
| Autostart without registry | R3: Hand-rolled, startup folder / LaunchAgent / XDG |
| Settings storage | R4: `platformdirs` + JSON + `pydantic` |
| Audio playback | R5: `pygame.mixer` |

All NEEDS CLARIFICATION items resolved. No blockers for Phase 1 design.
