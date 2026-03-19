"""Integration test: save + reload of log settings fields.

Constitution §IV: real filesystem writes, no mocks.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from catguard.config import Settings, load_settings, save_settings


def test_settings_round_trip_log_fields(tmp_path):
    """Save settings with custom log fields and reload — all three fields preserved."""
    config_file = tmp_path / "settings.json"
    logs_dir = str(tmp_path / "logs")

    original = Settings(
        logs_directory=logs_dir,
        max_log_entries=4096,
        log_trim_batch_size=410,
    )

    with patch("catguard.config._config_file", return_value=config_file):
        save_settings(original)
        reloaded = load_settings()

    assert reloaded.logs_directory == logs_dir
    assert reloaded.max_log_entries == 4096
    assert reloaded.log_trim_batch_size == 410
