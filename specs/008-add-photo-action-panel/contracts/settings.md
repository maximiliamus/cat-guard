# Photo Action Panel Settings Contract

This document specifies the new settings fields added for the Photo Action Panel feature (`008-add-photo-action-panel`).

## Settings Overview

Six new settings have been added to the `catguard.config.Settings` pydantic model to control photo capture, countdown timing, and file storage behavior.

---

## Settings Reference

### `photos_directory`

**Type**: `str`  
**Default**: System pictures directory + `/CatGuard/photos` (e.g., `C:\Users\Username\Pictures\CatGuard\photos` on Windows, `~/Pictures/CatGuard/photos` on Unix)  
**Validation**: Must be a relative or absolute path; MUST NOT contain `..` components (path traversal protection)  
**Description**: 
- Root directory where captured photos are stored when user clicks "Save" (without dialog).
- Organized into subdirectories by capture date: `YYYY-MM-DD/HH-MM-SS.jpg`
- Directory is created automatically if it doesn't exist.
- Defaults to the system's Pictures directory, making photos easily accessible to the user.
- Used by: PhotoWindow Save button (NFR-SEC-001)

**Example**:
```python
settings = Settings()
# On Windows: photos_directory = "C:\\Users\\Alice\\Pictures\\CatGuard\\photos"
# On Linux: photos_directory = "/home/alice/Pictures/CatGuard/photos"

settings = Settings(photos_directory="/custom/photo/path")
# Results in: /custom/photo/path/2026-03-05/14-23-05.jpg
```

---

### `tracking_directory`

**Type**: `str`  
**Default**: System pictures directory + `/CatGuard/tracking` (e.g., `C:\Users\Username\Pictures\CatGuard\tracking` on Windows, `~/Pictures/CatGuard/tracking` on Unix)  
**Validation**: Must be a relative or absolute path; MUST NOT contain `..` components (path traversal protection)  
**Description**:
- Directory for effectiveness tracking screenshots from detection verification workflows (features 005–007).
- Replaces the deprecated `screenshots_root_folder` setting from earlier versions.
- Organized into subdirectories by capture date: `YYYY-MM-DD/HH-MM-SS.jpg`
- Directory is created automatically if it doesn't exist.
- Defaults to the system's Pictures directory for consistency with photos_directory.
- If path is relative, it's resolved relative to the current working directory.
- Used by: `screenshots.py:resolve_root()` to determine tracking screenshot storage location

**Example**:
```python
settings = Settings()
# On Windows: tracking_directory = "C:\\Users\\Alice\\Pictures\\CatGuard\\tracking"
# On Linux: tracking_directory = "/home/alice/Pictures/CatGuard/tracking"

settings = Settings(tracking_directory="/custom/tracking/path")
# Results in: /custom/tracking/path/2026-03-05/14-23-05.jpg
```

---

### `photo_image_format`

**Type**: `str`  
**Default**: `"jpg"`  
**Validation**: Must be one of: `"jpg"`, `"png"`, `"bmp"`, `"webp"` (extensible list)  
**Description**:
- File format for saved photos.
- Currently only `"jpg"` is actively used; other formats reserved for future expansion.
- Used when determining file extension in `photos.py:build_photo_filepath()`.

**Example**:
```python
settings = Settings(photo_image_format="jpg")  # Results in .jpg extension
```

---

### `photo_image_quality`

**Type**: `int`  
**Default**: `95`  
**Validation**: Integer in range `[1, 100]` inclusive; values outside this range trigger pydantic validation error  
**Description**:
- JPEG compression quality for captured photos (1 = highest compression, 100 = highest fidelity).
- Passed to `cv2.imencode(..., [cv2.IMWRITE_JPEG_QUALITY, quality])` when encoding frames.
- Higher values = larger file sizes but better image quality.
- Recommended: 85–95 for visual inspection use case.
- Used by: `photos.py:encode_photo()` and ActionPanel photo capture (NFR-PERF-001)

**Example**:
```python
settings = Settings(photo_image_quality=90)
# Results in JPEG compressed at 90% quality when captured
```

---

