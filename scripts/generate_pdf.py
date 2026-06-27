#!/usr/bin/env python3
"""
Generate DroidBridge_Project_Document.pdf directly from Markdown.

Uses python-markdown + WeasyPrint so the TOC is automatically populated
with real page numbers — no LibreOffice step required.

Usage:  python3 scripts/generate_pdf.py
Output: docs/DroidBridge_Project_Document.pdf

Dependencies:  pip3 install weasyprint markdown
"""

import re
import sys
from pathlib import Path

try:
    import markdown as _markdown_lib
    from weasyprint import CSS, HTML
except ImportError:
    print("Missing deps — run:  pip3 install weasyprint markdown")
    sys.exit(1)

ROOT     = Path(__file__).parent.parent
MD_PATH  = ROOT / "docs" / "DroidBridge_Project_Document.md"
PDF_PATH = ROOT / "docs" / "DroidBridge_Project_Document.pdf"

BLUE     = "#2E75B6"
NAVY     = "#1F497D"
CODE_BG  = "#1E2D3D"
CODE_FG  = "#E8EFF5"


# ── helpers ───────────────────────────────────────────────────────────────────

def _heading_id(raw_html: str) -> str:
    """Stable slug from heading inner HTML (strips tags + emoji)."""
    text = re.sub(r"<[^>]+>", "", raw_html)
    text = re.sub(r"[^\w\s-]", "", text)          # drop emoji / punctuation
    return re.sub(r"[\s_]+", "-", text).strip("-").lower()


def _is_banner(text: str) -> bool:
    """True for 'Module N …' and 'Phase N …' H2 headings."""
    clean = re.sub(r"<[^>]+>", "", text)           # strip any inline tags
    core = clean.lstrip("0123456789. ").strip().lower()
    return core.startswith("module") or core.startswith("phase")


# ── step 1: parse preamble ────────────────────────────────────────────────────

def _parse_preamble(text: str) -> tuple[str, str, str, str]:
    title = tagline = subtitle = version = ""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# ") and not title:
            parts = s[2:].split(" — ", 1)
            title   = parts[0].strip()
            tagline = parts[1].strip() if len(parts) > 1 else ""
        elif s.startswith("**") and not subtitle:
            subtitle = s.strip("*").strip()
        elif re.match(r"Version\s", s) and not version:
            version = s
    return title, tagline, subtitle, version


# ── step 2: convert body markdown → html ─────────────────────────────────────

def _md_to_html(body: str) -> str:
    md = _markdown_lib.Markdown(
        extensions=["tables", "fenced_code", "nl2br"],
        extension_configs={"nl2br": {}},
    )
    return md.convert(body)


# ── step 3: post-process html ─────────────────────────────────────────────────

def _post_process(html: str) -> tuple[str, list[tuple[int, str, str]]]:
    """
    - Add id= to h2-h4
    - Add class="banner" to Module/Phase h2
    - Add class="banner-sub" to h3 following a banner h2
    - Classify blockquotes as callout-info / callout-note / callout-important
    Returns (processed_html, toc_entries[(level, id, display_text)])
    """
    toc: list[tuple[int, str, str]] = []
    in_banner = False

    def replace_heading(m: re.Match) -> str:
        nonlocal in_banner
        level  = int(m.group(1))
        inner  = m.group(2)
        hid    = _heading_id(inner)
        plain  = re.sub(r"<[^>]+>", "", inner).strip()

        if level in (2, 3, 4):
            toc.append((level, hid, plain))

        if level == 2:
            if _is_banner(inner):
                in_banner = True
                return f'<h{level} id="{hid}" class="banner">{inner}</h{level}>'
            else:
                in_banner = False
                return f'<h{level} id="{hid}">{inner}</h{level}>'
        elif level == 3:
            cls = "banner-sub" if in_banner else ""
            attr = f' class="{cls}"' if cls else ""
            return f'<h{level} id="{hid}"{attr}>{inner}</h{level}>'
        else:
            return f'<h{level} id="{hid}">{inner}</h{level}>'

    html = re.sub(r"<h([2-5])>(.*?)</h\1>", replace_heading, html, flags=re.DOTALL)

    def classify_bq(m: re.Match) -> str:
        content = m.group(1)
        low = re.sub(r"<[^>]+>", "", content).lower()
        if "important" in low:
            cls = "callout-important"
        elif any(k in low for k in ("note:", "recommendation", "recommended")):
            cls = "callout-note"
        else:
            cls = "callout-info"
        return f'<blockquote class="{cls}">{content}</blockquote>'

    html = re.sub(r"<blockquote>(.*?)</blockquote>", classify_bq, html, flags=re.DOTALL)

    return html, toc


