# Data Model: Pause/Continue Tracking Control

**Date**: 2026-03-03  
**Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

## State Machine: Tracking Control

### States

```
┌──────────────────┐
│  Uninitialized   │  (App just started)
│  Color: default  │
└────────┬─────────┘
         │ on_app_init()
         ▼
┌──────────────────┐
│      Active      │  (Tracking loop running)
│   Color: green   │
└────────┬─────────┘
         │ user_clicks_pause()
         │ OR camera_fails()
         ▼
┌──────────────────┐
│     Paused       │  (Tracking loop stopped)
│  Color: default  │
└────────┬─────────┘
         │ user_clicks_continue()
         └─────────────────┐
                           │
                           ▼
                    (back to Active)
```

### State Definitions

| State | Loop Running | Camera Enabled | Icon Color | Menu Item Label | Description |
|-------|---|---|---|---|---|
| **Uninitialized** | No | No | Default | N/A | App startup, before tracking begins |
| **Active** | Yes | Yes | Bright Green | "Pause" | Actively monitoring; user can click Pause |
| **Paused** | No | No | Default | "Continue" | Monitoring stopped; user can click Continue |
| **Error/Paused** | No | No | Default + tooltip | "Continue" | Camera failed; shown as Paused state with error tooltip |

### Transitions

| From | To | Trigger | Action | Menu Change |
|---|---|---|---|---|
| Uninitialized | Active | `app_init()` | Start loop, enable camera | N/A → "Pause" |
| Active | Paused | `user_pause()` | Stop loop, disable camera | "Pause" → "Continue" |
| Paused | Active | `user_resume()` | Start loop, enable camera | "Continue" → "Pause" |
| Active | Paused | `camera_error()` | Stop loop, disable camera, log error | "Pause" → "Continue" + tooltip |
| Any | Any | Idempotent calls | No-op (safe to call multiple times) | No change |

## Entity: TrackingState

**Responsibility**: Central tracking state for the entire application

**Location**: `detection.py` - extend `DetectionLoop` class

### Properties

```python
class DetectionLoop:
    # Existing
    _stop_event: threading.Event
    _frame_callback: Optional[Callable]
    _cooldown: datetime
    _model: YOLO
    
    # New for pause/continue
    _is_tracking: bool = False  # True when loop running, False when paused
    _tracking_lock: threading.Lock  # Protect state changes
    _camera: Optional[cv2.VideoCapture] = None  # Camera reference
```

### Methods

#### `pause() -> bool`

Stops the detection loop and disables the camera.

```python
def pause(self) -> bool:
    """
    Stop the detection loop and disable camera.
    
    Returns:
        bool: True if pause was executed, False if already paused
    
    Thread-safe: Can be called from any thread
    Idempotent: Safe to call multiple times
    """
    with self._tracking_lock:
        if not self._is_tracking:
            return False  # Already paused
        self._is_tracking = False
        if self._camera:
            self._camera.release()
            self._camera = None
    # Signal loop to stop (existing mechanism)
    self._stop_event.set()
    return True
```

#### `resume() -> bool`

Starts the detection loop and enables the camera.

```python
def resume(self) -> bool:
    """
    Start the detection loop and enable camera.
    
    Returns:
        bool: True if resume was executed, False if already active
    
    Thread-safe: Can be called from any thread
    Idempotent: Safe to call multiple times
    
    Raises:
        CameraError: If camera cannot be opened
    """
    with self._tracking_lock:
        if self._is_tracking:
            return False  # Already running
        self._is_tracking = True
        self._stop_event.clear()  # Clear stop signal
    # Restart detection thread (caller responsibility)
    return True
```

#### `is_tracking() -> bool`

Returns whether tracking is currently active.

```python
def is_tracking(self) -> bool:
    """
    Check if tracking loop is currently running.
    
    Returns:
        bool: True if tracking active, False if paused/stopped
    
    Thread-safe: Read-only lock
    """
    with self._tracking_lock:
        return self._is_tracking
```

## Entity: TrayIconState

**Responsibility**: Tray icon visual state (color, menu label)

**Location**: `tray.py`

### Properties

```python
# Tray icon color state
TRACKING_ACTIVE_COLOR = (0, 255, 0)  # Bright green RGB
TRACKING_PAUSED_COLOR = None  # System default (no recolor)

# Menu item state
PAUSE_LABEL = "Pause"
CONTINUE_LABEL = "Continue"
```

### Functions

#### `update_tray_icon_color(icon: pystray.Icon, is_tracking: bool) -> None`

