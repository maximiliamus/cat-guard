"""Unit tests for wake/rebuild logic in :mod:`catguard.main`.

These tests focus on the behaviour of the ``on_wake`` callback that is
returned by ``_make_on_wake_callback``.  Prior to the fix, the tray icon
would disappear after sleep because the callback never recreated it.

We patch out ``build_tray_icon`` and ``threading.Thread`` so that the
callback can be exercised without launching a real GUI thread.
"""
from __future__ import annotations

import logging
import platform
import threading
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from catguard import main as main_module


def make_fake_environment(is_tracking: bool = True):
    """Create a minimal fake state suitable for constructing the callback."""
    root = MagicMock()
    # initial icon (will be replaced)
    old_icon = MagicMock()
    root._tray_icon = old_icon

    stop_event = threading.Event()
    settings = MagicMock()
    settings.tracking_window_enabled = False
    on_settings_saved = MagicMock()

    detection_loop = MagicMock()
    detection_loop.is_tracking.return_value = is_tracking
    detection_loop.resume = MagicMock()

    time_window_monitor = MagicMock()

    # _was_tracking list used by main to preserve state
    was_tracking = [is_tracking]

    # craft the callback with closed-over references exactly as main.main does
    # we'll mimic the closure by temporarily setting local names on a lambda
    # but easiest is to replicate main._make_on_wake_callback behaviour manually

    return (
        root,
        stop_event,
        settings,
        on_settings_saved,
        detection_loop,
        time_window_monitor,
        was_tracking,
    )


@patch("threading.Thread")
def test_on_wake_recreates_tray_thread(mock_thread):
    """When a wake happens and tracking was active, the tray icon is rebuilt.

    The old icon should be stopped, a new one constructed, assigned back to
    ``root._tray_icon`` and a new thread spawned (or detached on macOS).
    """
    (
        root,
        stop_event,
        settings,
        on_settings_saved,
        detection_loop,
        time_window_monitor,
        was_tracking,
    ) = make_fake_environment(is_tracking=True)
    old_icon = root._tray_icon

    # ensure platform branch uses non-Darwin path
    with patch("platform.system", return_value="Windows"), \
         patch("catguard.main._build_and_prepare_tray_icon") as mock_build:
        # prepare the build_tray_icon return value
        new_icon = MagicMock()
        mock_build.return_value = new_icon

        # obtain callback as main does
        on_track_cb = MagicMock()
        callback = main_module._make_on_wake_callback(
            root,
            stop_event,
            settings,
            on_settings_saved,
            detection_loop,
            time_window_monitor,
            was_tracking,
            on_track_cb,
        )

        # call the callback as if SleepWatcher detected a wake
        callback()

    # old icon stop should have been invoked
    old_icon.stop.assert_called_once()
    # build_tray_icon invoked with expected args
    mock_build.assert_called_once_with(
        root,
        stop_event,
        settings,
        on_settings_saved,
        detection_loop,
        time_window_monitor,
    )
    # new icon stored on root
    assert root._tray_icon is new_icon

    # a thread should have been created to run the new icon
    mock_thread.assert_called_once()
    thread_args = mock_thread.call_args[1]
    assert thread_args["target"] is new_icon.run
    assert thread_args["daemon"]
    # start() should have been called on the thread instance
    mock_thread.return_value.start.assert_called_once()

    # detection loop resume and tracking-state notification
    detection_loop.resume.assert_called_once()
    on_track_cb.assert_called_once_with(True)


def test_on_wake_skips_when_not_tracking():
    """If tracking was paused before sleep, no resume or tray recreation."""
    (
        root,
        stop_event,
        settings,
        on_settings_saved,
        detection_loop,
        time_window_monitor,
        was_tracking,
    ) = make_fake_environment(is_tracking=False)

    with patch("catguard.main._build_and_prepare_tray_icon") as mock_build:
        on_track_cb = MagicMock()
        callback = main_module._make_on_wake_callback(
            root,
            stop_event,
            settings,
            on_settings_saved,
            detection_loop,
            time_window_monitor,
            was_tracking,
            on_track_cb,
        )
        callback()

    # build_tray_icon should not be called and detection loop not resumed
    mock_build.assert_not_called()
    detection_loop.resume.assert_not_called()
    on_track_cb.assert_not_called()


