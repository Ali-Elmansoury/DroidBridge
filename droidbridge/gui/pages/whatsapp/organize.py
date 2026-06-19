from PyQt6.QtWidgets import QWidget
from droidbridge.gui.viewmodels.whatsapp.organize import OrganizeViewModel


class OrganizePanel(QWidget):
    def __init__(self, get_app, parent=None):
        super().__init__(parent)
        self.viewmodel = OrganizeViewModel()
