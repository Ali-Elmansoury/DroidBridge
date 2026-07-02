# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for BreadcrumbBar widget."""
import pytest
from PyQt6.QtWidgets import QPushButton


def _get_buttons(bar):
    """Return all QPushButton children in BreadcrumbBar's layout."""
    result = []
    for i in range(bar._layout.count()):
        widget = bar._layout.itemAt(i).widget()
        if isinstance(widget, QPushButton):
            result.append(widget)
    return result


class TestBreadcrumbBar:
    def test_set_path_creates_root_button(self, qapp):
        from droidbridge.gui.widgets.breadcrumb_bar import BreadcrumbBar
        bar = BreadcrumbBar()
        bar.set_path("/sdcard/DCIM")
        buttons = _get_buttons(bar)
        assert any(b.text() == "/" for b in buttons)

    def test_set_path_creates_segment_buttons(self, qapp):
        from droidbridge.gui.widgets.breadcrumb_bar import BreadcrumbBar
        bar = BreadcrumbBar()
        bar.set_path("/sdcard/DCIM")
        buttons = _get_buttons(bar)
        texts = [b.text() for b in buttons]
        assert "sdcard" in texts
        assert "DCIM" in texts

    def test_clicking_root_emits_slash(self, qapp):
        from droidbridge.gui.widgets.breadcrumb_bar import BreadcrumbBar
        bar = BreadcrumbBar()
        bar.set_path("/sdcard")
        received = []
        bar.pathRequested.connect(received.append)
        root_btn = next(b for b in _get_buttons(bar) if b.text() == "/")
        root_btn.click()
        assert received == ["/"]

    def test_clicking_segment_emits_cumulative_path(self, qapp):
        from droidbridge.gui.widgets.breadcrumb_bar import BreadcrumbBar
        bar = BreadcrumbBar()
        bar.set_path("/sdcard/DCIM/Camera")
        received = []
        bar.pathRequested.connect(received.append)
        sdcard_btn = next(b for b in _get_buttons(bar) if b.text() == "sdcard")
        sdcard_btn.click()
        assert received == ["/sdcard"]

    def test_clicking_last_segment_emits_full_path(self, qapp):
        from droidbridge.gui.widgets.breadcrumb_bar import BreadcrumbBar
        bar = BreadcrumbBar()
        bar.set_path("/sdcard/DCIM/Camera")
        received = []
        bar.pathRequested.connect(received.append)
        camera_btn = next(b for b in _get_buttons(bar) if b.text() == "Camera")
        camera_btn.click()
        assert received == ["/sdcard/DCIM/Camera"]

    def test_set_path_replaces_previous_content(self, qapp):
        from droidbridge.gui.widgets.breadcrumb_bar import BreadcrumbBar
        bar = BreadcrumbBar()
        bar.set_path("/sdcard/DCIM")
        bar.set_path("/sdcard/Download")
        texts = [b.text() for b in _get_buttons(bar)]
        assert "DCIM" not in texts
        assert "Download" in texts

    def test_root_only_path(self, qapp):
        from droidbridge.gui.widgets.breadcrumb_bar import BreadcrumbBar
        bar = BreadcrumbBar()
        bar.set_path("/")
        buttons = _get_buttons(bar)
        assert len(buttons) == 1
        assert buttons[0].text() == "/"