# ── step 4: build toc html ────────────────────────────────────────────────────

def _build_toc(entries: list[tuple[int, str, str]]) -> str:
    rows = []
    for level, hid, text in entries:
        indent = (level - 2) * 18
        rows.append(
            f'<div class="toc-row toc-l{level}" style="padding-left:{indent}pt">'
            f'  <a class="toc-link" href="#{hid}">{text}</a>'
            f'  <span class="toc-dots"></span>'
            f'  <a class="toc-num" href="#{hid}"></a>'
            f'</div>'
        )
    return (
        '<div class="toc-page">'
        '<h1 class="toc-heading">Table of Contents</h1>'
        + "".join(rows)
        + "</div>"
    )


# ── step 5: title page html ───────────────────────────────────────────────────

def _build_title_page(title: str, tagline: str, subtitle: str, version: str) -> str:
    ver_lines = "".join(
        f'<div class="ver-line">{v.strip()}</div>'
        for v in version.split("|")
    ) if version else ""
    return (
        '<div class="title-page">'
        f'<div class="app-name">{title.upper()}</div>'
        f'<div class="app-tagline">{tagline}</div>'
        f'<div class="blue-bar"></div>'
        f'<div class="doc-subtitle">{subtitle}</div>'
        f'<div class="ver-block">{ver_lines}</div>'
        "</div>"
    )


# ── step 6: css ───────────────────────────────────────────────────────────────

