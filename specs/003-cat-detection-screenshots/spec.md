# Feature Specification: Screenshot on Cat Detection

**Feature Branch**: `003-cat-detection-screenshots`  
**Created**: 2026-03-01  
**Status**: Draft  
**Input**: User description: "Current behavior: when a cat is detected, a sound is played. New behavior: in addition to playing the sound, a screenshot must be taken and saved to a folder. The folder name must be the current day in yyyy-mm-dd format. This folder must reside inside a root folder that is configurable in the application settings."

## Clarifications

### Session 2026-03-01

- Q: Should screenshot saving be always active or have its own enable/disable toggle? → A: Always on (no toggle), but screenshots are only taken when the main window is NOT open.
- Q: When a screenshot fails to save, should the user see any visible notification? → A: Yes — a brief non-blocking OS tray balloon/toast notification is shown.
- Q: How should the time-of-day restriction for screenshots be configured? → A: A single daily time window (start + end time, may span midnight) with an enable/disable checkbox; when disabled, screenshots are taken at any hour.
- Q: What image format should screenshots be saved in? → A: JPEG fixed, with maximum compression to minimise disk usage.
- Q: Should the app automatically delete old screenshots after a retention period? → A: No — screenshots accumulate indefinitely; cleanup is the user's responsibility.
- Q: Should the screenshots root folder path in Settings also have a "Browse..." button to open the configured folder in the file explorer? → A: Yes.

## Assumptions

- A "screenshot" in this context means capturing the current camera frame at the moment of detection — not a screenshot of the entire desktop.
- Screenshots are saved only when a detection event triggers the alert sound (i.e., outside of the cooldown period) **and** the main application window is not currently open.
- The default root folder for screenshots is a `CatGuard` sub-folder inside the OS-standard Pictures directory (e.g., `~/Pictures/CatGuard` on Windows/macOS/Linux).
- Folder creation (root folder, `CatGuard` sub-folder, and daily date sub-folder) is deferred until the first screenshot is actually taken — no folders are created at app startup.
- Screenshots are saved as JPEG images with maximum compression (lowest quality setting that still produces a recognisable image) to minimise disk usage. The format and compression level are fixed and not user-configurable.
- The app does not perform any automatic cleanup or deletion of saved screenshots. Managing disk space and removing old files is entirely the user's responsibility.
- File names within the daily sub-folder encode the time of detection for easy identification (e.g., `HH-MM-SS.jpg`).
- The app continues to function normally (plays sound) even if the screenshot cannot be saved (e.g., disk full, permissions error); the failure is logged **and** a brief non-blocking OS tray balloon/toast notification is shown to the user.
- A configurable daily time window controls when screenshots may be saved. The window has a start time and an end time and can span midnight (e.g., 22:00–06:00). It is disabled by default, meaning screenshots are taken at any hour.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic Screenshot on Detection (Priority: P1)

Each time a cat is detected and the alert sound is triggered, the app automatically saves a screenshot of the camera frame to a date-organised folder. The user can later review these screenshots to understand when and how often their cat was on the table.

**Why this priority**: This is the core of the new feature — automatic evidence capture tied directly to the existing detection event.

**Independent Test**: Can be fully tested by triggering a detection event and verifying a correctly named image file appears in the expected `<root>/<yyyy-mm-dd>/` folder path.

**Acceptance Scenarios**:

1. **Given** the app is running, the main window is closed, and a root screenshots folder is configured, **When** a cat is detected and the sound plays, **Then** a screenshot of the current camera frame is saved inside `<root>/<today's date>/`.
2. **Given** the main window is open, **When** a cat is detected and the sound plays, **Then** no screenshot is saved.
3. **Given** a detection event occurs with the main window closed, **When** the screenshot is saved, **Then** the file name encodes the time of detection (hours, minutes, seconds) so that multiple detections on the same day produce separate files.
4. **Given** a detection is within the cooldown period (sound is suppressed), **When** the cooldown elapses and the next sound fires, **Then** only that triggering event saves a screenshot (no screenshot is saved for suppressed events).
5. **Given** a detection event occurs at midnight causing the date to change, **When** the screenshot is saved, **Then** it is placed in the folder corresponding to the actual date at save time.

---

### User Story 2 - Configure Screenshots Root Folder (Priority: P1)

A user can set the root folder where all detection screenshots are stored via the app's Settings window. The chosen path is persisted and used across app restarts.

**Why this priority**: Without the ability to configure the root folder, screenshots would be placed in a hidden or unpredictable location, making the feature unusable in practice.

