# Implementation Plan: Add photo action panel

**Branch**: `008-add-photo-action-panel` | **Date**: 2026-03-05 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/008-add-photo-action-panel/spec.md`

## Summary

Add a persistent action panel at the bottom of the main window with `Take photo`, `Take photo with delay`, and `Close` buttons. Clicking either photo button captures a clean (overlay-free) JPEG frame, stores it in a transient `Photo` object, and opens a photo window with `Save`, `Save As...`, and `Close` actions. `Save` writes to a date-organised folder under `photos_directory` using a collision-safe `HH-MM-SS.jpg` filename; `Save As...` opens a system dialog pre-populated with `catguard_YYYYMMDD_HHMMSS.jpg`. All timestamps use local system time, consistent with the existing `screenshots` module. Implementation reuses `screenshots.build_filepath` and `cv2.imencode` from the existing codebase.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: tkinter (UI), opencv-python / `cv2` (JPEG encoding, reused from `screenshots.py`), pydantic-settings (Settings model in `config.py`)  
**Storage**: Local filesystem only — date-organised JPEG files under `photos_directory`; transient in-memory `Photo` dataclass (no DB)  
**Testing**: pytest, pytest-mock; tkinter UI tested via integration tests with mocked file dialog  
**Target Platform**: Windows desktop (primary); Linux desktop (secondary)  
**Project Type**: Desktop GUI application  
**Performance Goals**: Countdown tick accuracy ±200 ms; `Save` button feedback visible within 200 ms of write completion; JPEG encode <500 ms for typical webcam resolution  
**Constraints**: No new third-party dependencies; reuse existing `cv2` and `build_filepath`; no cloud/network; file permissions use OS defaults  
**Scale/Scope**: Single user; up to N concurrent photo windows (one per click); no persistence beyond local files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✅ PASS | Unit tests for `Photo`, `build_photo_filepath`, encoding; integration tests for UI flows written before implementation |
| II. Observability & Logging | ✅ PASS | All save operations log at DEBUG (path) and ERROR (failure); NFR-SEC-003/004 enforce no image bytes in logs |
| III. Simplicity & Clarity | ✅ PASS | Reuses existing helpers; no new patterns; `Photo` is a plain dataclass; countdown uses `after()` |
| IV. Integration Testing | ✅ PASS | Integration tests cover full Save/Save As flows with mocked `asksaveasfilename` and filesystem |
| V. Versioning & Breaking Changes | ✅ PASS | Additive only — new settings keys with defaults, new UI panel; no breaking changes to existing flows |
| Security constraints | ✅ PASS | NFR-SEC-001..005 in spec; path normalisation + `..` rejection; no new deps |
| Performance goals | ✅ PASS | Encode <500 ms; countdown ±200 ms; within existing detection <200 ms p95 (separate path) |

**No violations.** Complexity tracking table omitted.

## Project Structure

### Documentation (this feature)

```text
specs/008-add-photo-action-panel/
├── plan.md              ← this file
├── spec.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── settings.md      ← settings keys contract
└── tasks.md             (created by /speckit.tasks — not yet)
```

### Source Code

```text
src/catguard/
├── config.py            ← EDIT: add photos_directory, photo_image_format,
│                                photo_image_quality, tracking_image_quality,
│                                photo_countdown_seconds with validators
├── photos.py            ← NEW: Photo dataclass + build_photo_filepath helper
├── screenshots.py       ← READ-ONLY: reuse build_filepath, resolve_root
├── ui/
│   ├── main_window.py   ← EDIT: add ActionPanel widget to bottom
│   └── photo_window.py  ← NEW: PhotoWindow (image display + Save/Save As/Close)
└── main.py              ← EDIT if needed: wire ActionPanel to capture callback

tests/
├── unit/
│   ├── test_photos.py   ← NEW: Photo dataclass, build_photo_filepath,
│   │                            collision handling, encoding
│   └── test_config.py   ← EDIT: add assertions for new settings defaults/validators
└── integration/
    └── test_photo_action_panel.py  ← NEW: UI flows (mock dialog, mock filesystem)
