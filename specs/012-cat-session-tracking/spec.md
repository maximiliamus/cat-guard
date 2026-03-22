# Feature Specification: Cat Session Tracking with Evaluation Screenshots

**Feature Branch**: `012-cat-session-tracking`
**Created**: 2026-03-22
**Status**: Draft
**Input**: User description: "Lets add new feature. Need capture time of entire 'cat session'. Take the first evaluation screenshot. If cat detected now store it on disk with red alert: 'Cat remained after alert: 30s'. Wait the next cooldown time interval. Take the next evaluation screenshot. Detect an alert is working / not-working. If not working (cat still on the table) store evaluation screenshot as next tracked frame of 'cat session' with red alert: 'Cat remained after alert: 60s' i.e. double cooldown time. Or if alert is working (cat went away), add on the frame green alert: 'Cat disappeared after alert: 60s'. And so on."

## Clarifications

### Session 2026-03-22

- Q: What is the filename convention for session evaluation frames? → A: `<tracking_dir>/<yyyy-mm-dd>/<YYYYMMDD-HHmmss-NNN>.jpg` — no "session-" prefix, no "frame-" infix (e.g., `tracking/2026-03-22/20260322-143000-001.jpg`).

## Assumptions

- The cooldown interval used between evaluation checks is the existing configured alert cooldown — no new cooldown setting is introduced.
- The session begins at the moment the alert fires (T=0), and cumulative elapsed time on all labels is measured from that point.
- All evaluation screenshot captures and disk-write operations run asynchronously and do not block the detection pipeline.
- A session pending its first evaluation is abandoned (no files written) if the application stops before that first check completes.
- A cat returning after a green (cat-left) outcome closes the previous session and starts a brand-new session.
- If a new detection event occurs while a session is already active, it is absorbed into the running session — no new session is started and the cooldown timer is not reset.
- Existing annotation conventions from spec 005 (bounding boxes, confidence scores, top info bar with alert sound name and timestamp, bottom outcome strip) apply to every evaluation frame in the session.
- This feature extends spec-005 — the spec-005 single-evaluation save flow remains intact. The session tracking feature adds two things on top: (1) the cumulative elapsed time since the alert is shown on every evaluation screenshot, including the spec-005 first-evaluation frame; (2) additional evaluation cycles continue at each cooldown interval when the cat does not leave after the first check. The label format on all evaluation screenshots adopts the session time convention (e.g., "Cat remained after alert: 30s", "Cat disappeared after alert: 30s") in place of the non-timed labels previously defined in spec-005.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review a Full Cat Session Timeline (Priority: P1)

A user wants to understand how a cat behaved during an entire visit — not just whether the first alert worked, but what happened across every cooldown cycle. After a session ends, they can open a sequence of saved evaluation frames and see exactly how long the cat stayed and which cycle finally drove it away.

**Why this priority**: This is the core value of the feature. A single binary screenshot answers "did the alert work?", but a session timeline answers "how long did the cat stay and how stubborn was it?". Without this story there is nothing to deliver.

**Independent Test**: Can be fully tested by running the system while a cat (or simulated object) remains on the table for three or more cooldown cycles before leaving. After the session closes, verify that multiple evaluation frames exist on disk in chronological order, each carrying a red label with an increasing cumulative time, and the last frame carries a green label.

**Acceptance Scenarios**:

1. **Given** a cat is detected and the alert fires, **When** the first cooldown elapses and the cat is still present, **Then** an evaluation screenshot is saved with a red label showing the cumulative elapsed time equal to one cooldown interval.
2. **Given** a red-labeled evaluation frame was saved, **When** the next cooldown elapses and the cat is still present, **Then** another evaluation screenshot is saved with a red label showing a cumulative elapsed time equal to two cooldown intervals.
3. **Given** one or more red-labeled evaluation frames were saved, **When** the next cooldown elapses and the cat is no longer in the frame, **Then** a final evaluation screenshot is saved with a green label showing the total elapsed time since the session start, and the session closes.
4. **Given** a session has closed, **When** the user opens the saved evaluation frames in chronological order, **Then** the sequence reads as a coherent timeline: red frames increasing in cumulative time, followed by a single green frame as the final entry.

---

### User Story 2 - Single-Cycle Session (Cat Leaves on First Check) (Priority: P2)

A user's cat is successfully deterred after the very first alert. The session produces exactly one evaluation frame — a green one — confirming the alert worked immediately.

**Why this priority**: This is the minimal session — one frame, one outcome. It validates the feature works for the happy path and confirms session bookkeeping starts and closes correctly when no red frames are needed.

**Independent Test**: Can be tested by triggering an alert and removing the cat (or simulated object) before the first cooldown elapses. Verify that exactly one evaluation frame is saved, that it carries a green label, and that no red frames exist for that session.

**Acceptance Scenarios**:

1. **Given** a cat is detected and the alert fires, **When** the first cooldown elapses and the cat is no longer present, **Then** exactly one evaluation screenshot is saved, labeled green with the cumulative time equal to one cooldown interval, and the session closes.

---

### User Story 3 - Long-Running Session (Cat Never Leaves) (Priority: P2)

A persistent cat refuses to leave despite repeated alerts. The system continues to save red-labeled evaluation frames indefinitely at each cooldown interval, giving the user a complete record of the incident.

**Why this priority**: The system must handle indefinite persistence gracefully. Without bounding the session, the user has a complete audit trail even for the most stubborn visitors.

