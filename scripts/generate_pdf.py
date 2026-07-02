#!/usr/bin/env python3
"""
Generate a styled PDF from any DroidBridge Markdown document.

Usage:
  python3 scripts/generate_pdf.py                          # project doc (default)
  python3 scripts/generate_pdf.py --input docs/USER_GUIDE.md --output docs/USER_GUIDE.pdf

Handles two Markdown layouts:
  • Frontmatter style  (project doc) — explicit preamble block before first ---
  • H1-only style      (user guide)  — title is the H1, no separate preamble

Dependencies:  pip3 install weasyprint markdown
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import markdown as _md_lib
    from weasyprint import CSS, HTML
except ImportError:
    print("Missing deps — run:  pip3 install weasyprint markdown")
    sys.exit(1)

ROOT    = Path(__file__).parent.parent
BLUE    = "#2E75B6"


def _get_app_version() -> str:
    """Return the latest git tag (vX.Y.Z → X.Y.Z), falling back to __init__.py."""
    import subprocess
    try:
        tag = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=ROOT, stderr=subprocess.DEVNULL,
        ).decode().strip().lstrip("v")
        if re.match(r"^\d+\.\d+\.\d+", tag):
            return tag
    except Exception:
        pass
    init = ROOT / "droidbridge" / "__init__.py"
    m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init.read_text(), re.MULTILINE)
    return m.group(1) if m else "1.0.0"


def _inject_version(md: str, version: str) -> str:
    return re.sub(
        r"^(Version\s+)\d+\.\d+\.\d+",
        rf"\g<1>{version}",
        md,
        count=1,
        flags=re.MULTILINE,
    )
NAVY    = "#1F497D"
CODE_BG = "#1E2D3D"
CODE_FG = "#E8EFF5"

# Tagline shared across all DroidBridge docs
_TAGLINE = "ADB-Powered Android Device Management Tool"


# ── parsed document ───────────────────────────────────────────────────────────

@dataclass
class _Doc:
    title:       str
    tagline:     str
    subtitle:    str
    version:     str
    body:        str   # markdown body (preamble stripped, manual TOC removed)
    footer_name: str   # e.g. "DroidBridge Project Document"


# ── helpers ───────────────────────────────────────────────────────────────────

def _heading_id(raw_html: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw_html)
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_]+", "-", text).strip("-").lower()


def _is_banner(text: str) -> bool:
    clean = re.sub(r"<[^>]+>", "", text)
    core  = clean.lstrip("0123456789. ").strip().lower()
    return core.startswith("module") or core.startswith("phase")


def _strip_manual_toc(md: str) -> str:
    """Remove a manually-written '## Table of Contents' section from markdown."""
    return re.sub(
        r"## Table of Contents\n(?:(?!## ).+\n?)*",
        "",
        md,
        flags=re.IGNORECASE,
    )


# ── step 1: parse document ────────────────────────────────────────────────────

def _parse_doc(md_path: Path) -> _Doc:
    text = md_path.read_text(encoding="utf-8")

    # ── Frontmatter style: first --- block contains a Version line ────────────
    # (project doc has "Version 1.0.0 | Released…" in the preamble;
    #  user guide and other docs do not)
    first_block = re.split(r"\n---\n", text, maxsplit=1)[0]
    is_frontmatter = bool(re.search(r"^Version\s", first_block, re.MULTILINE))

    if is_frontmatter:
        parts    = re.split(r"\n---\n", text, maxsplit=1)
        preamble = parts[0]
        body     = parts[1] if len(parts) > 1 else text
        title = tagline = subtitle = version = ""
        for line in preamble.splitlines():
            s = line.strip()
            if s.startswith("# ") and not title:
                halves  = s[2:].split(" — ", 1)
                title   = halves[0].strip()
                tagline = halves[1].strip() if len(halves) > 1 else _TAGLINE
            elif s.startswith("**") and not subtitle:
                # Only a bare **…** line (entire line is bold) counts as subtitle
                if re.match(r"^\*\*[^*]+\*\*$", s):
                    subtitle = s.strip("*").strip()
            elif re.match(r"Version\s", s) and not version:
                version = s
        tagline     = tagline or _TAGLINE
        # Footer: "<Title> Project Document" (short, filename-style)
        footer_name = f"{title} Project Document"
        return _Doc(title, tagline, subtitle, version, body, footer_name)

    # ── H1-only style (user guide, etc.): title is the H1 ────────────────────
    h1_match = re.search(r"^# (.+)$", text, re.MULTILINE)
    if h1_match:
        halves   = h1_match.group(1).split(" — ", 1)
        title    = halves[0].strip()
        subtitle = halves[1].strip() if len(halves) > 1 else ""
    else:
        title = subtitle = "DroidBridge"

    tagline     = _TAGLINE
    version     = "Version 1.0.0"
    footer_name = f"{title} {subtitle}" if subtitle else title

    # Remove H1 (moves to title page) and any manually-written TOC section
    body = re.sub(r"^# .+\n", "", text, count=1, flags=re.MULTILINE)
    body = _strip_manual_toc(body)

    return _Doc(title, tagline, subtitle, version, body, footer_name)


# ── step 2: markdown → html ───────────────────────────────────────────────────

def _md_to_html(md: str) -> str:
    obj = _md_lib.Markdown(
        extensions=["tables", "fenced_code", "nl2br"],
        extension_configs={"nl2br": {}},
    )
    return obj.convert(md)


# ── step 3: post-process html ─────────────────────────────────────────────────

def _post_process(html: str) -> tuple[str, list[tuple[int, str, str]]]:
    toc: list[tuple[int, str, str]] = []
    in_banner = False

    def replace_heading(m: re.Match) -> str:
        nonlocal in_banner
        level = int(m.group(1))
        inner = m.group(2)
        hid   = _heading_id(inner)
        plain = re.sub(r"<[^>]+>", "", inner).strip()

        if level in (2, 3, 4):
            toc.append((level, hid, plain))

        if level == 2:
            if _is_banner(inner):
                in_banner = True
                return f'<h{level} id="{hid}" class="banner">{inner}</h{level}>'
            in_banner = False
            return f'<h{level} id="{hid}">{inner}</h{level}>'
        elif level == 3:
            cls  = "banner-sub" if in_banner else ""
            attr = f' class="{cls}"' if cls else ""
            return f'<h{level} id="{hid}"{attr}>{inner}</h{level}>'
        return f'<h{level} id="{hid}">{inner}</h{level}>'

    html = re.sub(r"<h([2-5])>(.*?)</h\1>", replace_heading, html, flags=re.DOTALL)

    def classify_bq(m: re.Match) -> str:
        content = m.group(1)
        low     = re.sub(r"<[^>]+>", "", content).lower()
        if "important" in low:
            cls = "callout-important"
        elif any(k in low for k in ("note:", "recommendation", "recommended")):
            cls = "callout-note"
        else:
            cls = "callout-info"
        return f'<blockquote class="{cls}">{content}</blockquote>'

    html = re.sub(r"<blockquote>(.*?)</blockquote>", classify_bq, html, flags=re.DOTALL)
    return html, toc


# ── step 4: toc html ──────────────────────────────────────────────────────────

def _build_toc(entries: list[tuple[int, str, str]]) -> str:
    rows = []
    for level, hid, text in entries:
        indent = (level - 2) * 18
        rows.append(
            f'<div class="toc-row toc-l{level}" style="padding-left:{indent}pt">'
            f'<a class="toc-link" href="#{hid}">{text}</a>'
            f'<span class="toc-dots"></span>'
            f'<a class="toc-num" href="#{hid}"></a>'
            f'</div>'
        )
    return (
        '<div class="toc-page">'
        '<h1 class="toc-heading">Table of Contents</h1>'
        + "".join(rows)
        + "</div>"
    )


# ── step 5: title page html ───────────────────────────────────────────────────

def _build_title_page(doc: _Doc) -> str:
    ver_lines = "".join(
        f'<div class="ver-line">{v.strip()}</div>'
        for v in doc.version.split("|")
    ) if doc.version else ""
    return (
        '<div class="title-page">'
        f'<div class="app-name">{doc.title.upper()}</div>'
        f'<div class="app-tagline">{doc.tagline}</div>'
        f'<div class="blue-bar"></div>'
        f'<div class="doc-subtitle">{doc.subtitle}</div>'
        f'<div class="ver-block">{ver_lines}</div>'
        "</div>"
    )


# ── step 6: css (parameterised footer) ───────────────────────────────────────

def _make_css(footer_name: str) -> str:
    return f"""
