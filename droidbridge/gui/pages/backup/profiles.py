# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget,
)

from droidbridge.gui import files_ops
from droidbridge.gui.viewmodels.backup.profiles import ProfilesViewModel
from droidbridge.gui.widgets.remote_browse_dialog import RemoteBrowseDialog

_CONFLICT_OPTIONS = ["skip", "overwrite", "rename"]


class ProfilesPanel(QWidget):
    def __init__(self, context, on_profiles_changed=None, parent=None):
        super().__init__(parent)
        self._context = context
        self.viewmodel = ProfilesViewModel()
        self._on_profiles_changed = on_profiles_changed
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Saved profiles:"))
        self.profile_list = QListWidget()
        self.profile_list.setToolTip("Select a saved profile to load it for editing.")
        layout.addWidget(self.profile_list)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setToolTip("Name for this backup profile.")
        name_row.addWidget(self.name_edit)
        layout.addLayout(name_row)

        layout.addWidget(QLabel("Sources:"))
        self.sources_list = QListWidget()
        self.sources_list.setToolTip("Device paths included in this profile's backup.")
        layout.addWidget(self.sources_list)
        sources_btn_row = QHBoxLayout()
        self.add_source_button = QPushButton("Add Source…")
        self.add_source_button.setToolTip("Browse the device and add a path to back up.")
        self.remove_source_button = QPushButton("Remove Selected Source")
        self.remove_source_button.setToolTip("Remove the selected source from this profile.")
        sources_btn_row.addWidget(self.add_source_button)
        sources_btn_row.addWidget(self.remove_source_button)
        layout.addLayout(sources_btn_row)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Destination:"))
        self.dest_edit = QLineEdit()
        self.dest_edit.setToolTip("Local folder on your computer where this profile's backups are stored.")
        dest_row.addWidget(self.dest_edit)
        self.browse_dest_button = QPushButton("Browse…")
        self.browse_dest_button.setToolTip("Browse your computer for a backup destination folder.")
        dest_row.addWidget(self.browse_dest_button)
        layout.addLayout(dest_row)

        conflict_row = QHBoxLayout()
        conflict_row.addWidget(QLabel("Conflict:"))
        self.conflict_combo = QComboBox()
        self.conflict_combo.addItems(_CONFLICT_OPTIONS)
        self.conflict_combo.setToolTip("How to handle files that already exist at the destination when running a backup.")
        conflict_row.addWidget(self.conflict_combo)
        conflict_row.addStretch()
        layout.addLayout(conflict_row)

        layout.addWidget(QLabel("Excludes:"))
        self.excludes_list = QListWidget()
        self.excludes_list.setToolTip("Device paths excluded from this profile's backup.")
        layout.addWidget(self.excludes_list)
        excludes_btn_row = QHBoxLayout()
        self.add_exclude_button = QPushButton("Add Exclude…")
        self.add_exclude_button.setToolTip("Browse the device and add a path to exclude from the backup.")
        self.remove_exclude_button = QPushButton("Remove Selected Exclude")
        self.remove_exclude_button.setToolTip("Remove the selected exclude from this profile.")
        excludes_btn_row.addWidget(self.add_exclude_button)
        excludes_btn_row.addWidget(self.remove_exclude_button)
        layout.addLayout(excludes_btn_row)

        action_row = QHBoxLayout()
        self.save_button = QPushButton("Save Profile")
        self.save_button.setToolTip("Save this profile under the given name.")
        self.remove_button = QPushButton("Remove Profile")
        self.remove_button.setToolTip("Delete the selected saved profile.")
        action_row.addWidget(self.save_button)
        action_row.addWidget(self.remove_button)
        layout.addLayout(action_row)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch()

    def _connect(self):
        self.add_source_button.clicked.connect(lambda: self._add_device_path(self.sources_list))
        self.remove_source_button.clicked.connect(lambda: self._remove_selected(self.sources_list))
        self.browse_dest_button.clicked.connect(self._browse_dest)
        self.add_exclude_button.clicked.connect(lambda: self._add_device_path(self.excludes_list))
        self.remove_exclude_button.clicked.connect(lambda: self._remove_selected(self.excludes_list))
        self.save_button.clicked.connect(self._on_save)
        self.remove_button.clicked.connect(self._on_remove)
        self.profile_list.currentTextChanged.connect(self._on_profile_selected)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.profilesChanged.connect(self._on_profiles_changed_internal)

    def _add_device_path(self, list_widget):
        client, serial = self._context.client, self._context.serial
        path = RemoteBrowseDialog.get_remote_path(
            self, client, serial, files_ops.QUICK_JUMP_PATHS["Root"], mode="directory"
        )
        if path:
            list_widget.addItem(path)

    def _remove_selected(self, list_widget):
        row = list_widget.currentRow()
        if row >= 0:
            list_widget.takeItem(row)

    def _browse_dest(self):
        path = QFileDialog.getExistingDirectory(self, "Select backup destination")
        if path:
            self.dest_edit.setText(path)

    def _on_profile_selected(self, name):
        if not name:
            return
        profile = self.viewmodel.get(name)
        if profile is None:
            return
        self.name_edit.setText(profile.name)
        self.sources_list.clear()
        self.sources_list.addItems(profile.sources)
        self.dest_edit.setText(profile.dest)
        self.conflict_combo.setCurrentText(profile.conflict)
        self.excludes_list.clear()
        self.excludes_list.addItems(profile.excludes)

    def _on_save(self):
        sources = [self.sources_list.item(i).text() for i in range(self.sources_list.count())]
        excludes = [self.excludes_list.item(i).text() for i in range(self.excludes_list.count())]
        self.viewmodel.save(self.name_edit.text(), sources, self.dest_edit.text(), self.conflict_combo.currentText(), excludes)

    def _on_remove(self):
        item = self.profile_list.currentItem()
        name = item.text() if item else self.name_edit.text()
        if name:
            self.viewmodel.remove(name)

    def refresh(self):
        self.viewmodel.refresh()

    def _on_profiles_changed_internal(self, profiles):
        self.profile_list.clear()
        self.profile_list.addItems([p.name for p in profiles])
        if self._on_profiles_changed:
            self._on_profiles_changed([p.name for p in profiles])
