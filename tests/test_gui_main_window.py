"""Tests for droidbridge.gui.main_window.MainWindow (Phase 6.1)."""

from unittest.mock import MagicMock

from PyQt6.QtGui import QCloseEvent

from droidbridge.gui import theme
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.main_window import MODULES, MainWindow
from droidbridge.gui.pages.files import FilesPage
from droidbridge.gui.pages.placeholder import PlaceholderPage
from droidbridge.gui.pages.search import SearchPage
from droidbridge.gui.pages.transfer import TransferPage


class TestMainWindow:
    def test_sidebar_lists_all_9_modules(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        assert window.sidebar.count() == 9
        labels = [window.sidebar.item(i).text() for i in range(9)]
        assert labels == MODULES

    def test_selecting_sidebar_entry_switches_stack(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        window.sidebar.setCurrentRow(2)

        assert window.stack.currentIndex() == 2

    def test_initial_state_shows_disconnected(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        assert window.status_text.text() == "Disconnected"

    def test_connection_changed_updates_top_bar(self, qtbot):
        context = DeviceContext()
        window = MainWindow(context=context)
        qtbot.addWidget(window)

        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")

        assert window.status_text.text() == "Pixel 7 (SERIAL123)"

    def test_log_message_appends_to_log_panel(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        window.device_viewmodel.logMessage.emit("hello world", "INFO")

        assert "hello world" in window.log_panel.toPlainText()

    def test_log_panel_toggle_action_hides_and_shows_panel(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.log_panel_action.setChecked(False)
        assert window.log_panel.isVisible() is False

        window.log_panel_action.setChecked(True)
        assert window.log_panel.isVisible() is True

    def test_busy_changed_shows_and_hides_progress_bar(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.device_viewmodel.busyChanged.emit(True)
        assert window.busy_bar.isVisible() is True

        window.device_viewmodel.busyChanged.emit(False)
        assert window.busy_bar.isVisible() is False

    def test_busy_bar_stays_visible_while_another_viewmodel_is_still_busy(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        # Search starts a long-running operation.
        window.search_viewmodel.busyChanged.emit(True)
        assert window.busy_bar.isVisible() is True

        # Device's auto-refresh fires and finishes while Search is still busy.
        window.device_viewmodel.busyChanged.emit(True)
        window.device_viewmodel.busyChanged.emit(False)

        assert window.busy_bar.isVisible() is True

        # Once Search also finishes, the bar hides.
        window.search_viewmodel.busyChanged.emit(False)
        assert window.busy_bar.isVisible() is False

    def test_busy_changed_disables_connect_button(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        window.device_viewmodel.busyChanged.emit(True)
        assert window.connect_button.isEnabled() is False

        window.device_viewmodel.busyChanged.emit(False)
        assert window.connect_button.isEnabled() is True

    def test_dark_theme_toggle_applies_and_saves_pref(self, qtbot, monkeypatch):
        applied = []
        saved = []
        monkeypatch.setattr(theme, "load_theme_pref", lambda: theme.LIGHT)
        monkeypatch.setattr(theme, "apply_theme", lambda app, mode: applied.append(mode))
        monkeypatch.setattr(theme, "save_theme_pref", lambda mode: saved.append(mode))

        window = MainWindow()
        qtbot.addWidget(window)
        window.dark_theme_action.setChecked(True)

        assert applied == [theme.DARK]
        assert saved == [theme.DARK]

    def test_close_event_writes_session_summary(self, qtbot):
        session_logger = MagicMock()
        window = MainWindow(session_logger=session_logger)
        qtbot.addWidget(window)

        window.closeEvent(QCloseEvent())

        session_logger.write_summary.assert_called_once()


class TestNewPages:
    def test_sidebar_indices_1_2_3_are_real_pages(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        assert isinstance(window.stack.widget(1), FilesPage)
        assert isinstance(window.stack.widget(2), TransferPage)
        assert isinstance(window.stack.widget(3), SearchPage)

    def test_remaining_modules_are_placeholders(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        for i in range(4, 9):
            assert isinstance(window.stack.widget(i), PlaceholderPage)


class TestPullRequestedWiring:
    def test_files_pull_requested_switches_to_transfer_and_pulls(self, qtbot, monkeypatch):
        window = MainWindow()
        qtbot.addWidget(window)

        calls = []
        monkeypatch.setattr(window.transfer_viewmodel, "pull_selected", lambda paths, d: calls.append((paths, d)))

        window.files_page.pullRequested.emit(["/sdcard/a.jpg"], "/tmp/out")

        assert calls == [(["/sdcard/a.jpg"], "/tmp/out")]
        assert window.sidebar.currentRow() == 2

    def test_search_pull_requested_switches_to_transfer_and_pulls(self, qtbot, monkeypatch):
        window = MainWindow()
        qtbot.addWidget(window)

        calls = []
        monkeypatch.setattr(window.transfer_viewmodel, "pull_selected", lambda paths, d: calls.append((paths, d)))

        window.search_page.pullRequested.emit(["/sdcard/b.jpg"], "/tmp/out2")

        assert calls == [(["/sdcard/b.jpg"], "/tmp/out2")]
        assert window.sidebar.currentRow() == 2


class TestNewViewModelWiring:
    def test_files_log_message_appends_to_log_panel(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        window.files_viewmodel.logMessage.emit("files hello", "INFO")

        assert "files hello" in window.log_panel.toPlainText()

    def test_transfer_busy_changed_shows_progress_bar(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.transfer_viewmodel.busyChanged.emit(True)
        assert window.busy_bar.isVisible() is True

        window.transfer_viewmodel.busyChanged.emit(False)
        assert window.busy_bar.isVisible() is False

    def test_search_status_changed_updates_status_bar(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        window.search_viewmodel.statusChanged.emit("search error")

        assert window.statusBar().currentMessage() == "search error"
