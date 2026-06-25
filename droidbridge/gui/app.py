"""GUI entry point (Phase 6.1): QApplication setup, theming, session logging, MainWindow."""

import sys

from PyQt6.QtWidgets import QApplication

from droidbridge.core.session import SessionLogger
from droidbridge.gui import theme
from droidbridge.gui.main_window import MainWindow


def main(argv=None):
    """Launch the DroidBridge GUI. Returns the Qt application's exit code."""
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("DroidBridge")
    app.setApplicationDisplayName("DroidBridge")

    theme.apply_theme(app, theme.load_theme_pref())

    session_logger = SessionLogger.start()
    window = MainWindow(session_logger=session_logger)
    screen = app.primaryScreen()
    avail = screen.availableGeometry()
    w = min(1280, avail.width())
    h = min(720, avail.height())
    window.resize(w, h)
    window.move(avail.x() + (avail.width() - w) // 2, avail.y() + (avail.height() - h) // 2)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
