# Contract: Tray Icon & Menu UI

**Location**: `tray.py`  
**Responsibility**: Define tray icon visual state and menu interaction interface

## Public Interface

### Functions

#### `update_tray_icon_color(icon: pystray.Icon, is_tracking: bool) -> None`

**Purpose**: Update tray icon color to reflect tracking state

**Signature**:
```python
def update_tray_icon_color(icon: pystray.Icon, is_tracking: bool) -> None: ...
```

**Input**:
- `icon` (pystray.Icon): Active tray icon instance
- `is_tracking` (bool): `True` for active (green), `False` for paused (default)

**Output**:
- None (updates icon in-place)

**Side Effects**:
- Modifies icon image in system tray
- Visual change appears immediately on screen
- Platform-specific (Win32/AppIndicator/Quartz backends handle rendering)

**Error Handling**:
- Catches PIL image errors and logs them
- Falls back to original icon if recoloring fails
- Never throws exception to caller (non-blocking)

**Performance**:
- Image recoloring: <50ms
- Icon replacement: <50ms
- Total: <100ms target

**Color Mapping**:
```
is_tracking=True   → Bright green: RGB(0, 255, 0) or system accent
is_tracking=False  → System default: No color overlay (use original)
```

**Platform Considerations**:
- **Windows (Win32)**: PIL Image → temporary .ico file → LoadImage API
- **Linux (AppIndicator)**: PIL Image → PNG buffer → AppIndicator D-Bus
- **macOS (Quartz)**: PIL Image → NSImage → Quartz render

---

#### `update_tray_menu(icon: pystray.Icon, is_tracking: bool) -> None`

**Purpose**: Rebuild tray menu with correct Pause/Continue label

**Signature**:
```python
def update_tray_menu(icon: pystray.Icon, is_tracking: bool) -> None: ...
```

**Input**:
- `icon` (pystray.Icon): Active tray icon instance
- `is_tracking` (bool): `True` to show "Pause", `False` to show "Continue"

**Output**:
- None (updates menu in-place)

**Menu Structure**:
```
1. Open               [pystray.MenuItem]
2. Settings…          [pystray.MenuItem]
3. ─────────          [pystray.MenuItem separator]
4. Pause/Continue     [pystray.MenuItem] ← dynamic label
5. ─────────          [pystray.MenuItem separator]
6. Exit               [pystray.MenuItem]
```

**Label Rules**:
- `is_tracking=True`  → Label = "Pause"
- `is_tracking=False` → Label = "Continue"

**Side Effects**:
- Rebuilds entire menu (pystray limitation)
- Menu disappears and reappears (brief flicker)
- Right-click tray icon shows new menu immediately

**Error Handling**:
- Catches pystray menu rebuild errors and logs them
- Falls back to last known menu state
- Never throws exception to caller

**Performance**:
- Menu rebuild: <50ms
- Icon update: <50ms
- Total: <100ms target

**Handler Callbacks**:
- All handlers must be callable (closures or bound methods)
- Handlers receive `(icon, item)` parameters (pystray convention)
- Handlers should be non-blocking (dispatch to threads if needed)

---

## State Synchronization Contract

### Invariant 1: Menu Label Reflects Tracking State

```
is_tracking() = True  ⟺  menu label = "Pause"
is_tracking() = False ⟺  menu label = "Continue"
```

**Enforcement**:
- Every call to `detection_loop.pause()` triggers `update_tray_menu(icon, False)`
- Every call to `detection_loop.resume()` triggers `update_tray_menu(icon, True)`
- Menu rebuilt before returning control to user

**Verification**:
- Test right-click tray, verify label matches state
- Test rapid pause/continue, verify label always matches

### Invariant 2: Icon Color Reflects Tracking State

```
is_tracking() = True  ⟺  icon color = bright green
is_tracking() = False ⟺  icon color = system default
```

**Enforcement**:
- Every call to `detection_loop.pause()` triggers `update_tray_icon_color(icon, False)`
- Every call to `detection_loop.resume()` triggers `update_tray_icon_color(icon, True)`
- Color updated before returning control to user

**Verification**:
- Test icon color on pause/resume
- Test color consistency with menu label
- Test color on startup (should be green for auto-start)

### Invariant 3: Menu Item Always Available

```
Pause/Continue menu item is clickable in both states
- is_tracking=True  → Click enabled, label="Pause"
- is_tracking=False → Click enabled, label="Continue"
```

**Enforcement**:
- Menu item never disabled or hidden
- Handler registered for both states

