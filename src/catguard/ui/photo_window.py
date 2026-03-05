"""Photo viewing and saving window for CatGuard.

Responsibilities:
- PhotoWindow: Toplevel window showing a captured photo with Save, Save As, Close buttons
- Display photo as PIL Image on a Canvas or Label
- Handle Save, Save As..., and Close button actions
- Session-scoped last_save_dir tracking (shared across PhotoWindow instances)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from catguard.ui.constants import ACTION_PANEL_HEIGHT

if TYPE_CHECKING:
    import tkinter as tk
    from catguard.config import Settings
    from catguard.photos import Photo

logger = logging.getLogger(__name__)


class PhotoWindow:
    """A window for viewing and saving captured photos.
    
    Args:
        master: Parent tkinter root or Toplevel.
        photo: Photo object containing timestamp, bytes, source.
        settings: Settings model with photos_directory, photo_image_format.
        last_save_dir: Session-scoped last directory used in Save As dialog.
        on_save_dir_change: Callback to update session-scoped last_save_dir.
        frame_width: Width of the captured frame (for geometry sizing).
        frame_height: Height of the captured frame (for geometry sizing).
    """
    
    def __init__(
        self,
        master: "tk.Widget",
        photo: "Photo",
        settings: Optional["Settings"] = None,
        last_save_dir: Optional[str] = None,
        on_save_dir_change: Optional[Callable[[str], None]] = None,
        frame_width: Optional[int] = None,
        frame_height: Optional[int] = None,
    ) -> None:
        import tkinter as tk
        
        self._tk = tk
        self._PIL_Image = None
        self._PIL_ImageTk = None
        try:
            from PIL import Image, ImageTk
            self._PIL_Image = Image
            self._PIL_ImageTk = ImageTk
        except ImportError:
            logger.warning("PIL not available; using placeholder for photo display")
        
        self._master = master
        self._photo = photo
        self._settings = settings
        self._last_save_dir = last_save_dir
        self._on_save_dir_change = on_save_dir_change or (lambda x: None)
        
        # Create Toplevel window
        self._window: tk.Toplevel = tk.Toplevel(master)
        self._window.title(f"Photo — {photo.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        self._window.resizable(False, False)
        self._window.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Set window geometry to match MainWindow size (accounting for action panel)
        # Use frame dimensions if provided; otherwise use reasonable defaults
        if frame_width is not None and frame_height is not None:
            sw = self._window.winfo_screenwidth()
            sh = self._window.winfo_screenheight()
            # Clamp only if needed, otherwise use full frame size
            cw = frame_width if frame_width <= sw else sw
            ch = frame_height if frame_height <= (sh - ACTION_PANEL_HEIGHT) else (sh - ACTION_PANEL_HEIGHT)
            total_h = ch + ACTION_PANEL_HEIGHT
            self._window.geometry(f"{cw}x{total_h}")
        
        # Button frame — must match ActionPanel height for consistency
        # Pack FIRST (at bottom) so it anchors correctly before display_frame expands
        self._button_frame: tk.Frame = tk.Frame(self._window, bg="lightgray", height=ACTION_PANEL_HEIGHT)
        self._button_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self._button_frame.pack_propagate(False)  # Enforce fixed height regardless of children
        
        # Left button frame for Save and Save As...
        self._left_frame: tk.Frame = tk.Frame(self._button_frame, bg="lightgray")
        self._left_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Save button
        self._save_btn: tk.Button = tk.Button(
            self._left_frame,
            text="Save",
            command=self._on_save_click,
            width=12,
        )
        self._save_btn.pack(side=tk.LEFT, padx=2)
        
        # Save As... button
        self._save_as_btn: tk.Button = tk.Button(
            self._left_frame,
            text="Save As...",
            command=self._on_save_as_click,
            width=12,
        )
        self._save_as_btn.pack(side=tk.LEFT, padx=2)
        
        # Right button frame for Close
        self._right_frame: tk.Frame = tk.Frame(self._button_frame, bg="lightgray")
        self._right_frame.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Close button
        self._close_btn: tk.Button = tk.Button(
            self._right_frame,
            text="Close",
            command=self._on_close_click,
            width=12,
        )
        self._close_btn.pack(side=tk.RIGHT, padx=2)
        
        # Display photo on a Canvas — match MainWindow: no padding, explicit size
        self._canvas: tk.Canvas = tk.Canvas(self._window, bg="black", highlightthickness=0)
        self._canvas.pack()
        self._status_canvas_id = None  # canvas text overlay for status messages
        self._canvas_image_id = None
        self._photo_image = None
        self._display_photo(photo, frame_width, frame_height)
        
        logger.info("PhotoWindow created for photo at %s", photo.timestamp)
    
    def _display_photo(self, photo: "Photo", frame_width: int = None, frame_height: int = None) -> None:
        """Decode photo bytes and display on canvas at original size."""
        try:
            if self._PIL_Image is None:
                # PIL not available, show placeholder
                self._canvas.create_text(
                    10, 10,
                    anchor=self._tk.NW,
                    text=f"Photo taken at {photo.timestamp.strftime('%H:%M:%S')}\n({len(photo.bytes)} bytes)",
                    fill="white",
                    font=(None, 12),
                )
                return
            import io
            img = self._PIL_Image.open(io.BytesIO(photo.bytes))
            img_w, img_h = img.size
            # If decoded image size does not match frame, resize to match
            if frame_width and frame_height and (img_w != frame_width or img_h != frame_height):
                logger.warning("PhotoWindow: Resizing photo from %dx%d to %dx%d to match viewport", img_w, img_h, frame_width, frame_height)
                img = img.resize((frame_width, frame_height), self._PIL_Image.Resampling.LANCZOS)
                img_w, img_h = img.size
            # Set canvas size to match frame
            if frame_width and frame_height:
                self._canvas.config(width=frame_width, height=frame_height)
            else:
                self._canvas.config(width=img_w, height=img_h)
            photo_tk = self._PIL_ImageTk.PhotoImage(img)
            if self._canvas_image_id is None:
                self._canvas_image_id = self._canvas.create_image(0, 0, anchor=self._tk.NW, image=photo_tk)
            else:
                self._canvas.itemconfig(self._canvas_image_id, image=photo_tk)
            self._photo_image = photo_tk  # Keep reference
        except Exception as exc:
            logger.error("Failed to display photo: %s", exc)
            self._canvas.create_text(
                10, 10,
                anchor=self._tk.NW,
                text=f"Error displaying photo: {exc}",
                fill="red",
                font=(None, 12),
            )
    
    def _on_save_click(self) -> None:
        """Handle Save button click."""
        if self._settings is None:
            self._set_status("Error: Settings not available", "red")
            return
        
        try:
            from catguard.photos import build_photo_filepath
            
            # Build filepath using configured directory
            root_path = Path(self._settings.photos_directory)
            ext = self._settings.photo_image_format or "jpg"
            filepath = build_photo_filepath(root_path, self._photo.timestamp, ext)
            
            # Ensure parent directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # Write photo bytes
            filepath.write_bytes(self._photo.bytes)
            logger.debug("Photo saved to %s", filepath)
            
            # Show success feedback
            self._save_btn.config(text="Saved ✓")
            self._set_status(f"Saved to {filepath.name}", "green")
            
            # Restore button label after 2 seconds
            self._window.after(2000, self._restore_save_button_label)
        except Exception as exc:
            logger.error("Photo save failed: %s", exc, exc_info=True)
            self._set_status(f"Save failed — {exc}", "red")
    
    def _on_save_as_click(self) -> None:
        """Handle Save As... button click."""
        import tkinter.filedialog as filedialog
        
        try:
            # Prepare initial filename
            filename = self._photo.timestamp.strftime("catguard_%Y%m%d_%H%M%S.jpg")
            
            # Open file save dialog
            filepath = filedialog.asksaveasfilename(
                initialdir=self._last_save_dir,
                initialfile=filename,
                defaultextension=".jpg",
                filetypes=[("JPEG", "*.jpg"), ("All Files", "*.*")],
                title="Save Photo As...",
            )
            
            if not filepath:
                # User cancelled
                logger.debug("Save As dialog cancelled")
                return
            
            # Normalize path and reject .. components for security (NFR-SEC-001)
            filepath = os.path.normpath(filepath)
            if ".." in filepath:
                self._set_status("Invalid path: contains '..'", "red")
                return
            
            filepath_obj = Path(filepath)
            
            # Write photo bytes
            filepath_obj.write_bytes(self._photo.bytes)
            logger.debug("Photo saved via Save As to %s", filepath_obj)
            
            # Update session-scoped last_save_dir
            parent_dir = str(filepath_obj.parent)
            self._last_save_dir = parent_dir
            self._on_save_dir_change(parent_dir)
            
            # Show success feedback
            self._set_status(f"Saved to {filepath_obj.name}", "green")
        except Exception as exc:
            logger.error("Save As failed: %s", exc, exc_info=True)
            self._set_status(f"Save failed — {exc}", "red")
    
    def _on_close_click(self) -> None:
        """Handle Close button click."""
        self._on_close()
    
    def _on_close(self) -> None:
        """Destroy window and clear photo reference (FR-008)."""
        logger.info("PhotoWindow closing")
        self._photo = None  # Release reference to allow GC
        self._window.destroy()
    
    def _restore_save_button_label(self) -> None:
        """Restore Save button label after feedback display."""
        self._save_btn.config(text="Save")

    def _clear_status(self) -> None:
        """Remove the status overlay text from the canvas."""
        if self._status_canvas_id is not None:
            try:
                self._canvas.delete(self._status_canvas_id)
            except Exception:
                pass
            self._status_canvas_id = None
    
    def _set_status(self, message: str, color: str = "black") -> None:
        """Display status feedback as a canvas overlay so it takes no extra layout space."""
        if self._status_canvas_id is not None:
            self._canvas.delete(self._status_canvas_id)
            self._status_canvas_id = None
        if message:
            self._status_canvas_id = self._canvas.create_text(
                8, 8,
                anchor=self._tk.NW,
                text=message,
                fill=color,
                font=(None, 10, "bold"),
            )
            # Auto-clear after 3 seconds
            self._window.after(3000, self._clear_status)
