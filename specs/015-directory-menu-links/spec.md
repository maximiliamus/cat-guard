# Feature Specification: Tray directory shortcuts

**Feature Branch**: `015-directory-menu-links`  
**Created**: 2026-03-28  
**Status**: Draft  
**Input**: User description: "Add menu items after Pause / Continue: Open Tracking Directory, Open Photos Directory. Put a separator before them."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open tracking screenshots folder from the tray (Priority: P1)

A user wants to review recently saved tracking screenshots without opening Settings or browsing the filesystem manually.

**Why this priority**: Tracking screenshots are part of the app's core monitoring workflow. Fast access from the tray removes friction from the main review flow.

**Independent Test**: Launch the app, open the tray menu, click `Tracking Directory`, and verify the configured tracking folder opens in the operating system's file manager.

**Acceptance Scenarios**:

1. **Given** the app is running and the tray menu is open, **When** the user clicks `Tracking Directory`, **Then** the configured tracking directory opens in the system file manager.
2. **Given** the configured tracking directory does not exist yet, **When** the user clicks `Tracking Directory`, **Then** the app creates the directory and opens it.
3. **Given** the tracking directory cannot be opened, **When** the user clicks `Tracking Directory`, **Then** the app remains running and shows a non-blocking error to the user.

---

### User Story 2 - Open saved photos folder from the tray (Priority: P2)

A user wants to jump directly to the folder where manually captured photos are saved.

**Why this priority**: This is a frequent follow-up action after taking photos, but it is secondary to reviewing tracking evidence.

**Independent Test**: Launch the app, open the tray menu, click `Photos Directory`, and verify the configured photos folder opens in the operating system's file manager.

**Acceptance Scenarios**:

1. **Given** the app is running and the tray menu is open, **When** the user clicks `Photos Directory`, **Then** the configured photos directory opens in the system file manager.
2. **Given** the configured photos directory does not exist yet, **When** the user clicks `Photos Directory`, **Then** the app creates the directory and opens it.
3. **Given** the photos directory cannot be opened, **When** the user clicks `Photos Directory`, **Then** the app remains running and shows a non-blocking error to the user.

---

### User Story 3 - Keep tray menu layout predictable (Priority: P3)

A user relies on muscle memory in the tray menu and expects the new directory shortcuts to appear in a stable, logical position without changing the existing pause/resume behavior.

**Why this priority**: The shortcuts are only useful if they are easy to discover and do not disrupt existing tray actions.

**Independent Test**: Build the tray menu in both active and paused states and verify the item order is `Live View`, `Logs`, `Settings…`, separator, `Pause`/`Continue`, separator, `Tracking Directory`, `Photos Directory`, separator, `Exit`.

**Acceptance Scenarios**:

1. **Given** tracking is active, **When** the tray menu is shown, **Then** the menu item after the second separator is `Tracking Directory` and the next item is `Photos Directory`.
2. **Given** tracking is paused, **When** the tray menu is shown, **Then** the same two directory items still appear after `Continue`.
3. **Given** the new items are added, **When** the user clicks `Pause` or `Continue`, **Then** the existing tracking toggle behavior remains unchanged.

### Edge Cases

- What happens if the configured directory path is relative? The app resolves it the same way it uses the setting elsewhere, then opens the resolved directory.
- What happens if the directory path contains leading or trailing whitespace? The app ignores surrounding whitespace before attempting to open the folder.
- What happens if the operating system rejects the open request? The app keeps running, logs the failure, and surfaces a non-blocking error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tray menu MUST include a `Tracking Directory` item.
- **FR-002**: The tray menu MUST include a `Photos Directory` item.
- **FR-003**: The tray menu MUST place a separator immediately before these two directory items.
- **FR-004**: The tray menu MUST keep the directory items after the `Pause` / `Continue` item and before `Exit`.
- **FR-005**: Selecting `Tracking Directory` MUST target the currently configured tracking directory.
- **FR-006**: Selecting `Photos Directory` MUST target the currently configured photos directory.
- **FR-007**: If the target directory does not exist, the app MUST create it before attempting to open it.
- **FR-008**: If the directory cannot be opened, the app MUST continue running and MUST provide a non-blocking user-visible error.
- **FR-009**: The directory menu items MUST be available in both active and paused tracking states.
- **FR-010**: Adding the new directory items MUST NOT change the existing behavior of `Live View`, `Logs`, `Settings…`, `Pause` / `Continue`, or `Exit`.

### Key Entities

- **Tracking Directory**: The folder configured by the user for saved tracking screenshots and related session exports.
- **Photos Directory**: The folder configured by the user for manually captured photos.
- **Tray Directory Shortcut**: A tray menu action that opens one configured folder in the operating system's file manager.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In both active and paused tray states, users can reach either configured directory in a single menu click after opening the tray.
- **SC-002**: In 100% of tested runs, the tray menu order matches the specified layout with the directory items grouped after `Pause` / `Continue`.
- **SC-003**: In 100% of tested runs where the configured directory is missing, the app creates the directory and opens it without requiring the user to visit Settings first.
- **SC-004**: When the operating system refuses to open a configured directory, the app stays responsive and preserves tray functionality in 100% of tested failure cases.

## Assumptions

- The operating system's default file manager is the correct destination for both directory shortcuts.
- Existing configured directory values remain valid sources of truth; no new settings fields are needed.
- `Exit` remains the last tray item, with a separator preserved before it for visual grouping.
