# Tasks: Log Viewer with Search, Clipboard Copy, and Auto-Trim

**Input**: Design documents from `/specs/011-log-viewer-search/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Included — TDD approach specified in spec (Constitution §I; plan.md Test Plan).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Exact file paths included in all task descriptions

## Path Conventions

- Single project layout: `src/catguard/` for source, `tests/unit/` and `tests/integration/` for tests

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create stub files for new modules needed by multiple user stories

- [X] T001 Create stub file `src/catguard/log_manager.py` with module docstring only
- [X] T002 [P] Create stub file `src/catguard/ui/log_viewer.py` with module docstring only

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Settings model extensions required by ALL user stories — US1 reads `logs_directory`, US3 reads all three fields

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

> **TDD**: Write T003 first and confirm it fails before implementing T004

- [X] T003 Write unit tests (`test_logs_directory_default`, `test_logs_directory_rejects_traversal`, `test_max_log_entries_minimum`, `test_log_trim_batch_size_minimum`, `test_load_settings_migrates_missing_log_fields`) in `tests/unit/test_config.py`
- [X] T004 Add `_default_logs_directory()` factory, `logs_directory: str` (default via factory, validator rejects `..`), `max_log_entries: int = 2048` (ge=2048), `log_trim_batch_size: int = 205` (ge=205), and `validate_logs_directory` field validator to `Settings` in `src/catguard/config.py`

**Checkpoint**: `pytest tests/unit/test_config.py` passes — Settings model accepts and validates all new fields

---

## Phase 3: User Story 1 — View Application Logs (Priority: P1) 🎯 MVP

**Goal**: User can open a singleton log viewer window from the tray "Logs" menu item and see log entries in reverse-chronological order, with a Refresh button to reload.

**Independent Test**: Click "Logs" in tray → window opens displaying log entries newest-first; click "Logs" again → existing window lifts (no duplicate); click "Refresh" → latest entries reload; no log file → "No log entries available." shown.

> **TDD**: Write T005 and T006 first and confirm they fail before implementing T007–T010

### Tests for User Story 1

- [X] T005 [P] [US1] Write unit tests (`test_settings_form_model_defaults`, `test_from_settings_roundtrip`, `test_to_settings_validates_minimums`) for `SettingsFormModel` additions in `tests/unit/test_log_viewer.py`
- [X] T006 [P] [US1] Write unit tests (`test_build_tray_icon_includes_logs_item`, `test_update_tray_menu_includes_logs_item`) for tray "Logs" menu item in `tests/unit/test_tray.py`

### Implementation for User Story 1

- [X] T007 [US1] Add `logs_directory: str`, `max_log_entries: int = 2048`, `log_trim_batch_size: int = 205` to `SettingsFormModel` dataclass and extend `from_settings()` and `to_settings()` to include these three fields in `src/catguard/ui/settings_window.py`
- [X] T008 [US1] Implement `open_log_viewer(root, settings)` in `src/catguard/ui/log_viewer.py`: singleton guard via `root._log_viewer_open`; `win = tk.Toplevel(root)`; `apply_app_icon(win)`; geometry persistence via `load_win_geometry("log_viewer")` on open and `save_win_geometry("log_viewer", ...)` on close; main `tk.Text` (state=DISABLED, monospace font, wrap=NONE) with vertical and horizontal `ttk.Scrollbar`; `_do_refresh()` reading `Path(settings.logs_directory) / "catguard.log"` (encoding="utf-8", errors="replace"), reversing lines for newest-first display, showing "No log entries available." when empty or missing, showing error message on OSError
- [X] T009 [US1] Add right-aligned toolbar `tk.Frame` with `tk.Button "Refresh"` calling `_do_refresh()` in `src/catguard/ui/log_viewer.py`
- [X] T010 [US1] Add `on_logs_clicked` factory dispatching `open_log_viewer(root, settings)` via `root.after(0, ...)` and insert `pystray.MenuItem("Logs", on_logs_clicked)` between "Open" and "Settings…" in both `build_tray_icon()` and `update_tray_menu()` in `src/catguard/tray.py`

**Checkpoint**: `pytest tests/unit/test_log_viewer.py tests/unit/test_tray.py` passes; manually clicking "Logs" in tray opens window with log entries newest-first; second click focuses existing window

---

## Phase 4: User Story 2 — Search Log Entries (Priority: P2)

**Goal**: User can type a keyword into a search input and activate search (button click or Enter key) to filter displayed entries case-insensitively; clearing the input and searching again restores the full view.

**Independent Test**: Open log viewer → type search term → click "Search" → only matching entries shown; press Enter in search input → same result; clear input → click "Search" → full log restored; no match → "No results found." shown.

> **TDD**: Write T011 first and confirm it fails before implementing T012–T014

### Tests for User Story 2

- [X] T011 [US2] Write unit tests for `_do_search()` filtering logic in `tests/unit/test_log_viewer.py` (no tkinter display required — use `tmp_path` to write a real log file, call `_do_search()` with a mock `tk.Text` widget using `unittest.mock.MagicMock`, assert correct lines are passed to the widget): `test_do_search_filters_case_insensitive` (matches regardless of case), `test_do_search_no_match_shows_no_results_message` (displays "No results found." when filter returns nothing), `test_do_search_empty_term_calls_refresh` (empty search_var triggers full reload)

### Implementation for User Story 2

- [X] T012 [US2] Add top `tk.Frame` search panel with `tk.Entry` (filling available width, bound to `search_var: tk.StringVar`) and `tk.Button "Search"` calling `_do_search()` to `src/catguard/ui/log_viewer.py`
- [X] T013 [US2] Implement `_do_search()` in `src/catguard/ui/log_viewer.py`: if `search_var` is empty call `_do_refresh()`; otherwise re-read log file, filter lines by `search_var.get().lower() in line.lower()` (case-insensitive, full line per FR-006), update `tk.Text` widget with filtered results newest-first, display "No results found." if no lines match
- [X] T014 [US2] Bind `<Return>` key on search `Entry` widget to trigger `_do_search()` in `src/catguard/ui/log_viewer.py`

**Checkpoint**: Search filters entries case-insensitively across full lines including timestamps; Enter key works; clearing search restores full view; "No results found." shown when no match

---

## Phase 5: User Story 3 — Automatic Log Trimming (Priority: P3)

**Goal**: Application automatically removes the oldest log entries after every `log_trim_batch_size` writes when total entries exceed `max_log_entries`; all three log settings are exposed on a new "Logs" tab in the Settings window; directory change takes effect after Save without restart.

**Independent Test**: Write >2048+205 entries → verify log file has ≤2048 lines, oldest removed; change `logs_directory` in Settings and save → new writes go to new path, old file untouched; load `settings.json` without new keys → defaults applied.

> **TDD**: Write T015, T016, T017 first and confirm they fail before implementing T018–T021

### Tests for User Story 3

- [X] T015 [P] [US3] Write unit tests (`test_trim_not_triggered_before_batch`, `test_trim_triggered_at_batch_boundary`, `test_trim_keeps_last_n_entries`, `test_trim_no_op_when_within_limit`, `test_trim_atomic_write`, `test_trim_handles_missing_file`, `test_write_count_resets_after_batch`) for `BatchTrimFileHandler` using `tmp_path` fixture in `tests/unit/test_log_manager.py`
- [X] T016 [P] [US3] Write unit tests (`test_on_settings_saved_reconfigures_handler_on_dir_change`, `test_on_settings_saved_no_handler_change_when_dir_unchanged`) for handler reconfiguration in `tests/unit/test_main.py`
- [X] T017 [P] [US3] Write integration test (`test_settings_round_trip_log_fields`) using real filesystem writes (no mocks, per Constitution §IV) for save + reload of `logs_directory`, `max_log_entries`, `log_trim_batch_size` in `tests/integration/test_log_settings.py`

### Implementation for User Story 3

- [X] T018 [US3] Implement `BatchTrimFileHandler(logging.FileHandler)` in `src/catguard/log_manager.py`: `__init__(filename, max_entries, batch_size, **kwargs)` stores `_max_entries`, `_batch_size`, `_write_count = 0`; `emit(record)` calls `super().emit(record)`, increments `_write_count`, when `_write_count >= _batch_size` resets to 0 and calls `_trim()`; `_trim()` reads file via `Path.read_text(encoding="utf-8", errors="replace")`, returns early if `len(lines) <= _max_entries`, otherwise atomically rewrites via `.tmp` rename keeping last `_max_entries` lines, calls `tmp.unlink(missing_ok=True)` on OSError
- [X] T019 [US3] Add `_configure_logging(logs_dir: Path, max_entries: int, batch_size: int)` and module-level `_file_handler: BatchTrimFileHandler | None = None` to `src/catguard/main.py`; inside `_configure_logging()` call `logs_dir.mkdir(parents=True, exist_ok=True)` before creating the handler to ensure the directory exists on first launch or after a directory change; swap init order in `main()` so `settings = load_settings()` is called before `_configure_logging(Path(settings.logs_directory), settings.max_log_entries, settings.log_trim_batch_size)`; replace `RotatingFileHandler` with `BatchTrimFileHandler`
- [X] T020 [US3] Add `logs_directory` change detection to `on_settings_saved()` in `src/catguard/main.py`: compare old vs new `logs_directory`; if changed, remove old `_file_handler` from root logger and close it, create new `BatchTrimFileHandler` at new path, add to root logger, update `_file_handler`
- [X] T021 [US3] Add `tab_logs = ttk.Frame(notebook, padding=8)` as 7th "Logs" tab in `src/catguard/ui/settings_window.py`: row 0 — "Logs directory:" label + `tk.Entry(state="readonly", textvariable=logs_dir_var)` + `tk.Button "Browse…"` opening `filedialog.askdirectory` (matching Storage tab pattern); row 1 — "Max log entries:" label + `tk.Spinbox(from_=2048, to=1000000, textvariable=max_entries_var)`; row 2 — "Trim batch size:" label + `tk.Spinbox(from_=205, to=100000, textvariable=batch_size_var)`; in `_save()` validate both spinbox values ≥ minimum, call `messagebox.showerror` and `return` on violation; collect values into `model.logs_directory`, `model.max_log_entries`, `model.log_trim_batch_size`

**Checkpoint**: `pytest tests/unit/test_log_manager.py tests/unit/test_main.py tests/integration/test_log_settings.py` passes; log file stays ≤2048 lines under load; "Logs" tab visible and functional in Settings window

---

## Phase 6: User Story 4 — Copy Logs to Clipboard (Priority: P3)

**Goal**: User can copy currently displayed log entries — or selected text — to the system clipboard using a "Copy to Clipboard" toolbar button positioned left of "Refresh".

**Independent Test**: Open log viewer → click "Copy to Clipboard" → paste elsewhere → all visible entries with timestamps intact; select a text range → click button → only selected text pasted; active search filter → only filtered entries copied; empty viewer → no-op; clipboard error → brief error dialog shown, viewer remains functional.

### Implementation for User Story 4

- [X] T022 [US4] Add `tk.Button "Copy to Clipboard"` to toolbar `tk.Frame` in `src/catguard/ui/log_viewer.py`, positioned left of "Refresh" (both right-aligned), calling `_do_copy()`
- [X] T023 [US4] Implement `_do_copy()` in `src/catguard/ui/log_viewer.py`: if `text_widget.tag_ranges(tk.SEL)` copy `text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)`; else copy `text_widget.get("1.0", tk.END).strip()`; skip clipboard write if text is empty; call `root.clipboard_clear()` then `root.clipboard_append(text)`; wrap in try/except and show `messagebox.showerror("Copy Failed", str(e))` on exception without disrupting viewer

**Checkpoint**: "Copy to Clipboard" copies all visible entries; selection-only copy works; clipboard error shows error dialog without crashing

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Acceptance validation and edge case verification across all user stories

- [ ] T024 Run manual acceptance scenarios from `specs/011-log-viewer-search/quickstart.md`: verify SC-001 (viewer opens <2s), SC-004 (≤2048 entries no UI freeze), SC-005 (search result <1s), all US1–US4 acceptance scenarios from spec.md
- [ ] T025 [P] Verify spec.md edge cases: unreadable log file shows error message and app continues; `settings.json` without new keys loads with defaults; log viewer open during trim shows no disruption on Refresh; clipboard failure shows error without crash

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 only
- **US2 (Phase 4)**: Depends on US1 (Phase 3) — adds search panel to the viewer window
- **US3 (Phase 5)**: Depends on Phase 2 — independent of US1/US2/US4
- **US4 (Phase 6)**: Depends on US1 (Phase 3) — adds Copy button to the viewer toolbar
- **Polish (Phase 7)**: Depends on all phases complete

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational only
- **US2 (P2)**: Depends on US1 — extends `log_viewer.py` with search panel
- **US3 (P3)**: Depends on Foundational only — fully independent of US1/US2/US4
- **US4 (P3)**: Depends on US1 — extends `log_viewer.py` with copy toolbar button; can run in parallel with US2 and US3

### Within Each User Story

- Tests MUST be written and confirmed FAILING before implementation begins
- Config/model changes before UI implementation
- Core implementation before integration

### Parallel Opportunities

- T001 and T002 (file stubs, different files) can run in parallel
- T005 and T006 (US1 tests, different files) can run in parallel
- T015, T016, and T017 (US3 tests, all different files) can run in parallel
- US3 (Phase 5) can be implemented in parallel with US1 (Phase 3) after Foundational completes
- US3 (Phase 5) can continue in parallel with US2 (Phase 4) and US4 (Phase 6) after US1 completes
- US4 (Phase 6, toolbar section) and US2 (Phase 4, top panel section) can be worked in parallel — different regions of `log_viewer.py`

---

## Parallel Example: User Story 1

```
Parallel (different files, no dependencies):
  T005 — "Write SettingsFormModel unit tests in tests/unit/test_log_viewer.py"
  T006 — "Write tray menu Logs item unit tests in tests/unit/test_tray.py"
