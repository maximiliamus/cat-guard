# Research: Pause/Continue Tracking Control

**Date**: 2026-03-03  
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Design Decisions Made

### 1. Detection Loop Control Mechanism

**Decision**: Add three new methods to `DetectionLoop` class:
- `pause()` - stop the detection loop and disable camera
- `resume()` - restart the detection loop and enable camera  
- `is_tracking()` - return current tracking state (boolean)

**Rationale**: 
- Encapsulates pause/resume logic within DetectionLoop responsibility
- Thread-safe via existing threading primitives
- Minimal API surface (3 methods)
- Aligns with existing DetectionLoop design pattern

**Alternatives Considered**:
- External pause flag: Would scatter state management across multiple files; rejected because it violates single responsibility
- State machine class: Overkill for binary state (tracking/paused); rejected because simpler solution exists

### 2. Tray Icon Color State Indicator

**Decision**: 
- Use `pystray.Icon` with PIL Image recoloring in memory
- Active tracking: Bright green (#00FF00 or system accent green)
- Paused/Uninitialized: System default tray icon color (no recoloring)

**Rationale**:
- No additional assets needed (reuse existing icon, apply color overlay)
- Works across Windows/Linux/macOS tray backends
- Green universally recognized as "active/running" state
- System default respects user's theme preferences

**Alternatives Considered**:
- Separate icon files for each state: Would double asset maintenance; rejected
- Blinking icon: Too aggressive for background app; rejected
- Tooltip only: Insufficient visual feedback at a glance; rejected

### 3. Menu Item Implementation

**Decision**: 
- Single dynamic menu item labeled "Pause" or "Continue" based on current state
- Menu items order: Open, Settings, Separator, Pause/Continue, Separator, Exit
- Rebuild menu on each state change to update label

**Rationale**:
- Single item is cleaner than Pause + Continue toggles
- Dynamic label immediately communicates current state to user
- Menu reorganization improves UX by grouping related actions
- Separators create visual hierarchy (navigation vs. control vs. exit)

**Alternatives Considered**:
- Two separate menu items (Pause + Continue, one always disabled): Clutters menu; rejected
- Settings option to customize menu layout: Out of scope; rejected

### 4. Auto-Pause on Camera Failure

**Decision**: 
- Catch camera exceptions in detection loop
- Automatically pause tracking and log error
- Show tray tooltip/notification with error message
- User must manually resume after troubleshooting

**Rationale**:
- Prevents silent failures and resource leaks
- User has explicit control to resume (safe default)
- Error visibility prevents user confusion
- Matches security/monitoring app best practices

**Alternatives Considered**:
- Auto-retry with exponential backoff: Adds complexity; could mask persistent issues; rejected
- Continue without camera frames: Defeats detection purpose; rejected
- Immediate app exit: Too disruptive; rejected

### 5. Application Startup Behavior

**Decision**: 
- Tracking automatically starts on app initialization (green tray icon)
- First user action can immediately pause if desired

**Rationale**: (From Clarification Answer A)
- User expects app to actively monitor when launched
- Matches user expectations for security/detection apps
- User has full control via Pause menu item

### 6. Main Window Close Behavior

**Decision**: 
- Closing main window does NOT stop tracking
- Tracking continues in background via tray icon
- Application remains running in system tray

**Rationale**: (From Clarification Answer A)
- Standard tray application behavior
- Enables uninterrupted background monitoring
- User can explicitly pause if they want to stop

### 7. Error Notification Strategy

**Decision**: 
- Primary: Tray tooltip showing error message (hover over tray icon)
- Secondary: Application log file for audit trail
- No intrusive modal dialogs or toast notifications

**Rationale**: (Suggested from Q5)
- Non-intrusive for background monitoring
- User can check status by hovering tray icon
- Maintains audit trail via logging
- Standard practice for background apps

## Technology Stack Confirmation

### Existing Dependencies (all available)

- **`pystray`**: Tray icon management
  - Provides: Icon creation, menu building, platform abstraction (Win32/AppIndicator/Quartz)
  - Status: Already used in `tray.py`

- **`Pillow (PIL)`**: Image manipulation
  - Provides: Icon image loading, format conversion, color operations
  - Status: Already used, available as optional dependency for icon caching

- **`threading`** (Python stdlib): Thread synchronization
  - Provides: `Event`, `Lock`, `Condition` for pause/resume coordination
  - Status: Already used in `detection.py`

- **`opencv-python (cv2)`**: Camera control
  - Provides: `VideoCapture.release()` to disable camera
  - Status: Already used

- **`pytest`**: Test framework
  - Provides: Test discovery, fixtures, mocking
  - Status: Already used, `pytest-mock` available

### No New Dependencies Required

✅ All technologies already in `pyproject.toml` dependencies or dev dependencies.

## Implementation Approach

### Phase 1: Data Model & Contracts

**State Machine** (tracking_state.md):
```
States: [Uninitialized] → [Active] ↔ [Paused] → [Error/Paused]
Transitions:
- Uninitialized → Active: on app init (auto-start)
- Active → Paused: user clicks "Pause" menu item
- Paused → Active: user clicks "Continue" menu item
- Active → Paused: on camera error (auto-pause)
- Paused → Active: manual user action (no auto-retry)
```

**Tray Icon Color Contract** (icon-color.md):
```
State:           | Icon Color
Active tracking  | Bright green (#00FF00 or system accent)
Paused           | System default (no overlay)
Uninitialized    | System default (no overlay)
Error/Paused     | System default + tooltip with error text
```

### Phase 2: Implementation Modules

**`detection.py`** additions:
- `DetectionLoop.pause()` - signal stop, disable camera
- `DetectionLoop.resume()` - signal start, enable camera
- `DetectionLoop.is_tracking()` - return tracking state
- Error handling: catch camera exceptions → auto-pause
- Thread safety: use existing `threading.Event` and locks

**`tray.py`** additions:
- `build_tray_icon()`: Add pause/continue menu item
- Menu reorganization: new item order with separators
- `update_tray_icon_color(icon, is_tracking)` - recolor icon based on state
- `update_tray_menu(icon, is_tracking)` - update menu label

**`main.py`** updates:
- Set initial tracking state to active (auto-start)
- Pass pause/resume callbacks to detection loop

### Phase 3: Testing Strategy

**Unit Tests** (`tests/unit/`):
- `test_detection.py::test_pause_stops_loop()` - verify loop halts
- `test_detection.py::test_resume_starts_loop()` - verify loop restarts
- `test_detection.py::test_is_tracking_state()` - verify state queries
- `test_tray.py::test_pause_menu_item_label()` - verify label updates
- `test_tray.py::test_tray_icon_color_active()` - verify green when active
- `test_tray.py::test_tray_icon_color_paused()` - verify system default when paused

**Integration Tests** (`tests/integration/`):
- `test_tray_pause_resume.py::test_menu_pause_stops_detection()` - E2E pause flow
- `test_tray_pause_resume.py::test_menu_continue_starts_detection()` - E2E resume flow
- `test_camera_failure_recovery.py::test_camera_unavailable_auto_pauses()` - Camera failure handling

## Open Questions (Resolved via Clarifications)

✅ All clarifications recorded in [spec.md](spec.md) Clarifications section:
- Startup behavior: Auto-start tracking
- Camera failure: Auto-pause with error notification
- Window close: Continue tracking in background
- Icon colors: System default + bright green

## Dependencies & Integration Points

### Internal Integration

1. **`DetectionLoop` (detection.py)**
   - Provides: Pause/resume methods
   - Consumes: No new dependencies

2. **Tray System (tray.py)**
   - Provides: Updated menu with pause/continue item
   - Consumes: `DetectionLoop` pause/resume/is_tracking methods

3. **Main Loop (main.py)**
   - Provides: Initial state = active
   - Consumes: Nothing new (existing start/stop logic)

### External APIs

- **System Tray (pystray)**
  - Icon coloring: Native PIL Image operations
  - Menu callbacks: Existing handler pattern

- **Camera (opencv-python)**
  - Release/open: Existing VideoCapture API

- **Threading (stdlib)**
  - Synchronization: Event, Lock, Condition already in use

## Risk Assessment

### Low Risk

✅ Minimal surface area (3 files, ~500 LOC changes)
✅ No new external dependencies
✅ No database/storage changes
✅ No breaking API changes to public interfaces
✅ Pause/resume is idempotent (safe to call multiple times)

### Mitigation Strategies

- **Camera release safety**: Wrap camera operations in try/except
- **Thread safety**: Use existing threading primitives (Event, Lock)
- **State consistency**: Unit tests verify state transitions
- **Platform compatibility**: Test on Windows, Linux, macOS

## Success Metrics

From [spec.md](spec.md) Success Criteria:

- SC-001: Pause completes within 500ms ✓
- SC-002: Resume completes within 500ms ✓
- SC-003: Icon color updates within 100ms ✓
- SC-004: Paused state persists until Continue clicked ✓
- SC-005: Menu state reflects tracking state 100% ✓
- SC-006: Menu order correct in 100% of tests ✓
- SC-007: No extra clicks needed for pause/resume ✓