### `tracking_image_quality`

**Type**: `int`  
**Default**: `90`  
**Validation**: Integer in range `[1, 100]` inclusive  
**Description**:
- JPEG compression quality for effectiveness tracking screenshots (reserved for future features 006, 007, 008).
- Not actively used in feature 008 but available for tracking workflows.
- Uses same validation rules and encoder as `photo_image_quality`.

**Example**:
```python
settings = Settings(tracking_image_quality=85)
```

---

### `photo_countdown_seconds`

**Type**: `int`  
**Default**: `3`  
**Validation**: No explicit range validation; must be positive integer (pydantic will reject negative/zero if needed in future)  
**Description**:
- Duration in seconds of the countdown timer when user clicks "Take photo with delay".
- During countdown, button text displays current tick (e.g. 3 → 2 → 1).
- Button is non-reactive to clicks during countdown (click suppression active).
- After countdown reaches 0, photo is captured and PhotoWindow opens.
- Used by: `ActionPanel._on_take_photo_delay_click()` via `settings.photo_countdown_seconds` (FR-US2-001)

**Example**:
```python
settings = Settings(photo_countdown_seconds=5)
# User sees: "5" → "4" → "3" → "2" → "1" → captures photo
```

---

## Validation Rules Summary

| Setting | Constraint | Error Behavior |
|---------|-----------|-----------------|
| `photos_directory` | No `..` path components | Pydantic validation error |
| `tracking_directory` | No `..` path components | Pydantic validation error |
| `photo_image_format` | Must be `"jpg"`, `"png"`, etc. | Pydantic validation error (if enum validation enabled) |
| `photo_image_quality` | Integer in `[1, 100]` | Pydantic validation error |
| `tracking_image_quality` | Integer in `[1, 100]` | Pydantic validation error |
| `photo_countdown_seconds` | Positive integer (recommended) | No hard validation; runtime errors if non-positive |

---

## Integration Points

### PhotoWindow

- Uses: `settings.photos_directory`, `settings.photo_image_format`, `settings.photo_image_quality`
- When user clicks "Save": Creates directories and encodes photo at specified quality

### ActionPanel

- Uses: `settings.photo_countdown_seconds`, `settings.photo_image_quality`
- Countdown timer: Reads `photo_countdown_seconds` to initialize countdown
- Photo capture: Passes `photo_image_quality` to `encode_photo()` for JPEG compression

### Detection Loop / Frame Capture

- No direct settings usage; settings are passed through to UI components

---

## File Format

Settings are stored in `catguard_config.json` in the standard pydantic model serialization format:

```json
{
  "photos_directory": "/home/alice/Pictures/CatGuard/photos",
  "tracking_directory": "/home/alice/Pictures/CatGuard/tracking",
  "photo_image_format": "jpg",
  "photo_image_quality": 95,
  "tracking_image_quality": 90,
  "photo_countdown_seconds": 3
}
```

**Note**: The `photos_directory` and `tracking_directory` paths in the JSON file reflect the actual system paths. On Windows, they would look like:
```json
{
  "photos_directory": "C:\\Users\\Alice\\Pictures\\CatGuard\\photos",
  "tracking_directory": "C:\\Users\\Alice\\Pictures\\CatGuard\\tracking",
  ...
}
```

All other settings from the base `Settings` model (e.g., camera index, detection threshold) are also present in this file.

---

## Backward Compatibility

**Status**: New settings (not present in existing configs).

When existing `catguard_config.json` files are loaded:
- Missing settings are populated with defaults via pydantic's `Field(default=...)` mechanism
- No migration script required; defaults are applied automatically
- File is NOT automatically rewritten; new settings appear only when user modifies settings via UI or rebuilds config

---

## Testing

All settings are validated by tests in `tests/unit/test_config.py`:

- `TestPhotoSettingsDefaults`: Verify all new settings have correct defaults
- `TestPhotoSettingsValidation`: Verify validators reject invalid values (e.g., quality outside 1–100, `..` in paths)
- Integration tests in `tests/integration/test_photo_action_panel.py` verify settings are properly read and applied during capture workflows

