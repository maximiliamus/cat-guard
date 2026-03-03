# Contract: Tracking State Machine

**Location**: `detection.py::DetectionLoop`  
**Responsibility**: Define and maintain tracking state lifecycle

## Public Interface

### Methods

#### `pause() -> bool`

**Purpose**: Stop tracking loop and disable camera

**Signature**:
```python
def pause(self) -> bool: ...
```

**Input**:
- None (state-based, called on demand)

**Output**:
- `bool`: `True` if pause executed; `False` if already paused

**Precondition**:
- None (idempotent - always safe to call)

**Postcondition**:
- `is_tracking()` returns `False`
- Detection loop thread stops
- Camera is released/disabled
- State is immediately Paused

**Side Effects**:
- Sets `_stop_event` to signal detection thread
- Releases camera resource if open
- May take up to 500ms to complete (performance guarantee)

**Error Handling**:
- Swallows camera release errors (non-critical)
- Never throws exception to caller

**Thread Safety**:
- Protected by `_tracking_lock`
- Safe to call from any thread simultaneously
- No race conditions or deadlocks

**Idempotency**:
- Safe to call multiple times
- Second call returns `False` (no-op)

---

#### `resume() -> bool`

**Purpose**: Start tracking loop and enable camera

**Signature**:
```python
def resume(self) -> bool: ...
```

**Input**:
- None (state-based, called on demand)

**Output**:
- `bool`: `True` if resume executed; `False` if already active

**Precondition**:
- None (idempotent - always safe to call)

**Postcondition**:
- `is_tracking()` returns `True`
- Detection loop thread restarts
- Camera is opened/enabled
- State is immediately Active

**Side Effects**:
- Clears `_stop_event` to allow detection thread to run
- Opens camera device (may take 100-200ms)
- Returns after state is set, not after thread fully resumes

**Error Handling**:
- Raises `CameraError` if camera cannot be opened
- On error: state rolls back to Paused, error logged
- Caller responsibility to handle and notify user

**Thread Safety**:
- Protected by `_tracking_lock`
- Safe to call from any thread simultaneously

**Idempotency**:
- Safe to call multiple times
- Second call returns `False` (no-op) without opening camera again

**Performance**:
- State change: <50ms
- Camera open: 100-200ms typical, may vary by device
- Total: ~500ms target (acceptable per spec)

---

#### `is_tracking() -> bool`

**Purpose**: Query current tracking state

**Signature**:
```python
def is_tracking(self) -> bool: ...
```

**Input**:
- None (read-only query)

**Output**:
- `bool`: `True` if tracking active; `False` if paused/stopped

**Precondition**:
- None (always safe to call)

**Postcondition**:
- No state change
- Returns accurate current state

**Side Effects**:
- None (read-only)

**Error Handling**:
- Never throws exception
- Returns last known state (safe fallback)

**Thread Safety**:
- Read lock (minimal contention)
- Safe to call concurrently with pause/resume

**Performance**:
- O(1) time complexity
- <1ms response time

---

## State Invariants

### Invariant 1: Loop-Camera Consistency

```
is_tracking() = True  ⟹  detection_loop is running AND camera is open
is_tracking() = False ⟹  detection_loop is not running AND camera is closed
```

**Enforcement**:
- Both operations (loop start/stop and camera open/close) happen together
- Lock prevents interleaving
- Atomic with respect to external observers

### Invariant 2: Thread Safety

```
All access to _is_tracking guarded by _tracking_lock
All access to _camera guarded by _tracking_lock
```

**Enforcement**:
- Lock acquired before any state read/write
- No direct field access outside lock

### Invariant 3: Idempotency

```
pause(); pause() has same effect as pause()
resume(); resume() has same effect as resume()
```

**Enforcement**:
- State check before operation
- Return value indicates operation was performed
- Redundant calls return False and do nothing

### Invariant 4: Atomicity

```
State change and side effects (loop start/stop, camera open/close) happen together
No partial states exposed to concurrent threads
```

**Enforcement**:
- Operations complete before lock is released
- Observers see complete state transitions only

## Error Handling

### Camera Unavailable

**When**: Resume called but camera cannot be opened

**Behavior**:
- `resume()` raises `CameraError`
- State rolls back to Paused
- `is_tracking()` returns `False`
- Error is logged

**Caller Responsibility**:
- Catch exception
- Notify user via tray tooltip/notification
- Retry on user action or timer

### Camera Disconnect During Tracking

**When**: Camera is released while detection loop running

**Behavior**:
- Detection loop catches `cv2.error`
- Calls `pause()` automatically
- Logs error with timestamp
- Updates tray icon to paused + error tooltip

**Example Scenario**:
```
Active tracking → USB camera unplugged
→ cv2.VideoCapture().read() fails
→ Detection loop calls pause()
→ Tray icon changes to default color
→ User sees tooltip on hover: "Camera unavailable"
→ User can plug camera back in and click Continue
```

### Thread Contention

**When**: Multiple threads call pause/resume simultaneously

**Behavior**:
- Lock serializes operations
- First thread succeeds, sets state
- Subsequent threads see already-changed state
- All threads exit cleanly with correct return value

**Example**:
```
Thread A: pause() acquires lock, stops loop → returns True
Thread B: pause() waits for lock, acquires lock, sees already paused → returns False
```

## Performance Guarantees

| Operation | Latency | Notes |
|-----------|---------|-------|
| `is_tracking()` | <1ms | Read-only, minimal lock contention |
| `pause()` state change | <50ms | Lock + flag change, no I/O |
| `pause()` camera release | <100ms | Depends on device driver |
| `pause()` total | ≤500ms | Spec compliance target |
| `resume()` state change | <50ms | Lock + flag change, no I/O |
| `resume()` camera open | 100-200ms | Device-dependent, typical range |
| `resume()` total | ≤500ms | Spec compliance target |
| Tray UI update (color) | <100ms | Triggered by state change |
| Tray UI update (menu) | <100ms | Triggered by state change |

## Testing Requirements

### Unit Tests

- `test_pause_when_tracking()` - pause from active state
- `test_pause_when_paused()` - pause from paused state (idempotent)
- `test_resume_when_paused()` - resume from paused state
- `test_resume_when_tracking()` - resume from active state (idempotent)
- `test_is_tracking_active()` - query when active
- `test_is_tracking_paused()` - query when paused
- `test_concurrent_pause_resume()` - thread safety under load
- `test_camera_error_on_resume()` - error handling

### Integration Tests

- `test_pause_stops_detection_frames()` - verify no frames processed
- `test_resume_restarts_detection()` - verify frames resume
- `test_state_and_camera_consistency()` - verify invariant 1
- `test_tray_color_updates_with_state()` - UI integration

### Contract Verification

- State invariants checked after every operation
- Lock contention profiled
- Performance measured against latency targets
