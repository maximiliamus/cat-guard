# quickstart.md

## Local dev steps (summary)

1. Create and switch to feature branch: `git checkout -b 008-add-photo-action-panel`
2. Run tests: `pytest -q`
3. Implement UI: modify `src/catguard/main.py` and `src/catguard/ui/*` to add panel and photo window.
4. Wire saving: reuse `src/catguard/screenshots.build_filepath` and `cv2.imencode` for encoding.
5. Run integration tests: `pytest tests/integration -q`

## Minimal manual QA

### User Story 1: Take Photo Immediately

1. **Start the app**: 
   - Run `python -m catguard` or similar
   - Click "Open" in system tray to reveal main window
   - Main window shows live camera feed with detection overlays

2. **Click "Take photo" button**:
   - Verify action panel is visible at bottom of main window
   - "Take photo" button is on the left side
   - Click "Take photo"
   - Verify a new "Photo Window" opens (separate from main window)
   - Verify the photo shows a **clean image WITHOUT detection overlays** (no bounding boxes, no labels, just the camera frame)

3. **Test "Save" button**:
   - In the photo window, click "Save" button (left side)
   - Verify button text briefly displays "Saved ✓" (~2 seconds), then returns to "Save"
   - Verify a file is created at: `images/CatGuard/photos/<YYYY-MM-DD>/<HH-MM-SS>.jpg`
   - Example: `images/CatGuard/photos/2026-03-05/14-23-05.jpg`

4. **Test "Save As..." button**:
   - In the photo window, click "Save As..." button (middle)
   - Verify system file-save dialog opens
   - On first use: dialog defaults to OS home directory
   - On subsequent uses: dialog defaults to the last directory used for "Save As..."
   - Select a location and filename (e.g., `my_photo.jpg`)
   - Click "Save" in the dialog
   - Verify file is created at the chosen location
   - Verify in-memory photo remains and window stays open (can click Save/Save As again)

5. **Test "Close" button**:
   - Click "Close" button (right side)
   - Verify photo window closes
   - Verify in-memory photo is released (cannot be saved anymore)
   - Verify main window is still visible

---

### User Story 2: Take Photo with Countdown

1. **Click "Take photo with delay" button**:
   - Verify button exists on the left side of action panel (next to "Take photo")
   - Click button
   - Verify button text immediately changes to show countdown number (default: 3)
   - Observe countdown: 3 → 2 → 1

2. **Test click suppression during countdown**:
   - Click "Take photo with delay" button
   - While countdown is active (showing 3, 2, or 1), click the button multiple times
   - Verify only ONE photo window opens (multiple clicks are suppressed)
   - Verify countdown continues uninterrupted

3. **Verify capture after countdown**:
   - Let countdown complete (reach 0)
   - Verify photo window opens automatically with a clean image
   - Verify button returns to "Take photo with delay" label after photo opens
   - Test "Save" and "Save As..." same as User Story 1

4. **Test custom countdown duration**:
   - Edit `catguard_config.json` and set `"photo_countdown_seconds": 5` (or another value)
   - Restart the app
   - Click "Take photo with delay"
   - Verify countdown now uses the new duration (5 → 4 → 3 → 2 → 1)

---

### User Story 3: Panel Layout and Close Button

1. **Verify action panel placement**:
   - Open main window
   - Verify action panel is visible at the **bottom** of the main window
   - Verify it spans the full width (`fill=X` behavior)

2. **Verify button positions**:
   - "Take photo" button: **left side**
   - "Take photo with delay" button: **left side** (next to "Take photo")
   - "Close" button: **right side**

3. **Test "Close" button in action panel**:
   - Click "Close" button in the action panel
   - Verify main window **minimizes to system tray**
   - Verify main window is **hidden** (not visible)
   - Verify system **tray icon remains active** (can click "Open" to restore)

4. **Verify resize behavior**:
   - Resize main window (make it wider/narrower, taller/shorter)
   - Verify action panel buttons remain visible and properly positioned
   - Verify "Take photo" and countdown text remain readable

---

## Error Scenarios & Edge Cases

### Save failures

1. **Permission denied**:
   - Set `photos_directory` to a read-only location
   - Click "Take photo" → "Save"
   - Verify error message displayed (inline status label)

2. **Collision handling**:
   - Take multiple photos in the same second
   - On third attempt at identical timestamp:
   - Expected file: `HH-MM-SS-1.jpg` (if HH-MM-SS.jpg and HH-MM-SS-1.jpg already exist)

### Settings edge cases

1. **Invalid quality**:
   - Edit `catguard_config.json`: set `"photo_image_quality": 150` (invalid)
   - Restart app
   - Verify app handles gracefully or shows validation warning

2. **Missing photos_directory**:
   - Set `photos_directory` to non-existent path
   - Click "Take photo" → "Save"
   - Verify directory is created automatically

---

## Important Notes for Manual Testing

### OS File Dialog Behavior

- **Automated tests**: File-save dialog is mocked (not actually executed)
- **Manual testing**: You MUST click through the OS native file-save dialog
  - Windows: FILE_DIALOG_OPEN behavior varies by Python/tkinter version
  - Linux / macOS: Similar native dialog behavior
- **Result**: The `Save As...` dialog experience varies by OS and Python version but functionality is consistent

### Photo Quality Verification

- Default `photo_image_quality=95` produces high-quality JPEGs
- If you need to verify compression, compare file sizes:
  - `photo_image_quality=95`: ~50–150 KB (typical for 1080p frame)
  - `photo_image_quality=50`: ~15–40 KB (visibly compressed)
- Visual quality inspection is subjective; recommend manual review with actual camera input

### Countdown Timing

- Default countdown is **3 seconds** (adjustable via `settings.photo_countdown_seconds`)
- Countdown precision depends on `root.after()` scheduler accuracy
- Slight variations (±100ms) are normal and acceptable

---

## Success Criteria Checklist

- [ ] All three "Take photo" buttons render and are clickable
- [ ] Photos captured are clean (no overlays, bounding boxes, or labels)
- [ ] "Save" button writes to correct dated subdirectory
- [ ] "Save As..." opens file dialog and saves to chosen location
- [ ] "Save As..." caches last directory for subsequent uses (session-scoped)
- [ ] Countdown displays ticking numbers and suppresses duplicate clicks
- [ ] "Close" button minimizes window to tray
- [ ] Action panel layout is correct (left/right alignment)
- [ ] No detection loop modifications detected (FR-010 regression gate)
- [ ] Settings are properly validated and stored
