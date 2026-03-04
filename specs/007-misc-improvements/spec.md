# Feature Specification: Miscellaneous UI and Behavior Improvements

**Feature Branch**: `007-misc-improvements`  
**Created**: March 4, 2026  
**Status**: Draft  
**Input**: User description: "Set of improvements. 1) Add Rename button for sound library. By clicking rename existing file in library in dialog window. 2) If time window specified in settings then camera should be enabled only in that time. In other words, outside time window the app is in pause. 3) If frame's top border is out of screen, draw object and confidence on bottom of the frame. If the bottom is out of screen too, try left border, try right, and in the end (if all borders and placeholder for text is out of screen) just draw in the center of border rectangle. 4) Draw date and time in format according to locale. 5) After sleep mode camera is not restored if app was launched before sleep mode."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Time Window Enforces Camera Pause (Priority: P1)

A user configures an active monitoring time window (e.g., 08:00–18:00) in the Settings. The app automatically pauses camera-based detection outside that window and resumes it when the window begins again — without any manual intervention.

**Why this priority**: This is a behavioral correctness issue. Once a time window is configured, any detection happening outside it is undesired and wastes resources. Users who configure a window expect strict enforcement.

**Independent Test**: Configure a time window. Advance system clock beyond the window end, restart the app or wait for the clock to cross the boundary, and verify the camera stops. Advance the clock back into the window and verify the camera resumes.

**Acceptance Scenarios**:

1. **Given** a time window is configured and the current time is inside the window, **When** the app starts, **Then** the camera activates and detection runs normally.
2. **Given** the app is running and detection is active, **When** the system clock crosses the end of the configured time window, **Then** the app transitions to paused state and the camera turns off.
3. **Given** the app is in time-window-enforced pause, **When** the system clock reaches the start of the configured time window, **Then** the app resumes detection and the camera activates.
4. **Given** a time window is configured and the current time is outside the window, **When** the app starts, **Then** the app starts in paused state with the camera off.
5. **Given** no time window is configured, **When** the app runs throughout the day, **Then** the camera runs continuously as before (no change in behavior).

---

### User Story 2 - Camera Restored After Sleep Mode (Priority: P2)

A user's computer enters sleep mode while CatGuard is running with the camera active. When the computer wakes, the app detects the wakeup event and automatically restores camera operation, resuming detection without requiring the user to restart the app.

**Why this priority**: This is a reliability defect that silently breaks protection after every sleep cycle. Users expect the app to self-recover from system sleep.

**Independent Test**: Start the app with detection active. Put the computer to sleep. Wake the computer. Verify within 10 seconds that detection resumes and the tray icon reflects an active state.

**Acceptance Scenarios**:

1. **Given** the app is running with the camera active, **When** the system wakes from sleep, **Then** the camera restarts and detection resumes automatically.
2. **Given** the app was in paused state before sleep (manual pause or outside time window), **When** the system wakes from sleep, **Then** the app remains in paused state (does not incorrectly restart the camera).
3. **Given** the app is running and the camera device becomes unavailable after wake, **When** the system wakes from sleep, **Then** the app retries camera access using the same retry logic as at startup and notifies the user if the camera cannot be restored.

---

### User Story 3 - Rename Sound File in Library (Priority: P3)

A user opens the sound library list and selects a file they want to rename. They click a "Rename" button, enter a new name in a dialog, confirm, and the file is immediately renamed on disk and updated in the list — without affecting playback configuration.

**Why this priority**: Sound library management is a quality-of-life improvement. Users who record many sounds need to organize them with meaningful names. It does not affect core detection behavior.

**Independent Test**: Open the sound library, select a file, click Rename, enter a new valid name, confirm, and verify the entry updates in the list and the file is renamed on disk.

**Acceptance Scenarios**:

1. **Given** the sound library is open and a file is selected, **When** the user clicks Rename, **Then** a dialog appears pre-filled with the current file name.
2. **Given** the rename dialog is open, **When** the user clears the name and enters a valid new name and confirms, **Then** the file is renamed on disk and the library list reflects the new name.
3. **Given** the rename dialog is open, **When** the user cancels, **Then** the file is unchanged and the library list is unaffected.
4. **Given** the rename dialog is open, **When** the user submits an empty name or a name containing invalid file-system characters, **Then** the rename is rejected and an inline error is shown.
5. **Given** the rename dialog is open, **When** the user submits a name that already exists in the library, **Then** the rename is rejected with a descriptive error message.
6. **Given** the sound is currently selected as the active alert sound, **When** it is renamed, **Then** the alert sound configuration updates to the new name automatically so alerts continue to work.

