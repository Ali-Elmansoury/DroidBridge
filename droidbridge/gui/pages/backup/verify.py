from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from droidbridge.gui.viewmodels.backup.verify import VerifyViewModel


class VerifyPanel(QWidget):
    def __init__(self, get_profile, parent=None):
        super().__init__(parent)
        self._get_profile = get_profile
        self.viewmodel = VerifyViewModel()
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.verify_button = QPushButton("Verify")
        btn_row.addWidget(self.verify_button)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.result_label = QLabel()
        layout.addWidget(self.result_label)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        layout.addStretch()

    def _connect(self):
        self.verify_button.clicked.connect(self._on_verify)
        self.viewmodel.busyChanged.connect(lambda busy: self.verify_button.setEnabled(not busy))
        self.viewmodel.resultChanged.connect(self._on_result)
        self.viewmodel.statusChanged.connect(self.status_label.setText)

    def _on_verify(self):
        self.viewmodel.run_verify(self._get_profile())

    def _on_result(self, result):
        self.result_label.setText(
            f"Expected: {result['expected_files']} files / {result['expected_bytes']} bytes — "
            f"Actual: {result['actual_files']} files / {result['actual_bytes']} bytes"
        )
