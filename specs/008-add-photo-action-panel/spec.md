# Feature Specification: Add photo action panel

**Feature Branch**: `008-add-photo-action-panel`  
**Created**: 2026-03-05  
**Status**: Draft  
**Input**: User description: "Add action panel on main window with actions: \"Take photo with delay\", \"Take photo\", \"Close\". Panel sits on the bottom of main window. Take photo buttons are on the left side, Close button is on right side of the panel. \"Take photo\" click just create a clean photo (without detection boundary, and all other lables on it) By clicking \"Take photo with delay\" the button's labels becomes countdown timer. It countdowns seconds specified in settings to take screenshot 3..2..1..takes photo. During this countdown we do not disable button (to remain text human-readable), but make button to not react on clicks (restore reaction after photo taken). After taking a photo should be stored in memory and opened in new photo window with action panel: single button  \"Save As...\" on left side and Close button on right side. By clicking on \"Save As...\" dialog opened and user can select place where to store a photot from memory."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Take photo immediately (Priority: P1)

A user wants to capture the current main window view without any detection overlays.

**Why this priority**: Core user value — ability to capture a clean photo quickly.

**Independent Test**: From the running main window, click the `Take photo` button. A new photo window opens showing the captured image; `Save`, `Save As...`, and `Close` buttons are present. The captured image contains no detection boundaries or labels.

**Acceptance Scenarios**:

1. Given the app is running and visible, When the user clicks `Take photo`, Then the app captures a clean image (no overlays), stores it in memory, and opens the photo window with `Save` (left), `Save As...` (middle), and `Close` (right).
2. Given the photo window is open, When the user clicks `Save As...`, Then a system file-save dialog opens initialised to the OS default save location (first use) or last-used directory (subsequent uses) with filename pre-populated as `catguard_YYYYMMDD_HHMMSS.jpg`; after the user confirms, the image is written to the chosen path and the in-memory copy remains until the window is closed.
3. Given the photo window is open, When the user clicks `Close`, Then the photo window closes and the in-memory photo is released.

4. Given the photo window is open, When the user clicks `Save`, Then the photo is written to the pre-configured photos directory into a subfolder named by the capture date in `YYYY-MM-DD` format (e.g. `images/CatGuard/photos/2026-03-05/14-23-05.jpg`), the `Save` button label briefly changes to `Saved ✓` for ~2 seconds then restores, and the photo window remains open.

---

### User Story 2 - Take photo with delay (Priority: P1)

A user wants a short countdown before the capture so they can prepare the scene.

**Why this priority**: Often users need a short delay to position or prepare the subject.

**Independent Test**: From the running main window, click `Take photo with delay`. The button text updates to show the countdown (e.g., 3 → 2 → 1). During countdown the button remains visually enabled (text readable) but is non-reactive to clicks. After countdown the app captures the clean image, stores it in memory, and opens the photo window.

**Acceptance Scenarios**:

1. Given countdown setting is 3 seconds, When user clicks `Take photo with delay`, Then the button text shows `3`, then `2`, then `1` each second, then triggers capture and opens the photo window.
2. Given countdown in progress, When the user clicks the countdown button, Then clicks are ignored (no new countdowns start) and the button remains showing the countdown text.
3. Given countdown completes, When capture occurs, Then the button returns to its normal label and becomes clickable again.

---

### User Story 3 - Panel layout and Close (Priority: P2)

A user expects the action panel to be accessible and for Close to dismiss the panel.

**Why this priority**: Usability — panel must not obstruct important UI and must be dismissible.

**Independent Test**: Verify the panel is anchored to the bottom of the main window; `Take photo` and `Take photo with delay` are on the left, `Close` is on the right. Clicking `Close` hides the panel (or closes the main window if that is the existing behavior — see Assumptions).

**Acceptance Scenarios**:

1. Given main window open, Then the action panel is visible at the bottom with left-aligned photo buttons and a right-aligned `Close` button.
2. Given the user clicks `Close` on the main window action panel, Then the application minimizes to the system tray (keeps running in background).

---

### Edge Cases

