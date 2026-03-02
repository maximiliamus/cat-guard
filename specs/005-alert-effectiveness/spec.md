# Feature Specification: Alert Effectiveness Tracking & Annotated Screenshots

**Feature Branch**: `005-alert-effectiveness`
**Created**: 2026-03-02
**Status**: Draft
**Input**: User description: "Current behavior: cat is detected and a plain screenshot is saved. Problem: we cannot understand the trigger conditions or how the alert affected the cat's behavior. New behavior: (1) draw bounding boxes with confidence scores on screenshots so we understand detection triggers; (2) implement an alert effectiveness mechanism — take a screenshot on detection, do not save immediately, wait for the cooldown, then check if the cat is gone (success → green message) or still present (failure → red message), save the annotated detection screenshot, discard the verification frame. Investigate and propose additional mechanisms for evaluating alert effectiveness."

## Clarifications

### Session 2026-03-02

- Q: What happens when a new detection occurs while a cooldown is already active? → A: New detections are ignored for screenshot purposes while a cooldown is in progress — one pending screenshot per cooldown cycle.
- Q: How should a re-entry event be recorded when the cat returns after a successful deterrence? → A: Save a new separate re-entry screenshot at the moment the cat returns, linked to the original by filename convention — the original saved screenshot is never modified.
- Q: Should screenshot annotation and disk write block the detection pipeline? → A: No — annotation and save run asynchronously in a background thread; the detection loop is never blocked.
- Q: What is the default duration of the re-entry monitoring window? → A: 2 minutes.
- Q: Which optional extensions are in scope for this feature? → A: Only US1 (bounding boxes) and US2 (outcome labeling) are in scope. US3, US4, US5 are explicitly deferred. Additional in-scope requirement: the filename of the alert sound played during detection MUST also be displayed on the saved screenshot.
- Q: What label is shown on the screenshot when the built-in default alert sound plays (no custom filename)? → A: Display "Alert: Default".
- Q: Where are the alert sound label and outcome overlay positioned on the screenshot? → A: Alert sound filename label in the top-left corner; outcome overlay in the bottom-left corner.
- Q: Are the example outcome messages in FR-009/FR-010 normative or illustrative? → A: Illustrative — any equivalent human-readable message conveying the same intent is acceptable.
- Q: Should SC-005 and SC-006 (which reference deferred features) be removed or marked deferred? → A: Marked deferred.

## Assumptions

- The cooldown period used for effectiveness verification is the same existing alert-suppression cooldown already configured in the application. No separate cooldown setting is introduced for this feature.
- "Verification" refers to inspecting the live camera frame at the end of the cooldown — it does not produce a saved screenshot.
- Bounding box annotation applies to every screenshot: no plain (unannotated) frames are ever saved.
- All image annotation and disk-write operations run asynchronously in a background thread. The detection loop and alert-sound pipeline are never blocked waiting for a screenshot to be annotated or saved.
- When multiple cats are detected in a single frame, all bounding boxes with their individual confidence scores are drawn.
- The outcome overlay is rendered directly onto the detection screenshot before it is written to disk; the original bounding boxes and confidence labels remain fully visible alongside the outcome label.
- The filename (without path) of the alert sound that was played at the time of detection is recorded and displayed on the saved screenshot as part of the annotation layer. When the built-in default sound is played, the label "Alert: Default" is shown.
- The annotation layout follows a fixed zone scheme: alert sound filename label is rendered in the top-left corner of the screenshot; the outcome overlay is rendered as a full-width filled strip at the bottom edge of the frame. Bounding boxes are rendered on the detected regions within the frame. These three zones do not overlap.
- User Stories 3 (time-to-clear), 4 (re-entry monitoring), and 5 (session statistics) are explicitly out of scope for this feature. They are deferred to future features and MUST NOT be implemented as part of this release.
- The verification check uses the same detection model and threshold as normal operation.
- If the verification check cannot be performed (e.g., camera becomes unavailable during the cooldown), the screenshot is saved without an outcome label, and the absence of an outcome label itself is meaningful to the user.
- While a cooldown is active, any new detection events are ignored for screenshot purposes. Only one pending screenshot exists per cooldown cycle; no queue of screenshots accumulates in memory.
- "Time-to-clear" measurement (User Story 3) requires periodic sampling during the cooldown — this is a separate optional mechanism on top of the basic end-of-cooldown check.
- Re-entry monitoring (User Story 4) begins only after a successful deterrence verdict and monitors for a configurable short window after the cat's departure is confirmed. The default re-entry monitoring window is 2 minutes. If a re-entry is detected, a new separate re-entry screenshot is saved with its own annotation; the original deterrence screenshot is never modified or overwritten. The two screenshots are linked by a shared filename prefix derived from the original detection timestamp.
- Statistics counters (User Story 5) are per-session (reset on app restart) in the initial implementation; persistence across sessions is out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Visual Detection Evidence (Priority: P1)

