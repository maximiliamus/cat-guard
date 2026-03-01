# Feature Specification: Tray Open - Main Window

**Feature Branch**: `[2-tray-open-mainwindow]`  
**Created**: 2026-03-01  
**Status**: Draft  
**Input**: User description: "Behavior now: The program starts and we see a tray icon with a context menu containing Settings and Exit. New behavior: When the program starts the tray context menu should include also a new menu item `Open`. When we click `Open`, the main application window should appear sized to the captured frame. The UI should indicate what it is detecting. If a cat is visible, the cat should be outlined with a bounding box."

## Clarifications

### Session 2026-03-01

- Q: Should the UI show the detected object class or the source application/process name? → A: Show the detected object class (e.g., "cat").

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open Main Window from Tray (Priority: P1)

A user starts the application; the app runs in the system tray. From the tray context menu the user chooses `Open` to view the live capture.

**Why this priority**: Core discoverability and inspection flow — users must be able to open the main view to verify detection results.

**Independent Test**: With the application running in the tray, right-click the tray icon and select `Open`. Verify the main window appears and matches acceptance criteria below.

**Acceptance Scenarios**:

1. **Given** the app is running in the tray with a standard tray menu (Settings, Exit), **When** the user opens the menu, **Then** the menu contains an `Open` item.
2. **Given** the user clicks `Open`, **When** the main window is shown, **Then** its outer window size equals the currently captured frame size (width × height) visually and programmatically.
3. **Given** the captured frame contains a cat, **When** the main window is visible, **Then** the cat is shown with a visible bounding box drawn around it.
4. **Given** the captured frame contains detections, **When** the main window is visible, **Then** the UI shows the detected object class (for example, "cat") next to each detection.

---

### User Story 2 - Tray Presence & Existing Items (Priority: P2)

Ensure the existing tray menu items remain: `Settings` and `Exit`, plus the new `Open`.

**Why this priority**: Preserve existing behavior while adding discoverability.

**Independent Test**: Right-click tray icon and confirm three items exist (order may be defined by UX).

**Acceptance Scenarios**:

1. **Given** the app is running, **When** the user inspects the tray menu, **Then** the menu contains `Settings`, `Open`, and `Exit`.

---

### User Story 3 - Detection Visualization (Priority: P2)

The main window should present the live capture with detection overlays, including bounding boxes and detection labels.

**Why this priority**: Visual verification of detection results is the main purpose of the main window.

**Independent Test**: With known test images or live camera that includes a cat, confirm bounding boxes appear around each detected cat and a textual label is visible.

**Acceptance Scenarios**:

1. **Given** the capture contains one or more cats, **When** view is open, **Then** each cat has a bounding box and a short label next to it.
2. **Given** no objects detected, **When** view is open, **Then** the UI shows an unobtrusive message such as "No detections" and still matches the captured frame size.

---

### Edge Cases

- Multiple cats in the frame: all cats should receive bounding boxes and labels.
- Missing capture source: selecting `Open` should show a clear error/message instead of crashing.
- Extremely large or very small frame sizes: window should adapt to the frame size or use a stable scaling rule (assumption documented below).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: On application start, the system tray icon MUST present a context menu containing `Settings`, `Open`, and `Exit`.
- **FR-002**: Selecting `Open` from the tray menu MUST open the main application window.
- **FR-003**: The main window outer size MUST match the captured frame size (width × height) when a capture frame is available.
- **FR-004**: The main window MUST display the current camera/capture frame in real time (or near real time consistent with existing detection frame rate).
- **FR-005**: When a cat is detected in the frame, a visible bounding box MUST be drawn around it and a short label displayed.
- **FR-006**: The main window MUST display the detected object class (for example, "cat") as a short label next to each detection.
- **FR-007**: If the capture source is unavailable, the main window MUST show an explanatory message and an action to retry/close.
- **FR-008**: Opening the main window MUST not remove or change the existing `Settings` and `Exit` tray items.

### Key Entities

- **Frame**: Live capture image with resolution (width, height) and timestamp.
- **Detection**: Identified object in a `Frame` with `label`, `confidence`, and `bounding_box`.
- **BoundingBox**: Coordinates (x, y, width, height) relative to the frame.
- **TrayMenu**: System tray context menu entries for the app.
- **MainWindow**: The UI surface that renders `Frame` and `Detection` overlays.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The tray menu contains an `Open` item and retains `Settings` and `Exit` (manual verification).
- **SC-002**: Clicking `Open` opens the main window within 1 second in at least 95% of attempts on a typical user machine.
- **SC-003**: The main window outer size equals the captured frame size within ±2 pixels on both axes for at least 95% of opening events (when a valid frame is available).
- **SC-004**: When a cat is present in the frame, a bounding box is drawn and visible in at least 90% of frames where a cat is present (measured over a sample of 100 frames).
- **SC-005**: The UI surface shows the detection class label (e.g., "cat") visibly next to detections in 100% of frames where a detection is reported.

## Assumptions

- The capture source provides frame resolution metadata (width × height) when available.
- If frame resolution is unavailable or extreme, the implementation may scale the window to fit the screen while preserving aspect ratio; this is acceptable unless otherwise specified.
- If multiple detections exist, the UI will render boxes and labels for all detections by default.
- The UI will display detected object classes (not source process names) as the primary detection descriptor.

## Testing Notes

- Use test images and live camera feeds containing a cat and no-cat scenes to validate FR-003 through FR-006.
- Record timing for window open latency to validate SC-002.
- Sample at least 100 frames across conditions to validate SC-004.



<!-- End of spec -->
