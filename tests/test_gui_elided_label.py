"""Tests for droidbridge.gui.widgets.elided_label.ElidedLabel (Phase 6.2 follow-up)."""

from droidbridge.gui.widgets.elided_label import ElidedLabel


class TestElidedLabel:
    def test_short_text_displayed_in_full(self, qtbot):
        label = ElidedLabel()
        qtbot.addWidget(label)
        label.resize(300, 20)

        label.setFullText("Ready")

        assert label.text() == "Ready"
        assert label.toolTip() == "Ready"

    def test_long_text_is_elided_to_fit_narrow_width(self, qtbot):
        label = ElidedLabel()
        qtbot.addWidget(label)
        label.resize(60, 20)

        long_text = "adb command failed (...): error: device '26597aca' not found"
        label.setFullText(long_text)

        assert label.text() != long_text
        assert "…" in label.text()  # ellipsis character

    def test_tooltip_always_shows_full_text(self, qtbot):
        label = ElidedLabel()
        qtbot.addWidget(label)
        label.resize(60, 20)

        long_text = "adb command failed (...): error: device '26597aca' not found"
        label.setFullText(long_text)

        assert label.toolTip() == long_text

    def test_resizing_wider_shows_more_text(self, qtbot):
        label = ElidedLabel()
        qtbot.addWidget(label)
        label.show()
        label.resize(60, 20)

        long_text = "adb command failed (...): error: device '26597aca' not found"
        label.setFullText(long_text)
        narrow_text = label.text()

        label.resize(2000, 20)

        assert label.text() == long_text
        assert label.text() != narrow_text