---

### User Story 4 - Annotation Stays Visible for Off-Screen Detection Boxes (Priority: P4)

A detected object's bounding box is partially or fully outside the visible screen area (e.g., object at the very top edge of the monitor). The annotation label (object class and confidence) is repositioned to remain visible within the screen boundaries using a defined fallback order.

**Why this priority**: Without this fix, annotation labels silently disappear for edge-positioned objects, making it impossible to read detection results. It is a display correctness fix.

**Independent Test**: Simulate or manually position a bounding box so its top edge is off-screen. Verify the label is drawn inside the screen at the bottom of the box. Repeat for bottom, left, and right edges off-screen. Verify the center fallback is used when all edges are off-screen.

**Acceptance Scenarios**:

1. **Given** a detected object's bounding box top edge is off-screen, **When** the annotation is drawn, **Then** the label is placed below the box (at the bottom edge), visible within the screen.
2. **Given** the bottom edge fallback position is also off-screen, **When** the annotation is drawn, **Then** the label is placed at the left edge of the box, visible within the screen.
3. **Given** the left edge fallback is also off-screen, **When** the annotation is drawn, **Then** the label is placed at the right edge of the box, visible within the screen.
4. **Given** all four edge positions are off-screen, **When** the annotation is drawn, **Then** the label is drawn at the center of the bounding rectangle.
5. **Given** a normally positioned bounding box (top edge on-screen), **When** the annotation is drawn, **Then** existing behavior is unchanged (label drawn at the top of the box).

---

### User Story 5 - Date and Time Display Follows System Locale (Priority: P5)

Dates and times stamped on saved screenshots and shown on live annotations use the format configured in the user's operating system locale settings (e.g., DD/MM/YYYY HH:mm for UK locale, MM/DD/YYYY for US locale, 24-hour vs. 12-hour time).

**Why this priority**: Locale-aware formatting is a correctness and usability improvement for users in non-US locales. It is a low-risk, isolated change.

**Independent Test**: Change the OS locale to a non-default setting, trigger a detection event, and verify that the date/time on the annotation uses the correct locale format.

**Acceptance Scenarios**:

1. **Given** the OS locale uses a day-first date format, **When** a detection annotation is rendered, **Then** the date follows that format.
2. **Given** the OS locale uses a 24-hour clock, **When** a detection annotation is rendered, **Then** the time is shown in 24-hour format.
3. **Given** the OS locale uses a 12-hour clock with AM/PM, **When** a detection annotation is rendered, **Then** the time is shown with AM/PM indicator.
4. **Given** the OS locale changes while the app is running, **When** the next annotation is rendered, **Then** the new locale format is applied (or applied at next app start — see Assumptions).

---

### Edge Cases

- What happens if the time window start and end are identical (zero-length window)? The window is treated as inactive, and the camera runs continuously.
- What happens when the user presses Resume while outside the time window? The camera starts (user override as per FR-004b); the app will auto-pause again at the next window-end crossing.
- What happens if the time window spans midnight (e.g., 22:00–06:00)? The app correctly handles cross-midnight windows.
- What happens if the computer wakes from sleep and no camera device is detected? The app retries access and shows an error notification if unsuccessful, then re-attempts at the next detection cycle.
- What happens if the user tries to rename a sound file while it is currently playing? Active playback is stopped immediately and the rename proceeds without a confirmation prompt.
- What happens if a detected bounding box is entirely outside the screen? The center-of-box fallback still positions the label at the box's geometric center.

## Requirements *(mandatory)*

### Functional Requirements

**Time Window Enforcement**

- **FR-001**: The app MUST monitor the current time against the configured time window continuously while running.
- **FR-002**: When the current time is outside the configured time window, the app MUST automatically pause camera access and detection, as if the user had manually paused.
- **FR-003**: When the current time enters the configured time window, the app MUST automatically resume camera access and detection.
- **FR-004**: If the user manually pauses during an active time window, the manual pause takes effect; resuming requires an explicit user action and will resume the camera regardless of whether the window is still active.
- **FR-004b**: If the app is auto-paused because the current time is outside the time window, the user MAY override by clicking Resume in the tray menu; the camera starts immediately and stays active until the next window-end boundary triggers an automatic pause.
- **FR-005**: If no time window is configured, the existing always-on behavior MUST remain unchanged.
- **FR-005b**: When the app is in a time-window-enforced pause, the tray icon MUST display the same paused visual state (color/icon) as a manual pause. No separate visual distinction is required for scheduled vs. manual pause.

