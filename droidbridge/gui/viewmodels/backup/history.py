from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import backup_ops


class HistoryViewModel(QObject):
    busyChanged = pyqtSignal(bool)
    statusChanged = pyqtSignal(str)
    historyChanged = pyqtSignal(dict)
    logMessage = pyqtSignal(str, str)

    def refresh(self, profile_name=None, max_age_days=7):
        result = backup_ops.get_history(profile_name, max_age_days)
        self.historyChanged.emit(result)
        return result
