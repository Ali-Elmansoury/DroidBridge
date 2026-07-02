# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from PyQt6.QtCore import QObject, pyqtSignal
from droidbridge.gui import whatsapp_ops


class OrganizeViewModel(QObject):
    statusChanged = pyqtSignal(str)
    resultsChanged = pyqtSignal(list)
    busyChanged = pyqtSignal(bool)
    logMessage = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()

    def organize(self, src, type_name):
        self.logMessage.emit("Organizing...", "INFO")
        try:
            result = whatsapp_ops.run_organize(src, type_name)
            message = (
                f"Organized {result['organized']} file(s), fixed {result['fixed']} filename(s) → {result['dest']}"
            )
            self.statusChanged.emit(message)
            self.logMessage.emit(message, "INFO")
        except Exception as exc:
            self.statusChanged.emit(str(exc))
            self.logMessage.emit(str(exc), "ERROR")