A user reviewing saved screenshots wants to understand exactly what triggered each detection — which region of the frame the model flagged and how confident it was. Instead of a plain camera frame, the user sees bounding boxes drawn around each detected cat, each labelled with a confidence score.

**Why this priority**: Every screenshot that is already being saved should explain why it was taken. This is foundational — all subsequent features build on annotated screenshots, and it adds immediate value with no behavioral change to the save flow.

**Independent Test**: Can be fully tested by triggering a detection event and verifying that the saved JPEG contains at least one labelled bounding box overlaid on the camera frame.

**Acceptance Scenarios**:

1. **Given** a cat is detected and a screenshot is about to be saved, **When** the screenshot is written to disk, **Then** it contains a bounding box drawn around every detected region, each with a human-readable confidence score label.
2. **Given** two cats are in the frame simultaneously at detection time, **When** the screenshot is saved, **Then** both bounding boxes and both confidence labels are present.
3. **Given** a screenshot is saved, **When** a user opens it in any image viewer, **Then** the bounding boxes and confidence labels are legible and do not fully obscure the cats.

---

### User Story 2 - Alert Outcome Labeling (Priority: P1)

After the alert fires, a user wants to know whether it actually deterred the cat. Each saved detection screenshot carries a clearly visible outcome label: if the cat left the area after the alert, the label is in green with a friendly message; if the cat stayed, the label is in red with an explanatory message. The screenshot is only saved once the outcome is known.

**Why this priority**: This is the central new capability — answering "did the alert work?" for every detection event. It directly addresses the stated problem of not understanding alert impact.

**Independent Test**: Can be tested by triggering a detection event, waiting for the cooldown, observing whether the cat is present or absent, and verifying the saved screenshot carries the correct colored outcome overlay.

**Acceptance Scenarios**:

1. **Given** a cat is detected and the alert fires, **When** the cooldown elapses and the cat is no longer in the frame, **Then** the detection screenshot is saved with a green outcome label and a human-readable message indicating the cat left.
2. **Given** a cat is detected and the alert fires, **When** the cooldown elapses and the cat is still in the frame, **Then** the detection screenshot is saved with a red outcome label and a human-readable message indicating the alert had no effect.
3. **Given** the alert fires and a detection screenshot is captured, **When** the cooldown is still running, **Then** the screenshot is NOT saved to disk yet — it waits for the verification result.
4. **Given** the outcome verification is complete, **When** the detection screenshot is saved, **Then** the verification frame (the camera frame captured at the end of the cooldown) is discarded and never written to disk.
5. **Given** a detection screenshot is annotated with an outcome label, **When** a user views it, **Then** the original bounding boxes and confidence scores are still visible alongside the outcome label.
6. **Given** the verification check cannot be performed (camera unavailable), **When** the cooldown elapses, **Then** the screenshot is saved without an outcome label and the absence of a label indicates an unknown outcome.
7. **Given** a cat is detected and an alert sound is played, **When** the detection screenshot is saved, **Then** the filename (without path) of the alert sound that was played is visible on the screenshot.

---

### User Story 3 - Time-to-Clear Measurement (Priority: P2) — ⛔ DEFERRED

> **Out of scope for this feature.** Deferred to a future feature. Not to be implemented in this release.

---

