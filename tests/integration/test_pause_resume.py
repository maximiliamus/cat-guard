"""Integration tests for pause/resume tracking control.

Tests:
- T013: Pause via menu stops detection
- T014: Pause completes within 500ms
- T022: Resume via menu starts detection
- T023: Resume completes within 500ms
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from catguard.config import Settings
from catguard.detection import DetectionLoop


class TestPauseResumeIntegration:
    """Integration tests for pause/resume functionality."""

    def test_menu_pause_stops_detection(self):
        """Test that pause via menu stops detection loop (T013)."""
        callback = MagicMock()
        loop = DetectionLoop(Settings(), callback)
        
        # Start tracking
        loop._is_tracking = True
        assert loop.is_tracking() is True
        
        # Pause
        result = loop.pause()
        
        assert result is True
        assert loop.is_tracking() is False
        assert loop._stop_event.is_set()

    def test_pause_completes_within_500ms(self):
        """Test that pause completes within 500ms (T014)."""
        callback = MagicMock()
        loop = DetectionLoop(Settings(), callback)
        loop._is_tracking = True
        
        start = time.perf_counter()
        loop.pause()
        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        
        assert elapsed < 500, f"Pause took {elapsed}ms, should be < 500ms"
        assert not loop.is_tracking()

    def test_menu_resume_starts_detection(self):
        """Test that resume via menu starts detection loop (T022)."""
        callback = MagicMock()
        loop = DetectionLoop(Settings(), callback)
        
        # Start paused
        loop._is_tracking = False
        loop._stop_event.set()
        assert loop.is_tracking() is False
        
        # Resume
        result = loop.resume()
        
        assert result is True
        assert loop.is_tracking() is True
        assert not loop._stop_event.is_set()

    def test_resume_completes_within_500ms(self):
        """Test that resume completes within 500ms (T023)."""
        callback = MagicMock()
        loop = DetectionLoop(Settings(), callback)
        loop._is_tracking = False
        loop._stop_event.set()
        
        start = time.perf_counter()
        loop.resume()
        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        
        assert elapsed < 500, f"Resume took {elapsed}ms, should be < 500ms"
        assert loop.is_tracking()

    def test_rapid_pause_continue_no_deadlock(self):
        """Test that rapid pause/continue doesn't cause deadlock."""
        callback = MagicMock()
        loop = DetectionLoop(Settings(), callback)
        loop._is_tracking = True
        
        # Rapidly toggle pause/continue
        for _ in range(10):
            loop.pause()
            loop.resume()
        
        # Should complete without deadlock
        assert loop.is_tracking() is True
