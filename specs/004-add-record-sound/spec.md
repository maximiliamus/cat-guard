# Feature Specification: Audio Recording & Playback Controls

**Feature Branch**: `004-add-record-sound`
**Created**: 2026-03-01
**Status**: Draft
**Input**: User description: "Current behavior: multiple audio files can be loaded in settings and play randomly. New behavior: in addition to loading a file, users can click a Record button and record sound from the microphone. After recording, the user is prompted to name the file and the file is saved to disk. Settings must also have a 'Use Default Sound' checkbox — when checked, the default sound plays; when unchecked, the sound library files are used. A 'Play Only This Sound' dropdown must be added: selecting a specific sound means only that sound plays; selecting nothing means all sounds play randomly (existing behavior)."

## Clarifications

### Session 2026-03-01

- Q: When a cat is detected (alert sound would normally fire) while the user is actively recording in the Settings window, what should the app do? → A: Suppress the alert sound for the duration of the recording session; sound resumes normally after recording is stopped or cancelled.
- Q: Should there be a maximum duration cap on a single recording? → A: 10 seconds.
- Q: Should the alerts folder path be visible to the user in the Settings window, with a button to open it in the file explorer? → A: Yes — show the path and provide a "Browse..." button on the same line to reveal it in the file explorer.
- Q: What should the initial state of the "Use Default Sound" checkbox be on a fresh install (first ever launch, no prior settings)? → A: Checked — default sound plays immediately on first detection; zero configuration required.
- Q: What should happen if the user closes the Settings window while a recording is in progress? → A: Discard the in-progress recording silently and close the window.
- Q: When the user clicks Record, which microphone should the app capture from? → A: Always use the OS default input device — no mic selection UI needed.
- Q: Where should the alerts folder be stored? → A: OS user-data (AppData) directory — `%APPDATA%\CatGuard\alerts` on Windows, `~/.local/share/CatGuard/alerts` on Linux/macOS.

## Assumptions

