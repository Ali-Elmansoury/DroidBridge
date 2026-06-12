"""Tests for `droidbridge gui` (Phase 6.1)."""

import importlib.util

from click.testing import CliRunner

from droidbridge.cli import main


class TestGuiCommand:
    def test_missing_pyqt6_shows_install_message_and_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)

        result = CliRunner().invoke(main.cli, ["gui"])

        assert result.exit_code == 1
        assert 'pip install -e ".[gui]"' in result.output

    def test_launches_gui_when_available(self, monkeypatch):
        monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())

        called = []
        monkeypatch.setattr("droidbridge.gui.app.main", lambda argv: called.append(argv) or 0)

        result = CliRunner().invoke(main.cli, ["gui"])

        assert result.exit_code == 0
        assert len(called) == 1
