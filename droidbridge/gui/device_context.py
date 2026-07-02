# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Shared connection state for the GUI (Phase 6.1): the current AdbClient/serial/model,
plus a signal so any page can react to connection changes.
"""

from PyQt6.QtCore import QObject, pyqtSignal


class DeviceContext(QObject):
    """Holds the current AdbClient/serial/model, shared across all pages/ViewModels."""

    connectionChanged = pyqtSignal(bool, str, str)  # connected, serial, model

    def __init__(self):
        super().__init__()
        self.client = None
        self.serial = None
        self.model = None

    @property
    def is_connected(self):
        return self.client is not None

    def set_connected(self, client, serial, model):
        self.client = client
        self.serial = serial
        self.model = model
        self.connectionChanged.emit(True, serial, model)

    def clear(self):
        self.client = None
        self.serial = None
        self.model = None
        self.connectionChanged.emit(False, "", "")
