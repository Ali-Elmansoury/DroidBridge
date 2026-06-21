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
        self._wrap = False
        self.setFullText(text)

    def fullText(self):
        return self._full_text

    def setFullText(self, text):
        self._full_text = text
        self.setToolTip(text)
        self._update_text()

    def setWrapMode(self, wrap):
        """Switch between single-line eliding (default) and full word-wrap.

        Used for error/warning messages, which matter enough to read in
        full rather than being truncated with "..." like routine status text.
        """
        self._wrap = wrap
        self.setWordWrap(wrap)
        self._update_text()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_text()

    def _update_text(self):
        if self._wrap:
            super().setText(self._full_text)
        else:
            elided = self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideRight, self.width())
            super().setText(elided)
