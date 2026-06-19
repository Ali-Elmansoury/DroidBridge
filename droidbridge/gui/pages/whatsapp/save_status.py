from PyQt6.QtWidgets import QWidget
from droidbridge.gui.viewmodels.whatsapp.save_status import SaveStatusViewModel


class SaveStatusPanel(QWidget):
    def __init__(self, context, get_app, parent=None):
        super().__init__(parent)
        self.viewmodel = SaveStatusViewModel(context)
