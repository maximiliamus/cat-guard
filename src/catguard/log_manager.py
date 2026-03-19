"""Log management for CatGuard.

Provides BatchTrimFileHandler — a logging.FileHandler subclass that enforces
an entry-count ceiling via batched write-time trimming.
"""
from __future__ import annotations

import logging
from pathlib import Path


class BatchTrimFileHandler(logging.FileHandler):
    """FileHandler that trims the log file to *max_entries* lines every *batch_size* writes.

    Trimming is atomic: the rewritten content is written to a .tmp file first,
    then renamed into place.  On OSError the .tmp file is removed and the
    original log is left intact.
    """

    def __init__(
        self,
        filename: str,
        max_entries: int = 2048,
        batch_size: int = 205,
        **kwargs,
    ) -> None:
        super().__init__(filename, **kwargs)
        self._max_entries = max_entries
        self._batch_size = batch_size
        self._write_count = 0

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self._write_count += 1
        if self._write_count >= self._batch_size:
            self._write_count = 0
            self._trim()

    def _trim(self) -> None:
        """Trim the log file to the last *max_entries* lines (atomic).

        Closes and reopens the stream around the file replacement so that
        subsequent writes go to the new (trimmed) file, not the old handle.
        This is required on Windows where file handles survive renames.
        """
        log_path = Path(self.baseFilename)
        if not log_path.is_file():
            return

        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return

        lines = [l for l in text.splitlines() if l.strip()]
        if len(lines) <= self._max_entries:
            return

        keep = lines[-self._max_entries:]
        tmp = log_path.with_suffix(".tmp")
        try:
            tmp.write_text("\n".join(keep) + "\n", encoding="utf-8")
            # Close stream before replacing the file so the handle is free
            if self.stream is not None:
                self.stream.flush()
                self.stream.close()
                self.stream = None
            tmp.replace(log_path)
            # Reopen stream so subsequent emits go to the new file
            self.stream = self._open()
        except OSError:
            tmp.unlink(missing_ok=True)
            # Restore stream if we closed it
            if self.stream is None:
                try:
                    self.stream = self._open()
                except OSError:
                    pass
