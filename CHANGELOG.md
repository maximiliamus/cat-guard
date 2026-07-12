# Changelog

All notable changes to CatGuard are documented in this file.
Releases follow [semantic versioning](https://semver.org/).

---

## [Unreleased] — branch `016-tracking-video-clips`

### Added
- **Tracking by video clips** — new tracking mode that records annotated `.avi`/`.mp4` clips of detected cat sessions instead of (or alongside) individual screenshots.
  - Configurable output format: `MJPG`, `XVID`, or `MP4V`.
  - Configurable clip frame rate (`videoclip_fps`).
  - Live elapsed-time counter on the "Cat detected" overlay strip (e.g. "Cat detected: 12s") so each clip is self-explanatory without additional metadata.
  - Outcome strip at session end: green "Cat disappeared after alert: Ns" or red "Cat remained after alert: Ns".
  - Atomic safe-write: frames streamed to a `.partial` temp file; renamed to the final path only when the clip is fully validated.
  - Sampler thread writes clip frames at the configured FPS independent of the detection loop rate.
  - Continuity sampling: repeats the latest processed frame when detection is slower than the selected clip FPS, preserving real session duration.
  - Deadline-based sampler timing skips missed ticks without drift or catch-up bursts.
  - Async finalization: session reset does not block the detection loop, while shutdown waits for pending finalizers.
  - Finalization failures are logged and surfaced through the existing non-blocking error notification path; readable partial clips are preserved when possible.

### Changed
- Settings dialog reorganized into dedicated tabs and extended with inline parameter help, tracking mode selector (`Screenshots` / `Video clips`), video format, and clip FPS fields.
- Run and build scripts updated to activate the project virtual environment before launch.

---

## [Unreleased] — commits on `master` after v0.5.0

### Added
- **Log viewer and log search** (spec 011) — searchable in-app log viewer.
- **Cat session tracking** (spec 012) — per-session statistics and history.
- **Cat session tracking improvements** (spec 014) — refined session boundary detection.
- **Directory menu links** (spec 015) — tray/menu shortcuts to open app data directories.

### Fixed
- Tray icon appearance after the system wakes from sleep.

---

## [0.5.0] — 2026-03-11

### Added
- **Detection FPS config** — new `detection_fps` setting; settings dialog updated to expose it.
- **ONNX Runtime migration** (spec 010) — replaced Ultralytics with `onnxruntime` for inference; re-enabled macOS and Linux distribution builds.
- Single-instance enforcement: only one running copy of the app is allowed at a time.

### Changed
- ONNX models are no longer bundled inside the executable; they are loaded from the data directory at runtime.
- UI/UX simplified to focus on taking and managing alert photos.
- Release artifacts: only the current and previous release are kept.

### Performance
- CPU usage optimised for the detection loop.

---

## [0.4.0] — 2026-03-09

### Added
- **Self-executable build** (spec 009) — single-file Windows `.exe` via PyInstaller; CI workflow to build and publish releases.
- **Photo action panel** (spec 008) — in-app panel to review and act on alert screenshots.
- **Miscellaneous improvements** (spec 007) — minor UX and stability fixes.
- **Pause / continue tracking** (spec 006) — tray menu actions to temporarily suspend and resume detection.
- **Alert effectiveness tracking** (spec 005) — records whether the deterrent sound succeeded in driving the cat away.
- **Sound recording** (spec 004) — record and manage custom alert sounds from within the app.

---

## [0.3.0 and earlier] — initial development

- **Cat detection screenshots** (spec 003) — save annotated JPEG on detection; bounding boxes, sound label and outcome overlay.
- **Main window from tray** (spec 002) — open the main application window from the system tray icon.
- Initial application scaffold: system tray icon, settings window, webcam capture loop with YOLO-based cat detection.
