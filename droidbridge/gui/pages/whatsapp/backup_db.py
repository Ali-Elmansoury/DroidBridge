from PyQt6.QtWidgets import QWidget
from droidbridge.gui.viewmodels.whatsapp.backup_db import BackupDbViewModel


class BackupDbPanel(QWidget):
    def __init__(self, context, get_app, parent=None):
        super().__init__(parent)
        self.viewmodel = BackupDbViewModel(context)
