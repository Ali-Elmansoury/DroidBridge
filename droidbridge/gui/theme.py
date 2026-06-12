"""Dark/light theming via Fusion style + QPalette, with a persisted preference
(Phase 6.1).
"""

import json
from pathlib import Path

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QStyleFactory

LIGHT = "light"
DARK = "dark"

DEFAULT_PREFS_PATH = Path.home() / ".droidbridge" / "gui_prefs.json"


def _dark_palette():
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    return palette


def _light_palette():
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(239, 239, 239))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(247, 247, 247))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Button, QColor(239, 239, 239))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    return palette


def apply_theme(app, mode):
    """Apply the Fusion style with a dark or light QPalette to `app`."""
    app.setStyle(QStyleFactory.create("Fusion"))
    if mode == DARK:
        app.setPalette(_dark_palette())
    else:
        app.setPalette(_light_palette())


def load_theme_pref(path=None):
    """Return the persisted theme ("dark"/"light"), or LIGHT if unset/unreadable."""
    path = Path(path) if path is not None else DEFAULT_PREFS_PATH
    if not path.exists():
        return LIGHT
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return LIGHT
    return data.get("theme", LIGHT)


def save_theme_pref(mode, path=None):
    """Persist the theme ("dark"/"light") to `path` (default ~/.droidbridge/gui_prefs.json)."""
    path = Path(path) if path is not None else DEFAULT_PREFS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"theme": mode}))
