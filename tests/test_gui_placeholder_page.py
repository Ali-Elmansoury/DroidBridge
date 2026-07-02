# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.gui.pages.placeholder.PlaceholderPage (Phase 6.1)."""

from droidbridge.gui.pages.placeholder import PlaceholderPage


class TestPlaceholderPage:
    def test_shows_title_and_coming_soon(self, qtbot):
        page = PlaceholderPage("Files")
        qtbot.addWidget(page)

        assert "Files" in page.label.text()
        assert "coming soon" in page.label.text().lower()
