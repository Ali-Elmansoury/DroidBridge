# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""QTableWidget that lets the user click an already-selected single row to
deselect it (Qt's default click-to-select has no toggle-off)."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTableWidget


class DeselectableTableWidget(QTableWidget):
    def mousePressEvent(self, event):
        index = self.indexAt(event.pos())
        selected_rows = self.selectionModel().selectedRows()
        was_sole_selection = (
            index.isValid()
            and len(selected_rows) == 1
            and selected_rows[0].row() == index.row()
        )

        super().mousePressEvent(event)

        no_modifiers = event.modifiers() == Qt.KeyboardModifier.NoModifier
        if (
            was_sole_selection
            and event.button() == Qt.MouseButton.LeftButton
            and no_modifiers
        ):
            self.clearSelection()
