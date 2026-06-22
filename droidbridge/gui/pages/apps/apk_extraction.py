from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QListWidget, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from droidbridge.gui.viewmodels.apps.apk_extraction import ApkExtractionViewModel

_NO_SELECTION_TEXT = "No app selected — select one in the Listing tab."


class ApkExtractionPanel(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.viewmodel = ApkExtractionViewModel(context)
        self._current_package = None
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.acting_on_label = QLabel(_NO_SELECTION_TEXT)
        layout.addWidget(self.acting_on_label)

        self.files_list = QListWidget()
        layout.addWidget(self.files_list)

        row = QHBoxLayout()
        self.extract_button = QPushButton("Extract APK...")
        self.extract_button.setEnabled(False)
        row.addWidget(self.extract_button)
        row.addStretch()
        layout.addLayout(row)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def _connect(self):
        self.extract_button.clicked.connect(self._on_extract)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.apkInfoChanged.connect(self._on_apk_info)
        self.viewmodel.extractionFinished.connect(self._on_extraction_finished)
        self.viewmodel.logMessage.connect(self._on_log_message)

    def set_current_app(self, package):
        self._current_package = package or None
        self.viewmodel.set_current_app(self._current_package)

    def _on_apk_info(self, info):
        self.files_list.clear()
        if info is None:
            self.acting_on_label.setText(_NO_SELECTION_TEXT)
            self.extract_button.setEnabled(False)
            return
        self.acting_on_label.setText(f"Acting on: {self._current_package} (total {info['total_size_str']})")
        for file_entry in info["files"]:
            self.files_list.addItem(f"{file_entry['path']} ({file_entry['size_str']})")
        self.extract_button.setEnabled(True)

    def _on_extract(self):
        if self._current_package is None:
            return
        dest_dir = QFileDialog.getExistingDirectory(self, "Select destination folder")
        if not dest_dir:
            return
        self.viewmodel.extract(dest_dir)

    def _on_extraction_finished(self, pulled_paths):
        self.status_label.setText(f"Extracted {len(pulled_paths)} file(s).")

    def _on_log_message(self, message, level):
        self.status_label.setText(message)

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.extract_button.setEnabled(not busy and self._current_package is not None)
