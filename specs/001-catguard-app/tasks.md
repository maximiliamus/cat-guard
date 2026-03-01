# Tasks: CatGuard App

**Input**: Design documents from `specs/1-catguard-app/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/config.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Exact file paths included in all descriptions

---

## Phase 1: Setup

**Purpose**: Project skeleton, dependencies, assets, and test infrastructure

- [X] T001 Create directory structure: `src/catguard/`, `src/catguard/ui/`, `assets/sounds/`, `tests/unit/`, `tests/integration/`
- [X] T002 Create `requirements.txt` with all dependencies per plan.md
- [X] T003 [P] Create `src/catguard/__init__.py` with package version constant
- [X] T004 [P] Add placeholder `assets/sounds/default.wav` (silent or short tone, bundled default alert)
- [X] T005 [P] Add placeholder `assets/icon.png` (64×64 RGBA tray icon)
- [X] T006 [P] Create `pytest.ini` (or `pyproject.toml` `[tool.pytest.ini_options]`) configuring `testpaths = tests`

**Checkpoint**: `pip install -r requirements.txt` succeeds; `pytest --collect-only` finds no errors

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure required by ALL user stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T009 Write `tests/unit/test_config.py`: tests for defaults, load/save round-trip, missing keys, corrupt file reset, stale path pruning, atomic write, and logging on first-run/corrupt-reset (RED — fails until T007/T008/T010 implemented)
- [X] T007 Implement `src/catguard/config.py`: `Settings` pydantic model with all fields and defaults (`camera_index`, `confidence_threshold`, `cooldown_seconds`, `sound_library_paths`, `autostart`)
- [X] T008 Implement `load_settings()` and `save_settings()` in `src/catguard/config.py` (atomic `.tmp` rename write; missing-key defaults; corrupt-file reset; stale-path validator)
- [X] T010 Configure structured logging in `src/catguard/config.py` (module-level `logging.getLogger`; log on first-run write and corrupt-file reset)
- [X] T011 Create `src/catguard/main.py` skeleton: imports, `stop_event = threading.Event()`, platform-safe `main()` stub (no logic yet — wired up in later phases)

**Checkpoint**: `pytest tests/unit/test_config.py` — all tests pass; `load_settings()` and `save_settings()` work correctly

---

## Phase 3: User Story 1 — Cat Detection and Alert (Priority: P1) 🎯 MVP

**Goal**: App detects a cat via YOLO11n on the webcam feed and plays the default alert sound. Cooldown suppresses repeat alerts. Works when screen is locked.

**Independent Test**: Run `python -m catguard`, place a cat (or printed cat photo) in front of the webcam — a sound should play within 200ms. No sound should replay until 15s have elapsed.

### Implementation

- [X] T014 [US1] Write `tests/unit/test_detection.py`: tests for cooldown suppression (mock YOLO + clock), no-detection path, confidence-below-threshold path, callback invocation (RED)
- [X] T015 [P] [US1] Write `tests/unit/test_audio.py`: tests for random selection across multiple files, fallback to default when list is empty, unsupported format filtering (RED)
- [X] T012 [US1] Implement `src/catguard/detection.py`: `DetectionLoop` class with `__init__(settings, on_cat_detected)`, `start()`, `stop()`, and `_run()` daemon thread; YOLO11n model load (`yolo11n.pt`, `classes=[15]`, `device="cpu"`); OpenCV `VideoCapture` loop; cooldown logic with `datetime`; `DetectionEvent` logging on every detection
- [X] T013 [P] [US1] Implement `src/catguard/audio.py`: `init_audio()` (`pygame.mixer.init()` only), `play_random_alert(paths, default_path)` (random selection, daemon thread, fallback to default), `shutdown_audio()`
- [X] T016 [US1] Wire detection + audio in `src/catguard/main.py`: start `DetectionLoop` with `on_cat_detected` callback calling `play_random_alert`; call `init_audio()` at startup; call `shutdown_audio()` on exit
- [X] T017 [US1] Write `tests/integration/test_detection_integration.py`: load real YOLO11n model; feed a synthetic BGR frame with a cat image; assert callback fires; assert cooldown suppresses second call within window
- [X] T018 [P] [US1] Write `tests/integration/test_audio_integration.py`: call `play_random_alert` with a real test WAV file; assert playback completes without error

**Checkpoint**: `python -m catguard` detects cat and plays default sound. `pytest tests/unit/test_detection.py tests/unit/test_audio.py tests/integration/` all pass.

---

## Phase 4: User Story 4 — System Tray Access (Priority: P2)

**Goal**: App runs in the system tray with "Settings..." and "Exit" menu items. Closing the settings window does not quit the app. Autostart toggle works via the tray menu.

**Independent Test**: Launch app → right-click tray icon → verify "Settings..." opens Settings window → verify "Exit" fully quits. Settings window shows all config options.

### Implementation

- [X] T039 [US4] Write `tests/unit/test_tray.py`: tests for menu construction (Settings… and Exit items present), `on_exit` sets `stop_event`, macOS `run_detached` branch selected when `platform.system() == "Darwin"`, Wayland AppIndicator backend selected when `XDG_SESSION_TYPE=wayland` (RED)
- [X] T019 [US4] Implement `src/catguard/tray.py`: `build_tray_icon(root, stop_event) → pystray.Icon`; menu with `Settings…` (dispatches `root.after(0, ...)`) and `Exit` (stops tray + sets stop_event + destroys root); platform-safe macOS `run_detached` vs daemon thread logic; Wayland AppIndicator backend detection
- [X] T040 [P] [US4] Write `tests/unit/test_settings_window.py`: tests for form population from `Settings` object, `on_save` calls `save_settings` with updated values, camera dropdown populated from `list_cameras()` mock result, autostart checkbox state matches `Settings.autostart` (RED)
- [X] T020 [P] [US4] Implement `src/catguard/ui/settings_window.py`: `open_settings_window(root, settings, on_save)`; `tk.Toplevel` with camera dropdown (populated from `Camera` list), sensitivity slider, cooldown spinbox, sound library list (Add/Remove buttons), autostart checkbox; `on_save` calls `save_settings` and propagates changes
- [X] T021 [P] [US4] Implement camera enumeration helper in `src/catguard/detection.py`: `list_cameras() → list[Camera]` (tries `cv2.VideoCapture(i)` for i in 0..7, returns available ones with display names)
- [X] T022 [US4] Wire tray into `src/catguard/main.py`: hidden tkinter root (`root.withdraw()`), build tray icon; `on_save` writes updated settings to disk via `save_settings()`; `DetectionLoop` reads fresh settings on each frame (pull model — no hot-reload callback required)
- [X] T037 [US4] Write `tests/unit/test_autostart.py`: tests for enable/disable/is_enabled on each platform (mock `Path.exists`, `win32com`, `subprocess`, `plistlib`) (RED)
- [X] T023 [US4] Implement `src/catguard/autostart.py`: `enable_autostart()`, `disable_autostart()`, `is_autostart_enabled()` with platform dispatch (Windows: `.lnk` via `win32com`; macOS: `plistlib` LaunchAgent; Linux: XDG `.desktop`); connect to autostart checkbox `on_save` in settings window

**Checkpoint**: `pytest tests/unit/test_tray.py tests/unit/test_settings_window.py tests/unit/test_autostart.py` all pass; tray icon visible; Settings… menu item opens window with all controls; Exit quits cleanly; autostart toggle creates/removes the correct file on each platform.

---

## Phase 5: User Story 2 — Camera Setup (Priority: P2)

**Goal**: User can select which camera to use from the Settings window. Selected camera index is persisted and used by the detection loop.

**Independent Test**: With two cameras connected, select the secondary camera in Settings → verify detection loop uses that camera's feed.

### Implementation

- [X] T026 [US2] Write `tests/unit/test_detection.py` (extend): test that `DetectionLoop` uses the configured `camera_index`; test graceful handling when camera index is unavailable (mock `cv2.VideoCapture`) (RED)
- [X] T024 [US2] Update `DetectionLoop._run()` in `src/catguard/detection.py` to use `settings.camera_index` when opening `cv2.VideoCapture(settings.camera_index)`; log a warning if the camera fails to open
- [X] T025 [P] [US2] Update camera dropdown in `src/catguard/ui/settings_window.py` to call `list_cameras()` on window open and populate with available cameras; save selected index to `settings.camera_index`

**Checkpoint**: Settings window shows all available cameras; selecting a different camera and saving causes the detection loop to use that camera.

---

## Phase 6: User Story 3 — Detection Sensitivity and Sound Customization (Priority: P3)

**Goal**: User can adjust detection confidence threshold and manage a sound library (upload multiple MP3/WAV files). On each detection, a random sound from the library is played.

**Independent Test**: Upload 3 different WAV files → trigger detection 10 times → verify all 3 sounds appear in the rotation (random, not always the same).

### Implementation

- [X] T031 [US3] Write `tests/unit/test_detection.py` (extend): test confidence threshold is passed correctly to YOLO mock; test that settings update takes effect on next frame via pull model (RED) — **Note**: `confidence_threshold` is inverse to sensitivity: high sensitivity = low threshold (e.g. 0.20), low sensitivity = high threshold (e.g. 0.70)
- [X] T027 [US3] Update `DetectionLoop._run()` in `src/catguard/detection.py` to use `settings.confidence_threshold` as `conf=` in `model.predict()`; re-reads `settings` reference on each frame via pull model (consistent with T022)
- [X] T028 [P] [US3] Update `src/catguard/audio.py`: `play_random_alert` already accepts `paths`; ensure it handles the case of a single file (always plays same file — not a bug), and skips non-MP3/WAV files with a logged warning
- [X] T029 [P] [US3] Update sound library UI in `src/catguard/ui/settings_window.py`: Add/Remove buttons open `tkinter.filedialog.askopenfilenames(filetypes=[("Audio", "*.mp3 *.wav")])`; show library list with filenames; save paths to `settings.sound_library_paths`
- [X] T030 [P] [US3] Update sensitivity slider in `src/catguard/ui/settings_window.py`: range 0.0–1.0, step 0.05; **invert direction** so slider min = high sensitivity (low threshold e.g. 0.20), slider max = low sensitivity (high threshold e.g. 0.70); save to `settings.confidence_threshold`; show current threshold value label

**Checkpoint**: Uploading sounds and adjusting sensitivity in Settings takes effect immediately; random sound rotation confirmed by running detection multiple times.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T032 [P] Add `__main__.py` in `src/catguard/` so `python -m catguard` works
- [X] T033 [P] Add `pyproject.toml` or `setup.cfg` with project metadata and entry point `catguard = catguard.main:main`
- [X] T034 [P] Add top-level `logging` configuration in `src/catguard/main.py`: rotating file handler to `platformdirs.user_log_dir("CatGuard")`; INFO level by default; DEBUG if `--debug` flag passed
- [X] T035 [P] Add graceful SIGTERM / SIGINT handler in `src/catguard/main.py` to stop detection, shutdown audio, and remove tray icon cleanly
- [X] T036 [P] Validate `quickstart.md` against actual setup: follow instructions from scratch, confirm all steps work
- [X] T038 [P] Code review: verify no camera frames are stored or transmitted anywhere (`grep` for `imwrite`, `imencode`, `socket`, `requests`, `http`) ✅ DONE (grep found zero matches)
- [X] T041 [P] Benchmark `DetectionLoop` p95 latency and peak memory: assert ≤200ms per frame using `time.perf_counter` and ≤100MB peak RSS using `tracemalloc`; run against real YOLO model with synthetic frames; add to CI as a performance gate (covers FR6 and constitution Tech Constraints)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1 — Detection & Alert)**: Depends on Phase 2 — MVP; implement first
- **Phase 4 (US4 — System Tray)**: Depends on Phase 2; integrates with Phase 3 via `main.py`
- **Phase 5 (US2 — Camera Setup)**: Depends on Phase 4 (Settings window already exists)
- **Phase 6 (US3 — Sound Customization)**: Depends on Phase 4 (Settings window already exists)
- **Phase 7 (Polish)**: Depends on all prior phases

### User Story Dependencies

- **US1 (P1)**: No story dependencies — implement first
- **US4 (P2)**: Integrates with US1 via `main.py`; independently testable for tray/UI
- **US2 (P2)**: Extends Settings window from US4; independently testable
- **US3 (P3)**: Extends Settings window from US4; independently testable

### Parallel Opportunities Per Phase

**Phase 1**: T003, T004, T005, T006 all parallel  
**Phase 2**: T009 → T007 → T008 → T010 → T011 (sequential; TDD order enforced)  
**Phase 3**: T014 [then T015 P] → T012 [then T013 P] → T016 → T017 [then T018 P]  
**Phase 4**: T039 → T019; T040 [P with T039] → T020 [P] + T021 [P]; T022; T037 → T023  
**Phase 5**: T026 → T024 + T025 [P]  
**Phase 6**: T031 → T027 + T028 [P] + T029 [P] + T030 [P]  
**Phase 7**: T032, T033, T034, T035, T036, T038, T041 all parallel  

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (config module + tests)
3. Complete Phase 3: US1 (detection + audio + main wiring)
4. **STOP and VALIDATE**: cat detected → sound played within 200ms
5. Deploy / demo

### Incremental Delivery

1. Setup + Foundational → config works
2. US1 → detection + audio → **MVP demo**
3. US4 → system tray + settings window
4. US2 → camera selection
5. US3 → sound library + sensitivity
6. Polish → logging, packaging, cleanup

---

## Notes

- `[P]` = different files, no incomplete dependencies → can run in parallel
- `[USN]` = maps task to user story for traceability
- Constitution rule (Principle I): all implementation tasks MUST be preceded by their test tasks (TDD: Red-Green-Refactor strictly enforced)
- No camera frames may be persisted or transmitted (T038 enforces this)
- YOLO11n weights auto-download on first run; cache at `~/.ultralytics/assets/`