**Independent Test**: Can be fully tested by changing the root folder in Settings, triggering a detection, and confirming the screenshot appears in the newly configured location.

**Acceptance Scenarios**:

1. **Given** the Settings window is open, **When** the user browses and selects a root folder, **Then** the selected path is displayed and saved.
2. **Given** a root folder is saved in settings, **When** the app restarts, **Then** the same root folder is still configured and used for new screenshots.
3. **Given** no root folder has been set by the user, **When** the app starts for the first time with this feature, **Then** the default `CatGuard` folder inside the system Pictures directory is used automatically — no configuration or setup is required.
4. **Given** the configured root folder (or any of its sub-folders) does not yet exist, **When** the first detection event occurs, **Then** the app creates all missing folders at that moment and saves the screenshot successfully.
5. **Given** the Settings window is open, **When** the user clicks the "Browse..." button next to the screenshots root folder path, **Then** the OS file explorer opens showing the contents of the currently configured root folder.

---

### User Story 3 - Graceful Failure Handling (Priority: P2)

If a screenshot cannot be saved for any reason (disk full, permissions error, invalid path), the app continues to operate normally — the alert sound still plays and the app does not crash or display a blocking error to the user.

**Why this priority**: Robustness; screenshot saving must never degrade the primary cat-detection-and-alert experience.

**Independent Test**: Can be tested by setting a read-only path as the root folder and triggering a detection, verifying the sound plays and no crash or modal error occurs.

**Acceptance Scenarios**:

1. **Given** the configured root folder is read-only, **When** a detection event occurs, **Then** the sound plays normally, the save failure is recorded in the application log, and a tray balloon/toast notification is shown.
2. **Given** the disk is full, **When** a detection event occurs, **Then** the sound plays normally, a log entry records the failed screenshot, and a tray balloon/toast notification is shown.
3. **Given** the root folder path contains invalid characters or is otherwise inaccessible, **When** the app starts, **Then** the app starts successfully and logs the problem without blocking startup; the notification is deferred until the first failed save attempt.

---

### User Story 4 - Restrict Screenshots to a Time Window (Priority: P2)

A user wants screenshots to be saved only during certain hours (e.g., at night). They can enable a daily time window in Settings by checking a checkbox and entering a start and end time. When the checkbox is unchecked, screenshots are taken at any hour.

**Why this priority**: Allows users to avoid accumulating unwanted screenshots during hours they are present and watching the table themselves.

**Independent Test**: Can be fully tested by enabling the time window, setting a range that excludes the current time, triggering a detection, and verifying no screenshot is saved; then setting a range that includes the current time and verifying a screenshot is saved.

**Acceptance Scenarios**:

1. **Given** the time window is disabled, **When** a detection event occurs at any hour, **Then** a screenshot is saved (subject to other conditions).
2. **Given** the time window is enabled with a range that covers the current time, **When** a detection event occurs, **Then** a screenshot is saved.
3. **Given** the time window is enabled with a range that does NOT cover the current time, **When** a detection event occurs, **Then** no screenshot is saved (sound still plays).
4. **Given** a midnight-spanning window (e.g., 22:00–06:00) is configured, **When** a detection occurs at 23:30, **Then** a screenshot is saved.
5. **Given** a midnight-spanning window (e.g., 22:00–06:00) is configured, **When** a detection occurs at 14:00, **Then** no screenshot is saved.
6. **Given** the time window settings are saved, **When** the app restarts, **Then** the same window enable-state, start time, and end time are restored.

---

### Edge Cases