```

## Parallel Example: User Story 3

```
Parallel (all different files):
  T015 — "Write BatchTrimFileHandler unit tests in tests/unit/test_log_manager.py"
  T016 — "Write handler reconfiguration unit tests in tests/unit/test_main.py"
  T017 — "Write settings round-trip integration test in tests/integration/test_log_settings.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003–T004)
3. Complete Phase 3: User Story 1 (T005–T010)

4. **STOP and VALIDATE**: Log viewer opens from tray, displays entries newest-first, Refresh reloads, singleton focus works
5. Demo / validate before continuing to US2/US3/US4

### Incremental Delivery

1. Setup + Foundational → Settings model ready
2. **+ US1** → viewable logs from tray (MVP!)
3. **+ US2** → searchable logs
4. **+ US3** → auto-trim + Settings Logs tab (can run in parallel with US2)
5. **+ US4** → copy to clipboard (can run in parallel with US3)
6. **+ Polish** → acceptance testing and edge case validation

### Parallel Team Strategy

After Foundational (Phase 2) completes:
- **Developer A**: US1 → US2 (sequential, same file)
- **Developer B**: US3 (fully independent — different files)
- **Developer C**: Waits for US1, then US4 (can overlap with US3)

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps each task to a specific user story for traceability
- Tests must FAIL before implementing — confirm with `pytest` before writing implementation
- `tmp_path` pytest fixture required for all `test_log_manager.py` tests (filesystem isolation, no real user directories)
- Integration test `test_log_settings.py` uses real filesystem — no mocks (Constitution §IV)
- `test_log_viewer.py` scope is `SettingsFormModel` only; log viewer window UI is covered by manual acceptance testing (T023)
- No new runtime dependencies — standard library only for `src/catguard/log_manager.py`
- Performance goals: viewer opens <2s (SC-001), search returns <1s (SC-005), ≤2048 entries no UI freeze (SC-004)
- Commit after each task or logical group
