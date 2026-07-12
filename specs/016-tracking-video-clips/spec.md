# Feature Specification: Tracking Mode with Video Clips

**Feature Branch**: `016-tracking-video-clips`  
**Created**: 2026-03-29  
**Status**: Draft  
**Input**: User description: "Add settings `Tracking mode` radio button: `Screenshots` or `Videoclips`. For video clips add setting `Videoclip FPS` with default 1. If tracking mode is videoclip then make screenshots with the specified FPS and store this screenshot stream as a video file. The video should include the usual cat detection alert for remained/disappeared with the corresponding time and a top information panel with alert file name and time."

## Clarifications

### Session 2026-03-29

- Q: When `Tracking mode` is `Videoclips`, should the app still save standalone tracking JPEG files for the same session? → A: No. `Videoclips` mode saves only one video clip per session; standalone tracking JPEG files are not created for that session.

## Assumptions

- This feature extends the existing tracking workflow defined by the screenshot and cat-session specifications rather than changing how cat detection, cooldown timing, or session outcomes are decided.
- `Screenshots` remains the default tracking mode so existing installs keep their current behavior until a user explicitly opts into `Videoclips`.
- In `Videoclips` mode, one cat session produces one reviewable clip artifact stored in the existing tracking directory structure instead of the current per-session still-image sequence.
- The clip reuses the current tracking annotations already familiar to users: session-start context, timed `Cat remained after alert: <duration>` outcomes, timed `Cat disappeared after alert: <duration>` outcomes, the alert sound name, and the local capture time.
- If a session ends unexpectedly because monitoring pauses, the camera fails, or the app stops, footage already captured for that session still has review value and should be preserved as a partial clip rather than discarded.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review One Cat Visit as One Video Clip (Priority: P1)

A user wants a single tracking artifact that plays back the whole cat visit instead of opening multiple still images one by one. After the visit ends, they can open one saved clip and review how the cat session started, how long the cat stayed, and when it finally disappeared.

**Why this priority**: This is the core value of the feature. Without a complete per-session clip, the new tracking mode provides no real benefit over the existing screenshot workflow.

**Independent Test**: Set tracking mode to `Videoclips`, trigger a cat session that lasts for one or more cooldown cycles, then verify that one saved clip appears in the tracking directory and can be reviewed as a chronological record of that session.

**Acceptance Scenarios**:

1. **Given** tracking mode is `Videoclips`, **When** a new cat session starts and later ends normally, **Then** the app saves one video clip for that session in the tracking directory.
2. **Given** a cat remains through multiple cooldown evaluations, **When** the user plays the saved clip, **Then** the clip shows the session in chronological order and includes each timed `Cat remained after alert: <duration>` update until the final outcome is reached.
3. **Given** the cat disappears during the session, **When** the user reaches the end of the saved clip, **Then** the final visible outcome is `Cat disappeared after alert: <duration>` with the correct cumulative session time.
4. **Given** the user opens any part of the saved clip, **When** frames are displayed, **Then** each frame shows the top information panel with the alert sound file name and the local capture time.
5. **Given** tracking mode is `Videoclips`, **When** a session clip is produced, **Then** no standalone tracking JPEG files are created for that same session.

---

### User Story 2 - Choose Tracking Output in Settings (Priority: P1)

A user wants to decide whether tracking is stored as still images or as a session video clip, and when video clips are enabled they want control over how many frames per second are captured.

**Why this priority**: The feature is user-facing only if the mode can be selected and understood in Settings. The FPS control is essential because clip smoothness and storage volume are direct user tradeoffs.

**Independent Test**: Open Settings, switch between `Screenshots` and `Videoclips`, verify the `Videoclip FPS` control behavior, save the settings, restart the app, and confirm the next cat session uses the selected mode and FPS.

**Acceptance Scenarios**:

1. **Given** the Settings window is open, **When** the user looks at tracking-related options, **Then** they can choose exactly one `Tracking mode`: `Screenshots` or `Videoclips`.
2. **Given** the user selects `Videoclips`, **When** the mode changes, **Then** the `Videoclip FPS` setting becomes available and starts from the default value `1` unless the user has already saved another value.
3. **Given** the user selects `Screenshots`, **When** the mode changes, **Then** the `Videoclip FPS` control becomes unavailable or visually inactive because it does not affect screenshot output.
4. **Given** the user saves `Videoclips` mode with a chosen FPS value, **When** the app is restarted and the next session is recorded, **Then** the same mode and FPS are still in effect.

---

### User Story 3 - Keep Screenshot Tracking Available (Priority: P2)

A user who prefers the current screenshot workflow wants to keep using it without any surprise changes. Choosing not to enable video clips should preserve the existing tracking output exactly as before.

**Why this priority**: This feature adds an alternative output mode, not a forced migration. Existing screenshot-based review habits must continue to work.

**Independent Test**: Leave tracking mode set to `Screenshots`, run one or more cat sessions, and verify that the app still produces the current screenshot-based tracking artifacts and does not create any video clips.

**Acceptance Scenarios**:

1. **Given** tracking mode is `Screenshots`, **When** a cat session is recorded, **Then** the app saves the normal screenshot-based tracking artifacts for that session.
2. **Given** tracking mode is `Screenshots`, **When** a cat session completes, **Then** no video clip file is created for that session.
3. **Given** a user switches from `Videoclips` back to `Screenshots`, **When** the next cat session starts, **Then** the app returns to screenshot-only tracking for that new session.

### Edge Cases