**Camera Recovery After Sleep**

- **FR-006**: The app MUST subscribe to operating system sleep/wake events.
- **FR-007**: Upon receiving a wake event, the app MUST evaluate the current time against the configured time window (if any) before deciding whether to restart the camera. The camera MUST only be restored if: (a) detection was active before sleep AND (b) the current time is inside the active time window (or no time window is configured).
- **FR-008**: If the app was paused before sleep (manual or time-window), the wake event MUST NOT restart the camera.
- **FR-009**: If the camera cannot be reacquired after wake, the app MUST apply the same retry/error handling logic used at startup.

**Sound Library Rename**

- **FR-010**: The sound library UI MUST display a Rename button that becomes active when a sound file is selected.
- **FR-011**: Clicking Rename MUST open a single-field dialog pre-filled with the current file name (without extension).
- **FR-012**: On confirmation, the app MUST rename the file on disk and update the display name in the library list.
- **FR-013**: The rename operation MUST validate that the new name is non-empty, contains only valid file-system characters, and does not conflict with an existing library entry.
- **FR-014**: If the renamed file is the currently configured alert sound, the configuration MUST be updated automatically to reference the new file name.
- **FR-015**: Cancelling the dialog MUST leave the file and configuration unchanged.
- **FR-015b**: If the file selected for renaming is currently playing, the app MUST stop playback immediately before opening the rename dialog, without any confirmation prompt.

**Annotation Placement Fallback**

- **FR-016**: Before drawing an annotation label, the app MUST check whether the intended draw position is within screen bounds.
- **FR-017**: Fallback order for an off-screen top position: bottom of box → left of box → right of box → center of box.
- **FR-018**: The fallback MUST use the first position where the entire label fits within the screen.
- **FR-019**: If no edge position fits, the label MUST be drawn at the geometric center of the bounding rectangle regardless of whether it is fully on-screen.

**Locale-Aware Date/Time**

- **FR-020**: Date and time values displayed in detection annotations MUST be formatted according to the operating system's locale settings.
- **FR-021**: The locale format MUST be read from the system at app startup; changes to locale while the app runs take effect at the next startup.

### Key Entities

- **Time Window**: A configured start time and end time that defines the daily active monitoring period. Has a flag indicating whether it is enabled.
- **Sound Library Entry**: A user-managed audio file with a display name, a file path on disk, and an association to playback configuration.
- **Annotation Label**: The text overlay drawn on a detection frame containing object class, confidence score, and timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a computer wakes from sleep, the app resumes detection within 10 seconds with no user action required.
- **SC-002**: When the system clock crosses a time window boundary, the camera state changes within 60 seconds.
- **SC-003**: A user can rename a sound file from the library in under 30 seconds with zero errors when the name is valid.
- **SC-004**: Annotation labels are visible on-screen for 100% of detected objects, including those with bounding boxes at screen edges.
- **SC-005**: Date/time annotations match the OS locale format for all tested locale configurations (verified for at least 3 distinct locale settings).
- **SC-006**: No existing detection, alerting, or sound playback functionality is disrupted by any of these changes.

## Clarifications

### Session 2026-03-04

- Q: When the app is auto-paused because the current time is outside the time window and the user clicks Resume in the tray, what should happen? → A: User override — Resume starts the camera and keeps it running; the next window-end boundary will auto-pause again as normal.
- Q: What happens if the user tries to rename a sound file while it is currently playing? → A: Stop playback immediately, then rename — no confirmation prompt.
- Q: What should the tray icon show when the app is auto-paused due to the time window? → A: Same color/icon as a manual pause — no visual distinction between scheduled and manual pause.
- Q: On wake from sleep, the camera was active before sleep but the current time is now outside the time window — should the camera restore? → A: Evaluate time window on wake — if outside the window, remain paused even though the camera was active before sleep.

## Assumptions

- **A-001**: "Time window" refers to a single daily time range (start time to end time). Recurring weekly schedules or multiple windows per day are out of scope.
- **A-002**: A cross-midnight time window (e.g., 22:00–06:00) is supported.
- **A-003**: Locale format is read once at app startup; live locale changes require a restart to take effect.
- **A-004**: Sound file renaming renames the underlying file on disk. It does not create a copy; the original file name is gone after rename.
- **A-005**: The annotation placement fallback checks whether the label text fits within the screen, not just the anchor point position.
- **A-006**: If the user is on a system where sleep/wake events are not available (e.g., headless server), the camera restoration feature degrades gracefully (no-op) and does not cause errors.
