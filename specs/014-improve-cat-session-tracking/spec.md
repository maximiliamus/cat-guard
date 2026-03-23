# Feature Specification: Immediate Cat Session Frame Saving

**Feature Branch**: `014-improve-cat-session-tracking`  
**Created**: 2026-03-23  
**Status**: Draft  
**Input**: User description: "Improve cat session tracking. Current behavior: First screenshot of the session is not stored on disk, only in memory. Subsequent screenshots are stored in memory to add cat session info on the frame, and the second evaluation screenshot is discarded. New behavior: take the first screenshot of a detected cat and store it on disk immediately with a neutral bottom-panel message using dark gray background, white text, and message 'Cat detected'. This first screenshot starts the session and is not stored in memory. Take subsequent screenshots, add the appropriate alert message on the bottom panel according to cat session state, and store them on disk immediately too. Log cat session time in human-readable format such as 30s, 2m 15s, 1h 2m 45s."

## Assumptions

- This feature extends the cat-session workflow defined in spec 012 rather than replacing it.
- The existing session folder and filename grouping convention remains in use so all frames from one cat visit can still be reviewed together.
- The first saved frame of a session shows only the neutral detection message; elapsed session time is shown starting with the first evaluation outcome.
- Session duration remains tied to completed cooldown intervals in the active session, preserving the existing cat-session timing semantics from spec 012.
- If monitoring stops, pauses, or becomes unavailable mid-session, frames already saved for that session remain available and only future session frames are skipped.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Capture the Start of Every Cat Visit (Priority: P1)

A user wants proof of the exact moment a cat visit begins, even if the session ends quickly. As soon as the cat is detected and a session starts, the first frame is already saved and ready to review.

**Why this priority**: The current gap is that the session can begin without leaving a saved record. Fixing that is the primary value of this feature.

**Independent Test**: Trigger a new cat detection and inspect the tracking folder before the first evaluation cycle completes. The first session frame should already exist on disk with the neutral session-start message.

**Acceptance Scenarios**:

1. **Given** no cat session is active, **When** a cat detection starts a new session, **Then** the system saves a session-start frame to disk immediately.
2. **Given** a session-start frame has just been saved, **When** the user reviews that frame, **Then** the bottom panel shows the neutral message `Cat detected`.
3. **Given** a session has started, **When** the first evaluation has not happened yet, **Then** the session-start frame is already available as the first reviewable artifact for that session.

---

### User Story 2 - Review Every Session Outcome Without Missing Frames (Priority: P1)

A user wants every later session check to produce a saved frame so the full cat visit can be reconstructed from disk, with no evaluation images silently skipped or discarded.

**Why this priority**: The timeline loses value if any evaluation outcome is missing. The user needs a complete, ordered record from first detection through the last outcome.

**Independent Test**: Run a session where the cat remains for several checks and then leaves. Verify that the initial detection frame and every later evaluation frame are saved in order, with no missing evaluation step.

**Acceptance Scenarios**:

1. **Given** an active cat session, **When** a scheduled evaluation finds the cat still present, **Then** the system saves a new frame immediately with the "cat remained" session message and keeps the session open.
2. **Given** an active cat session, **When** a scheduled evaluation finds the cat gone, **Then** the system saves a new frame immediately with the "cat disappeared" session message and closes the session after that save.
3. **Given** multiple scheduled evaluations occur during one session, **When** the user reviews the saved session frames, **Then** each evaluation outcome appears exactly once in chronological order.

---

### User Story 3 - Read Session Duration Quickly (Priority: P2)

A user wants the session duration on saved frames and in session-related logs to be easy to read at a glance, whether the cat stayed for seconds, minutes, or hours.

**Why this priority**: Session tracking is only useful if the duration can be understood quickly without converting raw seconds.

**Independent Test**: Review saved session outcomes and session-related log entries for sample durations of 30 seconds, 2 minutes 15 seconds, and 1 hour 2 minutes 45 seconds. Each should appear in the compact human-readable format.

**Acceptance Scenarios**:

