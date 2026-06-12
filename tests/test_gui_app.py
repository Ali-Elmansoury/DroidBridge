"""Tests for droidbridge.gui.app.main (Phase 6.1)."""

from PyQt6.QtWidgets import QApplication

from droidbridge.gui import app


class TestMain:
    def test_returns_exit_code_and_starts_session(self, monkeypatch, tmp_path):
        monkeypatch.setattr(QApplication, "exec", lambda self: 0)
        monkeypatch.chdir(tmp_path)

        exit_code = app.main([])

        assert exit_code == 0
        assert (tmp_path / "session_logs").is_dir()
