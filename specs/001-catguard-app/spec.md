# Feature Specification: CatGuard App

**Feature Branch**: `[1-catguard-app]`  
**Created**: 2026-02-28  
**Status**: Draft  
**Input**: User description: "CatGuard - the app that monitors via web camera your table for your cat. If the cat is detected on the table the app plays sound to scare away your cat :)"

## Clarifications

### Session 2026-02-28

- Q: What happens if a cat stays on the table or is detected repeatedly? → A: Play sound once, then enforce a configurable cooldown (default ~15s) before alerting again.
- Q: What sound(s) does the app play on detection? → A: Built-in default sound + user can upload multiple audio files (MP3/WAV); files are played in random order on each detection event.
- Q: Are camera frames stored or transmitted? → A: Frames are processed in memory only; never written to disk or transmitted anywhere.
- Q: How does the user define the monitored area? → A: Full camera frame is monitored; no area selection or region-of-interest configuration.
- Q: Should CatGuard start automatically on login? → A: Autostart on login is available as an opt-in setting (disabled by default).
- Q: How should cat detection work? → A: A YOLO (You Only Look Once) object detection model MUST be used to detect cats in camera frames.
- Q: How should autostart be implemented? → A: Must NOT use the Windows registry. Solution must be cross-platform (Windows startup folder, macOS launchd, Linux .desktop / systemd user service).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cat Detection and Alert (Priority: P1)

A user sets up CatGuard to monitor a table using a web camera. When the app detects a cat on the table, it immediately plays a sound to scare the cat away.

**Why this priority**: This is the core value proposition—preventing cats from being on the table in real time.

**Independent Test**: Can be fully tested by placing a cat (or cat image) on the table and verifying that the sound is played.

**Acceptance Scenarios**:

1. **Given** the app is running and monitoring the table, **When** a cat is detected, **Then** a sound is played instantly.
2. **Given** the app is running, **When** no cat is detected, **Then** no sound is played.
3. **Given** the computer is locked, **When** a cat is detected, **Then** a sound is played and the event is logged.
4. **Given** a sound was just played, **When** a cat is still detected within the cooldown period, **Then** no additional sound is played until the cooldown expires.

---

### User Story 4 - System Tray Access (Priority: P2)

A user can access all app controls from the system tray context menu. Clicking **"Settings..."** opens the Settings window where all flags and audio files can be adjusted. Clicking **"Exit"** fully quits the app.

**Why this priority**: The app runs in the background; the system tray is the primary point of interaction during normal operation.

**Independent Test**: Can be fully tested by right-clicking the tray icon and verifying that "Settings..." opens the Settings window and "Exit" fully terminates the app.

**Acceptance Scenarios**:

1. **Given** the app is running, **When** the user right-clicks the system tray icon, **Then** a context menu is shown containing at least "Settings..." and "Exit" items.
2. **Given** the tray menu is open, **When** the user clicks "Settings...", **Then** the Settings window opens showing all configurable options.
3. **Given** the Settings window is open, **When** the user changes any setting and saves, **Then** the change takes effect immediately.
4. **Given** the tray menu is open, **When** the user clicks "Exit", **Then** the app stops monitoring and fully quits.
5. **Given** the user closes the main window, **When** the app is still running, **Then** it remains accessible via the system tray icon.
6. **Given** autostart is disabled, **When** the user logs in, **Then** the app does not start automatically.
7. **Given** the user enables autostart in settings, **When** the user logs in next time, **Then** the app starts automatically and appears in the system tray.

---

### User Story 2 - Camera Setup (Priority: P2)

A user configures which camera to use for monitoring.

**Why this priority**: Users need to specify the correct camera for reliable detection.

**Independent Test**: Can be tested by selecting different cameras and verifying the correct camera feed is used for detection.

**Acceptance Scenarios**:

1. **Given** multiple cameras are available, **When** the user selects one, **Then** only that camera is used for detection.
2. **Given** a camera is selected, **When** the app starts monitoring, **Then** the full frame of the selected camera is monitored.

---

### User Story 3 - Detection Sensitivity and Sound Customization (Priority: P3)

A user adjusts detection sensitivity and manages a library of alert sounds. When a cat is detected, the app plays a randomly selected sound from the user's uploaded files.

