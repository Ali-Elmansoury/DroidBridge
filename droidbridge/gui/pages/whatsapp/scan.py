from PyQt6.QtWidgets import QWidget
from droidbridge.gui.viewmodels.whatsapp.scan import ScanViewModel


class ScanPanel(QWidget):
    def __init__(self, context, get_app, parent=None):
        super().__init__(parent)
        self.viewmodel = ScanViewModel(context)
