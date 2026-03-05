# Tasks: Add Photo Action Panel

**Input**: Design documents from `/specs/008-add-photo-action-panel/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths relative to repository root

---

## Phase 1: Setup

**Purpose**: Feature branch and confirming existing helpers are importable

- [ ] T001 Create feature branch `008-add-photo-action-panel` and confirm `screenshots.build_filepath` and `cv2.imencode` are importable from `src/catguard/screenshots.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Settings model extended and Photo data model implemented — MUST be complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T004 Edit `tests/unit/test_config.py`: assert all six new settings have correct defaults; assert `photo_image_quality` and `tracking_image_quality` validators reject values outside 1–100; assert `photos_directory` validator rejects paths with `..` components
- [ ] T005 Write `tests/unit/test_photos.py`: test `Photo` dataclass instantiation and attribute access; test `build_photo_filepath` returns correct date subfolder and time-based filename; test collision suffix appended when file already exists; test `encode_photo` output is valid JPEG bytes

- [ ] T002 Edit `src/catguard/config.py`: add `photos_directory` (default `images/CatGuard/photos`), `tracking_directory` (default `images/catGuard/tracking`), `photo_image_format` (default `jpg`), `photo_image_quality` (default `95`, validator 1–100), `tracking_image_quality` (default `90`, validator 1–100), `photo_countdown_seconds` (default `3`) using pydantic-settings `Field` entries with appropriate validators
- [ ] T003 Write `src/catguard/photos.py`: `Photo` dataclass with `timestamp: datetime`, `bytes: bytes`, `source: str = "clean-capture"`; `build_photo_filepath(root, ts, ext) -> Path` reusing `screenshots.build_filepath` semantics (date subfolder `YYYY-MM-DD`, filename `HH-MM-SS.jpg`, collision suffix `-1`, `-2`, ...); `encode_photo(frame, quality: int) -> bytes` using `cv2.imencode`

**Checkpoint**: `pytest tests/unit/ -q` green with no regressions — user story work can now begin

---

## Phase 3: User Story 1 — Take Photo Immediately (Priority: P1) 🎯 MVP

**Goal**: User clicks `Take photo` in the main window action panel; a clean image (no overlays) is captured, stored as a `Photo` object, and displayed in a new `PhotoWindow`; user can `Save` to the configured directory or `Save As...` to a chosen path, or `Close` to discard.

**Independent Test**: Start the app, click `Take photo` → `PhotoWindow` opens with a clean image (no detection overlays); `Save`, `Save As...`, and `Close` buttons are present and functional.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T006 [P] [US1] Write `tests/integration/test_photo_action_panel.py`: mock `tkinter.filedialog.asksaveasfilename`, `os.makedirs`, and `open`; write failing tests for: `Take photo` opens `PhotoWindow`; `PhotoWindow` renders three buttons with exact labels `Save`, `Save As...`, `Close` (NFR-UX-001); `Save` writes to correct `YYYY-MM-DD/<HH-MM-SS>.jpg` path under `photos_directory`; collision produces `-1` suffix; `Save As...` dialog initialised with OS default dir on first use and `ActionPanel._last_save_dir` on second use (session-scoped, not per-window); `initialfile` pre-populated with `catguard_YYYYMMDD_HHMMSS.jpg`; cancelled dialog leaves `PhotoWindow` open; `Save` button shows `Saved ✓` then restores label (NFR-UX-001); save failure shows inline `Save failed — <filename>` message; closing `PhotoWindow` sets `photo` reference to `None` (FR-008); no image bytes appear in log output during encode/save (NFR-SEC-003)

### Implementation for User Story 1