**Why this priority**: Allows users to tailor the app to their environment and cat's behavior.

**Independent Test**: Can be tested by uploading multiple sounds, triggering detection several times, and verifying a different sound is played each time (random selection across detections).

**Acceptance Scenarios**:

1. **Given** sensitivity is set high (low confidence threshold), **When** a partially visible cat is detected at low confidence, **Then** the alert still fires.
2. **Given** the user has uploaded multiple audio files (MP3/WAV), **When** a cat is detected, **Then** one file is selected at random and played.
3. **Given** no custom sounds have been uploaded, **When** a cat is detected, **Then** the built-in default sound is played.
4. **Given** the user uploads a new audio file, **When** a cat is next detected, **Then** the new file is eligible for random selection.

## Functional Requirements

1. The app MUST use a web camera to monitor the full camera frame for cat presence; no region-of-interest selection is required.
2. The app MUST play a sound immediately when a cat is detected in the monitored area; subsequent alerts MUST be suppressed until a configurable cooldown period (default: 15 seconds) has elapsed.
3. The app MUST allow users to select the active camera.
4. The app MUST allow users to adjust detection sensitivity and manage an alert sound library: users can upload multiple audio files (MP3/WAV), and on each detection event the app MUST play a randomly selected file from the library. A built-in default sound MUST be provided so the app works out of the box.
5. The app MUST provide clear feedback and logs for detection events and actions taken.
6. The app MUST operate with <200ms p95 latency for detection and <100MB memory footprint for core service.
7. The app MUST be testable with simulated cat images and sounds.
8. The app MUST sit in the system tray when running. The tray context menu MUST include at minimum: a **"Settings..."** item that opens the Settings window, and an **"Exit"** item that fully quits the app. All configurable options (camera selection, detection sensitivity, sound library, cooldown, autostart) MUST be accessible exclusively through the Settings window.
9. The app MUST continue monitoring and alerting even when the computer is locked, ensuring uninterrupted operation.
10. The app MUST process all camera frames in memory only; frames MUST NOT be written to disk, transmitted over a network, or persisted in any form.
11. The app MUST offer an opt-in setting to start automatically on user login; this setting MUST be disabled by default. The autostart mechanism MUST NOT use the Windows registry; it MUST be cross-platform (Windows: startup folder; macOS: launchd; Linux: XDG autostart .desktop file or systemd user service).
12. Cat detection MUST use a YOLO object detection model operating on the live camera feed.

## Success Criteria

- Users can set up the app and monitor a table with a web camera in under 5 minutes.
- Detection and sound playback occur within 200ms of a cat being detected.
- 95% of detection events are accurate (true positives for cats, minimal false alarms).
- Users can customize camera, sensitivity, and sound library.
- All detection events and actions are logged and observable.
- The app runs reliably for at least 24 hours without crashing or excessive resource use.
- The app remains accessible and controllable via the system tray at all times while running.
- The tray context menu always contains "Settings..." and "Exit"; all settings are adjustable from the Settings window.
- Detection and alerting continue uninterrupted when the computer is locked.
- Autostart on login is off by default and can be enabled via a single settings toggle.

## Key Entities

- Cat (detected object)
- Table (monitored area)
- Camera (input device)
- Sound File (individual alert audio file; MP3 or WAV)
- Sound Library (user-managed collection of Sound Files; includes built-in default)
- Detection Event (log entry)
- Settings Window (UI for configuring all app options; opened via tray "Settings..." item)
- System Tray Menu (context menu with "Settings..." and "Exit" items)

## Assumptions

- Users have at least one compatible web camera.
- The app runs on Python 3.11+.
- Detection uses a YOLO object detection model to identify cats in camera frames.
- Sound playback uses system audio.
- No cloud dependencies required for core detection.
- Camera frames are never persisted or transmitted; all processing is local and in-memory.
- The solution MUST be cross-platform (Windows, macOS, Linux); no Windows-registry-only APIs are permitted.

## Constitution Check

- Test-First Development: All features must have tests before implementation.
- Observability & Logging: All detection events and actions are logged.
- Simplicity & Clarity: UI and configuration are simple and clear.
- Integration Testing: Camera and sound integration are tested.
- Versioning & Breaking Changes: Any breaking changes require migration guidance.

