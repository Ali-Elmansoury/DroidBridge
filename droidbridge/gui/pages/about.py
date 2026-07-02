# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""About page — project info and developer contact details."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

_VERSION = "1.0.0"
_LICENSE = "Source-Available — Free for personal use"
_GITHUB  = "https://github.com/Ali-Elmansoury"
_LINKEDIN = "https://www.linkedin.com/in/ali-elmansoury/"
_EMAIL   = "ali.elmansoury21@gmail.com"

_REPO    = "https://github.com/Ali-Elmansoury/DroidBridge"


def _font(size_pt: int, bold: bool = False) -> QFont:
    f = QFont()
    f.setPointSize(size_pt)
    if bold:
        f.setBold(True)
    return f


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(_font(12, bold=True))
    lbl.setStyleSheet("color: #2E75B6; margin-top: 12px;")
    return lbl


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


def _row(label_text: str, value_text: str, is_link: bool = False) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 2, 0, 2)
    lay.setSpacing(12)

    lbl = QLabel(label_text + ":")
    lbl.setFixedWidth(100)
    lbl.setFont(_font(11, bold=True))
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    if is_link:
        val = QLabel(f'<a href="{value_text}" style="color: #2E75B6;">{value_text}</a>')
        val.setOpenExternalLinks(True)
    else:
        val = QLabel(value_text)
    val.setFont(_font(11))
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
        title.setFont(_font(28, bold=True))
        title.setStyleSheet("color: #2E75B6;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        tagline = QLabel("ADB-Powered Android Device Management Tool")
        tagline.setFont(_font(12))
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(tagline)

        lay.addSpacing(2)

        ver_lbl = QLabel(f"Version {_VERSION}  ·  {_LICENSE}")
        ver_lbl.setFont(_font(10))
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ver_lbl)

        lay.addSpacing(6)
        lay.addWidget(_divider())

        # ── Description ────────────────────────────────────────────────
        lay.addWidget(_section_label("About"))
        lay.addSpacing(4)
        desc = QLabel(
            "DroidBridge is a source-available, cross-platform desktop tool for managing "
            "Android devices via ADB. It provides significantly faster file transfers "
            "than standard MTP, intelligent media analysis and organization, a complete "
            "WhatsApp backup and cleanup toolkit, app management, and rich report "
            "generation — all without requiring internet access or cloud services."
        )
        desc.setFont(_font(11))
        desc.setWordWrap(True)
        lay.addWidget(desc)

        lay.addSpacing(4)
        lay.addWidget(_divider())

        # ── Project links ──────────────────────────────────────────────
        lay.addWidget(_section_label("Project"))
        lay.addWidget(_row("Source code", _REPO, is_link=True))
        lay.addWidget(_row("Issues", _REPO + "/issues", is_link=True))
        lay.addWidget(_row("License", "Proprietary source-available · Free for personal use · Commercial license required for business use"))

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
        lay.addSpacing(4)
        stack_lbl = QLabel(
            "Python 3.10+ · PyQt6 · Click · ADB (Google platform-tools v37) · "
            "PyInstaller · SQLite · Jinja2"
        )
        stack_lbl.setFont(_font(11))
        stack_lbl.setWordWrap(True)
        lay.addWidget(stack_lbl)

        lay.addStretch()
