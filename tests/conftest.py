"""Pytest configuration and shared fixtures.

This conftest installs lightweight sys.modules stubs for heavy optional
packages (cv2, pygame) that either:
  - have no Python 3.14 wheel yet, or
  - require a GPU/display which is unavailable in CI.

Unit tests mock the *behaviour* of these packages via pytest-mock / MagicMock.
Integration tests that need real packages are marked with @pytest.mark.integration
and are skipped automatically when the package is absent.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Stub modules for packages without Python 3.14 wheels
# ---------------------------------------------------------------------------

def _install_stub(dotted_name: str) -> MagicMock:
    """Insert a MagicMock into sys.modules for *dotted_name* and every parent."""
    parts = dotted_name.split(".")
    for i in range(1, len(parts) + 1):
        name = ".".join(parts[:i])
        if name not in sys.modules:
            sys.modules[name] = MagicMock(name=name)
    return sys.modules[dotted_name]  # type: ignore[return-value]


# Only stub packages that are genuinely absent — don't clobber real installs.
for _pkg in ("cv2", "pygame", "pygame.mixer", "pystray"):
    try:
        __import__(_pkg)
    except ModuleNotFoundError:
        _install_stub(_pkg)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_cv2(monkeypatch):
    """Return (and optionally patch) the cv2 stub already in sys.modules."""
    return sys.modules["cv2"]


@pytest.fixture()
def mock_pygame_mixer(monkeypatch):
    """Return (and optionally patch) the pygame.mixer stub."""
    return sys.modules.get("pygame.mixer", MagicMock())
