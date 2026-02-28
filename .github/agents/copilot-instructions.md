# source Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-28

## Active Technologies
- Python 3.11+ + OpenCV `cv2` (JPEG encoding — already a runtime dependency), `platformdirs` (transitive via ultralytics — `user_pictures_dir()`), `pystray` (tray `notify()` for failure notifications — already a runtime dependency), `pydantic` (Settings model extension), `tkinter` (settings UI — stdlib) (003-cat-detection-screenshots)
- JPEG files on local disk (`<root>/<yyyy-mm-dd>/<HH-MM-SS[-N]>.jpg`) (003-cat-detection-screenshots)

- Python 3.11+ (1-catguard-app)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes
- 003-cat-detection-screenshots: Added Python 3.11+ + OpenCV `cv2` (JPEG encoding — already a runtime dependency), `platformdirs` (transitive via ultralytics — `user_pictures_dir()`), `pystray` (tray `notify()` for failure notifications — already a runtime dependency), `pydantic` (Settings model extension), `tkinter` (settings UI — stdlib)

- 1-catguard-app: Added Python 3.11+

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
