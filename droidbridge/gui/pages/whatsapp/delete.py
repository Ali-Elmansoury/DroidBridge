from PyQt6.QtWidgets import QWidget
from droidbridge.gui.viewmodels.whatsapp.delete import DeleteViewModel


class DeletePanel(QWidget):
    def __init__(self, context, get_app, parent=None):
        super().__init__(parent)
        self.viewmodel = DeleteViewModel(context)