- User cancels the `Save As...` dialog: the in-memory photo remains and the photo window stays open.
- Multiple rapid clicks on `Take photo`: each click immediately opens its own independent photo window; parallel photo windows are allowed and each holds its own in-memory photo.
- Low memory or failure storing in-memory: show a user-friendly error in the photo window and disable save until resolved.
- Save operation fails (disk full / permission): show error and keep in-memory photo available for retry.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The main window MUST include a persistent action panel anchored at the bottom of the window.
- **FR-002**: The action panel MUST contain three actions: `Take photo with delay`, `Take photo`, and `Close`.
- **FR-003**: `Take photo` MUST capture a clean image of the main window without detection boundaries, overlays, or labels, store it temporarily in memory, and open it in a new photo window. Each click opens its own independent photo window; parallel photo windows are allowed.
- **FR-004**: `Take photo with delay` MUST display a countdown on the button label using an integer number of seconds obtained from app `Settings` and then perform the same capture flow as `Take photo`.
- **FR-005**: During the countdown, the `Take photo with delay` button MUST remain visually readable but MUST ignore additional click events until capture completes.
- **FR-006**: After capture, the photo window MUST open showing the captured image and an action panel containing `Save` (left), `Save As...` (middle), and `Close` (right).
- **FR-007**: `Save As...` MUST open a system file-save dialog with the directory initialised to the OS default save location on first use and to the last-used directory on subsequent uses within the same app session (in-memory only; resets on restart). The filename field MUST be pre-populated with `catguard_YYYYMMDD_HHMMSS.jpg` (using local system time of capture). The user may change both directory and filename before confirming.
- **FR-008**: Closing the photo window via `Close` MUST release the in-memory image and return focus to the main window.
- **FR-009**: The feature MUST handle user-cancelled saves and present clear error messages for save failures.
- **FR-010**: This feature MUST not alter existing detection capture logic for other flows; it only provides a clean-image capture path.
- **FR-011**: The photo window MUST include a `Save` button (left of `Close`) that saves the captured photo to a pre-configured directory without showing a dialog.
- **FR-012**: Saved photos MUST be organized into date-based subfolders using `YYYY-MM-DD` under the configured photos directory. Default photos directory: `images/CatGuard/photos`.
- **FR-013**: Tracking directories of the form `YYYY-MM-DD` (used by other tracking exports) MUST be stored under `images/catGuard/tracking`.
- **FR-014**: If the configured directory does not exist, the application MUST create the required folder structure (including the `YYYY-MM-DD` subfolder) before saving; on failure, show an error and keep the in-memory photo available.
- **FR-015**: Photo filenames MUST follow the time-based convention used by screenshots: `<HH-MM-SS>.jpg` with an appended counter suffix (`-1`, `-2`, ...) if a name collision occurs in the same `YYYY-MM-DD` folder. Both the date folder and the time component MUST use local system time.
- **FR-016**: Photos MUST be saved as JPEG files by default, using a default quality setting higher than tracking screenshots. Default photo JPEG quality: `95` (configurable via settings).
- **FR-017**: Tracking screenshots quality MUST be configurable via settings. Default tracking screenshot JPEG quality: `90` (configurable via settings).
- **FR-018**: After a successful `Save`, the `Save` button label MUST briefly change to `Saved ✓` for approximately 2 seconds, then restore to its original label. No modal dialog or blocking UI is shown.

### Key Entities

- **Photo (in-memory)**: A transient object representing a captured image stored in application memory until saved or closed. Attributes: capture timestamp, image bytes, source ("clean-capture").
- **Settings**: App settings relevant to this feature:
  - `photo_countdown_seconds`: integer countdown duration. Default: `3`.
  - `photos_directory`: path to default photos folder. Default: `images/CatGuard/photos`.
  - `tracking_directory`: path to tracking folder. Default: `images/catGuard/tracking`.
  - `photo_image_format`: image file format for saved photos. Default: `jpg`.
  - `photo_image_quality`: JPEG quality integer (1-100). Default: `95`.
  - `tracking_image_quality`: JPEG quality integer (1-100) for tracking screenshots. Default: `90`.
- **Photo Window**: UI component that displays the in-memory `Photo` and exposes `Save`, `Save As...`, and `Close` actions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of `Take photo` actions open the photo window with the correct clean image (testable via manual verification or automated UI test capturing expected absence of overlays).
- **SC-002**: `Take photo with delay` shows a visible countdown with integer second updates and captures at the end of countdown (verified in 95% of test runs across environments).
- **SC-003**: During countdown, the delay button ignores additional click attempts (no duplicate countdowns) in 100% of test runs.
- **SC-004**: `Save As...` successfully writes the image to disk in at least 95% of normal test cases (excluding environmental issues like disk full).
- **SC-005**: After closing the photo window, memory used by the captured photo is released (verifiable by memory inspector or by ensuring no accessible in-memory reference remains).
- **SC-006**: `Save` writes to the pre-configured photos directory inside a `YYYY-MM-DD` folder successfully in at least 95% of normal test cases.
- **SC-007**: Saved photos are encoded as JPEG with quality near the configured value (default 95) in at least 95% of normal test cases.
- **SC-008**: After a successful `Save`, the `Save` button label changes to `Saved ✓` within 200 ms and restores to its original label within 2.5 seconds in 100% of test runs.

