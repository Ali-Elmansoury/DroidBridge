# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.gui.theme (Phase 6.1)."""

from PyQt6.QtGui import QColor, QPalette

from droidbridge.gui import theme


class TestApplyTheme:
    def test_dark_theme_sets_dark_window_color(self, qapp):
        theme.apply_theme(qapp, theme.DARK)

        color = qapp.palette().color(QPalette.ColorRole.Window)

        assert color.lightness() < 128

    def test_light_theme_sets_light_window_color(self, qapp):
        theme.apply_theme(qapp, theme.DARK)
        theme.apply_theme(qapp, theme.LIGHT)

        color = qapp.palette().color(QPalette.ColorRole.Window)

        assert color.lightness() > 128

    def test_light_palette_uses_explicit_light_colors(self):
        """The light palette must be hand-rolled (not app.style().standardPalette()),
        which on some desktops returns the host's dark color scheme even for Fusion.
        """
        palette = theme._light_palette()

        assert palette.color(QPalette.ColorRole.Window) == QColor(239, 239, 239)
        assert palette.color(QPalette.ColorRole.WindowText) == QColor(0, 0, 0)
        assert palette.color(QPalette.ColorRole.Base) == QColor(255, 255, 255)
        assert palette.color(QPalette.ColorRole.Text) == QColor(0, 0, 0)


class TestThemePreference:
    def test_load_theme_pref_defaults_to_light_when_missing(self, tmp_path):
        path = tmp_path / "gui_prefs.json"

        assert theme.load_theme_pref(path) == theme.LIGHT

    def test_save_then_load_round_trips(self, tmp_path):
        path = tmp_path / "gui_prefs.json"

        theme.save_theme_pref(theme.DARK, path)

        assert theme.load_theme_pref(path) == theme.DARK

    def test_load_theme_pref_ignores_corrupt_file(self, tmp_path):
        path = tmp_path / "gui_prefs.json"
        path.write_text("not json")

        assert theme.load_theme_pref(path) == theme.LIGHT
