"""Unit tests for log viewer components (TDD RED before implementation).

Scope: SettingsFormModel additions and _do_search() filtering logic only.
Log viewer window UI is display-dependent and covered by manual acceptance
testing (T024).
"""
from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from catguard.config import Settings
from catguard.ui.settings_window import SettingsFormModel


# ---------------------------------------------------------------------------
# T005: SettingsFormModel additions (US1)
# ---------------------------------------------------------------------------

class TestSettingsFormModelLogDefaults:
    """T005 — new log fields have correct defaults in SettingsFormModel."""

    def test_logs_directory_default(self):
        model = SettingsFormModel()
        assert "CatGuard" in model.logs_directory
        assert model.logs_directory.endswith("logs") or "logs" in model.logs_directory

    def test_max_log_entries_default(self):
        model = SettingsFormModel()
        assert model.max_log_entries == 2048

    def test_log_trim_batch_size_default(self):
        model = SettingsFormModel()
        assert model.log_trim_batch_size == 205

    def test_log_auto_refresh_interval_default(self):
        model = SettingsFormModel()
        assert model.log_auto_refresh_interval == 5


class TestSettingsFormModelRoundTrip:
    """T005 — from_settings() + to_settings() round-trip preserves log fields."""

    def test_from_settings_maps_logs_directory(self):
        s = Settings(logs_directory="/tmp/my_logs")
        model = SettingsFormModel.from_settings(s)
        assert model.logs_directory == "/tmp/my_logs"

    def test_from_settings_maps_max_log_entries(self):
        s = Settings(max_log_entries=4096)
        model = SettingsFormModel.from_settings(s)
        assert model.max_log_entries == 4096

    def test_from_settings_maps_log_trim_batch_size(self):
        s = Settings(log_trim_batch_size=500)
        model = SettingsFormModel.from_settings(s)
        assert model.log_trim_batch_size == 500

    def test_to_settings_preserves_logs_directory(self):
        model = SettingsFormModel(logs_directory="/tmp/my_logs")
        s = model.to_settings()
        assert s.logs_directory == "/tmp/my_logs"

    def test_to_settings_preserves_max_log_entries(self):
        model = SettingsFormModel(max_log_entries=4096)
        s = model.to_settings()
        assert s.max_log_entries == 4096

    def test_to_settings_preserves_log_trim_batch_size(self):
        model = SettingsFormModel(log_trim_batch_size=500)
        s = model.to_settings()
        assert s.log_trim_batch_size == 500

    def test_from_settings_maps_log_auto_refresh_interval(self):
        s = Settings(log_auto_refresh_interval=30)
        model = SettingsFormModel.from_settings(s)
        assert model.log_auto_refresh_interval == 30

    def test_to_settings_preserves_log_auto_refresh_interval(self):
        model = SettingsFormModel(log_auto_refresh_interval=30)
        s = model.to_settings()
        assert s.log_auto_refresh_interval == 30

    def test_full_round_trip(self):
        s_original = Settings(
            logs_directory="/tmp/my_logs",
            max_log_entries=4096,
            log_trim_batch_size=410,
            log_auto_refresh_interval=10,
        )
        model = SettingsFormModel.from_settings(s_original)
        s_roundtrip = model.to_settings()
        assert s_roundtrip.logs_directory == "/tmp/my_logs"
        assert s_roundtrip.max_log_entries == 4096
        assert s_roundtrip.log_trim_batch_size == 410
        assert s_roundtrip.log_auto_refresh_interval == 10


class TestSettingsFormModelValidation:
    """T005 — to_settings() raises on values below minimum."""

    def test_to_settings_rejects_max_log_entries_below_minimum(self):
        model = SettingsFormModel(max_log_entries=100)
        with pytest.raises(Exception):
            model.to_settings()

    def test_to_settings_rejects_log_trim_batch_size_below_minimum(self):
        model = SettingsFormModel(log_trim_batch_size=10)
        with pytest.raises(Exception):
            model.to_settings()


# ---------------------------------------------------------------------------
# T011: logger filter (_do_refresh) and text highlight (_do_highlight) (US2)
# ---------------------------------------------------------------------------