```

**Structure Decision**: Single-project layout following existing `src/catguard` package. New source in `photos.py` and `ui/photo_window.py`; edits to `config.py` and `ui/main_window.py`. No new packages or directories at the project root.

## Implementation Phases

### Phase 1 — Settings & Data Model (no UI yet)

**Goal**: All new config fields exist with correct defaults and validators; `Photo` dataclass and `build_photo_filepath` are implemented and unit-tested.

**Tasks**:
1. Edit `config.py` — add 6 new `Field` entries (`photos_directory`, `tracking_directory`, `photo_image_format`, `photo_image_quality`, `tracking_image_quality`, `photo_countdown_seconds`) with defaults and `@validator` for quality (1–100) and non-empty path.
2. Write `photos.py` — `Photo` dataclass; `build_photo_filepath(root, ts, ext)` wrapping `screenshots.build_filepath` semantics; `encode_photo(frame, quality)` using `cv2.imencode`.
3. Write `tests/unit/test_photos.py` — covers: filepath uniqueness, collision suffix, date folder, encode output is valid JPEG, `Photo` attributes.
4. Edit `tests/unit/test_config.py` — assert defaults and validator rejection of out-of-range quality.

**Done when**: `pytest tests/unit/ -q` green with no regressions.

---

### Phase 2 — Photo Window UI

**Goal**: `PhotoWindow` opens with the correct layout and buttons; `Close` releases the `Photo`; `Save As...` dialog pre-populates correctly (mocked in tests).

**Tasks**:
5. Write `ui/photo_window.py` — `PhotoWindow(tk.Toplevel)`: image canvas, `Save` button (left), `Save As...` button (middle), `Close` button (right); in-memory `last_save_dir` state.
6. Wire `Save As...` to `tkinter.filedialog.asksaveasfilename` with `initialdir` (OS default first, `last_save_dir` after) and `initialfile=catguard_YYYYMMDD_HHMMSS.jpg`.
7. Wire `Save` to `build_photo_filepath` + `photos_directory` write; on success update button label to `Saved ✓` for 2 s via `after(2000, restore_label)`; on failure show inline error label (NFR-UX-002).
8. Write `tests/integration/test_photo_action_panel.py` — mock `asksaveasfilename`, mock `os.makedirs`/`open`; verify Save path, filename, collision handling, dialog initialisation values.

**Done when**: `pytest tests/integration/test_photo_action_panel.py -q` green.

---

### Phase 3 — Main Window Action Panel & Capture Flow

**Goal**: Action panel appears at bottom of main window; `Take photo` and `Take photo with delay` capture clean frames and open `PhotoWindow`; countdown works correctly.

**Tasks**:
9. Write `ui/action_panel.py` (or extend `main_window.py`) — `ActionPanel(tk.Frame)`: `Take photo` and `Take photo with delay` left-aligned; `Close` (minimize-to-tray) right-aligned.
10. Implement clean capture — obtain raw frame from detection pipeline without rendering overlays; create `Photo` object; open `PhotoWindow`.
11. Implement countdown — use `root.after(1000, tick)` loop; update button text each tick; set flag to suppress clicks during countdown; restore on completion.
12. Integrate `ActionPanel` into main window bottom via `pack(side=tk.BOTTOM, fill=tk.X)`.
13. Extend integration tests — click simulate `Take photo`, verify `PhotoWindow` opened with correct image; click simulate `Take photo with delay`, verify countdown suppression.

**Done when**: Manual quickstart walkthrough passes; `pytest -q` fully green.

---

### Phase 4 — Polish, Docs & PR

14. Update `quickstart.md` — manual QA steps for all three buttons, Save, Save As..., error scenarios; note CI limitation for OS dialog (NFR-PERF-002).
15. Update `contracts/settings.md` — document all 6 new settings keys (`photos_directory`, `tracking_directory`, `photo_image_format`, `photo_image_quality`, `tracking_image_quality`, `photo_countdown_seconds`) with defaults, types, and valid ranges.
16. Run full test suite: `pytest -q`.
17. Open PR targeting `master`; verify all implementation checklist items in `checklists/implementation.md`.
