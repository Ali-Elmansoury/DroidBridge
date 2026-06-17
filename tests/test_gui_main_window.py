"""Tests for droidbridge.gui.main_window.MainWindow (Phase 6.1)."""

from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
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

        assert window.status_label.fullText() == "search error"


class TestStatusBarLayout:
    """The status bar has two dedicated areas - a flexible status label on the
    left and a fixed-width progress bar on the right - so a long status
    message can never overlap the progress bar (it elides instead).
    """

    def test_status_label_shows_ready_when_idle(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        assert window.status_label.fullText() == "Ready"

    def test_status_changed_clears_back_to_ready(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        window.device_viewmodel.statusChanged.emit("device not found")
        assert window.status_label.fullText() == "device not found"

        window.device_viewmodel.statusChanged.emit("")
        assert window.status_label.fullText() == "Ready"

    def test_busy_bar_has_a_fixed_width_separate_from_status_label(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        assert window.busy_bar.minimumWidth() == window.busy_bar.maximumWidth()
        assert window.busy_bar.maximumWidth() < 16777215  # not Qt's "unbounded" default


class TestMainWindowTooltips:
    def test_connect_button_has_tooltip(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        assert window.connect_button.toolTip() != ""

    def test_status_dot_has_tooltip(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        assert window.status_dot.toolTip() != ""

    def test_sidebar_items_have_tooltips(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        for i in range(window.sidebar.count()):
            assert window.sidebar.item(i).toolTip() != "", \
                f"Sidebar item {i} ({window.sidebar.item(i).text()!r}) has no tooltip"


class TestMainWindowShortcuts:
    def test_ctrl_1_switches_to_device_page(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()
        window.sidebar.setCurrentRow(2)

        qtbot.keyClick(window, Qt.Key.Key_1, Qt.KeyboardModifier.ControlModifier)

        assert window.sidebar.currentRow() == 0

    def test_ctrl_2_switches_to_files_page(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        qtbot.keyClick(window, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)

        assert window.sidebar.currentRow() == 1

    def test_ctrl_3_switches_to_transfer_page(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        qtbot.keyClick(window, Qt.Key.Key_3, Qt.KeyboardModifier.ControlModifier)

        assert window.sidebar.currentRow() == 2

    def test_ctrl_4_switches_to_search_page(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        qtbot.keyClick(window, Qt.Key.Key_4, Qt.KeyboardModifier.ControlModifier)

        assert window.sidebar.currentRow() == 3


class TestStatusBarColorCoding:
    def test_error_log_colors_status_bar_red(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        window._on_log_message("Something failed", "ERROR")

        assert "red" in window.status_label.styleSheet()

    def test_warning_log_colors_status_bar_orange(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        window._on_log_message("Something warned", "WARNING")

        assert "orange" in window.status_label.styleSheet()

    def test_info_log_does_not_color_status_bar(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        window._on_log_message("Normal operation", "INFO")

        assert window.status_label.styleSheet() == ""

    def test_error_sets_status_bar_text(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        window._on_log_message("Disk full", "ERROR")

        assert "Disk full" in window.status_label.text()

    def test_second_error_resets_color_timer(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        window._on_log_message("First error", "ERROR")
        window._on_log_message("Second error", "ERROR")

        # Timer should be running and have been restarted (remaining time ≤ 5000ms)
        assert window._status_color_timer.isActive()
        assert "red" in window.status_label.styleSheet()