## Assumptions

- Default countdown value is 3 seconds when `photo_countdown_seconds` is not configured.
- "Store in memory" means a single captured image object kept in process memory until user saves or closes the photo window.
- Panel `Close` behavior: clicking `Close` on the action panel minimizes the application to the system tray (keeps app running in background). Update if alternate behavior is desired.
- Only one captured photo instance is shown per photo window; each `Take photo` click opens its own independent photo window (parallel windows are allowed).
- Saved photo files are written to user-accessible filesystem paths only; no cloud upload or network transmission occurs. File permissions follow OS defaults for the running user.
- Date folders (`YYYY-MM-DD`) and time-based filenames (`HH-MM-SS`) use local system time (wall clock), consistent with existing screenshot behavior.
- The last-used `Save As...` directory is tracked in memory only and resets to the OS default on app restart; it is not persisted to settings.

## Non-Functional Requirements

### UX & Accessibility

- **NFR-UX-001**: Button labels MUST use the exact copy: `Take photo`, `Take photo with delay`, `Close`, `Save`, `Save As...`. The `Save` button temporarily shows `Saved ✓` on success (see FR-018) and `Save failed — <reason>` on error.
- **NFR-UX-002**: On save failure, the photo window MUST display a brief inline status message below the action buttons; the message clears when the user retries or closes the window.
- **NFR-UX-003**: Keyboard tab order MUST follow the standard tkinter default focus chain for all interactive elements in both the action panel and the photo window; no custom keyboard navigation is required for MVP.
- **NFR-UX-004**: Standard tkinter widget labels are sufficient for accessibility in MVP; no additional screen-reader-specific attributes are required.
- **NFR-UX-005**: The action panel and photo window MUST use `pack`/`grid` layout without fixed pixel sizes so layout scales correctly when the window is resized or system DPI changes.

### Security & Logging

- **NFR-SEC-001**: `photos_directory` and any user-supplied save path MUST be normalised with `os.path.normpath` before use; paths containing `..` components after normalisation MUST be rejected with a validation error.
- **NFR-SEC-002**: Directory creation MUST use `os.makedirs(path, exist_ok=True)` relying on OS default permissions; no explicit `chmod` is required.
- **NFR-SEC-003**: Log entries MUST include file paths at DEBUG level only; image bytes and pixel data MUST NOT be logged at any level.
- **NFR-SEC-004**: User-facing error dialogs MUST display only the filename (not the full path); the full path MUST be logged at DEBUG level for diagnostics.
- **NFR-SEC-005**: This feature introduces no new third-party dependencies; the existing `opencv-python` version already in `requirements.txt` is used for JPEG encoding.

### Performance & Reliability

- **NFR-PERF-001**: Each countdown tick MUST fire within ±200 ms of the expected 1-second interval.
- **NFR-PERF-002**: The OS file-save dialog (`asksaveasfilename`) MUST be mocked in automated tests; this requirement MUST be noted in `quickstart.md` as a manual-only test step.

## Filesystem Layout (examples)

- Default photos save path: `images/CatGuard/photos/<YYYY-MM-DD>/<filename>`
- Tracking exports path: `images/catGuard/tracking/<YYYY-MM-DD>/...`

Example filename: `images/CatGuard/photos/2026-03-05/14-23-05.jpg` (if `14-23-05.jpg` exists then `14-23-05-1.jpg`, etc.)

## Notes

- Implementation must avoid rendering detection overlays into the captured image; capture should use the underlying source frame or render the main window contents without overlays.
- Keep UI text and placement consistent with the existing app style.


---

*Spec generated from user description by automation. Update sections if any assumption needs changing.*

## Clarifications

### Session 2026-03-05

- Q: What should the `Close` button do? → A: Minimize to tray (keep running in background)
- Q: Which timezone should be used for date folders (`YYYY-MM-DD`) and filenames (`HH-MM-SS`)? → A: Local system time (wall clock, consistent with existing screenshot behavior)
- Q: What happens when `Take photo` is clicked while a capture is already in progress? → A: Each click opens its own independent photo window immediately (parallel captures allowed)
- Q: What should the `Save As...` dialog pre-populate for directory and filename? → A: Directory — OS default on first use, last-used on subsequent uses; filename — `catguard_YYYYMMDD_HHMMSS.jpg` (local system time)
- Q: What visual feedback should the `Save` button provide after a successful save? → A: Briefly update label to `Saved ✓` for ~2 seconds then restore (no modal)
- Q: Should the last-used `Save As...` directory persist across app restarts or be in-memory only? → A: In-memory only — resets to OS default on app restart (no new settings field needed)