def test_on_wake_respects_time_window():
    """When tracking window is enabled and now is outside the window, skip."""
    (
        root,
        stop_event,
        settings,
        on_settings_saved,
        detection_loop,
        time_window_monitor,
        was_tracking,
    ) = make_fake_environment(is_tracking=True)

    settings.tracking_window_enabled = True
    # patch _is_in_window to return False
    with patch("catguard.main._is_in_window", return_value=False), \
         patch("catguard.main._build_and_prepare_tray_icon") as mock_build:
        on_track_cb = MagicMock()
        callback = main_module._make_on_wake_callback(
            root,
            stop_event,
            settings,
            on_settings_saved,
            detection_loop,
            time_window_monitor,
            was_tracking,
            on_track_cb,
        )
        callback()

    mock_build.assert_not_called()
    detection_loop.resume.assert_not_called()
    on_track_cb.assert_not_called()


@patch("threading.Thread")
def test_on_wake_detached_on_darwin(mock_thread):
    """macOS path should call ``run_detached`` instead of spawning a thread."""
    (
        root,
        stop_event,
        settings,
        on_settings_saved,
        detection_loop,
        time_window_monitor,
        was_tracking,
    ) = make_fake_environment(is_tracking=True)
    old_icon = root._tray_icon

    with patch("platform.system", return_value="Darwin"), \
         patch("catguard.main._build_and_prepare_tray_icon") as mock_build:
        new_icon = MagicMock()
        mock_build.return_value = new_icon
        on_track_cb = MagicMock()
        callback = main_module._make_on_wake_callback(
            root,
            stop_event,
            settings,
            on_settings_saved,
            detection_loop,
            time_window_monitor,
            was_tracking,
            on_track_cb,
        )
        callback()

    # stop old and assign new
    old_icon.stop.assert_called_once()
    assert root._tray_icon is new_icon
    # ensure run_detached called instead of creating thread
    assert new_icon.run_detached.called
    mock_thread.assert_not_called()
    on_track_cb.assert_called_once_with(True)


# ---------------------------------------------------------------------------
# T016: handler reconfiguration tests (011-log-viewer-search, US3)
# ---------------------------------------------------------------------------

class TestHandlerReconfiguration:
    """T016 — on_settings_saved reconfigures BatchTrimFileHandler on dir change."""

    def test_on_settings_saved_reconfigures_handler_on_dir_change(self, tmp_path):
        """When logs_directory changes, the old handler is removed and a new one added."""
        import logging as _logging
        import catguard.main as m
        from catguard.log_manager import BatchTrimFileHandler
        from catguard.config import Settings

        old_dir = tmp_path / "old_logs"
        new_dir = tmp_path / "new_logs"
        old_dir.mkdir()
        new_dir.mkdir()

        old_settings = Settings(logs_directory=str(old_dir))
        new_settings = Settings(logs_directory=str(new_dir))

        root_logger = _logging.getLogger()
        old_handler = BatchTrimFileHandler(
            str(old_dir / "catguard.log"),
            max_entries=2048,
            batch_size=205,
        )
        original_handlers = list(root_logger.handlers)

        try:
            m._file_handler = old_handler
            root_logger.addHandler(old_handler)

            m._reconfigure_file_handler(new_settings)

            assert old_handler not in root_logger.handlers
            assert m._file_handler is not None
            assert m._file_handler is not old_handler
            assert str(new_dir) in str(Path(m._file_handler.baseFilename))
        finally:
            if m._file_handler and m._file_handler in root_logger.handlers:
                root_logger.removeHandler(m._file_handler)
                m._file_handler.close()
            if old_handler in root_logger.handlers:
                root_logger.removeHandler(old_handler)
                old_handler.close()
            m._file_handler = None
            for h in list(root_logger.handlers):
                if h not in original_handlers:
                    root_logger.removeHandler(h)

    def test_on_settings_saved_no_handler_change_when_dir_unchanged(self, tmp_path):
        """When logs_directory is unchanged, _file_handler is NOT replaced."""
        import logging as _logging
        import catguard.main as m
        from catguard.log_manager import BatchTrimFileHandler
        from catguard.config import Settings

        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        settings = Settings(logs_directory=str(log_dir))

        old_handler = BatchTrimFileHandler(
            str(log_dir / "catguard.log"),
            max_entries=2048,
            batch_size=205,
        )
        root_logger = _logging.getLogger()
        original_handlers = list(root_logger.handlers)

        try:
            m._file_handler = old_handler
            root_logger.addHandler(old_handler)

            m._reconfigure_file_handler(settings)

            assert m._file_handler is old_handler
        finally:
            if old_handler in root_logger.handlers:
                root_logger.removeHandler(old_handler)
            old_handler.close()
            m._file_handler = None
            for h in list(root_logger.handlers):
                if h not in original_handlers:
                    root_logger.removeHandler(h)
