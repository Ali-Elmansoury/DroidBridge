"""Generate docs/DroidBridge_Project_Document.docx from the Markdown source."""

import re
import sys
from pathlib import Path

try:
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError:
    print("Install python-docx first: pip install python-docx")
    sys.exit(1)

SRC = Path(__file__).parent.parent / "docs" / "DroidBridge_Project_Document.md"
DST = Path(__file__).parent.parent / "docs" / "DroidBridge_Project_Document.docx"


def add_horizontal_rule(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "AAAAAA")
    pBdr.append(bottom)
    pPr.append(pBdr)


def set_run_inline(run, text):
    """Apply inline formatting (bold/code) to a run."""
    # already applied externally; just set text
    run.text = text


def add_paragraph_with_inline(doc, line, style=None):
    """Add a paragraph supporting **bold** and `code` inline markers."""
    p = doc.add_paragraph(style=style)
    p.paragraph_format.space_after = Pt(4)

    tokens = re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", line)
    for tok in tokens:
        if tok.startswith("**") and tok.endswith("**"):
            run = p.add_run(tok[2:-2])
            run.bold = True
        elif tok.startswith("`") and tok.endswith("`"):
            run = p.add_run(tok[1:-1])
            run.font.name = "Courier New"
            run.font.size = Pt(9)
        else:
            p.add_run(tok)
    return p


def build_docx(md_text):
    doc = Document()

    # Global font
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(11)

    # Heading styles
    for lvl, sz in [(1, 20), (2, 16), (3, 13), (4, 11)]:
        h = doc.styles[f"Heading {lvl}"]
        h.font.name = "Calibri"
        h.font.size = Pt(sz)
        h.font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)
        h.paragraph_format.space_before = Pt(12)
        h.paragraph_format.space_after = Pt(4)

    lines = md_text.split("\n")
    i = 0
    in_code = False
    code_lines = []
    table_lines = []

    def flush_table():
        nonlocal table_lines
        if not table_lines:
            return
        rows = [r for r in table_lines if not re.match(r"^\|[-| :]+\|$", r.strip())]
        if not rows:
            table_lines = []
            return
        cols = [c.strip() for c in rows[0].strip("|").split("|")]
        data = []
        for row in rows[1:]:
            cells = [c.strip() for c in row.strip("|").split("|")]
            while len(cells) < len(cols):
                cells.append("")
            data.append(cells[: len(cols)])

        t = doc.add_table(rows=1 + len(data), cols=len(cols))
        t.style = "Table Grid"
        hdr_cells = t.rows[0].cells
        for ci, h in enumerate(cols):
            hdr_cells[ci].text = h
            hdr_cells[ci].paragraphs[0].runs[0].bold = True
        for ri, row in enumerate(data):
            row_cells = t.rows[ri + 1].cells
            for ci, val in enumerate(row):
                row_cells[ci].text = val

        doc.add_paragraph()  # spacer after table
        table_lines = []

    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if line.strip().startswith("```"):
            if not in_code:
                in_code = True
                code_lines = []
                i += 1
                continue
            else:
                in_code = False
                if code_lines:
                    p = doc.add_paragraph()
                    p.paragraph_format.space_before = Pt(4)
                    p.paragraph_format.space_after = Pt(4)
                    p.paragraph_format.left_indent = Inches(0.25)
                    run = p.add_run("\n".join(code_lines))
                    run.font.name = "Courier New"
                    run.font.size = Pt(8.5)
                    run.font.color.rgb = RGBColor(0x00, 0x40, 0x00)
                code_lines = []
                i += 1
                continue

        if in_code:
            code_lines.append(line)
            i += 1
            continue

        # Table row
        if line.strip().startswith("|"):
            table_lines.append(line)
            i += 1
            continue
        else:
            flush_table()

        # Horizontal rule
        if re.match(r"^---+\s*$", line.strip()):
            add_horizontal_rule(doc)
            i += 1
            continue

        # Headings
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            lvl = len(m.group(1))
            text = m.group(2).strip()
            p = doc.add_heading(text, level=lvl)
            i += 1
            continue

        # Blockquote
        if line.strip().startswith(">"):
            text = re.sub(r"^>\s?", "", line.strip())
            p = add_paragraph_with_inline(doc, text)
            p.paragraph_format.left_indent = Inches(0.35)
            p.paragraph_format.space_before = Pt(2)
            for run in p.runs:
                run.italic = True
            i += 1
            continue

        # Ordered list
        m = re.match(r"^(\d+)\.\s+(.*)", line)
        if m:
            text = m.group(2)
            p = add_paragraph_with_inline(doc, text, style="List Number")
            i += 1
            continue

        # Unordered list (-, *, or indented)
        m = re.match(r"^(\s*)[*\-]\s+(.*)", line)
        if m:
            indent = len(m.group(1))
            text = m.group(2)
            lvl_style = "List Bullet 2" if indent >= 2 else "List Bullet"
            try:
                p = add_paragraph_with_inline(doc, text, style=lvl_style)
            except KeyError:
                p = add_paragraph_with_inline(doc, "• " + text)
            i += 1
            continue

        # Empty line
        if not line.strip():
            i += 1
            continue

        # Normal paragraph
        add_paragraph_with_inline(doc, line.strip())
        i += 1

    flush_table()
    return doc


if __name__ == "__main__":
    print(f"Reading {SRC}")
    md_text = SRC.read_text(encoding="utf-8")
    print("Building docx…")
    doc = build_docx(md_text)
    doc.save(DST)
    print(f"Written → {DST} ({DST.stat().st_size // 1024} KB)")
