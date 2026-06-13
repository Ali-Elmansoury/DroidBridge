"""A QLabel that elides long text to fit its width (Phase 6.2 follow-up)."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel


class ElidedLabel(QLabel):
    """QLabel that truncates text with "..." to fit its current width.

    The untruncated text is always available via toolTip(), so a long status
    message stays readable on hover without growing the surrounding layout
    (and overlapping neighboring widgets, e.g. a status bar's progress bar).
    """

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = ""
        self.setFullText(text)

    def fullText(self):
        return self._full_text

    def setFullText(self, text):
        self._full_text = text
        self.setToolTip(text)
        self._update_elided_text()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self):
        elided = self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideRight, self.width())
        super().setText(elided)