Updates tray icon color based on tracking state.

```python
def update_tray_icon_color(icon: pystray.Icon, is_tracking: bool) -> None:
    """
    Update tray icon color based on tracking state.
    
    Args:
        icon: pystray Icon instance
        is_tracking: True for active (green), False for paused (default)
    
    Implementation:
        - Load original icon image
        - Apply green color overlay if is_tracking
        - Replace icon image
    """
```

#### `update_tray_menu(icon: pystray.Icon, is_tracking: bool) -> None`

Updates tray menu to reflect current tracking state.

```python
def update_tray_menu(icon: pystray.Icon, is_tracking: bool) -> None:
    """
    Rebuild tray menu with correct Pause/Continue label.
    
    Args:
        icon: pystray Icon instance
        is_tracking: True to show "Pause", False to show "Continue"
    
    Menu order:
        1. Open
        2. Settings
        3. ---separator---
        4. Pause/Continue
        5. ---separator---
        6. Exit
    """
```

## Entity: TrackingError

**Responsibility**: Record camera errors for user notification

**Location**: `detection.py` or new `error_tracking.py`

### Data Class

```python
@dataclass
class TrackingError:
    """Record of tracking failure for notification."""
    timestamp: datetime
    error_type: str  # "CAMERA_UNAVAILABLE", "PERMISSION_DENIED", "DEVICE_DISCONNECT"
    error_message: str
    recovery_action: str  # "AUTO_PAUSED"
```

### Camera Error Handling

When camera fails during active tracking:

1. **Catch exception** in detection loop
2. **Create TrackingError** record with timestamp, error type, message
3. **Call pause()** to stop loop and disable camera
4. **Notify UI** with tooltip showing error message
5. **Log to file** for audit trail
6. **Return to Paused state** awaiting user action

## Contracts

### State Synchronization Contract

**Invariant**: Menu label and tracking state MUST always be synchronized

```
is_tracking() = True  ⟷  Menu shows "Pause"
is_tracking() = False ⟷  Menu shows "Continue"
```

**Guarantee**: Every call to `pause()` or `resume()` triggers menu update.

### Color State Contract

**Invariant**: Tray icon color MUST reflect tracking state

```
is_tracking() = True  ⟷  Icon color = bright green
is_tracking() = False ⟷  Icon color = system default
```

**Guarantee**: Color updates within 100ms of state change.

### Camera Resource Contract

**Invariant**: Camera can only be open when tracking is active

```
is_tracking() = True  ⟹  camera.isOpened() = True
is_tracking() = False ⟹  camera.isOpened() = False (or None)
```

**Exception Handling**: On camera error, pause() is called to maintain contract.

### Idempotency Contract

**Invariant**: Calling pause/resume multiple times is safe

```
pause(); pause(); pause()  ⟹  Same result as single pause()
resume(); resume(); resume()  ⟹  Same result as single resume()
```

**Guarantee**: State machines handle redundant calls without errors or side effects.

## Validation Rules

### Pause Validation

- ✓ Can pause when `is_tracking() == True` (normal case)
- ✓ Can pause when `is_tracking() == False` (idempotent - no-op)
- ✓ Cannot pause if camera hardware unavailable (raises exception in resume)

### Resume Validation

- ✓ Can resume when `is_tracking() == False` (normal case)
- ✓ Can resume when `is_tracking() == True` (idempotent - no-op)
- ✗ Cannot resume if camera unavailable (raises CameraError - back to paused)

### Menu State Validation

- ✓ Menu label matches tracking state at all times
- ✓ Menu updates occur within 100ms of state change
- ✓ Menu is clickable in both Pause and Continue states

## Design Rationale

### Why Extend DetectionLoop?

- DetectionLoop already owns the tracking thread
- Pause/resume is a core lifecycle operation for the loop
- Keeps state encapsulated in one location
- Aligns with existing class responsibilities

### Why Simple Boolean State?

- Feature only has two meaningful states: tracking/not-tracking
- No intermediate states needed (transient operations complete quickly)
- Simpler than state machine library for this use case
- Easier to test and reason about

### Why Threading Lock?

- Detection loop runs in background thread
- Pause/resume can be called from any thread (UI, main, etc.)
- Lock protects `_is_tracking` and `_camera` access
- Existing pattern in codebase (already uses locks)

### Why Idempotent Operations?

- User might click Pause multiple times
- Network/signal delays might trigger redundant pause calls
- Auto-pause on error concurrent with user pause
- Safe-by-default: No harm in redundant calls
