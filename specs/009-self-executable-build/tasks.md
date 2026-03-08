# Tasks: Self-Executable Build & Distribution

**Input**: Design documents from `/specs/009-self-executable-build/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/build-artifacts.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths included in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the packaging configuration and workflow skeleton that all user stories depend on.

- [X] T001 Add `pyinstaller` and `pyinstaller-hooks-contrib` as dev/build dependencies in `pyproject.toml` (optional-dependencies `build` group)
- [X] T002 Create `catguard.spec` PyInstaller spec file at repo root with `--onedir` mode, entry point `src/catguard/__main__.py`, and placeholder `datas`/`hiddenimports` sections
- [X] T003 [P] Create `.github/workflows/build.yml` skeleton with `on:` triggers (`push` to `main` and `v*` tags), `permissions: contents: write`, and empty `build` and `release` job stubs

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core changes that MUST be complete before any user story can be verified — asset path resolution in the packaged executable and full spec file configuration.

**⚠️ CRITICAL**: US1 (working executable) cannot be validated until this phase is complete.

- [X] T004 Patch `src/catguard/main.py`: add `_get_resource_dir()` helper using `sys._MEIPASS` for packaged mode and `Path(__file__).parent.parent.parent` for development mode; update `assets_dir` assignment to use it (per data-model.md)
- [X] T005 Complete `catguard.spec`: add `collect_all('ultralytics')` for datas/binaries/hiddenimports; add explicit hidden imports for `pystray._win32`, `pystray._darwin`, `pystray._xorg`, `pystray._appindicator`, `win32timezone`, `tkinter`, `tkinter.ttk`, `_tkinter`, `platformdirs.unix`, `platformdirs.windows`, `platformdirs.macos`; add `datas=[('assets', 'assets')]` to bundle sounds and icon; set `console=False` (windowed mode); configure `excludes` for unused torch backends
- [ ] T006 Verify `catguard.spec` builds successfully on the developer's primary OS (Windows): run `pyinstaller catguard.spec --clean --noconfirm` and confirm `dist/catguard/catguard.exe` is present and non-zero in size (per FR-006); macOS and Linux are verified by CI in T011

**Checkpoint**: Foundation ready — CI workflow and platform-specific tasks can now proceed.

---

## Phase 3: User Story 1 — Run CatGuard Without Python (Priority: P1) 🎯 MVP

**Goal**: A user on a machine with no Python installation can run the CatGuard executable and have all features work (camera monitoring, cat detection, sound alerts, system tray, config management, model auto-download).

**Independent Test**: Download the built artifact on a machine with no Python installed. Extract the zip. Run `catguard[.exe]`. Verify tray icon appears, camera starts, cat detection triggers alert, and YOLO model downloads on first run.

- [ ] T007 [US1] Build and manually smoke-test the executable on Windows: confirm tray icon, camera feed, sound alert, and first-run model download all function (per FR-002 feature list)
- [ ] T008 [P] [US1] Build and manually smoke-test the executable on macOS: same acceptance criteria as T007
- [ ] T009 [P] [US1] Build and manually smoke-test the executable on desktop Linux (X11 or Wayland): same acceptance criteria as T007
- [X] T010 [US1] Update `README.md`: add a "Download" section linking to GitHub Releases, and add per-OS instructions for bypassing SmartScreen (Windows) and Gatekeeper (macOS) when running an unsigned executable (per Assumption §5, Edge Cases)

---

## Phase 4: User Story 2 — Automated Build via GitHub Pipeline (Priority: P2)

**Goal**: A developer pushes to `main` or creates a version tag; the GitHub Actions pipeline automatically builds executables for all three platforms without manual steps.

**Independent Test**: Push a commit to `main`. Verify the `build` workflow runs and produces three platform artifacts (Actions artifacts, 7-day retention). No release is created.

- [X] T011 [US2] Implement `build` job in `.github/workflows/build.yml`: matrix strategy with `windows-latest`, `macos-latest`, `ubuntu-latest`; `fail-fast: false`; install Python 3.11 via `actions/setup-python@v5`; install `python3-tk` via apt on Linux; install dependencies with `pip install pyinstaller pyinstaller-hooks-contrib && pip install -e ".[dev]"`; run `pytest -m "not integration"` and fail the job if tests fail (Constitution Principles I & IV); run `pyinstaller catguard.spec --clean --noconfirm`; rename output per platform (`catguard-windows.exe`, `catguard-macos`, `catguard-linux`); zip each output directory; upload zip via `actions/upload-artifact@v4` with `retention-days: 7`
- [X] T012 [US2] Add version-validation step to `build` job in `.github/workflows/build.yml`: on tag pushes only (`if: startsWith(github.ref, 'refs/tags/v')`), extract version from tag and from `pyproject.toml` and fail the job if they do not match (per FR-004)
- [ ] T013 [US2] Verify CI build on `main` push: confirm all three matrix jobs complete, artifacts are uploaded, no release is created, and a failure in one matrix job does not prevent the others from uploading their artifacts (per FR-003, FR-006)

---

## Phase 5: User Story 3 — Download Executable from GitHub (Priority: P3)

**Goal**: A user visits the GitHub project page, finds and downloads the pre-built executable for their OS from a GitHub Release, and runs it successfully with no Python installed.

**Independent Test**: Navigate to the GitHub project → Releases page. Download the zip for your platform. Extract. Run executable. CatGuard operates with full functionality.

- [X] T014 [US3] Implement `release` job in `.github/workflows/build.yml`: trigger `if: startsWith(github.ref, 'refs/tags/v')`; `needs: build`; runs on `ubuntu-latest`; download all artifacts via `actions/download-artifact@v4` with `merge-multiple: true`; create/update GitHub Release via `softprops/action-gh-release@v2` with `files: artifacts/*`, `generate_release_notes: true`, and `fail_on_unmatched_files: false` (to support partial releases per FR-003)
- [ ] T015 [US3] Verify end-to-end release flow: update `pyproject.toml` version to the intended release version (e.g., `0.4.0`), push a matching tag (e.g., `v0.4.0`); confirm build jobs run, zips are produced, and a GitHub Release is created with all available platform zips attached (per SC-004, FR-004 version validation)
- [ ] T016 [US3] Verify re-run resilience: from the GitHub Actions UI, open the tag-triggered workflow run and click "Re-run all jobs"; confirm the existing Release is updated (artifacts replaced/appended) rather than the job failing on a duplicate release error (per FR-003); note: `gh workflow run` cannot re-trigger push/tag events and must not be used for this verification

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Documentation accuracy, artifact naming consistency, and spec compliance verification.

- [X] T017 [P] Update `contracts/build-artifacts.md` if artifact naming or zip structure differs from what was specified during implementation (keep contract in sync with actual output)
- [X] T018 [P] Update `quickstart.md` "Run the Built Executable" section to reflect exact paths produced by the final `catguard.spec` (e.g., confirm entry point name inside zip matches documented name)
- [ ] T019 Verify SC-003: confirm total pipeline wall-clock time from trigger to artifact upload is within 15 minutes by reviewing a completed workflow run's timing summary
- [ ] T020 Verify SC-005: trigger the build workflow twice from the same commit; confirm both runs produce artifacts where all FR-002 features work correctly (behavioral equivalence, not byte identity)

---

## Dependencies

```
Phase 1 (Setup)
    └─→ Phase 2 (Foundational — T004, T005, T006)
            ├─→ Phase 3 US1 (T007, T008, T009, T010) — local builds only, no CI needed
            └─→ Phase 4 US2 (T011, T012, T013) — CI workflow
                    └─→ Phase 5 US3 (T014, T015, T016) — release pipeline
                            └─→ Final Phase (T017–T020)
```

**US3 depends on US2** (release job requires the build job to exist).
**US1 (local test) is independent of US2/US3** — can be validated locally before CI is wired up.

---

## Parallel Execution Examples

**Within Phase 3 (US1)**:
- T007, T008, T009 can run in parallel (different platforms, same spec file)

**Within Final Phase**:
- T017 and T018 can run in parallel (different files)

**After Phase 2 completes**:
- Phase 3 (local validation) and Phase 4 (CI wiring) can be worked on in parallel by different contributors

---

## Implementation Strategy

**MVP scope (US1 only)**: Complete T001–T010. This delivers a working self-contained executable that any developer can build locally and share — the core feature value.

**Full scope**: Complete all phases in order for the automated CI/CD pipeline and GitHub Release distribution.

**Suggested delivery order**:
1. T001–T003 (setup skeleton — fast, unblocks everything)
2. T004–T005 (spec + patch — core packaging work)
3. T006 (local build verification — validates the spec before wiring CI)
4. T007–T009 (cross-platform smoke tests — validates US1)
5. T010 (README — ships alongside US1)
6. T011–T013 (CI pipeline — US2)
7. T014–T016 (release pipeline — US3)
8. T017–T020 (polish)
