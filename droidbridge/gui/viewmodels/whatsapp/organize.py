from PyQt6.QtCore import QObject, pyqtSignal


class OrganizeViewModel(QObject):
    statusChanged = pyqtSignal(str)
    resultsChanged = pyqtSignal(list)
    busyChanged = pyqtSignal(bool)
    logMessage = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
