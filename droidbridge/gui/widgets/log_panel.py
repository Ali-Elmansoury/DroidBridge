"""Real-time, color-coded operation log panel (Phase 6.1)."""

from datetime import datetime

from PyQt6.QtWidgets import QTextEdit

_LEVEL_COLORS = {
    "WARNING": "orange",
    "ERROR": "red",
}


class LogPanel(QTextEdit):
    """Read-only, color-coded log of GUI operations (INFO/WARNING/ERROR)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)

    def append_entry(self, message, level="INFO"):
        """Append one timestamped, color-coded log line."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        text = f"[{timestamp}] [{level}] {message}"
        color = _LEVEL_COLORS.get(level)
        if color:
            self.append(f'<span style="color:{color}">{text}</span>')
        else:
            self.append(text)