- [ ] T007 [US1] Write `src/catguard/ui/photo_window.py`: `PhotoWindow(tk.Toplevel)` — display captured image on a `Canvas`/`Label`; action panel with `Save` button (left), `Save As...` button (middle), `Close` button (right) using `pack`/`grid` without fixed pixel sizes; status label row below buttons for inline error/success feedback; accepts `last_save_dir: str | None` and `on_save_dir_change: Callable[[str], None]` constructor arguments (session state managed by `ActionPanel`, not per-window); `Close` button MUST set `self.photo = None` to release the in-memory image before destroying the window
- [ ] T008 [US1] Wire `Save` button in `src/catguard/ui/photo_window.py`: call `build_photo_filepath(root=settings.photos_directory, ts=photo.timestamp, ext=settings.photo_image_format)`; `os.makedirs(parent, exist_ok=True)`; write `photo.bytes` to resolved path; on success update button label to `Saved ✓` for 2 s via `root.after(2000, restore_label)`, then restore; on failure display `Save failed — <filename>` inline (NFR-UX-002, NFR-SEC-004); log full path at DEBUG level only
- [ ] T009 [US1] Wire `Save As...` button in `src/catguard/ui/photo_window.py`: call `asksaveasfilename(initialdir=self._last_save_dir or <OS default>, initialfile=catguard_YYYYMMDD_HHMMSS.jpg, defaultextension=.jpg, filetypes=[("JPEG", "*.jpg")])`; on non-empty result normalise path with `os.path.normpath` and reject `..` components (NFR-SEC-001); write `photo.bytes` to the resolved path; call `self._on_save_dir_change(parent_dir)` to update the session-scoped `last_save_dir` on `ActionPanel`; on cancellation do nothing
- [ ] T010 [US1] Write `src/catguard/ui/action_panel.py`: `ActionPanel(tk.Frame)` initialised with `capture_callback: Callable[[], np.ndarray]`, `close_callback: Callable[[], None]`, and `settings`; add `_last_save_dir: str | None = None` instance variable (session-scoped, shared across all `PhotoWindow` instances opened this session); add `Take photo` button that calls `capture_callback()` to obtain a raw overlay-free frame, encodes it via `encode_photo(frame, settings.photo_image_quality)`, creates `Photo(timestamp=datetime.now(), bytes=encoded)`, and opens `PhotoWindow(master=root, photo=photo, settings=settings, last_save_dir=self._last_save_dir, on_save_dir_change=self._update_last_save_dir)`; add `_update_last_save_dir(self, path: str) -> None` method that sets `self._last_save_dir = path`
- [ ] T011 [US1] Implement `get_clean_frame() -> np.ndarray` in `src/catguard/main.py`: retrieve the latest raw detection frame from the detection pipeline without rendering any annotation overlays; wire this method as the `capture_callback` passed to `ActionPanel` in T012
- [ ] T012 [US1] Integrate `ActionPanel` into `src/catguard/ui/main_window.py`: instantiate `ActionPanel(parent=self, capture_callback=self.get_clean_frame, close_callback=self.minimize_to_tray, settings=self.settings)` and attach via `action_panel.pack(side=tk.BOTTOM, fill=tk.X)`

**Checkpoint**: User Story 1 independently functional — `Take photo` → `PhotoWindow` → `Save`/`Save As...`/`Close` all work; integration tests green

---

## Phase 4: User Story 2 — Take Photo with Delay (Priority: P1)

**Goal**: User clicks `Take photo with delay`; the button shows a countdown (3 → 2 → 1 by default); during countdown the button remains readable but ignores further clicks; after countdown capture + `PhotoWindow` flow is identical to US1.

**Independent Test**: Click `Take photo with delay` → button text updates each second (3, 2, 1); clicking button during countdown has no effect (no duplicate window); after countdown completes a `PhotoWindow` opens and button label restores.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T013 [P] [US2] Extend `tests/integration/test_photo_action_panel.py`: mock `root.after` to advance ticks; assert button text transitions 3 → 2 → 1; assert click during countdown does not open a second window; assert button label restores and becomes clickable after capture; assert `photo_countdown_seconds` setting controls starting value

### Implementation for User Story 2

- [ ] T014 [US2] Add `Take photo with delay` button to `src/catguard/ui/action_panel.py`: read `settings.photo_countdown_seconds` as starting value; set `_countdown_active: bool = False` flag
- [ ] T015 [US2] Implement countdown loop in `src/catguard/ui/action_panel.py`: on click, if `_countdown_active` is `True` return immediately (suppress); set `_countdown_active = True`, update button text to current tick value, schedule next tick via `self.after(1000, _tick)`; when tick reaches `0` call the same capture flow as `Take photo`, then restore button label and set `_countdown_active = False`

**Checkpoint**: User Story 2 independently functional — countdown works, suppression works, capture opens `PhotoWindow`; integration tests green

---

## Phase 5: User Story 3 — Panel Layout and Close (Priority: P2)

**Goal**: The action panel is anchored at the bottom of the main window with correct layout: `Take photo` and `Take photo with delay` left-aligned, `Close` right-aligned; clicking `Close` minimizes the app to the system tray.

**Independent Test**: Verify the panel is visible at the bottom of the main window; confirm button positions match spec (left/right); click `Close` → main window hides and tray icon remains active.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T016 [P] [US3] Extend `tests/integration/test_photo_action_panel.py`: assert `ActionPanel` is packed at `side=BOTTOM, fill=X`; assert `Close` button is present; mock tray `withdraw`/`iconify` and assert it is called when `Close` is clicked

### Implementation for User Story 3

