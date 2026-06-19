from PyQt6.QtWidgets import QWidget
from droidbridge.gui.viewmodels.whatsapp.restore import RestoreViewModel


class RestorePanel(QWidget):
    def __init__(self, context, get_app, parent=None):
        super().__init__(parent)
        self.viewmodel = RestoreViewModel(context)
