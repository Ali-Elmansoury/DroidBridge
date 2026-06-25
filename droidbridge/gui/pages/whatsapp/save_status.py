import os
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget, QLineEdit,
)
from droidbridge.gui.viewmodels.whatsapp.save_status import SaveStatusViewModel

_IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}
_VIDEO_EXTS = {"mp4", "3gp", "mkv", "avi", "mov"}
_THUMB_SIZE = 120
_GRID_COLS = 4


class SaveStatusPanel(QWidget):
    def __init__(self, context, get_app, parent=None):
        super().__init__(parent)
        self._get_app = get_app
        self._checkboxes = []
        self._items = []
        self.viewmodel = SaveStatusViewModel(context)
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Destination:"))
        self.dest_edit = QLineEdit()
        self.dest_edit.setToolTip("Local directory to save selected status files.")
        dest_row.addWidget(self.dest_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_dest)
        dest_row.addWidget(browse_btn)
        layout.addLayout(dest_row)

        btn_row = QHBoxLayout()
        self.load_button = QPushButton("Load Statuses")
        btn_row.addWidget(self.load_button)
        self.save_button = QPushButton("Save Selected")
        self.save_button.setEnabled(False)
        btn_row.addWidget(self.save_button)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        grid_widget = QWidget()
        self._grid_layout = QGridLayout(grid_widget)
        self._grid_layout.setSpacing(8)
        self._grid_layout.setContentsMargins(8, 8, 8, 8)
        scroll.setWidget(grid_widget)
        layout.addWidget(scroll)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _connect(self):
        self.load_button.clicked.connect(self._on_load)
        self.save_button.clicked.connect(self._on_save)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.resultsChanged.connect(self._populate_grid)
        self.viewmodel.progressChanged.connect(self._on_progress)

    def _browse_dest(self):
        path = QFileDialog.getExistingDirectory(self, "Select destination directory")
        if path:
            self.dest_edit.setText(path)

    def _on_load(self):
        self.viewmodel.load_statuses(self._get_app())

    def _on_save(self):
        remote_paths = [
            self._items[i]["remote_path"]
            for i, cb in enumerate(self._checkboxes)
            if cb.isChecked()
        ]
        self.viewmodel.save_selected(self._get_app(), self.dest_edit.text(), remote_paths, "skip", False)

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.load_button.setEnabled(not busy)

    def _on_progress(self, done, total):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)

    def _populate_grid(self, items):
        self._items = items
        self._checkboxes = []
        while self._grid_layout.count():
            child = self._grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for idx, item in enumerate(items):
            cell = QFrame()
            cell.setFrameShape(QFrame.Shape.StyledPanel)
            cell.setFrameShadow(QFrame.Shadow.Raised)
            cell_layout = QVBoxLayout(cell)
            cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            thumb = QLabel()
            thumb.setFixedSize(_THUMB_SIZE, _THUMB_SIZE)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ext = item["extension"].lower()
            thumb_src = None
            if ext in _IMAGE_EXTS and os.path.exists(item["local_path"]):
                thumb_src = item["local_path"]
            elif item.get("thumb_path") and os.path.exists(item["thumb_path"]):
                thumb_src = item["thumb_path"]
            if thumb_src:
                pix = QPixmap(thumb_src).scaled(
                    _THUMB_SIZE, _THUMB_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                thumb.setPixmap(pix)
            else:
                thumb.setText("▶" if ext in _VIDEO_EXTS else "?")
            cell_layout.addWidget(thumb)

            name_label = QLabel(item["filename"])
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.addWidget(name_label)

            cb = QCheckBox()
            cb.setToolTip(f"Select {item['filename']} for saving.")
            cb.stateChanged.connect(self._update_save_button)
            self._checkboxes.append(cb)
            cell_layout.addWidget(cb)

            row, col = divmod(idx, _GRID_COLS)
            self._grid_layout.addWidget(cell, row, col)

        self._update_save_button()

    def _update_save_button(self):
        self.save_button.setEnabled(any(cb.isChecked() for cb in self._checkboxes))