- Recorded files are saved to a dedicated alerts folder within the OS user-data (AppData) directory: `%APPDATA%\CatGuard\alerts` on Windows and `~/.local/share/CatGuard/alerts` on Linux/macOS. The user provides only a filename (not a full path), so no folder navigation dialog is needed.
- The alerts folder path is displayed read-only in the Settings window, accompanied by a "Browse..." button on the same line that reveals the folder in the OS file explorer.
- On a fresh install (no prior settings), "Use Default Sound" defaults to checked so the app produces audible alerts immediately without any configuration.
- If the Settings window is closed while a recording is in progress, the recording is silently discarded and the sound library remains unchanged; alert sound suppression ends immediately.
- The "Use Default Sound" checkbox takes priority over both the sound library and the "Play Only This Sound" dropdown: when checked, the built-in default alert sound always plays, regardless of all other settings.
- The "Play Only This Sound" dropdown is only active (interactive) when "Use Default Sound" is unchecked.
- When "Use Default Sound" is unchecked and "Play Only This Sound" has no selection ("All"), all sounds in the library play randomly — identical to existing behaviour.
- If the file referenced by the dropdown selection is removed from the library or becomes inaccessible on disk, the dropdown resets to "All" automatically and random playback resumes.
- A recording is only considered valid if it produces a non-empty audio clip; a silent or zero-length recording is rejected with a user-visible message and is not added to the library.
- The filename prompt sanitises illegal characters automatically (spaces and special characters are replaced silently).
- If the entered filename conflicts with an existing recording, the app asks for confirmation before overwriting.
- Cancelling the name prompt (without confirming) discards the recording; the library remains unchanged.
- Only one recording session can be active at a time; the Record button is disabled while recording is in progress.
- A single recording session is capped at 10 seconds; recording stops automatically when the limit is reached and the name prompt is shown immediately, exactly as if the user had clicked Stop manually.
- The recording save location is fixed (the app's alerts folder) and is not user-configurable in this feature.
- The app always records from the OS default audio input device; no microphone selection UI is provided.

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Record and Save a Custom Alert Sound (Priority: P1)

A user wants a personalised alert sound without hunting for audio files externally. They open Settings, press Record, make a noise into their microphone, stop the recording, enter a name in the prompt that appears, and the new sound file is saved to disk and immediately appears in the library list — ready to be selected for playback.

**Why this priority**: Recording is the central new capability. Without it, the feature delivers no value beyond the existing file-load workflow.

**Independent Test**: Can be fully tested by opening Settings, completing the full record → stop → name → confirm flow, and verifying the new file appears in the library list and is used in playback on the next detection event.

**Acceptance Scenarios**:

1. **Given** the Settings window is open and no recording is in progress, **When** the user clicks the Record button, **Then** microphone capture begins immediately and the button changes to show that recording is active (e.g., label changes to "Stop Recording").
2. **Given** a recording is in progress, **When** the user clicks "Stop Recording", **Then** recording stops and a name-entry prompt is shown.
3. **Given** the name prompt is shown, **When** the user enters a valid name and confirms, **Then** the audio is saved to the app alerts folder and the new entry appears in the sound library list without requiring any further action.
4. **Given** the name prompt is shown, **When** the user dismisses the prompt or clicks Cancel, **Then** no file is saved and the library list remains unchanged.
5. **Given** the user enters a filename that already exists in the alerts folder, **When** they confirm the name, **Then** the app warns of the conflict and asks for confirmation before overwriting; the user may also choose a different name.
6. **Given** the recording contains no audible content (silent or zero-length), **When** the user tries to save it, **Then** the app shows a non-blocking warning message, does not save the file, and does not add anything to the library.
7. **Given** the Settings window is open, **When** the user clicks the "Browse..." button next to the alerts folder path, **Then** the OS file explorer opens showing the contents of the alerts folder.

---

### User Story 2 – Use Default Sound Toggle (Priority: P1)

A user wants a simple, always-reliable alert that is independent of their custom sound library. They check "Use Default Sound" in Settings, and from that point the app always plays the built-in default alert sound on every detection event, no matter what is in the library or selected in the dropdown.

**Why this priority**: Provides a zero-configuration, bulletproof fallback that is especially important for first-time users or after the custom library becomes empty or corrupted.

**Independent Test**: Can be fully tested by checking the "Use Default Sound" checkbox, triggering a detection event, and verifying the default sound plays even when library entries are present. Then uncheck it and verify library sounds are used.

**Acceptance Scenarios**:

1. **Given** "Use Default Sound" is checked, **When** a detection event is triggered, **Then** the built-in default sound plays, regardless of any entries in the library or the dropdown selection.
2. **Given** "Use Default Sound" is unchecked and the library has entries, **When** a detection event is triggered, **Then** a sound from the library plays (not the built-in default).
3. **Given** "Use Default Sound" is unchecked and the library is empty, **When** a detection event is triggered, **Then** the built-in default sound plays as a fallback — preserving the existing fallback behaviour.
4. **Given** the "Use Default Sound" state is saved in Settings, **When** the app restarts, **Then** the checkbox is restored to its saved state.
5. **Given** "Use Default Sound" is checked, **When** the user views the Settings window, **Then** the "Play Only This Sound" dropdown appears visually disabled (non-interactive) to make clear it has no effect.
6. **Given** the app is launched for the first time with no prior settings, **When** the Settings window is opened, **Then** the "Use Default Sound" checkbox is checked by default.

---

### User Story 3 – Play a Specific Sound from the Library (Priority: P2)

A user has several sounds loaded but always wants one particular sound to play on detection. They select that sound from the "Play Only This Sound" dropdown, and from that point on every detection event plays exactly that sound — not a random one.

**Why this priority**: Builds deterministic playback control on top of the existing library; useful when one sound is clearly preferable but the user also wants to keep the others in the library for future use.

**Independent Test**: Can be fully tested by selecting a specific entry in the dropdown, triggering multiple detection events, and verifying the same sound plays every time. Then reset to "All" and verify random playback resumes.

**Acceptance Scenarios**:

1. **Given** "Use Default Sound" is unchecked and a specific sound is selected in the dropdown, **When** a detection event is triggered, **Then** only the selected sound plays on every event.
2. **Given** a specific sound is selected in the dropdown, **When** that sound is removed from the library, **Then** the dropdown automatically resets to "All" and subsequent events play a random sound from the remaining library entries.
3. **Given** "All" is selected in the dropdown (no specific sound), **When** a detection event is triggered, **Then** a randomly chosen sound from the library plays — identical to the existing behaviour.
4. **Given** the dropdown selection is saved, **When** the app restarts, **Then** the same selection is restored.
5. **Given** the library contains exactly one sound and "All" is selected, **When** a detection event is triggered, **Then** that single sound plays.

---

### Edge Cases

- What happens when the Settings window is closed while a recording is in progress? — The recording is silently discarded, the window closes normally, the library remains unchanged, and alert sound suppression ends immediately.
- What happens when the 10-second recording limit is reached? — Recording stops automatically and the name prompt is shown immediately, identical to the user having clicked "Stop Recording" manually; no data is lost.
- What happens when a cat is detected while the user is actively recording? — The alert sound is suppressed for the entire duration of the recording session; normal sound playback resumes automatically once recording is stopped or cancelled.
- What happens when the microphone is not available or access is denied? — Recording fails immediately with a non-blocking notification to the user; no crash occurs and the Record button returns to its default state.
- What happens if the user starts recording but never clicks Stop? — The 10-second cap acts as an automatic stop; recording ends and the name prompt appears at the 10-second mark regardless of user action.
- What happens when the specific sound selected in the dropdown is no longer accessible on disk (e.g., file was deleted externally)? — The app treats the file as missing on next playback attempt, resets the dropdown to "All", and falls back to random playback.
- What happens when the sound library is empty and "Use Default Sound" is unchecked? — The built-in default sound plays as a fallback (existing behaviour preserved).
- What happens if disk space is exhausted while saving a recording? — The save fails gracefully; a non-blocking error notification is shown and no partial file is added to the library.
- What happens when the user tries to start a new recording while one is already in progress? — The Record button is disabled during active recording; a second recording cannot be started until the current one is stopped or cancelled.
- What happens when the dropdown lists a sound that has been removed from the library? — The removed entry is no longer displayed; if it was selected, the dropdown resets to "All".

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Settings window MUST include a "Record" button that begins capturing audio from the system microphone when clicked.
- **FR-002**: While a recording is in progress, the Record button MUST change its appearance or label to indicate the active state and MUST prevent a second recording from starting.
- **FR-003**: When the user stops a recording, the app MUST present a prompt asking the user to provide a filename before the file is saved.
- **FR-004**: The app MUST save the recorded audio as a WAV file into the OS user-data alerts folder (`%APPDATA%\CatGuard\alerts` on Windows; `~/.local/share/CatGuard/alerts` on Linux/macOS). The folder MUST be created automatically if it does not yet exist.
- **FR-005**: Upon a successful save, the app MUST automatically add the new recording to the sound library list with no additional user action.
- **FR-006**: If the user cancels the name prompt, the recording MUST be discarded and the library MUST remain unchanged.
- **FR-007**: If a filename entered in the prompt conflicts with an existing recording, the app MUST warn the user and require explicit confirmation before overwriting.
- **FR-008**: If microphone access is unavailable or denied, the app MUST display a non-blocking notification and MUST NOT crash or freeze.
- **FR-009**: A recording that produces no audible content (silent or zero-length) MUST be rejected with a non-blocking user notification and MUST NOT be added to the library.
- **FR-010**: The Settings window MUST include a "Use Default Sound" checkbox.
- **FR-011**: When "Use Default Sound" is checked, the app MUST play only the built-in default sound on every detection event, ignoring the library and dropdown selection entirely.
- **FR-012**: When "Use Default Sound" is unchecked, the app MUST use the sound library for playback, applying the dropdown selection if one is set, or random selection otherwise.
- **FR-013**: When "Use Default Sound" is checked, the "Play Only This Sound" dropdown MUST be visually disabled (non-interactive).
- **FR-014**: The Settings window MUST include a "Play Only This Sound" dropdown populated with all current entries in the sound library, plus an "All" option (no specific selection).
- **FR-015**: When a specific sound is selected in the dropdown and "Use Default Sound" is unchecked, the app MUST play only that sound on each detection event.
- **FR-016**: When "All" is selected in the dropdown, the app MUST play a randomly chosen sound from the library on each detection event — preserving existing behaviour.
- **FR-017**: If the sound file referenced by the dropdown selection is removed from the library or becomes inaccessible, the dropdown MUST reset to "All" and random playback MUST resume automatically.
- **FR-018**: The "Use Default Sound" checkbox state and the "Play Only This Sound" dropdown selection MUST be persisted and correctly restored after every application restart.
- **FR-019**: While a recording session is active, the app MUST suppress all alert sound playback; normal playback MUST resume automatically once the recording is stopped or cancelled.
- **FR-020**: A recording session MUST be capped at 10 seconds; when the limit is reached the app MUST stop recording automatically and present the name prompt immediately, with no data loss.
- **FR-021**: The Settings window MUST display the alerts folder path as a read-only field and MUST include a "Browse..." button on the same line that opens the alerts folder in the OS file explorer.
- **FR-022**: On a fresh install with no prior settings, the "Use Default Sound" checkbox MUST default to checked.
- **FR-023**: If the Settings window is closed while a recording is in progress, the app MUST silently discard the recording, close the window normally, leave the sound library unchanged, and immediately end alert sound suppression.
- **FR-024**: The app MUST capture audio from the OS default input device; no microphone selection UI is provided.

### Key Entities

- **Sound Library**: The collection of audio file paths available for alert playback; managed (add, remove) in the Settings window.
- **Recorded Sound**: An audio clip captured from the system microphone, named by the user, saved to the app's alerts folder, and added to the Sound Library.
- **Playback Mode**: The effective rule that determines which sound plays on a detection event — one of: *Default Sound* (built-in), *Specific Sound* (fixed library entry), or *Random from Library* (existing behaviour).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can complete the full record → stop → name → confirm → verify-in-list flow in under 60 seconds from clicking the Record button.
- **SC-002**: After toggling the "Use Default Sound" checkbox and saving Settings, the next detection event plays the correct sound with no additional delay compared to the existing playback latency.
- **SC-003**: After selecting a specific sound in the dropdown, 100% of subsequent detection events play that exact sound until the selection changes or the file becomes inaccessible.
- **SC-004**: All three settings — recorded sound in library, "Use Default Sound" state, and dropdown selection — survive an application restart and are correctly restored 100% of the time.
- **SC-005**: A microphone failure at recording start produces a visible, non-blocking user notification within 3 seconds and does not crash, freeze, or degrade the running detection session.
- **SC-006**: When recording is saved successfully, the audio file exists on disk and the library entry is present in Settings; the file is never silently lost after a confirmed save.
