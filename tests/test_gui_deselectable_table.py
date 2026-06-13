"""Tests for droidbridge.gui.widgets.deselectable_table.DeselectableTableWidget."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem

from droidbridge.gui.widgets.deselectable_table import DeselectableTableWidget


def _make_table(qtbot, rows=3):
    table = DeselectableTableWidget(rows, 1)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    for row in range(rows):
        table.setItem(row, 0, QTableWidgetItem(f"row{row}"))
    qtbot.addWidget(table)
    table.resize(200, 200)
    table.show()
    return table


def _click_row(qtbot, table, row):
    rect = table.visualRect(table.model().index(row, 0))
    qtbot.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())


class TestDeselectableTableWidget:
    def test_clicking_selected_row_deselects_it(self, qtbot):
        table = _make_table(qtbot)

        _click_row(qtbot, table, 0)
        assert {i.row() for i in table.selectedIndexes()} == {0}

        _click_row(qtbot, table, 0)
        assert table.selectedIndexes() == []

    def test_clicking_different_row_selects_only_that_row(self, qtbot):
        table = _make_table(qtbot)

        _click_row(qtbot, table, 0)
        _click_row(qtbot, table, 1)

        assert {i.row() for i in table.selectedIndexes()} == {1}
