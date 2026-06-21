"""A QLabel that elides long text to fit its width (Phase 6.2 follow-up)."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel


class ElidedLabel(QLabel):
    """QLabel that truncates text with "..." to fit its current width.

    The untruncated text is always available via toolTip(), so a long status
    message stays readable on hover without growing the surrounding layout
    (and overlapping neighboring widgets, e.g. a status bar's progress bar).
    """

    _MAX_WRAP_LINES = 4

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = ""
        self._wrap = False
        self._single_line_height = self.fontMetrics().height()
        self.setFullText(text)

    def fullText(self):
        return self._full_text

    def setFullText(self, text):
        self._full_text = text
        self.setToolTip(text)
        self._update_text()

    def setWrapMode(self, wrap):
        """Switch between single-line eliding (default) and word-wrap.

        Used for error/warning messages, which matter enough to read in
        full rather than being truncated with "..." like routine status text.

        A QStatusBar's QHBoxLayout doesn't re-run heightForWidth() against
        the label's actual allocated width, so leaving the height to be
        inferred automatically produces an oversized box (computed from a
        narrower hypothetical width) that never shrinks back once wrapping
        is turned off. Setting the height explicitly, both ways, avoids that.
        """
        self._wrap = wrap
        self.setWordWrap(wrap)
        self._update_text()
        if wrap:
            max_height = self._single_line_height * self._MAX_WRAP_LINES
            height = min(self.heightForWidth(self.width()), max_height) if self.width() > 0 else max_height
            self.setFixedHeight(max(height, self._single_line_height))
        else:
            self.setFixedHeight(self._single_line_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_text()
        if self._wrap:
            max_height = self._single_line_height * self._MAX_WRAP_LINES
            height = min(self.heightForWidth(self.width()), max_height)
            new_height = max(height, self._single_line_height)
            if new_height != self.height():
                self.setFixedHeight(new_height)

    def _update_text(self):
        if self._wrap:
            super().setText(self._full_text)
        else:
            elided = self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideRight, self.width())
            super().setText(elided)
