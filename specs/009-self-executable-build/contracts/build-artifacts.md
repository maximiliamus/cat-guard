# Contract: Build Artifacts

**Branch**: `009-self-executable-build` | **Date**: 2026-03-08

---

## Overview

The CI pipeline exposes the following contract: on every successful build, it produces platform-specific executable archives as GitHub Actions artifacts. On version-tagged builds, these archives are attached to a GitHub Release.

---

## Artifact Contract

### Per-Platform Archive

Each artifact is a zip archive containing the `--onedir` PyInstaller output.

```
catguard-{version}-{platform}.zip
└── catguard/
    ├── catguard[.exe]       # main executable
    ├── assets/
    │   ├── sounds/
    │   │   └── default.wav
    │   └── icon.ico
    ├── _internal/           # PyInstaller bundled runtime (torch, ultralytics, cv2, …)
    └── [platform DLLs/dylibs]
```

### Platforms

| Platform | `{platform}` | Executable name | Runner |
|----------|-------------|-----------------|--------|
| Windows | `windows` | `catguard.exe` | `windows-latest` |
| macOS | `macos` | `catguard` | `macos-latest` |
| Desktop Linux | `linux` | `catguard` | `ubuntu-latest` |

### Versioning

- `{version}` matches the git tag (e.g., `v0.4.0`) and `pyproject.toml` project version.
- Tags must follow semver prefixed with `v` (e.g., `v1.0.0`, `v0.4.1`).

---

## Pipeline Contract

### Triggers

| Event | Outcome |
|-------|---------|
| `push` to `main` | Build all 3 platforms; upload as Actions artifacts (7-day retention); no GitHub Release |
| `push` of `v*` tag | Build all 3 platforms; upload as Actions artifacts; create GitHub Release with all 3 archives attached |

### Failure Contract

- FR-006 mandates clear failure reporting. If any build step fails:
  - The failed matrix job exits non-zero with its full build log visible in the GitHub Actions UI.
  - `fail-fast: false` ensures other platforms continue building for diagnostic comparison.
  - The `release` job is blocked if any `build` job fails (via `needs: build`).

### Permissions Required

The workflow requires `contents: write` permission to create GitHub Releases. This is declared at the workflow level; no PAT is required.

---

## End-User Contract

A user who downloads a release artifact receives:

1. A zip archive named `catguard-{version}-{platform}.zip`.
2. After extraction, a directory named `catguard/` containing the executable at `catguard/catguard[.exe]`.
3. On first run, the app downloads the YOLO model (~6 MB) to `~/.ultralytics/assets/` and creates the default config file — same behavior as the Python version.
4. All existing CatGuard features function as in the Python version (FR-002, SC-002).

**Known limitations** (accepted for MVP):
- Windows: SmartScreen security warning on first run. Workaround: right-click → Properties → Unblock.
- macOS: Gatekeeper blocks unsigned executable. Workaround: System Settings → Privacy & Security → Open Anyway.
- Linux: Requires a desktop session (X11 or Wayland). Headless Linux is out of scope.