### User Story 4 - Re-Entry Monitoring (Priority: P2) — ⛔ DEFERRED

> **Out of scope for this feature.** Deferred to a future feature. Not to be implemented in this release.

---

### User Story 5 - Running Effectiveness Statistics (Priority: P3) — ⛔ DEFERRED

> **Out of scope for this feature.** Deferred to a future feature. Not to be implemented in this release.

---

### Edge Cases

- **Camera unavailable during cooldown**: Verification cannot be performed — screenshot is saved without an outcome label; the missing label itself signals "unknown outcome" to the user.
- **Multiple cats — some leave, some stay**: If at least one cat is still detected at verification time, the outcome is "failure" (area not fully cleared).
- **App closed or crashed during cooldown**: The pending (unsaved) screenshot is lost — no partial or outcome-less file is written to disk during a crash.
- **Very short cooldown (< sampling interval)**: If the cooldown is shorter than the mid-cooldown sampling interval used for time-to-clear, the system falls back to the basic binary check with no time-to-clear annotation.
- **Cat leaves and returns before cooldown ends**: At verification time the cat is present → result is "failure", even though the cat briefly left. This is the defined behavior for the basic check; time-to-clear sampling (User Story 3) can detect the brief absence.
- **New detection during active cooldown**: The new detection is ignored for screenshot purposes — no second pending screenshot is created. The existing cooldown and its pending screenshot continue unaffected. The normal alert-sound suppression behaviour (already in effect during cooldown) applies equally to the screenshot pipeline.
- **Detection at the same moment as a previous cooldown ending**: If a new detection fires exactly as the cooldown expires, the cooldown is considered complete and the existing pending screenshot is saved with its outcome; the new detection then starts a fresh pending screenshot cycle.
- **False positive at high confidence quickly resolved**: Bounding boxes and confidence scores allow the user to retrospectively judge whether a trigger was a genuine cat or a false positive.

## Requirements *(mandatory)*

### Functional Requirements

**Bounding Box Annotation**

- **FR-001**: System MUST render a bounding box on every saved screenshot around each region identified as containing a cat at the moment of detection.
- **FR-002**: Each bounding box MUST be labelled with the detection confidence score expressed as a human-readable percentage (e.g., "92%").
- **FR-003**: When multiple cats are detected simultaneously, all bounding boxes and confidence labels MUST be drawn — one per detected region.
- **FR-004**: Bounding box lines and confidence labels MUST be visually distinct from the background of the camera frame (sufficient contrast) and MUST NOT fully obscure the detected cat.

**Delayed Save with Outcome Determination**

- **FR-005**: Upon detection and alert firing, the system MUST capture a detection frame and hold it in memory — it MUST NOT be written to disk immediately.
- **FR-005a**: While a cooldown is active and a pending screenshot exists, any subsequent detection events MUST be ignored for screenshot purposes — no additional pending screenshots are created or queued.
- **FR-006**: After the cooldown period elapses, the system MUST perform a verification check by inspecting the current camera frame for cat presence.
- **FR-007**: The verification frame MUST NOT be saved to disk under any circumstances.
- **FR-008**: After the verification check, the system MUST apply an outcome overlay to the held detection screenshot and then save it to disk.

**Outcome Overlay**

- **FR-009**: If no cat is detected in the verification frame, the outcome overlay MUST use green visual styling with a human-readable message conveying that the cat left and the alert was effective (e.g., "Cat left – alert worked!" — the example is illustrative; any equivalent message conveying the same intent is acceptable).
- **FR-010**: If a cat is still detected in the verification frame, the outcome overlay MUST use red visual styling with a human-readable message conveying that the cat remained and the alert had no effect (e.g., "Cat remained after alert" — the example is illustrative; any equivalent message conveying the same intent is acceptable).
- **FR-011**: The outcome overlay MUST be rendered as a full-width filled strip at the bottom edge of the frame. This zone MUST NOT overlap with bounding boxes or the top-left sound filename label.
- **FR-011a**: The alert sound filename label MUST be rendered in the top-left corner of the screenshot. When the built-in default alert sound is played, the label MUST read "Alert: Default".
- **FR-012**: If the verification check cannot be completed (e.g., camera unavailable), the screenshot MUST be saved without an outcome overlay; no placeholder or error code is added.

