"""Action panel for the main window with photo capture buttons.

Responsibilities:
- ActionPanel: Frame with Take photo button, delay checkbox, delay spinbox, Close button
- Capture callback to obtain raw frame
- Session-scoped last_save_dir for Save As... dialogs
- Integration with PhotoWindow for save operations
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

from catguard.ui.constants import ACTION_PANEL_HEIGHT

if TYPE_CHECKING:
    import tkinter as tk
    from catguard.config import Settings

logger = logging.getLogger(__name__)


class ActionPanel:
    """Action panel at the bottom of the main window.

    Args:
        parent: Parent tkinter widget (typically the main window).
        capture_callback: Callable that returns np.ndarray (raw frame).
        close_callback: Callable to minimize window to tray.
        settings: Settings model with photo_countdown_seconds, photo_image_quality.
    """

    def __init__(
        self,
        parent: "tk.Widget",
        capture_callback: Callable,
        close_callback: Callable,
        settings: Optional["Settings"] = None,
    ) -> None:
        import tkinter as tk

        self._tk = tk
        self._parent = parent
        self._capture_callback = capture_callback
        self._close_callback = close_callback
        self._settings = settings
        self._last_save_dir: Optional[str] = None

        # Frame container — pack_propagate(False) enforces exactly 40px height
        self._frame: tk.Frame = tk.Frame(parent, bg="lightgray", height=ACTION_PANEL_HEIGHT)
        self._frame.pack(side=tk.BOTTOM, fill=tk.X)
        self._frame.pack_propagate(False)

        # Left button frame
        self._left_frame: tk.Frame = tk.Frame(self._frame, bg="lightgray")
        self._left_frame.pack(side=tk.LEFT, padx=5, pady=5)

        # Take photo button
        self._take_photo_btn: tk.Button = tk.Button(
            self._left_frame,
            text="Take photo",
            command=self._on_take_photo_click,
            width=16,
        )
        self._take_photo_btn.pack(side=tk.LEFT, padx=2)

        # Delay checkbox (label: "Delay:")
        self._delay_var: tk.BooleanVar = tk.BooleanVar(value=False)
        self._delay_checkbox: tk.Checkbutton = tk.Checkbutton(
            self._left_frame,
            text="Delay:",
            variable=self._delay_var,
            bg="lightgray",
            command=self._on_delay_toggle,
        )
        self._delay_checkbox.pack(side=tk.LEFT, padx=(6, 2))

        # Delay spinbox (disabled until checkbox is checked)
        default_delay = settings.photo_countdown_seconds if settings is not None else 3
        self._delay_spinbox: tk.Spinbox = tk.Spinbox(
            self._left_frame,
            from_=1,
            to=60,
            width=4,
            state=tk.DISABLED,
        )
        self._delay_spinbox.config(state=tk.NORMAL)
        self._delay_spinbox.delete(0, tk.END)
        self._delay_spinbox.insert(0, str(default_delay))
        self._delay_spinbox.config(state=tk.DISABLED)
        self._delay_spinbox.pack(side=tk.LEFT, padx=2)

        # "sec" label after spinbox
        tk.Label(self._left_frame, text="sec", bg="lightgray").pack(side=tk.LEFT, padx=(0, 2))

        # Right button frame for Close
        self._right_frame: tk.Frame = tk.Frame(self._frame, bg="lightgray")
        self._right_frame.pack(side=tk.RIGHT, padx=5, pady=5)

        # Close button
        self._close_btn: tk.Button = tk.Button(
            self._right_frame,
            text="Close",
            command=self._on_close_click,
            width=12,
        )
        self._close_btn.pack(side=tk.RIGHT, padx=2)

        # Countdown state
        self._countdown_active = False
        self._countdown_remaining = 0

        logger.info("ActionPanel created")

    def _on_delay_toggle(self) -> None:
        """Enable or disable the spinbox based on the delay checkbox state."""
        if self._delay_var.get():
            self._delay_spinbox.config(state=self._tk.NORMAL)
        else:
            self._delay_spinbox.config(state=self._tk.DISABLED)

    def _on_take_photo_click(self) -> None:
        """Handle Take photo button click."""
        if self._countdown_active:
            logger.debug("Take photo: click suppressed during countdown")
            return

        if self._delay_var.get():
            try:
                delay = int(self._delay_spinbox.get())
            except (ValueError, self._tk.TclError):
                delay = self._settings.photo_countdown_seconds if self._settings else 3
            delay = max(1, delay)
            self._countdown_active = True
            self._countdown_remaining = delay
            self._start_countdown()
        else:
            self._capture_and_show_photo()

    def _start_countdown(self) -> None:
        """Run countdown timer, showing remaining seconds on the Take photo button."""
        if self._countdown_remaining > 0:
            self._take_photo_btn.config(text=str(self._countdown_remaining))
            self._countdown_remaining -= 1
            self._parent.after(1000, self._start_countdown)
        else:
            self._countdown_active = False
            self._take_photo_btn.config(text="Take photo")
            self._capture_and_show_photo()

    def _capture_and_show_photo(self) -> None:
        """Capture a frame, encode it as photo, and open PhotoWindow."""
        try:
            from datetime import datetime
            from catguard.photos import Photo, encode_photo
            from catguard.ui.photo_window import PhotoWindow
            import numpy as np

            if self._settings is None:
                logger.error("Settings not available for photo capture")
                return

            # Capture frame
            frame = self._capture_callback()
            if frame is None or not isinstance(frame, np.ndarray):
                logger.error("Capture callback returned invalid frame")
                return
            # Get frame dimensions before encoding
            frame_height, frame_width = frame.shape[:2]
            # Encode as JPEG
            quality = self._settings.photo_image_quality
            encoded = encode_photo(frame, quality)
            # Create Photo object
            photo = Photo(
                timestamp=datetime.now(),
                bytes=encoded,
                source="clean-capture",
            )
            # Open PhotoWindow with frame dimensions for proper sizing
            window = PhotoWindow(
                master=self._parent,
                photo=photo,
                settings=self._settings,
                last_save_dir=self._last_save_dir,
                on_save_dir_change=self._update_last_save_dir,
                frame_width=frame_width,
                frame_height=frame_height,
            )

            logger.info("Photo captured and PhotoWindow opened")
        except Exception as exc:
            logger.error("Failed to capture and show photo: %s", exc, exc_info=True)

    def _update_last_save_dir(self, path: str) -> None:
        """Update session-scoped last_save_dir from PhotoWindow."""
        self._last_save_dir = path
        logger.debug("Updated last_save_dir to %s", path)

    def _on_close_click(self) -> None:
        """Handle Close button click."""
        self._close_callback()