- What happens when two detection events occur within the same second? — File names must not collide; a counter or sub-second component ensures uniqueness.
- What happens when the root folder is on a network drive that becomes unavailable? — The save attempt fails gracefully; the sound still plays and the error is logged.
- What happens when the date changes at exactly midnight during a long monitoring session? — The first detection after midnight creates a new date sub-folder automatically.
- What happens if the configured root folder is the same folder as a pre-existing important directory? — The app does not restrict this, but documentation notes the user is responsible for choosing an appropriate location.
- What happens when the main window is opened while the cat is on the table (detection is active)? — The in-progress detection event does not produce a screenshot; screenshot suppression takes effect immediately when the window opens.
- What happens when a midnight-spanning time window (e.g., 22:00–06:00) is active and the clock crosses midnight? — The window evaluation uses wall-clock time; the app handles the wrap-around correctly without requiring a restart.
- What happens when the start time and end time of the window are equal? — This is treated as a degenerate case; the app behaves as if the window is disabled (screenshots taken at any hour) and logs a warning.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The app MUST capture a screenshot of the current camera frame at every detection event that triggers an alert sound, **provided the main application window is not open at that moment**.
- **FR-002**: The app MUST save each screenshot into a sub-folder named with the current date in `yyyy-mm-dd` format inside the configured root folder.
- **FR-012**: The app MUST NOT save a **plain** screenshot if the main application window is open at the time of the detection event, regardless of all other conditions. *Note: this rule applies only to plain camera-frame screenshots captured by this feature. Annotated effectiveness screenshots produced by feature 005 are always saved regardless of window state.*
- **FR-003**: Screenshot file names MUST encode the time of detection (at minimum: hours, minutes, seconds) to uniquely identify each event within a day.
- **FR-004**: If multiple detections occur within the same second, the app MUST ensure file names are unique (e.g., by appending a counter).
- **FR-005**: The app MUST create any missing intermediate folders (root folder, `CatGuard` sub-folder, and/or date sub-folder) on-demand at the moment the first screenshot is saved — not at app startup.
- **FR-006**: The Settings window MUST include a field where the user can view and change the screenshots root folder path.
- **FR-007**: The Settings window MUST place a "Browse..." button on the same line as the root folder path field; clicking it MUST open an OS folder-picker dialog so the user can select the root folder without typing a path manually.
- **FR-008**: The configured root folder path MUST be persisted in the application settings and survive app restarts.
- **FR-009**: When no root folder has been explicitly configured, the app MUST default to a `CatGuard` sub-folder inside the user's standard Pictures directory. This default MUST be resolved at runtime for the current user and operating system.
- **FR-010**: If saving a screenshot fails for any reason, the app MUST continue operating normally (sound plays, detection continues), MUST log the error, and MUST display a brief non-blocking OS tray balloon/toast notification describing the failure.
- **FR-011**: Screenshots MUST NOT be saved for detection events suppressed by the cooldown timer.
- **FR-013**: The Settings window MUST include a checkbox to enable or disable the screenshot time window. When unchecked, screenshots are taken at any hour.
- **FR-014**: When the time window is enabled, the Settings window MUST allow the user to set a start time and an end time (hours and minutes). The window MAY span midnight (end time earlier than start time).
- **FR-015**: The app MUST NOT save a screenshot if the time window is enabled and the current wall-clock time falls outside the configured window. The alert sound is unaffected by this restriction.
- **FR-016**: The time window enable-state, start time, and end time MUST be persisted in application settings and restored on restart.
- **FR-017**: Screenshots MUST be saved in JPEG format with maximum compression. The format and compression level are fixed and MUST NOT be exposed as user-configurable settings.
- **FR-018**: The Settings window MUST include a "Browse..." button on the same line as the screenshots root folder path field; clicking it MUST open the configured root folder in the OS file explorer.

### Key Entities

- **Detection Event**: A moment in time when the app's detection engine triggers an alert (sound plays, cooldown starts). Carries a timestamp and the camera frame at that instant.
- **Screenshot**: A still image captured from the camera frame at the moment of a detection event. Stored as a file on disk inside a date-organised folder hierarchy.
- **Screenshots Root Folder**: A user-configurable directory that acts as the top-level container for all screenshot sub-folders. Stored as a setting.
- **Screenshot Time Window**: An optional daily time restriction (start time + end time, can span midnight) stored as a setting. When enabled, only detection events occurring within the window produce screenshots. Has an explicit enabled/disabled flag; disabled by default.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every detection event that plays a sound produces exactly one screenshot file in the correct date sub-folder within 2 seconds of the detection occurring — **provided** the main application window is closed and, when the time window is enabled, the current wall-clock time falls within the configured window.
- **SC-002**: A user can locate all screenshots from a given day by navigating to a single, predictably named folder (`<root>/<yyyy-mm-dd>/`) — no manual search required.
- **SC-003**: A user can change the screenshots root folder in Settings and have the change take effect for the very next detection event, without restarting the app.
- **SC-004**: Zero detection-sound events are lost or delayed due to screenshot saving — the primary alert functionality remains unaffected in 100% of observed test cases.
- **SC-005**: When screenshot saving fails, the failure is visible in the application log and a tray notification is shown to the user within 5 seconds, with a message that identifies the cause (e.g., permission denied, disk full).
- **SC-006**: When the time window is enabled, zero screenshots are produced for detection events outside the configured window, while alert sounds continue to fire normally in 100% of observed test cases.
