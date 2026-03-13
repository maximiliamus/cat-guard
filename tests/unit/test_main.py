"""Unit tests for wake/rebuild logic in :mod:`catguard.main`.

These tests focus on the behaviour of the ``on_wake`` callback that is
returned by ``_make_on_wake_callback``.  Prior to the fix, the tray icon
would disappear after sleep because the callback never recreated it.

We patch out ``build_tray_icon`` and ``threading.Thread`` so that the
callback can be exercised without launching a real GUI thread.
"""
from __future__ import annotations

import platform
import threading
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
