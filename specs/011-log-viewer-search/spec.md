# Feature Specification: Log Viewer with Search, Clipboard Copy, and Auto-Trim

**Feature Branch**: `011-log-viewer-search`
**Created**: 2026-03-19
**Status**: Draft
**Input**: User description: "Trim logs to avoid extra disk usage. Add window to view logs opened via "Logs" menu item. Add search by log text feature: input and button on top window panel. Add Copy To Clipboard button on tool bar aligned to right to copy logs into clipboard."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Application Logs (Priority: P1)

A user wants to review what CatGuard has been doing — detections, alerts played, errors — by opening a dedicated log viewer window from the tray icon menu.

**Why this priority**: Providing visibility into application activity is foundational. Without the log viewer window, the search and trim features have no surface to display or act upon.

**Independent Test**: Can be fully tested by clicking "Logs" in the tray menu and verifying a window opens showing log entries, independent of search or trim functionality.

**Acceptance Scenarios**:

1. **Given** CatGuard is running, **When** the user clicks "Logs" in the tray icon menu, **Then** a log viewer window opens displaying application log entries in reverse-chronological order (newest first).
2. **Given** the log viewer window is already open, **When** the user clicks "Logs" again, **Then** the existing window is brought to focus rather than opening a duplicate.
3. **Given** the log viewer is open, **When** the user clicks the "Refresh" button, **Then** the viewer reloads and displays the latest log entries.
4. **Given** no log entries exist, **When** the user opens the log viewer, **Then** the window displays a message indicating no log entries are available.

---

### User Story 2 - Search Log Entries (Priority: P2)

A user wants to quickly find specific events in the log — such as all cat detections or a particular error — by typing keywords into a search input in the log viewer.

**Why this priority**: With potentially large log history, search is essential for the log viewer to be useful. It directly extends P1 without being required for basic viewing.

**Independent Test**: Can be fully tested by opening the log viewer, typing a search term, clicking the search button, and verifying only matching entries are shown.

**Acceptance Scenarios**:

1. **Given** the log viewer is open with entries, **When** the user types text into the search input and clicks the search button, **Then** only log entries containing the typed text (case-insensitive) are displayed.
2. **Given** a search is active, **When** the user clears the search input and clicks the search button, **Then** all log entries are shown again.
3. **Given** a search term matches no entries, **When** the user performs the search, **Then** the log list shows a message indicating no results were found.
4. **Given** the log viewer is open, **When** the user presses Enter in the search input, **Then** the search executes (same as clicking the search button).

---

### User Story 3 - Automatic Log Trimming (Priority: P3)

The application automatically limits the size of stored log data so that CatGuard does not consume excessive disk space over time.

**Why this priority**: Important for long-running deployments, but does not affect day-to-day user interaction with the log viewer. It is a background maintenance behavior.

**Independent Test**: Can be fully tested by running the app until trimming conditions are met and verifying the log file or entry count stays within defined bounds.

**Acceptance Scenarios**:

1. **Given** the log has grown beyond the defined size limit, **When** new log entries are written, **Then** the oldest entries are automatically removed to bring the log back within the limit.
2. **Given** the log is within the size limit, **When** new entries are added, **Then** no trimming occurs and all existing entries are preserved.
3. **Given** trimming has occurred, **When** the user opens the log viewer, **Then** only the retained (non-trimmed) entries are shown with no errors.

---

### User Story 4 - Copy Logs to Clipboard (Priority: P3)

A user wants to copy the currently displayed log entries to the clipboard so they can paste them into a bug report, support message, or another application.

**Why this priority**: Useful for sharing or escalating issues, but not required for the core log viewing and search experience. It extends the viewer without blocking any other story.

**Independent Test**: Can be fully tested by opening the log viewer, clicking the "Copy to Clipboard" button, and verifying the displayed entries are available to paste elsewhere.

**Acceptance Scenarios**:

1. **Given** the log viewer is open with entries, **When** the user clicks the "Copy to Clipboard" button (right-aligned on the toolbar), **Then** all currently displayed log entries are copied to the system clipboard as plain text.
2. **Given** a search filter is active, **When** the user clicks "Copy to Clipboard", **Then** only the filtered (visible) entries are copied, not the full log.
3. **Given** the user has selected a portion of text within the log display, **When** the user clicks "Copy to Clipboard", **Then** only the selected text is copied to the clipboard (not the full visible log).
4. **Given** no log entries are displayed (empty or search returns nothing), **When** the user clicks "Copy to Clipboard", **Then** nothing is copied and the button action is a no-op (or provides subtle feedback that there is nothing to copy).
5. **Given** the copy succeeds, **When** the user pastes elsewhere, **Then** the text is human-readable with timestamps and messages intact.

---

### Edge Cases