- [ ] T017 [US3] Add `Close` button to `src/catguard/ui/action_panel.py`: wire to `close_callback` (passed at init); button placed right-aligned using a second inner `Frame` with `pack(side=tk.RIGHT)` (photo buttons packed `side=tk.LEFT`)
- [ ] T018 [US3] Implement `close_callback` in `src/catguard/ui/main_window.py` or `src/catguard/main.py`: call existing minimize-to-tray logic (e.g., `root.withdraw()` + tray icon notification); pass as `close_callback` when constructing `ActionPanel`
- [ ] T019 [US3] Finalize `ActionPanel` layout in `src/catguard/ui/action_panel.py`: `Take photo` and `Take photo with delay` in a left `Frame`, `Close` in a right `Frame`, both inside the `ActionPanel` frame; use `pack`/`grid` with no fixed pixel sizes so layout scales on resize/DPI changes (NFR-UX-005)

**Checkpoint**: All three user stories independently functional; `pytest -q` fully green

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, contracts, and final validation

- [ ] T020 [P] Create `specs/008-add-photo-action-panel/contracts/settings.md`: document all six new settings keys (`photos_directory`, `tracking_directory`, `photo_image_format`, `photo_image_quality`, `tracking_image_quality`, `photo_countdown_seconds`) with defaults, types, valid ranges, and validation rules
- [ ] T021 [P] Update `specs/008-add-photo-action-panel/quickstart.md`: add manual QA steps for all three action-panel buttons (`Take photo`, `Take photo with delay`, `Close`); add steps for `Save` and `Save As...` including error scenarios; add note that OS file-save dialog is mocked in automated tests and must be verified manually (NFR-PERF-002)
- [ ] T022 Run full test suite `pytest -q` and confirm zero regressions, explicitly including existing detection integration tests (`tests/integration/test_detection_integration.py` and related) as a regression gate for FR-010 (no alteration to existing detection logic); verify implementation checklist items in `specs/008-add-photo-action-panel/checklists/implementation.md`
- [ ] T023 Bump `pyproject.toml` version to the next MINOR identifier (additive feature, no breaking changes — Constitution V)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 completion
- **US2 (Phase 4)**: Depends on Phase 2 completion; T014–T015 also depend on `ActionPanel` shell from T010 (Phase 3)
- **US3 (Phase 5)**: Depends on Phase 2 completion; T017–T019 extend work from Phases 3–4
- **Polish (Phase 6)**: Depends on all user story phases complete

### User Story Dependencies

- **US1 (P1)**: Can start immediately after Phase 2 — no dependencies on other stories
- **US2 (P1)**: Depends on `ActionPanel` shell (T010) from US1; countdown is additive
- **US3 (P2)**: Depends on `ActionPanel` base (T010, T014) from US1/US2; layout and Close are additive

### Parallel Opportunities Within Phases

- **Phase 2**: T004 and T005 are test-first gates (must be written and FAIL before implementation begins); T002 and T003 follow sequentially after the failing tests are in place
- **Phase 3**: T006 (integration test skeleton) can run in parallel with T007–T012 (implementation); T007–T009 can be parallelised once T007 (`PhotoWindow` shell) is merged
- **Phase 4**: T013 (tests) can run in parallel with T014–T015 (implementation in same file — coordinate if pair programming)
- **Phase 5**: T016 (tests) can run in parallel with T017–T019
- **Phase 6**: T020 and T021 can run in parallel

---

## Parallel Example: User Story 1 (Phase 3)

```bash
# Stream 1 — tests (can start as soon as Phase 2 is done)
pytest tests/integration/test_photo_action_panel.py -q  # should FAIL initially

# Stream 2 — PhotoWindow UI (T007–T009)
# Edit src/catguard/ui/photo_window.py

# Stream 3 — ActionPanel + capture (T010–T012)
# Edit src/catguard/ui/action_panel.py
# Edit src/catguard/ui/main_window.py

# After all streams complete:
pytest tests/integration/test_photo_action_panel.py -q  # should PASS
```

---

## Implementation Strategy

### MVP Scope (suggested first delivery)

**Phase 1 + Phase 2 + Phase 3 only** (`Take photo` → `PhotoWindow` → `Save`/`Save As...`/`Close`).
This is independently useful and deliverable before countdown and layout work.

### Incremental Delivery

1. **MVP** — Phase 3 complete: core photo capture and save
2. **+ Countdown** — Phase 4 complete: delay capture with countdown
3. **+ Layout** — Phase 5 complete: full panel layout and Close to tray
4. **Polish** — Phase 6: documentation and contract files

### Format Validation

All tasks follow the required checklist format: `- [ ] [TaskID] [P?] [Story?] Description with file path`

| Story label | Phase | Task IDs |
|-------------|-------|----------|
| (none — setup) | Phase 1 | T001 |
| (none — foundational) | Phase 2 | T002–T005 |
| [US1] | Phase 3 | T006–T012 |
| [US2] | Phase 4 | T013–T015 |
| [US3] | Phase 5 | T016–T019 |
| (none — polish) | Phase 6 | T020–T022 |
