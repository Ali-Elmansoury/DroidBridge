from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import backup_ops


class HistoryViewModel(QObject):
    historyChanged = pyqtSignal(dict)

    def refresh(self, profile_name=None, max_age_days=7):
        result = backup_ops.get_history(profile_name, max_age_days)
        self.historyChanged.emit(result)
        return result
