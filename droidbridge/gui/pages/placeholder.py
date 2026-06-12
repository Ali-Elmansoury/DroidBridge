"""Placeholder page (Phase 6.1) for modules not yet implemented in the GUI."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    """A simple "<title> — coming soon" page for an unimplemented module screen."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.label = QLabel(f"{title} — coming soon")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
