# Quickstart: Implementation Guide

**Date**: 2026-03-03  
**Spec**: [spec.md](spec.md) | **Data Model**: [data-model.md](data-model.md)

## Implementation Overview

This guide provides a step-by-step implementation plan for adding pause/continue tracking control to CatGuard.

### Key Components

1. **DetectionLoop State** (`detection.py`)
   - Add `pause()`, `resume()`, `is_tracking()` methods
   - Add threading lock for state safety
   - Add error handling for camera failures

2. **Tray UI Updates** (`tray.py`)
   - Add menu reorganization (Open, Settings, Pause/Continue, Exit)
   - Add dynamic menu item label based on state
   - Add icon color updates (green=active, default=paused)

3. **Application Initialization** (`main.py`)
   - Set initial tracking state to active (auto-start)

## Phase 1: Detection Loop State Management

### File: `src/catguard/detection.py`

#### Step 1.1: Add State Variables to DetectionLoop

```python
class DetectionLoop(threading.Thread):
    def __init__(self, settings: Settings, ...):
        # Existing initialization
        
        # New: Pause/resume state
        self._is_tracking = False  # False initially, set to True on start
        self._tracking_lock = threading.Lock()  # Protect state
```

#### Step 1.2: Implement pause() Method

```python
def pause(self) -> bool:
    """Stop detection loop and disable camera."""
    with self._tracking_lock:
        if not self._is_tracking:
            return False  # Already paused
        
        self._is_tracking = False
        
        # Release camera if open
        if self._camera and hasattr(self._camera, 'release'):
            try:
                self._camera.release()
                self._camera = None
            except Exception as e:
                logger.warning("Camera release error: %s", e)
    
    # Signal loop to stop
    self._stop_event.set()
    return True
```

#### Step 1.3: Implement resume() Method

```python
def resume(self) -> bool:
    """Start detection loop and enable camera."""
    with self._tracking_lock:
        if self._is_tracking:
            return False  # Already running
        
        # Try to open camera
        try:
            camera_index = self._settings.camera_index
            self._camera = cv2.VideoCapture(camera_index)
            if not self._camera.isOpened():
                raise RuntimeError(f"Camera {camera_index} not available")
        except Exception as e:
            logger.error("Resume failed: %s", e)
            raise CameraError(str(e))
        
        # Set state to tracking
        self._is_tracking = True
        self._stop_event.clear()  # Allow loop to run
    
    return True
```

#### Step 1.4: Implement is_tracking() Method

```python
def is_tracking(self) -> bool:
    """Return whether tracking is currently active."""
    with self._tracking_lock:
        return self._is_tracking
```

#### Step 1.5: Add Auto-Pause on Camera Error

In the main detection loop (in `run()` method):

```python
def run(self) -> None:
    """Main detection thread."""
    while not self._stop_event.is_set():
        try:
            # Capture frame
            ret, frame_bgr = self._camera.read()
            
            if not ret:
                raise RuntimeError("Camera read failed")
            
            # Process frame...
            
        except Exception as e:
            logger.error("Detection error: %s", e)
            
            # Auto-pause on camera error
            self.pause()
            
            # Notify UI (if callback registered)
            if hasattr(self, '_on_error_callback') and self._on_error_callback:
                self._on_error_callback(str(e))
            
            break  # Exit detection loop
```

#### Step 1.6: Update Initialization

In `DetectionLoop.__init__()`, set initial state:

```python
def __init__(self, settings: Settings, ...):
    # Existing code...
    self._is_tracking = False  # Initially paused
    self._tracking_lock = threading.Lock()
    self._on_error_callback = None  # For error notifications
```

---

## Phase 2: Tray UI Updates

### File: `src/catguard/tray.py`

#### Step 2.1: Add Color Constants

```python
# At module level
TRACKING_ACTIVE_COLOR = (0, 255, 0)  # Bright green RGB
TRACKING_PAUSED_COLOR = None  # System default (no overlay)

# Debounce rapid updates
_last_color_update = None
_last_menu_update = None
_ui_update_debounce_ms = 100
```

#### Step 2.2: Add update_tray_icon_color() Function

```python
def update_tray_icon_color(icon: pystray.Icon, is_tracking: bool) -> None:
    """Update tray icon color based on tracking state."""
    global _last_color_update
    
    # Debounce rapid updates
    import time
    now = time.time() * 1000  # ms
    if _last_color_update and now - _last_color_update < _ui_update_debounce_ms:
        return
    _last_color_update = now
    
    try:
        # Load original icon
        if _ICON_PATH.exists():
            img = Image.open(_ICON_PATH).convert("RGBA")
        else:
            logger.warning("Icon not found")
            return
        
        # Apply green overlay if tracking
        if is_tracking:
            # Create green overlay
            overlay = Image.new("RGBA", img.size, (0, 255, 0, 128))
            img = Image.alpha_composite(img, overlay)
        
        # Update icon
        icon.icon = img
        logger.debug("Icon color updated: %s", "green" if is_tracking else "default")
        
    except Exception as e:
        logger.warning("Icon color update failed: %s", e)
```

