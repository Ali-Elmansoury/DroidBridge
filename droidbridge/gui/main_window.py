"""Main application window (Phase 6.1): sidebar nav, top bar device status, bottom
status bar, collapsible log panel, and dark/light theme toggle.
"""

from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from droidbridge.gui import theme
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.pages.device import DevicePage
from droidbridge.gui.pages.files import FilesPage
from droidbridge.gui.pages.placeholder import PlaceholderPage
from droidbridge.gui.pages.search import SearchPage
from droidbridge.gui.pages.transfer import TransferPage
from droidbridge.gui.viewmodels.device import DeviceViewModel
from droidbridge.gui.viewmodels.files import FilesViewModel
from droidbridge.gui.viewmodels.search import SearchViewModel
from droidbridge.gui.viewmodels.transfer import TransferViewModel
from droidbridge.gui.widgets.log_panel import LogPanel

MODULES = [
    "Device",
    "Files",
    "Transfer",
    "Search",
    "WhatsApp",
    "Storage",
    "Backup",
    "Apps",
    "Reports",
]


class MainWindow(QMainWindow):
    """Top-level window: sidebar navigation, top status bar, log panel, and status bar."""

    def __init__(self, context=None, session_logger=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DroidBridge")

        self.context = context or DeviceContext()
        self.session_logger = session_logger
        self.device_viewmodel = DeviceViewModel(self.context)
        self.files_viewmodel = FilesViewModel(self.context)
        self.transfer_viewmodel = TransferViewModel(self.context)
        self.search_viewmodel = SearchViewModel(self.context)

        self.sidebar = QListWidget()
        self.sidebar.addItems(MODULES)

        self.files_page = FilesPage(self.files_viewmodel)
        self.transfer_page = TransferPage(self.transfer_viewmodel)
        self.search_page = SearchPage(self.search_viewmodel)

        self.stack = QStackedWidget()
        self.stack.addWidget(DevicePage(self.device_viewmodel))
        self.stack.addWidget(self.files_page)
        self.stack.addWidget(self.transfer_page)
        self.stack.addWidget(self.search_page)
        for name in MODULES[4:]:
            self.stack.addWidget(PlaceholderPage(name))
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        self.status_dot = QLabel()
        self.status_dot.setFixedSize(12, 12)
        self.status_text = QLabel("Disconnected")
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.device_viewmodel.connect_device)

        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.addWidget(self.status_dot)
        top_layout.addWidget(self.status_text)
        top_layout.addStretch()
        top_layout.addWidget(self.connect_button)

        self.log_panel = LogPanel()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(top_bar)
        right_layout.addWidget(self.stack)
        right_layout.addWidget(self.log_panel)

        central = QWidget()
        central_layout = QHBoxLayout(central)
        central_layout.addWidget(self.sidebar)
        central_layout.addWidget(right)
        self.setCentralWidget(central)

        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.busy_bar)

        view_menu = self.menuBar().addMenu("View")

        self.log_panel_action = view_menu.addAction("Show Log Panel")
        self.log_panel_action.setCheckable(True)
        self.log_panel_action.setChecked(True)
        self.log_panel_action.toggled.connect(self.log_panel.setVisible)

        self.dark_theme_action = view_menu.addAction("Dark Theme")
        self.dark_theme_action.setCheckable(True)
        self.dark_theme_action.setChecked(theme.load_theme_pref() == theme.DARK)
        self.dark_theme_action.toggled.connect(self._on_theme_toggled)

        self.context.connectionChanged.connect(self._on_connection_changed)
        self.device_viewmodel.statusChanged.connect(self.statusBar().showMessage)
        self.device_viewmodel.busyChanged.connect(self.busy_bar.setVisible)
        self.device_viewmodel.busyChanged.connect(
            lambda busy: self.connect_button.setEnabled(not busy)
        )
        self.device_viewmodel.logMessage.connect(self._on_log_message)

        self.files_page.pullRequested.connect(self._on_pull_requested)
        self.search_page.pullRequested.connect(self._on_pull_requested)

        for vm in (self.files_viewmodel, self.transfer_viewmodel, self.search_viewmodel):
            vm.statusChanged.connect(self.statusBar().showMessage)
            vm.busyChanged.connect(self.busy_bar.setVisible)
            vm.logMessage.connect(self._on_log_message)

        self._on_connection_changed(
            self.context.is_connected, self.context.serial or "", self.context.model or ""
        )

    def _on_connection_changed(self, connected, serial, model):
        color = "green" if connected else "red"
        self.status_dot.setStyleSheet(f"background-color: {color}; border-radius: 6px;")
        self.status_text.setText(f"{model} ({serial})" if connected else "Disconnected")

    def _on_pull_requested(self, remote_paths, local_dir):
        self.transfer_viewmodel.pull_selected(remote_paths, local_dir)
        self.sidebar.setCurrentRow(2)

    def _on_log_message(self, message, level):
        if self.session_logger is not None:
            self.session_logger.log(message, level)
        self.log_panel.append_entry(message, level)

    def _on_theme_toggled(self, checked):
        mode = theme.DARK if checked else theme.LIGHT
        theme.apply_theme(QApplication.instance(), mode)
        theme.save_theme_pref(mode)

    def closeEvent(self, event):
        if self.session_logger is not None:
            self.session_logger.write_summary()
        super().closeEvent(event)
