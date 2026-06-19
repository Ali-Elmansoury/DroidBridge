from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout, QWidget, QLineEdit,
)
from droidbridge.gui.viewmodels.whatsapp.organize import OrganizeViewModel
from droidbridge.modules.whatsapp import ORGANIZE_DATE_TYPES

_TYPE_KEYS = list(ORGANIZE_DATE_TYPES.keys()) + ["documents"]


class OrganizePanel(QWidget):
    def __init__(self, get_app, parent=None):
        super().__init__(parent)
        self._get_app = get_app
        self.viewmodel = OrganizeViewModel()
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("Source:"))
        self.src_edit = QLineEdit()
        self.src_edit.setToolTip("Local backup folder to reorganize by date.")
        src_row.addWidget(self.src_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_src)
        src_row.addWidget(browse_btn)
        layout.addLayout(src_row)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.setToolTip("Media type determines the folder organization strategy.")
        self.type_combo.addItems(_TYPE_KEYS)
        type_row.addWidget(self.type_combo)
        type_row.addStretch()
        layout.addLayout(type_row)

        btn_row = QHBoxLayout()
        self.organize_button = QPushButton("Organize")
        btn_row.addWidget(self.organize_button)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        layout.addStretch()

    def _connect(self):
        self.organize_button.clicked.connect(self._on_organize)
        self.viewmodel.statusChanged.connect(self.status_label.setText)

    def _browse_src(self):
        path = QFileDialog.getExistingDirectory(self, "Select local backup folder")
        if path:
            self.src_edit.setText(path)

    def _on_organize(self):
        type_name = _TYPE_KEYS[self.type_combo.currentIndex()]
        self.viewmodel.organize(self.src_edit.text(), type_name)