#### Step 2.3: Add update_tray_menu() Function

```python
def update_tray_menu(
    icon: pystray.Icon,
    is_tracking: bool,
    on_pause_clicked,
    on_open_clicked,
    on_settings_clicked,
    on_exit_clicked,
) -> None:
    """Rebuild tray menu with updated Pause/Continue label."""
    global _last_menu_update
    
    # Debounce rapid updates
    import time
    now = time.time() * 1000  # ms
    if _last_menu_update and now - _last_menu_update < _ui_update_debounce_ms:
        return
    _last_menu_update = now
    
    try:
        # Pause/Continue label based on state
        pause_continue_label = "Pause" if is_tracking else "Continue"
        
        # Build menu in correct order
        menu = pystray.Menu(
            pystray.MenuItem("Open", on_open_clicked),
            pystray.MenuItem("Settings\u2026", on_settings_clicked),
            pystray.MenuItem(None),  # Separator
            pystray.MenuItem(pause_continue_label, on_pause_clicked),
            pystray.MenuItem(None),  # Separator
            pystray.MenuItem("Exit", on_exit_clicked),
        )
        
        # Replace menu
        icon.menu = menu
        logger.debug("Tray menu updated: %s", pause_continue_label)
        
    except Exception as e:
        logger.warning("Menu update failed: %s", e)
```

#### Step 2.4: Update build_tray_icon()

```python
def build_tray_icon(
    root,
    stop_event: threading.Event,
    settings: Settings,
    on_settings_saved: Callable,
    detection_loop,
) -> pystray.Icon:
    """Build tray icon with pause/continue control."""
    
    image = _load_icon()
    
    # Create callbacks
    def on_open_clicked(icon, item):
        logger.info("Open clicked")
        root.after(0, lambda: _ensure_main_window(root, detection_loop))
    
    def on_settings_clicked(icon, item):
        logger.info("Settings clicked")
        _on_settings(root, settings, on_settings_saved)
    
    def on_pause_continue_clicked(icon, item):
        """Toggle between pause and continue."""
        logger.info("Pause/Continue clicked")
        
        if detection_loop.is_tracking():
            # Pause
            detection_loop.pause()
            # Update UI
            update_tray_icon_color(icon, False)
            update_tray_menu(
                icon, False,
                on_pause_continue_clicked,
                on_open_clicked,
                on_settings_clicked,
                on_exit_clicked,
            )
        else:
            # Resume
            try:
                detection_loop.resume()
                # Update UI
                update_tray_icon_color(icon, True)
                update_tray_menu(
                    icon, True,
                    on_pause_continue_clicked,
                    on_open_clicked,
                    on_settings_clicked,
                    on_exit_clicked,
                )
            except Exception as e:
                logger.error("Resume failed: %s", e)
                # Show error tooltip
                notify_error(icon, f"Camera unavailable: {e}")
    
    def on_exit_clicked(icon, item):
        logger.info("Exit clicked")
        _on_exit(icon, root, stop_event)
    
    # Build initial menu (assuming auto-start = tracking)
    menu = pystray.Menu(
        pystray.MenuItem("Open", on_open_clicked),
        pystray.MenuItem("Settings\u2026", on_settings_clicked),
        pystray.MenuItem(None),  # Separator
        pystray.MenuItem("Pause", on_pause_continue_clicked),  # Initial label
        pystray.MenuItem(None),  # Separator
        pystray.MenuItem("Exit", on_exit_clicked),
    )
    
    icon = pystray.Icon("CatGuard", image, "CatGuard", menu)
    
    # Set initial color (green for auto-start)
    update_tray_icon_color(icon, True)
    
    logger.info("Tray icon built with pause/continue control")
    return icon
```

---

## Phase 3: Application Initialization

### File: `src/catguard/main.py`

#### Step 3.1: Auto-Start Tracking

In `main()` function, after creating `DetectionLoop`:

```python
def main():
    # Existing setup code...
    
    detection_loop = DetectionLoop(settings)
    
    # Auto-start tracking (from clarification: Option A)
    try:
        detection_loop.resume()  # Start tracking immediately
        logger.info("Tracking started on app init")
    except Exception as e:
        logger.warning("Could not start tracking: %s", e)
        # App continues, user can click Continue to retry
    
    # Build tray icon (now with green color, Pause label)
    icon = build_tray_icon(
        root,
        stop_event,
        settings,
        on_settings_saved_callback,
        detection_loop,
    )
    
    # Rest of initialization...
```

