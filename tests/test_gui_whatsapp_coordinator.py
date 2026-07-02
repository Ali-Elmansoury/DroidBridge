# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
import pytest
from pytestqt.qt_compat import qt_api
from unittest.mock import MagicMock
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.pages.whatsapp import WhatsAppPage


def _make_page():
    ctx = DeviceContext()
    page = WhatsAppPage(ctx)
    return page


class TestWhatsAppPage:
    def test_app_combo_has_three_items(self, qtbot):
        page = _make_page()
        qtbot.addWidget(page)
        assert page.app_combo.count() == 3

    def test_selected_app_returns_whatsapp_by_default(self, qtbot):
        page = _make_page()
        qtbot.addWidget(page)
        assert page.selected_app() == "whatsapp"

    def test_selected_app_returns_business_when_second_item(self, qtbot):
        page = _make_page()
        qtbot.addWidget(page)
        page.app_combo.setCurrentIndex(1)
        assert page.selected_app() == "business"

    def test_selected_app_returns_all_when_third_item(self, qtbot):
        page = _make_page()
        qtbot.addWidget(page)
        page.app_combo.setCurrentIndex(2)
        assert page.selected_app() == "all"

    def test_op_list_has_eight_items(self, qtbot):
        page = _make_page()
        qtbot.addWidget(page)
        assert page.op_list.count() == 8

    def test_op_list_switching_changes_stack_index(self, qtbot):
        page = _make_page()
        qtbot.addWidget(page)
        page.op_list.setCurrentRow(2)
        assert page.stack.currentIndex() == 2

    def test_viewmodels_property_returns_eight_entries(self, qtbot):
        page = _make_page()
        qtbot.addWidget(page)
        assert len(page.viewmodels) == 8
