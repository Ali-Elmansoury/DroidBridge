from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from droidbridge.gui.viewmodels.backup.run import RunViewModel


class RunPanel(QWidget):
    def __init__(self, context, get_profile, parent=None):
        super().__init__(parent)
        self._get_profile = get_profile
        self.viewmodel = RunViewModel(context)
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.no_verify_checkbox = QCheckBox("Skip verification")
        self.no_verify_checkbox.setToolTip("Skip confirming every pulled file matches the device original by size.")
        layout.addWidget(self.no_verify_checkbox)

        btn_row = QHBoxLayout()
        self.run_button = QPushButton("Run Backup")
        btn_row.addWidget(self.run_button)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel()
        layout.addWidget(self.progress_label)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        layout.addStretch()

    def _connect(self):
        self.run_button.clicked.connect(self._on_run)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.progressChanged.connect(self._on_progress)

    def _on_run(self):
        self.viewmodel.run_backup(self._get_profile(), self.no_verify_checkbox.isChecked())

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.run_button.setEnabled(not busy)

    def _on_progress(self, done, total):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        self.progress_label.setText(f"{done} / {total} files")
