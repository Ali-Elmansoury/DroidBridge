from unittest.mock import MagicMock
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.pages.storage import StoragePage


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


def _make_page(qtbot):
    page = StoragePage(_connected_ctx())
    qtbot.addWidget(page)
    return page


class TestStoragePage:
    def test_op_list_has_five_items_in_order(self, qtbot):
        page = _make_page(qtbot)
        assert page.op_list.count() == 5
        labels = [page.op_list.item(i).text() for i in range(5)]
        assert labels == ["Overview", "Apps", "Media", "Large Files", "Cleanup"]

    def test_selecting_row_switches_stack(self, qtbot):
        page = _make_page(qtbot)
        page.op_list.setCurrentRow(2)
        assert page.stack.currentIndex() == 2

    def test_viewmodels_returns_five_entries_in_order(self, qtbot):
        page = _make_page(qtbot)
        assert len(page.viewmodels) == 5

    def test_default_selected_row_is_overview(self, qtbot):
        page = _make_page(qtbot)
        assert page.op_list.currentRow() == 0
        assert page.stack.currentIndex() == 0