def _write_log_file(path: Path, lines: list[str]) -> None:
    """Helper: write lines to a log file."""
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestLoggerFilter:
    """T011 — _do_refresh() logger filtering logic."""

    def _make_settings(self, tmp_path: Path, lines: list[str]):
        from catguard.ui import log_viewer as lv

        log_file = tmp_path / "catguard.log"
        _write_log_file(log_file, lines)

        settings = MagicMock()
        settings.logs_directory = str(tmp_path)
        text_widget = MagicMock()
        text_widget.yview.return_value = (0.0, 1.0)
        text_widget.tag_ranges.return_value = ()
        return lv, settings, text_widget

    def test_refresh_shows_all_entries_without_filter(self, tmp_path):
        lines = [
            "2026-03-19 10:00:00,000 [INFO] catguard.main: Cat detected",
            "2026-03-19 10:00:01,000 [INFO] catguard.detector: Motion start",
        ]
        lv, settings, text_widget = self._make_settings(tmp_path, lines)

        lv._do_refresh(settings, text_widget)

        insert_calls = [str(c) for c in text_widget.insert.call_args_list]
        inserted_text = " ".join(insert_calls)
        assert "Cat detected" in inserted_text
        assert "Motion start" in inserted_text

    def test_refresh_filters_by_logger(self, tmp_path):
        lines = [
            "2026-03-19 10:00:00,000 [INFO] catguard.main: Cat detected",
            "2026-03-19 10:00:01,000 [INFO] catguard.detector: Motion start",
        ]
        lv, settings, text_widget = self._make_settings(tmp_path, lines)
        logger_var = MagicMock()
        logger_var.get.return_value = "catguard.detector"

        lv._do_refresh(settings, text_widget, logger_var=logger_var)

        insert_calls = [str(c) for c in text_widget.insert.call_args_list]
        inserted_text = " ".join(insert_calls)
        assert "Motion start" in inserted_text
        assert "Cat detected" not in inserted_text

    def test_refresh_all_logger_shows_all_entries(self, tmp_path):
        lines = [
            "2026-03-19 10:00:00,000 [INFO] catguard.main: Cat detected",
            "2026-03-19 10:00:01,000 [INFO] catguard.detector: Motion start",
        ]
        lv, settings, text_widget = self._make_settings(tmp_path, lines)
        logger_var = MagicMock()
        logger_var.get.return_value = "All"

        lv._do_refresh(settings, text_widget, logger_var=logger_var)

        insert_calls = [str(c) for c in text_widget.insert.call_args_list]
        inserted_text = " ".join(insert_calls)
        assert "Cat detected" in inserted_text
        assert "Motion start" in inserted_text


class TestDoHighlight:
    """T011 — _do_highlight() text search and tag logic."""

    def _make_widget(self, content: str):
        from catguard.ui import log_viewer as lv

        text_widget = MagicMock()
        text_widget.get.return_value = content
        search_var = MagicMock()
        return lv, text_widget, search_var

    def test_highlight_finds_case_insensitive_matches(self):
        content = "Cat detected\nNo activity\nCAT again"
        lv, text_widget, search_var = self._make_widget(content)
        search_var.get.return_value = "cat"

        lv._do_highlight(search_var, text_widget)

        assert text_widget.tag_add.call_count == 2
        text_widget.see.assert_called_once()

    def test_highlight_empty_term_only_removes_tags(self):
        lv, text_widget, search_var = self._make_widget("some text")
        search_var.get.return_value = ""

        lv._do_highlight(search_var, text_widget)

        text_widget.tag_remove.assert_called_with("highlight", "1.0", "end")
        text_widget.tag_add.assert_not_called()
        text_widget.see.assert_not_called()

    def test_highlight_no_match_does_not_call_see(self):
        lv, text_widget, search_var = self._make_widget("Dog barked")
        search_var.get.return_value = "cat"

        lv._do_highlight(search_var, text_widget)

        text_widget.tag_add.assert_not_called()
        text_widget.see.assert_not_called()

    def test_highlight_scroll_to_match_false_skips_see(self):
        content = "Cat detected"
        lv, text_widget, search_var = self._make_widget(content)
        search_var.get.return_value = "cat"

        lv._do_highlight(search_var, text_widget, scroll_to_match=False)

        assert text_widget.tag_add.call_count == 1
        text_widget.see.assert_not_called()
