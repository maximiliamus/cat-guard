# Data Model: Self-Executable Build & Distribution

**Branch**: `009-self-executable-build` | **Date**: 2026-03-08

---

## Overview

This feature introduces no new runtime data models or persistent state. It adds build infrastructure and a small source patch. The relevant "data" is the structure of build artifacts and pipeline configuration.

---

## Build Artifact

Represents a single packaged executable produced by the CI pipeline.

| Field | Type | Description |
|-------|------|-------------|
| `platform` | `enum` | `windows`, `macos`, `linux` |
| `filename` | `string` | Platform-specific name (see Naming Convention) |
| `version` | `semver` | Matches `pyproject.toml` project version and git tag (`v{version}`) |
| `contents` | `directory` | `--onedir` PyInstaller output, zipped for distribution |
| `entry_point` | `string` | `catguard.exe` (Windows) or `catguard` (macOS/Linux) inside the zip |
| `trigger` | `enum` | `ci` (main branch push) or `release` (version tag) |
| `retention` | `int` | 7 days for CI artifacts; permanent for GitHub Release assets |

### Naming Convention

| Platform | CI Artifact Name | Release Asset Name |
|----------|------------------|--------------------|
| Windows | `catguard-windows` | `catguard-{version}-windows.zip` |
| macOS | `catguard-macos` | `catguard-{version}-macos.zip` |
| Linux | `catguard-linux` | `catguard-{version}-linux.zip` |

---

## Source Patch: Resource Path Resolution

The only runtime code change is a path-resolution helper added to `src/catguard/main.py`.

### Current behavior (development)

```python
assets_dir = Path(__file__).parent.parent.parent / "assets" / "sounds"
```

`__file__` resolves to `<repo_root>/src/catguard/main.py`, so `parent.parent.parent` is the repo root.

### Patched behavior (development + packaged)

```python
def _get_resource_dir() -> Path:
    """Return the root resource directory for both dev and packaged environments."""
    if getattr(sys, 'frozen', False):   # set by PyInstaller at runtime
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent.parent

assets_dir = _get_resource_dir() / "assets" / "sounds"
```

`sys._MEIPASS` is the temp directory where PyInstaller extracts bundled data files. The `assets/` tree is bundled via the spec `datas` entry, so `_get_resource_dir() / "assets" / "sounds"` resolves correctly in both environments.

---

## Pipeline Configuration Structure

The GitHub Actions workflow (`build.yml`) configures:

| Element | Value |
|---------|-------|
| Triggers | `push` to `main` (CI); `push` of `v*` tag (release) |
| Build matrix | `windows-latest`, `macos-latest`, `ubuntu-latest` |
| Python version | `3.11` |
| PyInstaller mode | `--onedir` + zip |
| Artifact retention | 7 days |
| Release action | `softprops/action-gh-release@v2` |

---

## State Transitions

```
git push → main
    └─→ [build job: windows + macos + linux in parallel]
            └─→ CI artifacts uploaded (retention: 7 days)
            └─→ (no release)

git push → v* tag
    └─→ [build job: windows + macos + linux in parallel]
            └─→ CI artifacts uploaded
    └─→ [release job: after all build jobs pass]
            └─→ artifacts downloaded
            └─→ GitHub Release created with all 3 zips attached
```
