# research.md

## Decisions and open questions

- Capture image format: JPEG (quality configurable). Decision: JPEG, quality 95 for photos, tracking screenshots default 90.
- Filename convention: reuse `screenshots.build_filepath` pattern — `<HH-MM-SS>.jpg` with collision suffix.
- Photos directory setting name: `photos_directory` (default `images/CatGuard/photos`).
- Tracking directory: `images/catGuard/tracking`.

## Tasks for Phase 0 research

- Confirm whether `screenshots.build_filepath` is public and importable (it is in `src/catguard/screenshots.py`).
- Confirm existing settings structure and add new settings keys to `Settings` model.
- Determine UI placement code path for main window and photo window (`src/catguard/ui` or `src/catguard/main.py`).
- Decide whether to reuse CV2 encoding path from `save_screenshot` for photos.

## Rationale

- Reusing existing `screenshots` helpers ensures filename consistency and reduces duplication.
- JPEG with quality 95 provides higher fidelity for user photos while keeping sizes reasonable.