**Time-to-Clear Measurement — ⛔ DEFERRED (out of scope for this feature)**

- **FR-013**: *(Deferred)* If mid-cooldown sampling is enabled, the system MUST sample the camera at regular intervals during the cooldown to detect the approximate moment the cat leaves the frame.
- **FR-014**: *(Deferred)* When a departure is detected mid-cooldown, the elapsed time since the alert MUST be recorded and displayed on the saved screenshot alongside the success outcome overlay.

**Re-Entry Monitoring — ⛔ DEFERRED (out of scope for this feature)**

- **FR-015**: *(Deferred)* After a successful deterrence verdict, the system MUST monitor for re-entry of the cat for a configurable window (default: 2 minutes).
- **FR-016**: *(Deferred)* If a cat is detected within the re-entry monitoring window, the system MUST save a new separate re-entry screenshot annotated to indicate the cat returned. The original deterrence screenshot MUST NOT be modified. Both files MUST share a common filename prefix derived from the original detection timestamp so they can be associated by the user.

**Running Statistics — ⛔ DEFERRED (out of scope for this feature)**

- **FR-017**: *(Deferred)* The system MUST accumulate per-session counts of total alerts fired and successful deterrences.
- **FR-018**: *(Deferred)* Each saved screenshot MUST display the current session statistics at the time of saving.
- **FR-019**: *(Deferred)* Session statistics MUST reset when the application is restarted.

### Key Entities

- **Detection Snapshot**: A camera frame captured at the exact moment of detection. Holds bounding boxes and confidence scores for all detected regions, and the filename of the alert sound played. Retained in memory until an outcome overlay is applied and the image is written to disk.
- **Detection Region**: A sub-region within a Detection Snapshot identified as containing a cat. Has a position within the frame and an associated confidence score.
- **Alert Sound Filename**: The filename (without directory path) of the sound file played as the alert during a detection event. Recorded at detection time and displayed on the saved screenshot.
- **Alert Outcome**: The result associated with a Detection Snapshot following the verification check. Values: "deterred" (cat left), "remained" (cat still present), or "unknown" (verification could not be performed).
- **Cooldown Period**: The waiting interval between alert trigger and verification check. Uses the existing configurable cooldown setting.
- **Re-Entry Event** *(Deferred — US4)*: A new detection that occurs within the re-entry monitoring window following a successful deterrence. Links back to the original Detection Snapshot.
- **Session Statistics** *(Deferred — US5)*: Counters tracking total alerts and successful deterrences accumulated since the application was last started.

## Non-Functional Requirements

### Performance

- **NFR-001**: All image annotation (bounding boxes, confidence labels, outcome overlay) and disk-write operations MUST execute asynchronously in a background thread. The main detection loop MUST NOT be blocked or delayed by screenshot processing.
- **NFR-002**: A failure in the background annotation or save operation (e.g., disk full, I/O error) MUST NOT crash the application or interrupt subsequent detection events.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can identify why a detection triggered — from the bounding boxes and confidence labels — within 5 seconds of opening a saved screenshot.
- **SC-002**: Every saved screenshot with a completed verification check carries a clearly visible outcome label; zero screenshots are saved with a missing outcome when a verification was possible. (When verification cannot be performed — e.g., camera unavailable — no outcome label is expected; see FR-012.)
- **SC-003**: Users can determine at a glance (under 3 seconds) from any saved screenshot whether a given alert worked or not.
- **SC-004**: The outcome classification is correct in 100% of cases where the verification check completes normally (cat present → failure, cat absent → success).
- **SC-005**: *(Deferred — references time-to-clear measurement, US3)* When time-to-clear measurement is active, the recorded elapsed time is accurate to within the sampling interval (no systematic over- or under-reporting by more than one interval).
- **SC-006**: *(Deferred — references session statistics, US5)* Over a session with at least 10 detection events, users can read the running effectiveness rate directly from any screenshot without manual counting.