**Independent Test**: Can be tested by simulating a cat that stays on the table for many cooldown cycles (e.g., ten or more). Verify that a new red-labeled evaluation frame is saved after every cooldown interval with the correct increasing cumulative time, and that no session closes prematurely.

**Acceptance Scenarios**:

1. **Given** an active session with several red frames already saved, **When** the next cooldown elapses and the cat is still present, **Then** a new red-labeled frame is saved with the correct next cumulative time, and the session remains open.
2. **Given** a long-running session, **When** the cat finally leaves, **Then** a green-labeled frame is saved with the correct total cumulative time and the session closes normally.

---

### Edge Cases

- **Cat leaves between evaluations but returns before the next check**: The evaluation at check time finds the cat present — a red label is saved. The brief absence is not recorded.
- **Camera unavailable during an evaluation check**: The detection loop auto-pauses. The active session is immediately abandoned — no frame is saved for the current in-progress cycle and no session-closing green frame is produced. When the user resumes monitoring, the next cat detection starts a fresh session.
- **Multiple cats — some leave, some stay**: If at least one cat is detected at evaluation time, the outcome is "still present" and a red label is saved.
- **App stopped mid-session**: The pending state for any incomplete cycle is discarded. No partial or unlabeled frame is written to disk.
- **New detection while a session is already active**: The new detection does not start a new session or reset the cooldown timer. The running session absorbs it.
- **Cat returns after session closes**: A brand-new session starts from scratch when the returning cat triggers a new alert.

## Requirements *(mandatory)*

### Functional Requirements

**Session Lifecycle**

- **FR-001**: When an alert fires and a cooldown begins, the system MUST start a new cat session and record the alert trigger timestamp as the session start time.
- **FR-002**: A cat session MUST remain active until a green (cat-left) evaluation outcome is recorded for that session.
- **FR-003**: If a new detection event occurs while a session is already active, the system MUST continue the existing session without resetting the cooldown timer or starting a new session.
- **FR-004**: When a green evaluation outcome is recorded, the system MUST close the current session. Any subsequent new detection MUST start a fresh session.

**Evaluation Screenshots**

- **FR-005**: After each cooldown interval elapses during an active cat session, the system MUST capture an evaluation screenshot from the current camera frame.
- **FR-006**: If the cat is still detected in the evaluation frame, the system MUST save it to disk with a red outcome label displaying the cumulative elapsed time since the session start (e.g., "Cat remained after alert: 30s").
- **FR-007**: If the cat is no longer detected in the evaluation frame, the system MUST save it to disk with a green outcome label displaying the cumulative elapsed time since the session start (e.g., "Cat disappeared after alert: 60s").
- **FR-008**: The cumulative elapsed time shown in the label MUST equal the configured cooldown duration multiplied by the number of completed evaluation cycles in this session (i.e., one cooldown duration for the first check, two cooldown durations for the second, and so on).
- **FR-009**: Every evaluation screenshot MUST include all standard annotation layers defined in spec 005: bounding boxes with confidence scores on detected regions, a top info bar showing the alert sound name and the local timestamp at save time, and a full-width bottom outcome strip carrying the colored label.
- **FR-010**: If monitoring is paused for any reason during an active session — including camera unavailability (auto-pause), user-initiated pause, or time-window auto-pause — the system MUST immediately abandon the active session. No frame is saved for the in-progress cycle and no session-closing green frame is produced. When monitoring resumes, the next cat detection MUST start a fresh session from the beginning.

**Session Storage**

- **FR-011**: Evaluation frames MUST be saved in the existing flat tracking folder under the date-subfolder for the session start date. All frames belonging to the same session MUST share a common filename prefix derived from the session start timestamp, with a zero-padded 3-digit cycle number suffix, making it trivial to sort and associate frames from the same visit (e.g., `20260322-143000-001.jpg`, `20260322-143000-002.jpg`).

### Key Entities

- **Cat Session**: A time-bounded monitoring period that starts when an alert fires and ends when a green evaluation outcome is recorded. Consists of an ordered sequence of evaluation frames.
- **Evaluation Frame**: A screenshot captured at the end of each cooldown interval during an active cat session. Annotated with a colored outcome label showing cumulative elapsed time since the session start.
- **Session Start Time**: The timestamp at which the alert fired, serving as the session identifier and as the reference point for cumulative elapsed time calculations.
- **Cumulative Elapsed Time**: The total number of seconds between the session start and the current evaluation check, expressed as the cooldown duration multiplied by the cycle count.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After any completed cat session, a user can reconstruct the full visit timeline — including how many cooldown cycles elapsed and whether the cat eventually left — by reviewing the saved evaluation frames in chronological order, without consulting any other record.
- **SC-002**: The cumulative time shown in each evaluation frame label is accurate to within the cooldown duration (i.e., no frame shows a time value that skips or repeats a cycle).
- **SC-003**: For every session where the cat eventually leaves, exactly one green-labeled frame exists as the final frame of that session; zero sessions close without a green terminal frame when the cat's departure was confirmed.
- **SC-004**: For sessions where the cat never leaves during the monitoring period, red-labeled evaluation frames continue to accumulate at every cooldown interval with monotonically increasing cumulative times, and no session data is lost or truncated due to session length.
- **SC-005**: All evaluation frame saves complete without blocking or perceptibly delaying the live detection pipeline.
