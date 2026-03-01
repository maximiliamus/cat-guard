# Tasks: Audio Recording & Playback Controls

**Input**: Design documents from `/specs/004-add-record-sound/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/config.md ✅ quickstart.md ✅

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (touches different files, no incomplete dependencies)
- **[Story]**: User story this task belongs to (US1, US2, US3)
- Exact file paths included in every task description

---

## Phase 1: Setup

**Purpose**: Add new dependencies and prepare the project for feature work.

- [X] T001 Add `sounddevice` and `soundfile` to `requirements.txt` and `pyproject.toml`

**Checkpoint**: `python -c "import sounddevice, soundfile; print('OK')"` passes in the project venv.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure required by all three user stories — `Settings` model extension, `SettingsFormModel` extension, `Recorder` class, `play_alert()` dispatcher, and recording-suppression signal. Must be complete before any user story phase begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Extend `Settings` in `src/catguard/config.py` — add `use_default_sound: bool = True` and `pinned_sound: str = ""` fields with validators (reset stale `pinned_sound` path to `""` on load)
- [X] T003 [P] Write unit tests for new `Settings` fields in `tests/unit/test_config.py` — default values, round-trip persistence (`save_settings` → `load_settings`), stale `pinned_sound` validator, backward-compat load of old JSON without the new keys
- [X] T004 [P] Extend `SettingsFormModel` in `src/catguard/ui/settings_window.py` — add `use_default_sound` and `pinned_sound` fields; update `from_settings()` and `to_settings()`
- [X] T005 [P] Write unit tests for `SettingsFormModel` extensions in `tests/unit/test_settings_window.py` — `from_settings` / `to_settings` round-trip for both new fields
- [X] T006 [P] Create `src/catguard/recording.py` — `Recorder` class (`start()`, `stop()`, `is_recording`), `get_alerts_dir()` (resolves `user_data_dir("CatGuard")/alerts`), `save_recording()`, `open_alerts_folder()`, `sanitise_filename()`, `is_silent()` (NumPy RMS < 100 guard)
- [X] T007 [P] Write unit tests for `recording.py` in `tests/unit/test_recording.py` — `get_alerts_dir` path by platform, `sanitise_filename` (special chars, spaces, path traversal, empty string), `is_silent` (zero-length, RMS below/above threshold), `save_recording` with tmp dir, `open_alerts_folder` (mock `os.startfile`/`subprocess`)
- [X] T008 Add `play_alert(settings, default_path)` dispatcher to `src/catguard/audio.py` — implements DEFAULT → PINNED → RANDOM priority; delegates to existing `_play_async`; logs which mode fired and why
- [X] T009 Write unit tests for `play_alert()` in `tests/unit/test_audio.py` — DEFAULT mode (use_default_sound=True), PINNED mode (use_default_sound=False, valid pinned_sound), RANDOM mode (use_default_sound=False, pinned_sound=""), RANDOM fallback (library empty), PINNED fallback when file missing (resets to RANDOM)
- [X] T010 Initialise `root._recording_event = threading.Event()` in `src/catguard/main.py` (alongside existing root-attribute flags); update `on_cat_detected` to check `if root._recording_event.is_set(): return` before calling `play_alert()`; replace `play_random_alert()` call with `play_alert(settings, default_sound)`

**Checkpoint**: All unit tests for `test_config.py`, `test_settings_window.py`, `test_recording.py`, and `test_audio.py` pass. `python -m catguard` starts without errors.

---

## Phase 3: User Story 1 — Record and Save a Custom Alert Sound (Priority: P1) 🎯 MVP

**Goal**: User opens Settings, clicks Record, speaks, clicks Stop (or waits 10 s), enters a name, confirms — WAV file is saved to the alerts folder and immediately appears in the library list.

**Independent Test**: Open Settings → click Record → make a sound → click Stop → enter a name → confirm → verify new entry in the library listbox → trigger a detection event → verify the new sound plays.

- [X] T011 [US1] Add Record/Stop button to `src/catguard/ui/settings_window.py` — single button that toggles label between "Record" and "Stop Recording"; disabled while name prompt is showing; on click-Record: creates a `Recorder`, sets `root._recording_event`, starts recording on daemon thread with `root.after(0, _on_recording_done)` callback; on click-Stop or auto-cap: clears `root._recording_event`, shows name prompt
- [X] T012 [US1] Implement name-entry prompt in `src/catguard/ui/settings_window.py` — modal `tk.simpledialog`-style dialog (or `tk.Toplevel`) showing the alerts folder path as context; accepts filename input; on confirm: calls `save_recording()` + adds path to `path_listbox`; on cancel: discards recording; on duplicate filename: warns via `messagebox.askyesno` before overwriting; on silent recording: warns via `messagebox.showwarning` and does not save
- [X] T013 [US1] Add alerts folder read-only display row to `src/catguard/ui/settings_window.py` — `tk.Entry(state="readonly")` showing `get_alerts_dir()` path; "Browse…" button on the same line calling `open_alerts_folder()`
- [X] T014 [US1] Write integration test for the full record→stop→name→save→library flow in `tests/integration/test_recording_integration.py` — mock `sounddevice.rec` and `sounddevice.wait`; assert WAV file written to temp alerts dir; assert path added to library list; assert silent-recording rejection; assert cancel-discards-file behaviour

**Checkpoint**: User Story 1 fully functional and independently testable. A new recording appears in the library and plays on next detection.

---

## Phase 4: User Story 2 — Use Default Sound Toggle (Priority: P1)

**Goal**: "Use Default Sound" checkbox controls whether the built-in default sound overrides the library entirely. Defaults to checked on fresh install. Persists across restarts. Disables the dropdown while checked.

**Independent Test**: Check "Use Default Sound" → save → trigger detection → confirm `default.wav` plays even with library entries present. Uncheck → save → trigger detection → confirm library sound plays.

- [X] T015 [US2] Add "Use Default Sound" checkbox to `src/catguard/ui/settings_window.py` — `tk.Checkbutton` bound to `BooleanVar`; positioned in the sound section above the library list; on toggle: calls `_update_dropdown_state()` to enable/disable the "Play Only This Sound" dropdown; value read into `model.use_default_sound` in `_save()`
- [X] T016 [US2] Wire `use_default_sound` into the save path in `src/catguard/ui/settings_window.py` — `_save()` sets `model.use_default_sound` from checkbox var before calling `model.apply(on_settings_saved)`
- [X] T017 [US2] Write unit tests for the checkbox enable/disable interaction in `tests/unit/test_settings_window.py` — `SettingsFormModel`: `use_default_sound=True` disables dropdown logic; `use_default_sound=False` enables it; verify `to_settings()` serialises both states correctly
- [X] T018 [US2] Write integration test for default-sound toggle persistence in `tests/integration/test_audio_integration.py` — set `use_default_sound=True` in settings, call `play_alert()`, assert `_play_async` receives `default_path`; set `use_default_sound=False` with a library entry, assert library sound is used

**Checkpoint**: User Story 2 fully functional. Checkbox persists, correct sound plays, dropdown visually disabled when checkbox is checked.

---

## Phase 5: User Story 3 — Play a Specific Sound from the Library (Priority: P2)

**Goal**: "Play Only This Sound" dropdown lets the user pin a specific library sound. Empty selection → random. Persists across restarts. Resets to "All" if pinned file is removed.

**Independent Test**: Select a specific sound in the dropdown → save → trigger 3 detection events → confirm same sound plays each time. Remove that sound from the library → confirm dropdown resets to "All" → trigger detection → confirm random playback.

- [X] T019 [P] [US3] Add "Play Only This Sound" `ttk.Combobox` to `src/catguard/ui/settings_window.py` — populated with `["All"] + list(path_listbox.get(0, END))`; refreshes when library list changes (after Add, Remove, or new recording saved); initial value: `"All"` if `model.pinned_sound == ""` else the matching path; disabled when `use_default_sound` checkbox is checked
- [X] T020 [P] [US3] Implement `_update_dropdown_state()` in `src/catguard/ui/settings_window.py` — sets combobox `state="disabled"` when `use_default_sound` is True, `state="readonly"` otherwise; called on checkbox toggle and on window open
- [X] T021 [US3] Wire `pinned_sound` into the save path in `src/catguard/ui/settings_window.py` — `_save()` sets `model.pinned_sound` to `""` when "All" selected, or to the selected path otherwise
- [X] T022 [US3] Implement auto-reset in `src/catguard/ui/settings_window.py` — `_remove_path()` checks if removed path equals current `pinned_sound` var; if so, resets combobox to "All"; `prune_stale_paths` validator in `config.py` already handles the persistence-layer reset on load
- [X] T023 [US3] Write unit tests for dropdown logic in `tests/unit/test_settings_window.py` — `pinned_sound=""` maps to "All"; specific path round-trips through `to_settings()`; dropdown disabled when `use_default_sound=True`; removal of pinned path resets to "All"
- [X] T024 [US3] Write integration test for pinned-sound playback in `tests/integration/test_audio_integration.py` — `pinned_sound` set to a valid path: assert `play_alert()` always calls `_play_async` with that path; `pinned_sound` set to a missing path: assert fallback to random; `pinned_sound=""`: assert random selection from library

**Checkpoint**: All three user stories fully functional. Detection always plays the correct sound per the active playback mode.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: UI layout finalisation, error handling completeness, logging coverage, and quickstart validation.

- [X] T025 [P] Verify all new Settings UI rows in `src/catguard/ui/settings_window.py` use consistent `pad`, column layout, and `Browse…` button positioning on the same line as their path fields (matching spec FR-007 / FR-021 same-line requirement)
- [X] T026 [P] Add structured logging to `src/catguard/recording.py` — log session start, stop (user vs auto-cap), save success (path), save failure (exception), discard (cancel / window close / silent)
- [X] T027 [P] Add structured logging to `src/catguard/audio.py` `play_alert()` — log active mode (DEFAULT / PINNED / RANDOM), the path chosen, and any fallback reason
- [X] T028 [P] Handle microphone-unavailable / permission-denied in `src/catguard/recording.py` — wrap `sounddevice.rec()` launch in try/except `sounddevice.PortAudioError`; on failure: clear `root._recording_event`, reset button label, show non-blocking `messagebox.showerror`; log the exception
- [X] T029 [P] Handle disk-full and write-error in `src/catguard/recording.py` `save_recording()` — catch `OSError`; show non-blocking `messagebox.showerror`; do not add path to library; log exception
- [X] T030 Validate quickstart.md — run `pip install sounddevice soundfile`, start the app, exercise all three user stories manually per `specs/004-add-record-sound/quickstart.md`, confirm the playback-mode table is accurate; update `quickstart.md` if any step is wrong

**Checkpoint**: `pytest` passes green. App starts and all three user stories work end-to-end. Quickstart validated.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **blocks all user story phases**
- **Phase 3 (US1)**: Depends on Phase 2 completion — no dependency on US2 or US3
- **Phase 4 (US2)**: Depends on Phase 2 completion — no dependency on US1 or US3
- **Phase 5 (US3)**: Depends on Phase 2 completion — no dependency on US1 or US2
- **Phase 6 (Polish)**: Depends on Phases 3, 4, 5 all being complete

### Within Phase 2 — Parallel Opportunities

Tasks T002–T009 all touch different files and can run in parallel:

```
T002  src/catguard/config.py          (Settings fields)
T003  tests/unit/test_config.py       (tests for T002)
T004  src/catguard/ui/settings_window.py (SettingsFormModel fields)
T005  tests/unit/test_settings_window.py (tests for T004)
T006  src/catguard/recording.py       (new module)
T007  tests/unit/test_recording.py    (tests for T006)
T008  src/catguard/audio.py           (play_alert dispatcher)
T009  tests/unit/test_audio.py        (tests for T008)
```

T010 (main.py wiring) must come after T002, T006, T008.

### User Story Dependencies (within each story)

- Tests must be **written and failing** before implementation (TDD — Constitution Principle I)
- UI widget (T011/T015/T019) before wiring into `_save()` (T012/T016/T021)
- T014/T018/T024 integration tests require Phase 2 complete + story implementation complete

---

## Parallel Execution Examples

### Phase 2 — all foundational tasks in parallel

```
T002  Extend Settings (config.py)
T003  Unit tests — config (test_config.py)
T004  Extend SettingsFormModel (settings_window.py)
T005  Unit tests — SettingsFormModel (test_settings_window.py)
T006  Create recording.py
T007  Unit tests — recording (test_recording.py)
T008  Add play_alert() to audio.py
T009  Unit tests — audio (test_audio.py)
```
→ then T010 (main.py wiring, depends on T002 + T006 + T008)

### User Stories 1, 2, 3 — in parallel once Phase 2 is done

```
US1: T011 → T012 → T013 → T014
US2: T015 → T016 → T017 → T018
US3: T019/T020 (parallel) → T021 → T022 → T023 → T024
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (all T002–T010)
3. **STOP and verify**: `pytest tests/unit/` passes
4. Complete Phase 3: US1 (Recording flow)
5. Complete Phase 4: US2 (Default Sound toggle)
6. **STOP and validate**: Open Settings, record a sound, toggle checkbox, trigger detections
7. Ship MVP — US3 (pinned dropdown) can follow separately

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 → Recording works → demo-able
3. Phase 4 → Default toggle works → demo-able
4. Phase 5 → Pinned dropdown → feature complete
5. Phase 6 → Polish → release-ready

---

## Task Count Summary

| Phase | Tasks | Parallelisable |
|-------|-------|----------------|
| Phase 1 — Setup | 1 | 0 |
| Phase 2 — Foundational | 9 (T002–T010) | 8 (T002–T009) |
| Phase 3 — US1 | 4 (T011–T014) | 0 |
| Phase 4 — US2 | 4 (T015–T018) | 0 |
| Phase 5 — US3 | 6 (T019–T024) | 2 (T019, T020) |
| Phase 6 — Polish | 6 (T025–T030) | 5 (T025–T029) |
| **Total** | **30** | **15** |
