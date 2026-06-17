"""Clickable breadcrumb bar for filesystem path navigation."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class BreadcrumbBar(QWidget):
    """Shows a filesystem path as clickable segments. Emits pathRequested(str) on click."""

    pathRequested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)

    def set_path(self, path: str) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        parts = [p for p in path.split("/") if p]
        cumulative_paths = ["/"] + ["/" + "/".join(parts[:i + 1]) for i in range(len(parts))]
        labels = ["/"] + parts

        for i, (label, target) in enumerate(zip(labels, cumulative_paths)):
            if i > 0:
                sep = QLabel("›")
                sep.setStyleSheet("color: gray; padding: 0 2px;")
                self._layout.addWidget(sep)

            btn = QPushButton(label)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, p=target: self.pathRequested.emit(p))
            self._layout.addWidget(btn)

        self._layout.addStretch()
