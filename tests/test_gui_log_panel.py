# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.gui.widgets.log_panel.LogPanel (Phase 6.1)."""

from droidbridge.gui.widgets.log_panel import LogPanel


class TestLogPanel:
    def test_is_read_only(self, qtbot):
        panel = LogPanel()
        qtbot.addWidget(panel)

        assert panel.isReadOnly() is True

    def test_append_entry_shows_level_and_message(self, qtbot):
        panel = LogPanel()
        qtbot.addWidget(panel)

        panel.append_entry("Connected to SERIAL123", "INFO")

        text = panel.toPlainText()
        assert "INFO" in text
        assert "Connected to SERIAL123" in text

    def test_append_entry_error_is_colored_red(self, qtbot):
        panel = LogPanel()
        qtbot.addWidget(panel)

        panel.append_entry("boom", "ERROR")

        # PyQt6 converts "red" to hex #ff0000
        assert "#ff0000" in panel.toHtml().lower()
        assert "boom" in panel.toPlainText()

    def test_append_entry_warning_is_colored_orange(self, qtbot):
        panel = LogPanel()
        qtbot.addWidget(panel)

        panel.append_entry("careful", "WARNING")

        # PyQt6 converts "orange" to hex #ffa500
        assert "#ffa500" in panel.toHtml().lower()