@page {{
    size: A4;
    margin: 2.5cm 2cm 2.5cm 2cm;
    @bottom-center {{
        content: "{footer_name}  ·  Page " counter(page) " of " counter(pages);
        font-size: 9pt;
        color: #888888;
        font-family: Calibri, Arial, sans-serif;
    }}
}}
@page :first {{ @bottom-center {{ content: none; }} }}

body {{
    font-family: Calibri, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #000000;
    margin: 0; padding: 0;
}}

/* ── Title page ── */
.title-page {{
    page-break-after: always;
    text-align: center;
    padding-top: 100pt;
}}
.app-name {{
    font-size: 52pt; font-weight: bold;
    color: {BLUE}; margin-bottom: 10pt;
}}
.app-tagline {{ font-size: 16pt; margin-bottom: 14pt; }}
.blue-bar {{
    background: {BLUE}; height: 18pt; width: 55%;
    margin: 4pt auto 14pt auto;
}}
.doc-subtitle {{ font-size: 14pt; font-style: italic; margin-bottom: 20pt; }}
.ver-block {{ font-size: 10pt; color: #555555; margin-top: 12pt; }}
.ver-line  {{ margin-bottom: 3pt; }}

/* ── TOC page ── */
.toc-page {{ page-break-after: always; padding-top: 10pt; }}
.toc-heading {{
    font-size: 26pt; font-weight: bold; color: {BLUE};
    margin: 0 0 24pt 0;
    border-bottom: 2pt solid {BLUE}; padding-bottom: 6pt;
}}
.toc-row {{
    display: flex; align-items: baseline; margin-bottom: 5pt;
}}
.toc-l2 {{ font-size: 11pt; }}
.toc-l3 {{ font-size: 10pt; }}
.toc-l4 {{ font-size: 9pt; color: #444444; }}
.toc-link {{
    text-decoration: none; color: #000000;
    white-space: nowrap; flex-shrink: 0;
}}
.toc-l2 .toc-link {{ font-weight: bold; }}
.toc-dots {{
    flex: 1; border-bottom: 1pt dotted #AAAAAA;
    margin: 0 5pt 3pt 5pt; min-width: 20pt;
}}
.toc-num {{
    text-decoration: none; color: #000000;
    flex-shrink: 0; min-width: 20pt; text-align: right;
}}
.toc-num::after {{ content: target-counter(attr(href), page); }}

/* ── Body headings ── */
h2 {{
    font-size: 15pt; color: {BLUE}; font-weight: bold;
    margin-top: 20pt; margin-bottom: 6pt;
    border-bottom: 1pt solid {BLUE}; padding-bottom: 3pt;
}}
h3 {{
    font-size: 12pt; color: {BLUE}; font-weight: bold;
    margin-top: 12pt; margin-bottom: 4pt;
}}
h4 {{
    font-size: 11pt; color: #000000; font-weight: bold;
    margin-top: 8pt; margin-bottom: 3pt;
}}
h5 {{ font-size: 10pt; font-weight: bold; }}

/* ── Module/Phase banners ── */
h2.banner {{
    background: {NAVY}; color: #FFFFFF;
    text-align: center; padding: 10pt 16pt;
    margin-top: 24pt; margin-bottom: 0; border-bottom: none;
}}
h3.banner-sub {{ color: #000000; font-size: 12pt; font-weight: bold; }}

/* ── Callout boxes ── */
blockquote {{
    margin: 8pt 0; padding: 9pt 14pt;
    font-size: 10pt; border-radius: 2pt;
}}
blockquote.callout-info      {{ border-left: 4pt solid {BLUE};    background: #EBF3FB; }}
blockquote.callout-note      {{ border-left: 4pt solid #4CAF50;   background: #E8F5E9; }}
blockquote.callout-important {{ border-left: 4pt solid #E36C09;   background: #FFF3E6; }}
blockquote p {{ margin: 0; }}

/* ── Code blocks ── */
pre {{
    background: {CODE_BG}; color: {CODE_FG};
    padding: 9pt 12pt;
    font-family: "Courier New", Consolas, monospace;
    font-size: 8.5pt; white-space: pre-wrap;
    word-break: break-all; margin: 8pt 0; border-radius: 2pt;
}}
pre code {{ background: none; color: inherit; padding: 0; }}
code {{
    font-family: "Courier New", Consolas, monospace;
    font-size: 9pt; background: #F0F0F0;
    padding: 1pt 3pt; border-radius: 2pt;
}}

/* ── Tables ── */
table {{
    width: 100%; border-collapse: collapse;
    font-size: 10pt; margin: 8pt 0;
}}
th {{
    background: {NAVY}; color: #FFFFFF;
    font-weight: bold; padding: 5pt 8pt; text-align: left;
}}
td {{
    padding: 5pt 8pt;
    border-bottom: 0.5pt solid #DDDDDD; vertical-align: top;
}}
tr:nth-child(even) td {{ background: #F7F7F7; }}

/* ── Body misc ── */
p  {{ margin: 5pt 0; }}
ul, ol {{ margin: 5pt 0 5pt 18pt; }}
li {{ margin-bottom: 3pt; }}
a  {{ color: {BLUE}; }}
hr {{ border: none; border-top: 1pt solid #CCCCCC; margin: 12pt 0; }}
.body-content {{ padding-top: 10pt; }}
"""


# ── step 7: assemble + render ─────────────────────────────────────────────────

def build(md_path: Path, pdf_path: Path) -> None:
    print(f"Reading  {md_path}")
    version = _get_app_version()
    text = md_path.read_text(encoding="utf-8")
    text = _inject_version(text, version)
    md_path.write_text(text, encoding="utf-8")
    doc = _parse_doc(md_path)

    body_html, toc_entries = _post_process(_md_to_html(doc.body))

    full_html = (
        "<!DOCTYPE html><html><head>"
        f'<meta charset="utf-8"><title>{doc.title} — {doc.subtitle}</title>'
        "</head><body>"
        + _build_title_page(doc)
        + _build_toc(toc_entries)
        + f'<div class="body-content">{body_html}</div>'
        + "</body></html>"
    )

    print(f"Building PDF  ({doc.footer_name})…")
    HTML(string=full_html, base_url=str(ROOT)).write_pdf(
        pdf_path,
        stylesheets=[CSS(string=_make_css(doc.footer_name))],
    )
    kb = pdf_path.stat().st_size // 1024
    print(f"Written  {pdf_path}  ({kb} KB)")


# ── cli ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a styled DroidBridge PDF from a Markdown file."
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=ROOT / "docs" / "DroidBridge_Project_Document.md",
        help="Source Markdown file (default: docs/DroidBridge_Project_Document.md)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output PDF path (default: same directory and stem as input, .pdf extension)",
    )
    args = parser.parse_args()

    md_path  = args.input
    pdf_path = args.output or md_path.with_suffix(".pdf")
    build(md_path, pdf_path)


if __name__ == "__main__":
    main()
