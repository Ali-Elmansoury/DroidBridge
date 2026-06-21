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

    def test_wrap_mode_shows_full_text_even_when_narrow(self, qtbot):
        label = ElidedLabel()
        qtbot.addWidget(label)
        label.resize(60, 20)

        long_text = "adb command failed (...): error: device '26597aca' not found"
        label.setFullText(long_text)
        assert "…" in label.text()

        label.setWrapMode(True)
        assert label.text() == long_text
        assert label.wordWrap() is True

    def test_disabling_wrap_mode_restores_eliding(self, qtbot):
        label = ElidedLabel()
        qtbot.addWidget(label)
        label.resize(60, 20)

        long_text = "adb command failed (...): error: device '26597aca' not found"
        label.setFullText(long_text)
        label.setWrapMode(True)

        label.setWrapMode(False)

        assert label.text() != long_text
        assert "…" in label.text()
        assert label.wordWrap() is False

    def test_wrap_mode_grows_height_then_shrinks_back_when_disabled(self, qtbot):
        """A QStatusBar's QHBoxLayout doesn't re-run heightForWidth() against the
        label's actual allocated width, so leaving Qt to size the label
        automatically produced an oversized box that never shrank back once
        unwrapped - the height must be set explicitly, both ways."""
        label = ElidedLabel()
        qtbot.addWidget(label)
        label.show()
        label.resize(150, 20)

        long_text = "Device denied access to content://call_log/calls: " + "x " * 50
        label.setFullText(long_text)
        label.setWrapMode(True)

        assert label.height() > label._single_line_height

        label.setWrapMode(False)

        assert label.height() == label._single_line_height

    def test_wrap_mode_height_is_capped(self, qtbot):
        """A very long message at a narrow width shouldn't take over the window -
        capped to a fixed number of lines, with the rest reachable via tooltip."""
        label = ElidedLabel()
        qtbot.addWidget(label)
        label.show()
        label.resize(60, 20)

        long_text = "x " * 500
        label.setFullText(long_text)
        label.setWrapMode(True)

        assert label.height() <= label._single_line_height * ElidedLabel._MAX_WRAP_LINES
