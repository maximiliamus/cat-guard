"""Auto-mark every test collected from this directory as 'integration'.

This means ``pytest -m "not integration"`` (used in CI for unit-only runs)
reliably skips all tests here without requiring each file to declare
``pytestmark = pytest.mark.integration`` individually.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_HERE = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        try:
            item.path.relative_to(_HERE)
            item.add_marker(pytest.mark.integration)
        except ValueError:
            pass
