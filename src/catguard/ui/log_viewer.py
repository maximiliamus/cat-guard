"""Log viewer window for CatGuard.

Provides open_log_viewer(root, settings) — a singleton tkinter Toplevel that
displays catguard.log entries in reverse-chronological order, with search and
clipboard-copy support.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

# Matches the start of a standard log entry: "2026-03-08 22:09:40,123 [LEVEL] ..."
_LOG_ENTRY_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
# Captures the logger name from a log entry header
_LEVEL_RE = re.compile(r"\[(?:DEBUG|INFO|WARNING|ERROR|CRITICAL)\] (\S+):")

from catguard.config import Settings
from catguard.ui.geometry import load_win_geometry, save_win_geometry

logger = logging.getLogger(__name__)

_LOG_FILENAME = "catguard.log"

# Mutable cell — persists saved geometry within a process
_log_viewer_geometry: list[str] = [load_win_geometry("log_viewer")]


def _flush_log_handler() -> None:
    """Flush the active file handler so all buffered writes reach disk before reading."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            try:
                handler.flush()
            except Exception:
                pass


def _extract_loggers(entries: list[str]) -> list[str]:
    """Return sorted unique logger names found in *entries*."""
    loggers: set[str] = set()
    for entry in entries:
        m = _LEVEL_RE.search(entry)
        if m:
            loggers.add(m.group(1))
    return sorted(loggers)


def _read_log_lines(settings: Settings) -> list[str]:
    """Read log entries from the log file, newest-first.

    Multi-line entries (e.g. tracebacks) are kept together as a single string
    so that reversing operates at the entry level, not the line level.
    """
    _flush_log_handler()
    log_path = Path(settings.logs_directory) / _LOG_FILENAME
    if not log_path.is_file():
        return []
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.exception("Failed to read log file: %s", log_path)
        return []

    entries: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if _LOG_ENTRY_RE.match(line):
            if current:
                entries.append("\n".join(current))
            current = [line]
        elif line.strip():
            current.append(line)
    if current:
        entries.append("\n".join(current))

    return entries


def _do_refresh(
    settings: Settings,
    text_widget,
    *,
    scroll_to_end: bool = False,
    logger_combobox=None,
    logger_var=None,
) -> None:
    """Reload the log file, apply logger filter, and populate *text_widget*."""
    ypos = text_widget.yview()[0]
    try:
        sel_ranges = text_widget.tag_ranges("sel")
        sel_start = str(sel_ranges[0]) if sel_ranges else None
        sel_end = str(sel_ranges[1]) if sel_ranges else None
    except Exception:
        sel_start = sel_end = None

    lines = _read_log_lines(settings)

    if logger_combobox is not None:
        loggers = _extract_loggers(lines)
        new_values = ["All"] + loggers
        current = logger_combobox.get()
        logger_combobox["values"] = new_values
        if current not in new_values:
            logger_combobox.set("All")

    if logger_var is not None:
        logger_name = logger_var.get().strip()
        if logger_name and logger_name != "All":
            lines = [e for e in lines if (logger_name + ":") in e]

    text_widget.delete("1.0", "end")
    if lines:
        text_widget.insert("end", "\n".join(lines))
    else:
        text_widget.insert("end", "(no log entries)")

    if sel_start and sel_end:
        try:
            text_widget.tag_add("sel", sel_start, sel_end)
        except Exception:
            pass

    if scroll_to_end:
        text_widget.yview_moveto(1.0)
    else:
        text_widget.yview_moveto(ypos)


def _find_match_positions(term: str, content: str) -> list[tuple[str, str]]:
    """Return (start_pos, end_pos) tkinter index pairs for every case-insensitive match."""
    term_lower = term.lower()
    content_lower = content.lower()
    matches: list[tuple[str, str]] = []
    start_idx = 0
    while True:
        idx = content_lower.find(term_lower, start_idx)
        if idx == -1:
            break
        line = content[:idx].count("\n") + 1
        col = idx - (content[:idx].rfind("\n") + 1)
        matches.append((f"{line}.{col}", f"{line}.{col + len(term)}"))
        start_idx = idx + len(term)
    return matches


def _do_highlight(search_var, text_widget, *, scroll_to_match: bool = True) -> None:
    """Find *search_var* text in *text_widget* and highlight all occurrences in yellow."""
    term = search_var.get().strip()
    text_widget.tag_remove("highlight", "1.0", "end")
    if not term:
        return
    text_widget.tag_configure("highlight", background="yellow", foreground="black")
    content = text_widget.get("1.0", "end-1c")
    matches = _find_match_positions(term, content)
    for s, e in matches:
        text_widget.tag_add("highlight", s, e)
    if matches and scroll_to_match:
        text_widget.see(matches[0][0])