- What happens when copying to clipboard fails (e.g., clipboard is locked by another process)? The user is shown a brief error message; the log viewer remains functional.
- What happens when the log file is corrupted or unreadable? The viewer shows an error message and the app continues running normally.
- What happens when the user changes `logs_directory` to a new folder? The existing log file is left in the old directory; a new log file is created in the new directory and all subsequent writes go there. The log viewer will read from the new location.
- What happens when the log file is very large (e.g., thousands of entries)? The viewer loads and renders entries without freezing the UI; older entries may be paginated or lazy-loaded.
- What happens if new log entries are written while the viewer is open? The viewer does not update automatically; the user must click Refresh to see new entries.
- What happens when trimming removes entries the user is currently viewing? The viewer is not disrupted mid-session; changes appear on next Refresh or re-open.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tray icon menu MUST include a "Logs" menu item that opens the log viewer window.
- **FR-002**: The log viewer window MUST display application log entries, each showing at minimum a timestamp and message text.
- **FR-003**: The log viewer window MUST display entries in reverse-chronological order by default (newest first).
- **FR-004**: The log viewer window MUST contain a text input field and a search button in the top panel.
- **FR-005**: Users MUST be able to filter displayed log entries by typing text into the search input and activating search (button click or Enter key).
- **FR-006**: Search filtering MUST be case-insensitive and match any part of the full log line, including the timestamp and message text.
- **FR-007**: Clearing the search input and re-activating search MUST restore the full unfiltered log view.
- **FR-008**: The system MUST automatically trim log data using a batched write-time strategy: after every N new entries are written (configurable `log_trim_batch_size`, minimum and default 205), trimming is triggered if the total entry count exceeds the configured maximum.
- **FR-008b**: `log_trim_batch_size` (trim check frequency, minimum and default 205) and `max_log_entries` (maximum retained entry count, minimum and default 2,048) MUST be configurable settings. Values below their respective minimums MUST be rejected with an inline validation error.
- **FR-014**: The Settings window MUST include a "Logs" tab exposing three settings: `max_log_entries`, `log_trim_batch_size`, and `logs_directory`.
- **FR-015**: The "Logs" tab MUST include a "Logs directory" field with a "Browse…" button that opens a folder picker dialog, consistent with the pattern used in other Settings tabs.
- **FR-017**: Changes on the "Logs" tab MUST be applied only when the user confirms via the existing Settings window Save/Apply button, consistent with all other tabs.
- **FR-016**: The log file MUST be written to and read from the directory specified by the `logs_directory` setting. When `logs_directory` is changed, the existing log file is left in the previous directory and a new log file is created in the new directory; all subsequent writes and reads use the new location.
- **FR-009**: Log trimming MUST remove the oldest entries first, preserving the most recent activity.
- **FR-010**: If the log viewer window is already open, activating "Logs" from the menu MUST bring the existing window to focus instead of opening a new one.
- **FR-011**: The log viewer toolbar MUST include a "Refresh" button positioned at the far right of the toolbar; clicking it reloads the log entries from the current log store.
- **FR-011b**: The log viewer toolbar MUST include a "Copy to Clipboard" button positioned to the left of the "Refresh" button (right-aligned area of the toolbar).
- **FR-012**: Clicking "Copy to Clipboard" MUST copy to the clipboard: the selected text if any text is selected in the log display, or all currently displayed entries (respecting any active search filter) if no text is selected.
- **FR-013**: The copied text MUST preserve the timestamp and message content of each entry in a human-readable format.

### Key Entities

- **Log Entry**: A single recorded event in the application, with a timestamp and descriptive text. May include an event type/level (e.g., info, warning, error).
- **Log Store**: The collection of all persisted log entries. Subject to size constraints enforced by the auto-trim policy.
- **Trim Policy**: The rule governing log retention. Defined by two settings: `max_log_entries` (maximum retained entries, minimum and default 2,048) and `log_trim_batch_size` (how many new writes must occur before a trim check runs, minimum and default 205 — approximately 10% of the default `max_log_entries`). When a trim check fires and the entry count exceeds `max_log_entries`, the oldest entries are removed.
- **Logs Directory**: A configurable setting (`logs_directory`) specifying the folder where the log file is written and read from. Exposed on the "Logs" Settings tab with a "Browse…" folder picker button.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can open the log viewer from the tray menu in under 2 seconds on a standard system.
- **SC-002**: Users can locate a specific event in the log using search in under 30 seconds, regardless of log size.
- **SC-003**: The application log storage remains below a defined maximum at all times during normal operation (trimming keeps size bounded).
- **SC-004**: The log viewer displays up to 2,048 entries without causing the application UI to become unresponsive.
- **SC-005**: Search results are returned and displayed within 1 second of activating the search action.

## Assumptions

- Log entries are written to and read from a log file located in the directory specified by the `logs_directory` setting. The viewer reads this file directly to display its contents.
- The "Logs" menu item will be added to the existing tray icon context menu alongside current items (Open, Settings, Pause/Continue, etc.).
- `max_log_entries` minimum and default is 2,048; `log_trim_batch_size` minimum and default is 205 (≈10% of default `max_log_entries`); both are configurable settings exposed on the Logs tab in Settings.
- The log viewer is a read-only interface; users cannot edit or delete individual entries manually.
- Log entries are stored locally on the user's machine; no remote access or export is in scope for this feature.

## Clarifications

### Session 2026-03-19

- Q: What settings appear on the Logs tab in Settings? → A: `max_log_entries`, `log_trim_batch_size`, and `logs_directory` (with Browse… button); log file respects the directory setting.
- Q: When `logs_directory` changes, what happens to the existing log file? → A: Leave old file in place; create new log file in new directory for all subsequent writes.
- Q: Do Settings changes apply immediately or via Save button? → A: Save/Apply button, consistent with existing Settings window behavior.
- Q: Valid constraints for `max_log_entries` and `log_trim_batch_size` (renamed from `trim_batch_size`)? → A: `max_log_entries` min and default 2,048; `log_trim_batch_size` min and default 205 (10%).
- Q: What is the trim enforcement mechanism — entry count, file size, or both? → A: Entry count only.
- Q: How should the log viewer update when new entries are written — auto-polling, file watcher, or manual? → A: Manual Refresh button at far right of toolbar; no automatic polling.
- Q: Where are log entries stored — file, database, or in-memory? → A: Existing log file on disk; viewer reads file contents directly.
- Q: Does search match the full log line (including timestamp) or message text only? → A: Full line — timestamp and message text both searchable.
- Q: When does trimming run and how is it triggered? → A: Batched write-time — trim check fires every `log_trim_batch_size` writes (minimum and default 205, configurable); `max_log_entries` (minimum and default 2,048) is also a configurable setting.