---

## Phase 4: Testing

### Unit Tests: `tests/unit/test_detection.py`

```python
def test_pause_stops_tracking(mock_camera):
    """Verify pause() stops tracking and disables camera."""
    loop = DetectionLoop(settings)
    loop._is_tracking = True
    loop._camera = mock_camera
    
    result = loop.pause()
    
    assert result is True
    assert loop.is_tracking() is False
    mock_camera.release.assert_called_once()

def test_resume_starts_tracking(mock_camera):
    """Verify resume() starts tracking and opens camera."""
    loop = DetectionLoop(settings)
    loop._is_tracking = False
    
    result = loop.resume()
    
    assert result is True
    assert loop.is_tracking() is True

def test_pause_idempotent():
    """Verify calling pause() twice is safe."""
    loop = DetectionLoop(settings)
    loop._is_tracking = True
    
    result1 = loop.pause()
    result2 = loop.pause()
    
    assert result1 is True
    assert result2 is False
```

### Integration Tests: `tests/integration/test_pause_resume.py`

```python
def test_pause_resume_cycle(tray_icon, detection_loop):
    """Full pause/resume workflow."""
    # Start with tracking active
    assert detection_loop.is_tracking() is True
    
    # Pause
    detection_loop.pause()
    assert detection_loop.is_tracking() is False
    
    # Resume
    detection_loop.resume()
    assert detection_loop.is_tracking() is True
```

---

## Implementation Checklist

- [ ] Add state variables to `DetectionLoop.__init__()`
- [ ] Implement `pause()` method
- [ ] Implement `resume()` method
- [ ] Implement `is_tracking()` method
- [ ] Add error handling in detection loop (auto-pause)
- [ ] Add color update function to `tray.py`
- [ ] Add menu update function to `tray.py`
- [ ] Update `build_tray_icon()` with pause/continue handler
- [ ] Update menu order (Open, Settings, Pause/Continue, Exit)
- [ ] Add auto-start in `main.py`
- [ ] Write unit tests for pause/resume
- [ ] Write integration tests for menu interaction
- [ ] Write tests for error scenarios
- [ ] Test on Windows, Linux, macOS
- [ ] Verify performance targets (<500ms pause/resume, <100ms UI updates)

---

## Performance Validation

After implementation, verify:

- **Pause latency**: Time from menu click to loop stopped and camera disabled
  - Target: ≤500ms
  - Measure: Add timing logs in pause() and detection loop

- **Resume latency**: Time from menu click to loop restarted and camera enabled
  - Target: ≤500ms
  - Measure: Add timing logs in resume() and camera open

- **UI update latency**: Time from state change to icon/menu update visible
  - Target: <100ms
  - Measure: Add timing logs in update_tray_icon_color() and update_tray_menu()

- **State consistency**: Menu label and icon color always reflect tracking state
  - Target: 100%
  - Measure: Unit tests verify invariants

---

## Common Issues & Solutions

### Issue: Icon color not updating on Linux
- **Cause**: AppIndicator backend caching or D-Bus delay
- **Solution**: Force icon reload via `icon.update_menu()` after color change
- **Reference**: Check platform-specific pystray documentation

### Issue: Menu rebuild causes flicker
- **Cause**: pystray requirement to rebuild entire menu
- **Solution**: Debounce rapid updates (already implemented in code above)
- **Alternative**: Accept brief flicker as acceptable UX

### Issue: Camera won't reopen after pause
- **Cause**: Device driver holding exclusive lock
- **Solution**: Add retry logic in resume() with exponential backoff
- **Reference**: See research.md for error handling strategy

### Issue: Rapid pause/continue creates race condition
- **Cause**: Threading contention between UI clicks and detection loop
- **Solution**: Use locks (already implemented in code above)
- **Testing**: Stress test with rapid clicks

---

## Debugging Tips

1. **Enable debug logging**:
   ```python
   logging.getLogger("catguard.detection").setLevel(logging.DEBUG)
   logging.getLogger("catguard.tray").setLevel(logging.DEBUG)
   ```

2. **Monitor state transitions**:
   - Add log statement in pause/resume before and after lock
   - Verify lock is acquired/released

3. **Profile timing**:
   ```python
   import time
   start = time.time()
   detection_loop.pause()
   elapsed_ms = (time.time() - start) * 1000
   logger.info("Pause took %.1f ms", elapsed_ms)
   ```

4. **Test platform-specific icon rendering**:
   - Windows: Check temporary .ico file creation
   - Linux: Monitor D-Bus traffic with `dbus-monitor`
   - macOS: Use Quartz debugger

