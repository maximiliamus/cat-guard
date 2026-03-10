"""Main window for CatGuard — displays live capture with detection overlays.

Responsibilities:
- MainWindow: tkinter Toplevel showing the camera feed + YOLO bounding boxes/labels
- show_or_focus(): create once, raise on re-call
- update_frame(frame_bgr, detections): resize window to frame, render overlays
- _show_no_source_message(): fallback UI when no capture is available
- All tkinter calls MUST be dispatched on the main thread via root.after(0, ...)
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import numpy as np

from catguard.ui.action_panel import ActionPanel
from catguard.ui.constants import ACTION_PANEL_HEIGHT
from catguard.ui.geometry import load_win_geometry, save_win_geometry

if TYPE_CHECKING:
    import tkinter as tk

logger = logging.getLogger(__name__)


class MainWindow:
    """Live-capture main window with YOLO detection overlays.

    Create once via ``MainWindow(root)``; call ``show_or_focus()`` to make it
    visible.  Call ``update_frame(frame_bgr, detections)`` (on the main thread,
    via root.after) to push each new frame.
    """

    def __init__(self, root) -> None:
        import tkinter as tk_mod
        self._root = root
        self._tk = tk_mod
        self._window: tk_mod.Toplevel = tk_mod.Toplevel(root)
        self._window.title("CatGuard — Live View")
        self._window.withdraw()  # hidden until show_or_focus() called
        self._window.resizable(False, False)
        self._window.protocol("WM_DELETE_WINDOW", self._on_close)

        # Add ActionPanel FIRST (at bottom) so it takes priority in packing order
        self._action_panel = ActionPanel(
            parent=self._window,
            capture_callback=lambda: self._root.get_clean_frame(),
            close_callback=self.minimize_to_tray,
            settings=self._root.settings,
        )
        # Note: ActionPanel already calls pack() in its __init__, so don't pack again

        # Canvas fills remaining space above the action panel
        self._canvas: tk_mod.Canvas = tk_mod.Canvas(
            self._window, bg="black", highlightthickness=0
        )
        self._canvas.pack()

        self._photo_image = None   # holds reference to prevent GC
        self._canvas_image_id = None
        self._last_canvas_size = (0, 0)  # (cw, ch) — skip geometry/config when unchanged
        self._closed = False         # set to True in _on_close; guards update_frame
        self._on_close_extra = None  # optional callback invoked just before destroy
        self._alert_label = None     # non-None while an alert sound is playing

        # Restore saved window position (size is always set from the camera frame)
        _saved_geom = load_win_geometry("main_window")
        if _saved_geom:
            m = re.search(r'([+-]\d+[+-]\d+)$', _saved_geom)
            if m:
                self._window.geometry(m.group(1))
                logger.debug("MainWindow: restored position %s from disk.", m.group(1))

        # Store reference on root so callers can retrieve/check the instance
        root._main_window = self
        logger.info("MainWindow created.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_or_focus(self) -> None:
        """Make the window visible; if already visible, bring it to front."""
        self._root._main_window_visible = True
        self._window.deiconify()
        self._window.lift()
        self._window.focus_force()
        logger.info("MainWindow shown/focused.")

    def update_frame(self, frame_bgr: np.ndarray, detections) -> None:
        """Render *frame_bgr* with detection overlays on the canvas.

        Called via ``root.after(0, ...)`` from the DetectionLoop thread.
        Sizes the window to the frame on first call.
        """
        from catguard.ui.overlays import draw_alert_bar, draw_detections

        if self._closed:
            return

        try:
            h, w = frame_bgr.shape[:2]

            # Resize window and canvas to match the frame on first call and
            # whenever the camera resolution changes; skip the costly geometry
            # and config calls when dimensions are unchanged.
            sw = self._window.winfo_screenwidth()
            sh = self._window.winfo_screenheight()
            cw = min(w, sw)
            ch = min(h, sh - ACTION_PANEL_HEIGHT)  # Leave room for action panel
            if (cw, ch) != self._last_canvas_size:
                total_h = ch + ACTION_PANEL_HEIGHT  # Include action panel in window height
                self._window.geometry(f"{cw}x{total_h}")
                self._canvas.config(width=cw, height=ch)
                self._last_canvas_size = (cw, ch)
                logger.debug("MainWindow geometry: %dx%d (frame=%dx%d, action_panel=%d).", cw, total_h, w, h, ACTION_PANEL_HEIGHT)

            # Draw bounding-box overlays onto a copy of the frame
            annotated = draw_detections(frame_bgr, detections)

            # Draw alert-sound label bar if a sound is currently playing
            if self._alert_label is not None:
                draw_alert_bar(annotated, self._alert_label)

            # Convert BGR (OpenCV) → RGB (PIL) → PhotoImage (tkinter)
            from PIL import Image, ImageTk
            rgb = annotated[:, :, ::-1]  # BGR → RGB
            pil_img = Image.fromarray(rgb)
            photo = ImageTk.PhotoImage(image=pil_img)

            # Update canvas image
            if self._canvas_image_id is None:
                self._canvas_image_id = self._canvas.create_image(0, 0, anchor=self._tk.NW, image=photo)
            else:
                self._canvas.itemconfig(self._canvas_image_id, image=photo)

            self._photo_image = photo  # keep reference to prevent GC


        except Exception:
            logger.exception("Error updating MainWindow frame.")

    def set_alert_label(self, label) -> None:
        """Set or clear the alert-sound label shown in the live-view top bar.

        Pass the sound filename (str) when playback starts; pass None when it ends.
        Safe to call from any thread via root.after(0, ...).
        """
        self._alert_label = label

    def _update_no_detections_label(self, detections) -> None:
        """Show or hide a 'No detections' text overlay."""
        has_detections = bool(detections)

        tag = "no_detections_label"
        self._canvas.delete(tag)
        if not has_detections:
            self._canvas.create_text(
                10, 10,
                anchor=self._tk.NW,
                text="No detections",
                fill="white",
                font=("Helvetica", 12),
                tags=(tag,),
            )

    def minimize_to_tray(self) -> None:
        """Hide the window and minimize to tray (can be shown again later)."""
        logger.debug("MainWindow minimized to tray.")
        self._window.withdraw()
        self._root._main_window_visible = False

    def _on_close(self) -> None:
        """Destroy the window and clear the reference on root."""
        logger.info("MainWindow closed.")
        # Persist geometry before destroying so position/size survives restarts
        try:
            save_win_geometry("main_window", self._window.geometry())
        except Exception:
            pass
        self._root._main_window_visible = False
        self._closed = True  # guard: drop any update_frame callbacks still queued
        if self._on_close_extra is not None:
            try:
                self._on_close_extra()
            except Exception:
                logger.exception("Error in MainWindow close callback.")
        self._window.destroy()
        self._root._main_window = None

    def _show_no_source_message(self) -> None:
        """Replace canvas with a human-readable 'no capture source' message."""
        logger.warning("MainWindow: no capture source available.")
        self._canvas.pack_forget()

        frame = self._tk.Frame(self._window, bg="black")
        frame.pack(expand=True)

        self._tk.Label(
            frame,
            text="No capture source available.\nPlease check your camera connection.",
            fg="white",
            bg="black",
            font=("Helvetica", 13),
            justify=self._tk.CENTER,
        ).pack(pady=(20, 10))

        btn_frame = self._tk.Frame(frame, bg="black")
        btn_frame.pack()

        self._tk.Button(
            btn_frame,
            text="Retry",
            command=self._on_close,
        ).pack(side=self._tk.LEFT, padx=5)

        self._tk.Button(
            btn_frame,
            text="Close",
            command=self._on_close,
        ).pack(side=self._tk.LEFT, padx=5)

