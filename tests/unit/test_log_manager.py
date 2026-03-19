"""Unit tests for catguard.log_manager.BatchTrimFileHandler (TDD RED).

Covers:
- trim not triggered before batch_size writes
- trim triggered at batch boundary
- trim keeps last max_entries lines
- trim is a no-op when within limit
- trim writes atomically via .tmp rename
- trim handles missing log file gracefully
- write count resets after batch
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest


class TestBatchTrimFileHandler:
    def _make_handler(self, tmp_path: Path, max_entries: int = 10, batch_size: int = 3):
        from catguard.log_manager import BatchTrimFileHandler

        log_file = tmp_path / "catguard.log"
        handler = BatchTrimFileHandler(str(log_file), max_entries=max_entries, batch_size=batch_size)
        handler.setFormatter(logging.Formatter("%(message)s"))
        return handler, log_file

    def _emit_n(self, handler, n: int, msg: str = "line") -> None:
        for i in range(n):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg=f"{msg} {i}", args=(), exc_info=None,
            )
            handler.emit(record)

    def test_trim_not_triggered_before_batch(self, tmp_path):
        handler, log_file = self._make_handler(tmp_path, max_entries=2, batch_size=3)
        # Write 5 lines that exceed max_entries=2, but only 2 writes (< batch_size=3)
        # Pre-populate file with 5 lines that would need trimming
        log_file.write_text("a\nb\nc\nd\ne\n", encoding="utf-8")
        # emit only 2 times — trim not yet triggered
        self._emit_n(handler, 2)
        handler.close()
        # File should still have more than 2 lines (trim not run)
        lines = [l for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) > 2

    def test_trim_triggered_at_batch_boundary(self, tmp_path):
        handler, log_file = self._make_handler(tmp_path, max_entries=3, batch_size=3)
        # Emit 9 writes: trim triggers at 3 (no-op), 6 (trim), 9 (trim) → ≤3 lines
        self._emit_n(handler, 9)
        handler.close()
        lines = [l for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) <= 3

    def test_trim_keeps_last_n_entries(self, tmp_path):
        handler, log_file = self._make_handler(tmp_path, max_entries=3, batch_size=3)
        self._emit_n(handler, 9, msg="entry")
        handler.close()
        lines = [l for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) <= 3
        # Last entries should be the most recent ones
        assert "entry 8" in lines[-1]

    def test_trim_no_op_when_within_limit(self, tmp_path):
        handler, log_file = self._make_handler(tmp_path, max_entries=100, batch_size=3)
        self._emit_n(handler, 6)  # triggers trim twice; only 6 lines ≤ 100 → no trim
        handler.close()
        lines = [l for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 6

    def test_trim_atomic_write(self, tmp_path):
        """Trim must not leave a .tmp file behind on success."""
        handler, log_file = self._make_handler(tmp_path, max_entries=2, batch_size=3)
        self._emit_n(handler, 6)
        handler.close()
        tmp_file = log_file.with_suffix(".tmp")
        assert not tmp_file.exists()

    def test_trim_handles_missing_file(self, tmp_path):
        """_trim() must not raise if the log file was deleted externally."""
        from catguard.log_manager import BatchTrimFileHandler

        log_file = tmp_path / "catguard.log"
        handler = BatchTrimFileHandler(str(log_file), max_entries=2, batch_size=3)
        handler.setFormatter(logging.Formatter("%(message)s"))
        # Close the handler first to release the file handle (required on Windows)
        # before deleting, then verify _trim() is a no-op on missing file
        handler.close()
        log_file.unlink(missing_ok=True)
        # Should not raise even with missing file
        handler._trim()

    def test_write_count_resets_after_batch(self, tmp_path):
        """_write_count must reset to 0 after each batch boundary."""
        handler, log_file = self._make_handler(tmp_path, max_entries=100, batch_size=3)
        self._emit_n(handler, 3)  # hits boundary → resets
        assert handler._write_count == 0
        handler.close()
