"""Pytest configuration and fixtures.

Shared fixtures for the GUI test suite (pytest-qt setup, mock AdbClient/device
fixtures, etc.) can be added here as Phase 6 grows.
"""

import os

import pytest
from click.testing import CliRunner

# pytest-qt's QApplication must not depend on the host's display/desktop theme.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def runner():
    return CliRunner()