1. **Given** a session duration of 30 seconds, **When** a session message or log entry includes elapsed time, **Then** it is shown as `30s`.
2. **Given** a session duration of 2 minutes 15 seconds, **When** a session message or log entry includes elapsed time, **Then** it is shown as `2m 15s`.
3. **Given** a session duration of 1 hour 2 minutes 45 seconds, **When** a session message or log entry includes elapsed time, **Then** it is shown as `1h 2m 45s`.

### Edge Cases

- A new cat detection occurs while a session is already active: the system continues the existing session and does not create a second neutral `Cat detected` frame.
- Monitoring pauses or the camera becomes unavailable after the session-start frame is saved but before the next evaluation: saved session frames remain on disk, and the current session ends without a fabricated final outcome frame.
- A session crosses midnight: the session still reads as one continuous timeline with correct elapsed times and preserved frame ordering.
- Multiple cats appear in view: if at least one cat remains at evaluation time, the saved outcome for that evaluation is the "cat remained" state.

## Requirements *(mandatory)*

### Functional Requirements

**Session Start Capture**

- **FR-001**: When a cat detection starts a new session, the system MUST save a session-start frame to disk immediately.
- **FR-002**: The session-start frame MUST display a full-width bottom-panel message reading `Cat detected`.
- **FR-003**: The session-start frame message MUST use a neutral visual style with a dark gray background and white text.
- **FR-004**: The session-start frame MUST be the first reviewable artifact of the session and MUST NOT wait for a later evaluation outcome before it becomes available on disk.

**Evaluation Frames**

- **FR-005**: After each cooldown interval during an active session, the system MUST capture a new evaluation frame and save it to disk immediately.
- **FR-006**: If a scheduled evaluation finds at least one cat still present, the saved evaluation frame MUST show the session message `Cat remained after alert: <duration>`.
- **FR-007**: If a scheduled evaluation finds no cat present, the saved evaluation frame MUST show the session message `Cat disappeared after alert: <duration>` and MUST close the session after that frame is saved.
- **FR-008**: Each evaluation outcome reached during an active session MUST produce exactly one saved frame. The system MUST NOT discard an evaluation frame after using it to determine session state.
- **FR-009**: While a session is active, additional cat detections MUST continue the existing session instead of creating another session-start frame or resetting the session timeline.

**Elapsed Time Presentation**

- **FR-010**: Any saved session frame or session-related log entry that includes elapsed time MUST use a compact human-readable duration format.
- **FR-011**: Durations shorter than one minute MUST be displayed as seconds only, durations from one minute up to but not including one hour MUST be displayed as minutes and seconds, and durations of one hour or more MUST be displayed as hours, minutes, and seconds.
- **FR-012**: The elapsed duration shown on an evaluation frame or session-related log entry MUST represent the total session duration measured in completed cooldown intervals since the session-start frame.

**Session Continuity**

- **FR-013**: All saved frames belonging to one session MUST remain grouped and ordered so a user can review the cat visit as one continuous timeline from the initial `Cat detected` frame through the final saved outcome.
- **FR-014**: If monitoring pauses, stops, or becomes unavailable mid-session, the system MUST preserve all frames already saved for that session and end the unfinished session without creating a synthetic final outcome frame.

### Key Entities

- **Cat Session**: One continuous cat visit that starts with the first saved detection frame and ends when the system saves a final outcome frame or the session is interrupted.
- **Session-Start Frame**: The first saved frame of a cat session, carrying the neutral `Cat detected` message and establishing the beginning of the timeline.
- **Evaluation Frame**: A later saved frame captured after a cooldown interval that records whether the cat remained or disappeared and shows the elapsed session time.
- **Elapsed Session Time**: The total session duration measured in completed cooldown intervals since the session-start frame, shown in a compact human-readable format.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In every completed validation run, a newly started cat session produces a saved session-start frame on disk before the first evaluation cycle completes.
- **SC-002**: In every completed validation run, each evaluation outcome reached during a cat session is represented by exactly one saved frame in the session timeline.
- **SC-003**: In validation runs covering short, medium, and long sessions, 100% of saved session frames and session-related log entries display elapsed time using the required human-readable duration format.
- **SC-004**: A user can reconstruct the full sequence of a cat visit, from first detection to final saved outcome, by reviewing the saved session frames alone without relying on unsaved transient state.