- The user changes `Tracking mode` or `Videoclip FPS` while a cat session is already active: the session already in progress continues with the mode and FPS it started with; the new values apply from the next session onward.
- A session crosses midnight: the saved clip remains one continuous session artifact while the top information panel continues showing the actual local time on each captured frame.
- A session is interrupted before a final disappearance outcome is confirmed: the app preserves a partial clip containing all footage captured so far and does not invent a final success or failure message that never occurred.
- The tracking directory is unavailable or cannot be written when a clip should be saved: monitoring continues, the failure is logged, and the user receives a non-blocking error.
- A saved `Videoclip FPS` value is missing, invalid, non-integer, or non-positive when Settings are loaded: the app falls back to the default value `1` rather than leaving video mode unusable.
- A saved video-format value is missing or unsupported: the app falls back to `MJPG (AVI)` so existing settings and platform defaults remain usable.

## Requirements *(mandatory)*

### Functional Requirements

**Tracking Settings**

- **FR-001**: The Settings window MUST include a `Tracking mode` choice with exactly two mutually exclusive options: `Screenshots` and `Videoclips`.
- **FR-002**: The default `Tracking mode` MUST be `Screenshots`.
- **FR-003**: The Settings window MUST include a `Videoclip FPS` setting for `Videoclips` mode.
- **FR-004**: `Videoclip FPS` MUST default to `1`.
- **FR-005**: `Videoclip FPS` MUST accept only positive whole-number values.
- **FR-006**: When `Tracking mode` is `Screenshots`, the `Videoclip FPS` control MUST be unavailable or visually inactive.
- **FR-007**: The selected `Tracking mode` and `Videoclip FPS` value MUST be persisted across app restarts.
- **FR-007a**: In `Videoclips` mode, the Settings window MUST let the user choose `MJPG (AVI)`, `XVID (AVI)`, or `MP4V (MP4)` output.
- **FR-007b**: The default video format MUST be `MJPG (AVI)` for backward compatibility.
- **FR-007c**: The selected video format MUST be persisted and snapshotted at session start so an active session is not changed by later settings edits.

**Videoclip Session Output**

- **FR-008**: When `Tracking mode` is `Videoclips` and a new cat session starts, the system MUST begin capturing tracking frames for that session at the configured `Videoclip FPS` cadence.
- **FR-009**: One completed cat session in `Videoclips` mode MUST produce exactly one saved video clip as the primary tracking artifact for that session.
- **FR-009a**: When `Tracking mode` is `Videoclips`, the system MUST NOT save standalone tracking JPEG files for that same session.
- **FR-010**: A saved tracking clip MUST be stored under the existing tracking directory organization so users can find it alongside other date-organized tracking artifacts.
- **FR-011**: The saved clip MUST preserve the chronological flow of the cat session from session start through final confirmed outcome or interruption.
- **FR-012**: Every frame written into a tracking clip MUST include the existing top information panel showing the alert sound file name and the local capture time.
- **FR-013**: The clip MUST use the existing cat-session outcome messaging conventions so that remained outcomes appear as `Cat remained after alert: <duration>`-style messages and disappearance outcomes appear as `Cat disappeared after alert: <duration>`-style messages with the correct cumulative session time.
- **FR-014**: The clip MUST preserve the beginning of the visit before the first timed outcome occurs, using the existing session-start tracking context rather than starting only at a later evaluation point.
- **FR-015**: If a cat remains through multiple cooldown evaluations, the clip MUST show each remained outcome in sequence with monotonically increasing session times.
- **FR-016**: When the cat disappears, the system MUST finalize the clip after recording the disappearance outcome for that session.
- **FR-017**: Video-mode tracked frames MUST keep the existing detection evidence visible, including the cat-detection overlays already present in current session artifacts.

**Compatibility and Failure Handling**

- **FR-018**: When `Tracking mode` is `Screenshots`, the system MUST continue the current screenshot-based tracking workflow and MUST NOT create a video clip for that session.
- **FR-019**: Changing `Tracking mode`, `Videoclip FPS`, or video format during an active cat session MUST NOT alter the artifact already in progress; the new setting applies starting with the next session.
- **FR-020**: If a cat session ends unexpectedly before a disappearance outcome is confirmed, the system MUST preserve the captured footage for that session as a partial clip and MUST NOT fabricate a final outcome that did not occur.
- **FR-021**: If a tracking clip cannot be created or saved, the system MUST continue monitoring normally, MUST log the failure, and MUST present a non-blocking user-visible error.

### Key Entities

- **Tracking Mode**: The user-selected output type for tracked cat sessions. Values: `Screenshots` or `Videoclips`.
- **Videoclip FPS**: The user-configured frame-capture cadence, in frames per second, used only when `Tracking mode` is `Videoclips`.
- **Videoclip Format**: The session-locked codec/container selection: `MJPG (AVI)`, `XVID (AVI)`, or `MP4V (MP4)`.
- **Tracking Videoclip**: A single saved session artifact that represents one cat visit as an annotated moving image instead of a still-image sequence.
- **Session Outcome Overlay**: The visible session-status messaging shown within tracked artifacts, including the timed remained and disappeared messages associated with cooldown-based evaluations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In `Videoclips` mode, every fully completed cat session produces exactly one saved clip in the tracking directory within 10 seconds of session completion, with zero standalone tracking JPEG files created for that same session.
- **SC-002**: In validation runs covering both one-cycle and multi-cycle sessions, users can determine the alert sound name, frame time, and final session outcome by reviewing the saved clip alone without opening separate screenshots or logs.
- **SC-003**: In 100% of tested runs, changing `Tracking mode`, `Videoclip FPS`, or video format in Settings takes effect for the next cat session after saving and persists across restart.
- **SC-004**: In `Screenshots` mode, 100% of tested sessions continue producing screenshot-based tracking artifacts only, with no unexpected video clip file created.
- **SC-005**: In interruption tests covering manual pause, camera error, and schedule stop, 100% of sessions that captured footage before interruption retain a partial reviewable clip rather than losing all evidence.