def _do_copy(text_widget, root) -> None:
    """Copy selected text (if any) or all visible text to the system clipboard."""
    try:
        sel_ranges = text_widget.tag_ranges("sel")
        if sel_ranges:
            content = text_widget.get(sel_ranges[0], sel_ranges[1])
        else:
            content = text_widget.get("1.0", "end").strip()
        if content:
            root.clipboard_clear()
            root.clipboard_append(content)
    except Exception:
        pass


def open_log_viewer(root, settings: Settings) -> None:
    """Open the Log Viewer window (singleton per root).

    If already open, raises the existing window instead of creating a second one.
    """
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        logger.error("tkinter not available; cannot open Log Viewer.")
        return

    from catguard.tray import apply_app_icon

    # Singleton guard
    if getattr(root, "_log_viewer_open", False):
        try:
            existing = getattr(root, "_log_viewer_window", None)
            if existing is not None and existing.winfo_exists():
                existing.lift()
                return
        except Exception:
            logger.exception("Failed to raise existing log viewer")

    win = tk.Toplevel(root)
    apply_app_icon(win)
    root._log_viewer_open = True
    root._log_viewer_window = win
    win.title("CatGuard — Logs")
    win.resizable(True, True)
    win.minsize(600, 400)

    # Restore saved geometry
    saved = _log_viewer_geometry[0]
    if saved:
        try:
            win.geometry(saved)
        except Exception:
            pass

    def _on_close():
        _log_viewer_geometry[0] = win.geometry()
        save_win_geometry("log_viewer", win.geometry())
        root._log_viewer_open = False
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", _on_close)

    # ------------------------------------------------------------------
    # Toolbar — all controls in a single row
    # ------------------------------------------------------------------
    toolbar = tk.Frame(win)
    toolbar.pack(side="top", fill="x", padx=8, pady=(8, 2))

    auto_var = tk.BooleanVar(value=False)
    tk.Checkbutton(toolbar, text="Auto", variable=auto_var, command=lambda: _on_auto_toggle()).pack(side="right", padx=(0, 2))
    tk.Button(
        toolbar,
        text="Refresh",
        command=lambda: _on_refresh(),
    ).pack(side="right", padx=2)

    tk.Button(
        toolbar,
        text="Copy to Clipboard",
        command=lambda: _do_copy(text_widget, win),
    ).pack(side="right", padx=2)

    tk.Label(toolbar, text="Logger:").pack(side="left")
    logger_var = tk.StringVar(value="All")
    logger_combobox = ttk.Combobox(toolbar, textvariable=logger_var, state="readonly", width=25)
    logger_combobox["values"] = ["All"]
    logger_combobox.set("All")
    logger_combobox.pack(side="left", padx=(4, 8))

    tk.Label(toolbar, text="Search:").pack(side="left")
    search_var = tk.StringVar()
    search_frame = tk.Frame(toolbar, relief="sunken", borderwidth=1)
    search_frame.pack(side="left", padx=(4, 4))
    search_entry = tk.Entry(search_frame, textvariable=search_var, width=27, relief="flat", borderwidth=0)
    search_entry.pack(side="left", fill="y")
    tk.Button(
        search_frame, text="×", relief="flat", borderwidth=0,
        padx=2, pady=0, cursor="arrow",
        command=lambda: _on_clear_search(),
    ).pack(side="right")
    tk.Button(
        toolbar,
        text="Search",
        command=lambda: _find_and_iterate(),
    ).pack(side="left")
    reverse_var = tk.BooleanVar(value=True)
    tk.Checkbutton(toolbar, text="Reverse", variable=reverse_var).pack(side="left", padx=(4, 0))

    # ------------------------------------------------------------------
    # Text area with scrollbars
    # ------------------------------------------------------------------
    frame = tk.Frame(win)
    frame.pack(fill="both", expand=True, padx=6, pady=(0, 2))

    scrollbar_y = tk.Scrollbar(frame, orient="vertical")
    scrollbar_y.pack(side="right", fill="y")
    scrollbar_x = tk.Scrollbar(frame, orient="horizontal")
    scrollbar_x.pack(side="bottom", fill="x")

    text_widget = tk.Text(
        frame,
        wrap="none",
        state="normal",
        yscrollcommand=scrollbar_y.set,
        xscrollcommand=scrollbar_x.set,
        font=("Courier New", 9),
    )
    text_widget.pack(fill="both", expand=True)
    scrollbar_y.config(command=text_widget.yview)
    scrollbar_x.config(command=text_widget.xview)

    # Keep the widget selectable but block all keyboard editing
    text_widget.bind("<Key>", lambda e: "break" if len(e.char) == 1 else None)
    text_widget.bind("<BackSpace>", lambda e: "break")
    text_widget.bind("<Delete>", lambda e: "break")

    # ------------------------------------------------------------------
    # Search-iteration state — one instance per viewer window
    # ------------------------------------------------------------------
    _search_state: dict = {"matches": [], "current": -1, "last_term": ""}

    def _reset_search_highlights() -> None:
        """Re-apply yellow highlights after content changes; reset current position."""
        text_widget.tag_configure("highlight", background="yellow", foreground="black")
        text_widget.tag_configure("highlight_current", background="#1e90ff", foreground="white")
        term = _search_state["last_term"]
        text_widget.tag_remove("highlight", "1.0", "end")
        text_widget.tag_remove("highlight_current", "1.0", "end")
        _search_state["matches"] = []
        _search_state["current"] = -1
        if not term:
            return
        content = text_widget.get("1.0", "end-1c")
        matches = _find_match_positions(term, content)
        for s, e in matches:
            text_widget.tag_add("highlight", s, e)
        _search_state["matches"] = matches

    def _find_and_iterate(_event=None) -> str:
        """Highlight all matches yellow; iterate to the next one with blue highlight."""
        term = search_var.get().strip()
        text_widget.tag_configure("highlight", background="yellow", foreground="black")
        text_widget.tag_configure("highlight_current", background="#1e90ff", foreground="white")
        if not term:
            text_widget.tag_remove("highlight", "1.0", "end")
            text_widget.tag_remove("highlight_current", "1.0", "end")
            _search_state.update({"matches": [], "current": -1, "last_term": ""})
            return "break"
        if len(term) < 3:
            return "break"
        # Re-find all matches when the term has changed
        if term != _search_state["last_term"]:
            text_widget.tag_remove("highlight", "1.0", "end")
            text_widget.tag_remove("highlight_current", "1.0", "end")
            _search_state["last_term"] = term
            _search_state["current"] = -1
            content = text_widget.get("1.0", "end-1c")
            matches = _find_match_positions(term, content)
            for s, e in matches:
                text_widget.tag_add("highlight", s, e)
            _search_state["matches"] = matches
        matches = _search_state["matches"]
        if not matches:
            return "break"
        # Restore previous current match to yellow
        prev = _search_state["current"]
        if 0 <= prev < len(matches):
            s, e = matches[prev]
            text_widget.tag_remove("highlight_current", s, e)
            text_widget.tag_add("highlight", s, e)
        # Advance in chosen direction (wraps around)
        if reverse_var.get():
            next_idx = len(matches) - 1 if prev == -1 else (prev - 1) % len(matches)
        else:
            next_idx = (prev + 1) % len(matches)
        _search_state["current"] = next_idx
        s, e = matches[_search_state["current"]]
        text_widget.tag_remove("highlight", s, e)
        text_widget.tag_add("highlight_current", s, e)
        text_widget.see(s)
        return "break"

    def _on_clear_search() -> None:
        search_var.set("")
        text_widget.tag_remove("highlight", "1.0", "end")
        text_widget.tag_remove("highlight_current", "1.0", "end")
        _search_state.update({"matches": [], "current": -1, "last_term": ""})
        search_entry.focus_set()

    def _on_logger_change(_event=None) -> None:
        _do_refresh(settings, text_widget, logger_combobox=logger_combobox, logger_var=logger_var)
        _reset_search_highlights()

    def _on_refresh() -> None:
        _do_refresh(settings, text_widget, logger_combobox=logger_combobox, logger_var=logger_var)
        _reset_search_highlights()

    _auto_job: list = [None]

    def _run_auto_refresh() -> None:
        if not win.winfo_exists():
            return
        _on_refresh()
        if auto_var.get():
            _auto_job[0] = win.after(settings.log_auto_refresh_interval * 1000, _run_auto_refresh)

    def _on_auto_toggle() -> None:
        if auto_var.get():
            _auto_job[0] = win.after(settings.log_auto_refresh_interval * 1000, _run_auto_refresh)
        else:
            if _auto_job[0] is not None:
                win.after_cancel(_auto_job[0])
                _auto_job[0] = None

    logger_combobox.bind("<<ComboboxSelected>>", _on_logger_change)
    search_entry.bind("<Return>", _find_and_iterate)
    win.bind("<F3>", _find_and_iterate)

    # ------------------------------------------------------------------
    # Bottom panel
    # ------------------------------------------------------------------
    bottom = tk.Frame(win)
    bottom.pack(side="bottom", fill="x", padx=8, pady=8)
    tk.Button(bottom, text="Close", command=_on_close, width=10).pack(side="right")

    # Initial load — scroll to the bottom so the latest entry is visible
    _do_refresh(
        settings, text_widget, scroll_to_end=True,
        logger_combobox=logger_combobox, logger_var=logger_var,
    )