**Verification**:
- Test pause menu item is clickable when active
- Test continue menu item is clickable when paused

---

## Interaction Model

### User Clicks Pause (when active)

```
User right-clicks tray icon
  ↓
Sees menu: "Pause" (menu label)
  ↓
Clicks "Pause"
  ↓
Handler calls detection_loop.pause()
  ↓
pause() returns True (was tracking)
  ↓
update_tray_menu(icon, False) → label becomes "Continue"
  ↓
update_tray_icon_color(icon, False) → icon becomes default color
  ↓
Handler returns, user sees updated tray icon and menu
```

**Timing**:
- Menu label updates: <100ms from click
- Icon color updates: <100ms from click
- Next right-click shows new state: immediate

---

### User Clicks Continue (when paused)

```
User right-clicks tray icon
  ↓
Sees menu: "Continue" (menu label)
  ↓
Clicks "Continue"
  ↓
Handler calls detection_loop.resume()
  ↓
resume() returns True (was paused)
  ↓
update_tray_menu(icon, True) → label becomes "Pause"
  ↓
update_tray_icon_color(icon, True) → icon becomes green
  ↓
Handler returns, user sees updated tray icon and menu
```

**Timing**:
- Menu label updates: <100ms from click
- Icon color updates: <100ms from click
- Camera opens: 100-200ms (happens in background)
- Detection resumes: immediate after camera opens

---

### Rapid Pause/Continue Clicks

**Scenario**: User clicks Pause, quickly clicks Continue before camera fully closes

**Behavior**:
- First click: pause() stops loop, disables camera, returns True
- Second click (queue or buffered): continue() starts loop, enables camera, returns True
- Final state: Tracking active
- Menu/color: Synchronized to active state
- No errors or race conditions

**Guarantee**:
- Thread safety enforced by DetectionLoop locks
- UI always reflects final state accurately
- No intermediate states leak to UI

---

## Error Scenarios

### Camera Unavailable on Resume

**When**: User clicks Continue but camera cannot be opened

**Behavior**:
- `detection_loop.resume()` raises `CameraError`
- Tray handler catches exception
- Menu remains "Continue" (state is Paused)
- Icon color remains default
- Error tooltip shown on tray icon hover

**Example**:
```
User clicks "Continue" with camera unplugged
  ↓
resume() raises CameraError("Camera not found")
  ↓
Handler catches exception, calls show_error_tooltip()
  ↓
Tray tooltip: "Camera unavailable - plug in and try again"
  ↓
User plugs camera back in, clicks "Continue" again
  ↓
resume() succeeds, tracking resumes
```

### Platform-Specific Icon Rendering

**Windows**: PIL Image → .ico file → Win32 LoadImage
- Potential failure: ICO encoding error
- Fallback: Log warning, use original icon
- User sees: No color change but app continues

**Linux**: PIL Image → PNG buffer → AppIndicator D-Bus
- Potential failure: D-Bus connection error
- Fallback: Log warning, retry on next state change
- User sees: No color change but app continues

**macOS**: PIL Image → NSImage → Quartz
- Potential failure: Image codec error
- Fallback: Log warning, use original icon
- User sees: No color change but app continues

---

## Performance Guarantees

| Operation | Latency | Notes |
|-----------|---------|-------|
| Menu label update | <100ms | Rebuild + render |
| Icon color update | <100ms | Recolor + render |
| Combined UI update | <200ms | Both happen on same event |
| Rapid clicks handling | <500ms | Per click, no queueing |
| Error tooltip appear | <1s | May show with slight delay |

---

## Testing Requirements

### Unit Tests

- `test_update_menu_pause_label()` - Menu shows "Pause" when tracking
- `test_update_menu_continue_label()` - Menu shows "Continue" when paused
- `test_update_icon_color_green()` - Icon green when tracking
- `test_update_icon_color_default()` - Icon default when paused
- `test_menu_item_callback_pause()` - Pause handler calls detection_loop.pause()
- `test_menu_item_callback_continue()` - Continue handler calls detection_loop.resume()
- `test_error_handling_camera_fail()` - Camera error shows tooltip

### Integration Tests

- `test_ui_state_sync_pause()` - Menu + icon both update on pause
- `test_ui_state_sync_resume()` - Menu + icon both update on resume
- `test_rapid_pause_continue_clicks()` - No race conditions
- `test_tray_tooltip_on_camera_error()` - Error notification appears

### Contract Verification

- State invariants checked after every UI update
- Synchronization tested under concurrent load
- Performance measured against latency targets
- Platform compatibility tested on Windows/Linux/macOS
