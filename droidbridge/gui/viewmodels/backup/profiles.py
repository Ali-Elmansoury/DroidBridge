# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import backup_ops


class ProfilesViewModel(QObject):
    profilesChanged = pyqtSignal(list)
    statusChanged = pyqtSignal(str)
    logMessage = pyqtSignal(str, str)

    def refresh(self):
        profiles = backup_ops.list_profiles()
        self.profilesChanged.emit(profiles)
        return profiles

    def get(self, name):
        return backup_ops.get_profile(name)

    def save(self, name, sources, dest, conflict, excludes):
        backup_ops.save_profile(name, sources, dest, conflict, excludes)
        message = f"Saved profile {name!r}."
        self.statusChanged.emit(message)
        self.logMessage.emit(message, "INFO")
        self.refresh()

    def remove(self, name):
        removed = backup_ops.remove_profile(name)
        if removed:
            message = f"Removed profile {name!r}."
            self.logMessage.emit(message, "INFO")
        else:
            message = f"Profile {name!r} not found."
            self.logMessage.emit(message, "ERROR")
        self.statusChanged.emit(message)
        self.refresh()
