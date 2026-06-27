"""About page — project info and developer contact details."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

_VERSION = "1.0.0"
_LICENSE = "MIT License"
_GITHUB  = "https://github.com/Ali-Elmansoury"
_LINKEDIN = "https://www.linkedin.com/in/ali-elmansoury/"
_EMAIL   = "ali.elmansoury21@gmail.com"

_REPO    = "https://github.com/Ali-Elmansoury/DroidBridge"


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #2E75B6; margin-top: 12px;")
    return lbl


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    line.setStyleSheet("color: #CCCCCC;")
    return line


def _row(label_text: str, value_text: str, is_link: bool = False) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 2, 0, 2)
    lay.setSpacing(12)

    lbl = QLabel(label_text + ":")
    lbl.setFixedWidth(90)
    lbl.setStyleSheet("font-weight: bold; color: palette(window-text);")
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    if is_link:
        val = QLabel(f'<a href="{value_text}" style="color: #2E75B6;">{value_text}</a>')
        val.setOpenExternalLinks(True)
    else:
        val = QLabel(value_text)
    val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    val.setWordWrap(True)

    lay.addWidget(lbl)
    lay.addWidget(val, 1)
    return w


class AboutPage(QWidget):
    """About page showing project description and developer contact info."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        lay = QVBoxLayout(content)
        lay.setContentsMargins(40, 30, 40, 30)
        lay.setSpacing(6)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ── Title ──────────────────────────────────────────────────────
        title = QLabel("DroidBridge")
        f = QFont()
        f.setPointSize(28)
        f.setBold(True)
        title.setFont(f)
        title.setStyleSheet("color: #2E75B6;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        tagline = QLabel("ADB-Powered Android Device Management Tool")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet("font-size: 13px; color: palette(window-text); margin-bottom: 4px;")
        lay.addWidget(tagline)

        ver_lbl = QLabel(f"Version {_VERSION}  ·  {_LICENSE}  ·  Open Source")
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver_lbl.setStyleSheet("font-size: 11px; color: palette(window-text); margin-bottom: 8px;")
        lay.addWidget(ver_lbl)

        lay.addWidget(_divider())

        # ── Description ────────────────────────────────────────────────
        lay.addWidget(_section_label("About"))
        desc = QLabel(
            "DroidBridge is an open-source, cross-platform desktop tool for managing "
            "Android devices via ADB. It provides significantly faster file transfers "
            "than standard MTP, intelligent media analysis and organization, a complete "
            "WhatsApp backup and cleanup toolkit, app management, and rich report "
            "generation — all without requiring internet access or cloud services."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 12px; color: palette(window-text); margin-top: 4px;")
        lay.addWidget(desc)

        lay.addWidget(_divider())

        # ── Project links ──────────────────────────────────────────────
        lay.addWidget(_section_label("Project"))
        lay.addWidget(_row("Source code", _REPO, is_link=True))
        lay.addWidget(_row("Issues", _REPO + "/issues", is_link=True))
        lay.addWidget(_row("License", "MIT — free for personal and commercial use"))

        lay.addWidget(_divider())

        # ── Developer ─────────────────────────────────────────────────
        lay.addWidget(_section_label("Developer"))
        lay.addWidget(_row("Name",     "Ali Elmansoury"))
        lay.addWidget(_row("Title",    "Junior Embedded Software / Android Automotive Engineer"))
        lay.addWidget(_row("Email",    _EMAIL,    is_link=True))
        lay.addWidget(_row("GitHub",   _GITHUB,   is_link=True))
        lay.addWidget(_row("LinkedIn", _LINKEDIN, is_link=True))

        lay.addWidget(_divider())

        # ── Tech stack quick-ref ───────────────────────────────────────
        lay.addWidget(_section_label("Built With"))
        stack_text = (
            "Python 3.10+ · PyQt6 · Click · ADB (Google platform-tools v37) · "
            "PyInstaller · SQLite · Jinja2"
        )
        stack_lbl = QLabel(stack_text)
        stack_lbl.setWordWrap(True)
        stack_lbl.setStyleSheet("font-size: 12px; color: palette(window-text); margin-top: 4px;")
        lay.addWidget(stack_lbl)

        lay.addStretch()
