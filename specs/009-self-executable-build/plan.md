# Implementation Plan: Self-Executable Build & Distribution

**Branch**: `009-self-executable-build` | **Date**: 2026-03-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/009-self-executable-build/spec.md`

## Summary

Package CatGuard as a self-contained executable (no Python required) for Windows, macOS, and desktop Linux using PyInstaller with `--onedir` mode, and automate builds via GitHub Actions. CI runs on every push to `main`; GitHub Releases with platform-specific zip archives are published on version tags (`v*`). A small source patch to `main.py` resolves asset paths correctly inside the packaged bundle.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: PyInstaller 6.x, pyinstaller-hooks-contrib; existing: ultralytics, opencv-python, pystray, Pillow, pygame-ce, sounddevice, soundfile, pywin32 (Windows), tkinter
**Storage**: N/A — no new persistent storage layer
**Testing**: pytest (existing, unchanged); CI build + artifact upload as integration test; manual smoke test of built executable against acceptance criteria
**Target Platform**: Windows (`windows-latest`), macOS (`macos-latest`), desktop Linux (`ubuntu-latest`)
**Project Type**: Desktop app — `--onedir` zip distribution via GitHub Releases
**Performance Goals**: App launch ≤ 5 s after executable run; CI pipeline (all 3 platforms in parallel) completes within 15 min (SC-003)
**Constraints**: No Python on end-user machine (FR-001); OS security warnings are accepted known limitation for MVP; headless Linux out of scope
**Scale/Scope**: 3 platform executables; single GitHub Actions workflow; one `.spec` file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✅ PASS | Acceptance scenarios defined in spec; CI pipeline build is the integration test; existing test suite unchanged |
| II. Observability & Logging | ✅ PASS | No new runtime components; existing structured logging preserved in packaged executable |
| III. Simplicity & Clarity | ✅ PASS | PyInstaller + one spec file is the minimal approach; source patch is 4 lines; no new abstraction layers |
| IV. Integration Testing | ✅ PASS | CI build verifies packaging contract; smoke test of executable covers acceptance criteria |
| V. Versioning & Breaking Changes | ✅ PASS | `v*` tags trigger release; semantic versioning via existing `pyproject.toml`; no breaking changes to user-facing API |
| Tech Constraints | ✅ PASS | Python 3.14+; PyInstaller is dev/CI tooling only (not a new runtime dependency) |
| Quality Gates | ✅ PASS | CI must pass before merge; partial releases allowed (individual platform failures do not block release per FR-003); existing pytest suite runs in CI before packaging |

**Post-Phase 1 re-check**: PASS — design (spec file + workflow) adds no violations. The `main.py` patch is a 4-line addition; it does not increase complexity beyond what is strictly necessary.

## Project Structure

### Documentation (this feature)

```text
specs/009-self-executable-build/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/
│   └── build-artifacts.md   # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
└── catguard/
    └── main.py              # PATCH: add _get_resource_dir() helper (4 lines)

.github/
└── workflows/
    └── build.yml            # NEW: CI/CD pipeline (build + release jobs)

catguard.spec                # NEW: PyInstaller spec file

assets/                      # existing — bundled via spec datas entry
├── icon.ico
└── sounds/
    └── default.wav

tests/
├── integration/             # existing — unchanged
└── unit/                    # existing — unchanged
```

**Structure Decision**: Single project layout. This feature adds only build infrastructure (`catguard.spec`, `.github/workflows/build.yml`) and a 4-line patch to `src/catguard/main.py` for asset path resolution in packaged environments. No new source directories or modules are introduced.

## Complexity Tracking

> No constitution violations detected — this section is not required.
