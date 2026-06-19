from PyQt6.QtWidgets import QWidget
from droidbridge.gui.viewmodels.whatsapp.analyze import AnalyzeViewModel


class AnalyzePanel(QWidget):
    def __init__(self, context, get_app, parent=None):
        super().__init__(parent)
        self.viewmodel = AnalyzeViewModel(context)