_CSS = f"""
@page {{
    size: A4;
    margin: 2.5cm 2cm 2.5cm 2cm;
    @bottom-center {{
        content: "DroidBridge Project Document  ·  Page " counter(page) " of " counter(pages);
        font-size: 9pt;
        color: #888888;
        font-family: Calibri, Arial, sans-serif;
    }}
}}

/* suppress footer on title page */
@page :first {{ @bottom-center {{ content: none; }} }}

body {{
    font-family: Calibri, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #000000;
    margin: 0;
    padding: 0;
}}

/* ── Title page ── */
.title-page {{
    page-break-after: always;
    text-align: center;
    padding-top: 100pt;
}}
.app-name {{
    font-size: 52pt;
    font-weight: bold;
    color: {BLUE};
    margin-bottom: 10pt;
}}
.app-tagline {{
    font-size: 16pt;
    margin-bottom: 14pt;
}}
.blue-bar {{
    background: {BLUE};
    height: 18pt;
    width: 55%;
    margin: 4pt auto 14pt auto;
}}
.doc-subtitle {{
    font-size: 14pt;
    font-style: italic;
    margin-bottom: 20pt;
}}
.ver-block {{ font-size: 10pt; color: #555555; margin-top: 12pt; }}
.ver-line  {{ margin-bottom: 3pt; }}

/* ── TOC page ── */
.toc-page {{ page-break-after: always; padding-top: 10pt; }}
.toc-heading {{
    font-size: 26pt;
    font-weight: bold;
    color: {BLUE};
    margin-bottom: 24pt;
    margin-top: 0;
    border-bottom: 2pt solid {BLUE};
    padding-bottom: 6pt;
}}

.toc-row {{
    display: flex;
    align-items: baseline;
    margin-bottom: 5pt;
}}
.toc-l2 {{ font-size: 11pt; }}
.toc-l3 {{ font-size: 10pt; }}
.toc-l4 {{ font-size: 9pt;  color: #444444; }}

.toc-link {{
    text-decoration: none;
    color: #000000;
    white-space: nowrap;
    flex-shrink: 0;
}}
.toc-l2 .toc-link {{ font-weight: bold; }}

.toc-dots {{
    flex: 1;
    border-bottom: 1pt dotted #AAAAAA;
    margin: 0 5pt 3pt 5pt;
    min-width: 20pt;
}}

.toc-num {{
    text-decoration: none;
    color: #000000;
    flex-shrink: 0;
    min-width: 20pt;
    text-align: right;
}}
.toc-num::after {{
    content: target-counter(attr(href), page);
}}

/* ── Body headings ── */
h2 {{
    font-size: 15pt;
    color: {BLUE};
    font-weight: bold;
    margin-top: 20pt;
    margin-bottom: 6pt;
    border-bottom: 1pt solid {BLUE};
    padding-bottom: 3pt;
}}
h3 {{
    font-size: 12pt;
    color: {BLUE};
    font-weight: bold;
    margin-top: 12pt;
    margin-bottom: 4pt;
}}
h4 {{
    font-size: 11pt;
    color: #000000;
    font-weight: bold;
    margin-top: 8pt;
    margin-bottom: 3pt;
}}
h5 {{ font-size: 10pt; font-weight: bold; }}

/* ── Module/Phase banners ── */
h2.banner {{
    background: {NAVY};
    color: #FFFFFF;
    text-align: center;
    padding: 10pt 16pt;
    margin-top: 24pt;
    margin-bottom: 0;
    border-bottom: none;
}}

/* ── H3 under a banner (numbered subsections) ── */
h3.banner-sub {{
    color: #000000;
    font-size: 12pt;
    font-weight: bold;
}}

/* ── Callout boxes ── */
blockquote {{
    margin: 8pt 0;
    padding: 9pt 14pt;
    font-size: 10pt;
    border-radius: 2pt;
}}
blockquote.callout-info {{
    border-left: 4pt solid {BLUE};
    background: #EBF3FB;
}}
blockquote.callout-note {{
    border-left: 4pt solid #4CAF50;
    background: #E8F5E9;
}}
blockquote.callout-important {{
    border-left: 4pt solid #E36C09;
    background: #FFF3E6;
}}
blockquote p {{ margin: 0; }}

/* ── Code blocks ── */
pre {{
    background: {CODE_BG};
    color: {CODE_FG};
    padding: 9pt 12pt;
    font-family: "Courier New", Consolas, monospace;
    font-size: 8.5pt;
    white-space: pre-wrap;
    word-break: break-all;
    margin: 8pt 0;
    border-radius: 2pt;
}}
pre code {{ background: none; color: inherit; padding: 0; }}

code {{
    font-family: "Courier New", Consolas, monospace;
    font-size: 9pt;
    background: #F0F0F0;
    padding: 1pt 3pt;
    border-radius: 2pt;
}}

/* ── Tables ── */
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 10pt;
    margin: 8pt 0;
}}
th {{
    background: {NAVY};
    color: #FFFFFF;
    font-weight: bold;
    padding: 5pt 8pt;
    text-align: left;
}}
td {{
    padding: 5pt 8pt;
    border-bottom: 0.5pt solid #DDDDDD;
    vertical-align: top;
}}
tr:nth-child(even) td {{ background: #F7F7F7; }}

/* ── Body ── */
p  {{ margin: 5pt 0; }}
ul, ol {{ margin: 5pt 0 5pt 18pt; }}
li {{ margin-bottom: 3pt; }}
a  {{ color: {BLUE}; }}
hr {{ border: none; border-top: 1pt solid #CCCCCC; margin: 12pt 0; }}

.body-content {{ padding-top: 10pt; }}
"""


# ── step 7: assemble + render ─────────────────────────────────────────────────

def build(md_path: Path = MD_PATH, pdf_path: Path = PDF_PATH) -> None:
    print(f"Reading  {md_path}")
    text = md_path.read_text(encoding="utf-8")

    # Split preamble (before first ---) from body
    parts = re.split(r"\n---\n", text, maxsplit=1)
    preamble = parts[0]
    body     = parts[1] if len(parts) > 1 else text

    title, tagline, subtitle, version = _parse_preamble(preamble)

    body_html, toc_entries = _post_process(_md_to_html(body))

    full_html = (
        "<!DOCTYPE html><html><head>"
        f'<meta charset="utf-8"><title>{title}</title>'
        "</head><body>"
        + _build_title_page(title, tagline, subtitle, version)
        + _build_toc(toc_entries)
        + f'<div class="body-content">{body_html}</div>'
        + "</body></html>"
    )

    print("Building PDF…")
    HTML(string=full_html, base_url=str(ROOT)).write_pdf(
        pdf_path,
        stylesheets=[CSS(string=_CSS)],
    )
    kb = pdf_path.stat().st_size // 1024
    print(f"Written  {pdf_path}  ({kb} KB)")


if __name__ == "__main__":
    build()
