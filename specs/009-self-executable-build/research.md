# Research: Self-Executable Build & Distribution

**Branch**: `009-self-executable-build` | **Date**: 2026-03-08

---

## Decision 1: Packaging Tool — PyInstaller

**Decision**: Use PyInstaller 6.x with `pyinstaller-hooks-contrib`.

**Rationale**:
- Largest community for this exact dependency stack (ultralytics + torch + OpenCV + pystray + tkinter). Every known pain point has documented workarounds.
- `pyinstaller-hooks-contrib` includes maintained hooks for torch, cv2, Pillow, sounddevice — this is the first line of defense before manual `--hidden-import` flags.
- Build times are fast (minutes vs. 30–60 min for Nuitka on this stack).
- Well-established GitHub Actions integration with many existing examples for Python ML desktop apps.

**Alternatives considered**:
- **Nuitka**: Compiles Python to C (faster/smaller binaries), but torch/ultralytics packaging is notoriously broken. `--nofollow-import-to=torch,ultralytics` removes the advantage; build times are 30–60 min; open DLL-loading bugs for sounddevice (#2009). Not recommended.
- **cx_Freeze**: Poorly documented for this stack; essentially no community examples for torch + ultralytics. Hook ecosystem is much smaller than PyInstaller's. Not recommended.

---

## Decision 2: Bundle Mode — `--onedir` (zipped for distribution)

**Decision**: Build with `--onedir` (directory bundle), then zip the output directory into a single archive per platform for GitHub Release download.

**Rationale**:
- `--onefile` unpacks itself into a temp directory on every launch. With PyTorch, this creates a multi-hundred MB extraction cost on every cold start — confirmed PyInstaller issue #8211 shows 6–7× slower inference after `--onefile` packing.
- Windows antivirus frequently quarantines or delays extraction from temp directories for large ML bundles.
- `--onedir` with zip satisfies the "single downloadable artifact per platform" distribution requirement at zero performance cost.
- macOS produces a `.app` bundle directory anyway with `--windowed`; zipping is the natural distribution format.

**Alternatives considered**:
- **`--onefile`**: Simpler distribution (truly one file), but severe performance penalty with torch. Rejected.
- **`--onefile` with `--runtime-tmpdir .`**: Extracts next to itself rather than temp, but still re-extracts on every run. Not a clean solution. Rejected.

---

## Decision 3: Asset Path Resolution — `sys._MEIPASS` Shim Required

**Decision**: Add a small `_get_resource_path()` helper to `main.py` to resolve the assets directory in both development and packaged environments.

**Rationale**: In `main.py`, assets are currently resolved as:
```python
assets_dir = Path(__file__).parent.parent.parent / "assets" / "sounds"
```
In a PyInstaller bundle, `__file__` points to inside the extraction directory, so `parent.parent.parent` does not reach the repo root. The fix is:
```python
def _get_resource_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent.parent

assets_dir = _get_resource_dir() / "assets" / "sounds"
```
The assets directory (`assets/sounds/` and `assets/icon.ico`) is bundled via the PyInstaller spec's `datas` entry.

**Alternatives considered**:
- Embedding sounds as base64 strings in source: unnecessary complexity, contradicts Principle III (Simplicity). Rejected.
- Placing assets inside the `catguard` package (`src/catguard/assets/`): valid alternative, but requires moving files that are currently in the repo root `assets/` directory; deferring this restructure keeps the PR diff minimal.

---

## Decision 4: YOLO Model — Not Bundled

**Decision**: Do not bundle the YOLO `.pt` model file inside the executable. Let ultralytics download it at first run as it does today.

**Rationale**:
- The model is ~6 MB but ultralytics caches it to the user's home directory (`~/.ultralytics/assets/`). This logic works correctly in a packaged executable — no change required.
- Bundling the model would inflate every executable download by 6 MB for something downloaded once anyway.
- The first-run download flow is already tested and documented; no regression risk.

---

## Decision 5: GitHub Actions Workflow Structure

**Decision**: Two-job workflow — `build` (matrix, all pushes) + `release` (tag-only, downloads all artifacts and publishes GitHub Release).

**Rationale**:
- Separating build and release jobs prevents race conditions (all matrix runners would otherwise try to create the same Release concurrently).
- `fail-fast: false` on the matrix allows all three platforms to complete even if one fails, enabling better debugging.
- Using `softprops/action-gh-release@v2` (community standard) — `actions/create-release` is unmaintained since 2021.
- `actions/upload-artifact@v4` and `actions/download-artifact@v4` (v3 deprecated November 2024).

**Trigger conditions** (matching spec FR-003):
- `push` to `main` → `build` job only (CI verification, no release)
- `push` of `v*` tag → `build` + `release` jobs (publishes GitHub Release with artifacts)

---

## Decision 6: Required PyInstaller Hidden Imports

The following must be specified in the `.spec` file or via CLI flags. `pyinstaller-hooks-contrib` handles most of these automatically, but explicit declarations are needed for runtime-selected backends:

| Module | Why explicit |
|--------|-------------|
| `pystray._win32`, `pystray._darwin`, `pystray._xorg`, `pystray._appindicator` | Backend selected at runtime; static analysis cannot detect it |
| `win32timezone` | Frequently missing from auto-detected pywin32 imports |
| `tkinter`, `tkinter.ttk`, `_tkinter` | Not always auto-included, especially on Linux |
| `platformdirs.unix`, `platformdirs.windows`, `platformdirs.macos` | Dynamic submodule selection |

`collect_all('ultralytics')` in the spec collects ultralytics data files (including `cfg/default.yaml`, which is the most common ultralytics/PyInstaller failure mode) plus hidden imports automatically.

---

## Decision 7: Linux System Dependencies in CI

**Decision**: Install `python3-tk` via `apt-get` on `ubuntu-latest` before building.

**Rationale**: The `ubuntu-latest` GitHub runner does not bundle tkinter with its Python installation. PyInstaller cannot bundle `_tkinter.so` if it is not installed on the build system. This is a one-line CI step.

**Note**: `libportaudio2` and other audio libraries are not required for the PyInstaller *build* step — only for runtime. The built Linux executable will need to document this runtime dependency for users (or statically link it via the bundled pygame/sounddevice DLLs, which handle this on most platforms).

---

## Key Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| ultralytics `cfg/default.yaml` not found in bundle | High | `collect_all('ultralytics')` in spec |
| pystray backend not found at runtime | High | Explicit hidden imports for all 4 backends |
| Large bundle size (300–600 MB with torch) | Certain | Expected; documented in quickstart; not a blocker |
| Windows SmartScreen blocks unsigned executable | Certain | Accepted known limitation (spec Assumptions); user guidance in README |
| macOS Gatekeeper blocks unsigned executable | Certain | Accepted known limitation (spec Assumptions); user guidance in README |
| CI build time > 15 min (SC-003) | Medium | `exclude_modules` for unused torch backends; UPX compression |
| Windows WMIC popup from ultralytics utility | Low | Test post-build; monkeypatch if needed |
