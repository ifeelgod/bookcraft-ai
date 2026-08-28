"""
DOCX Extractor
Extracts rich text, bold/italic runs, tables, and heading structure
from .docx files using python-docx + mammoth.
"""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bookcraft.extractor.docx")


@dataclass
class RichRun:
    """A run of text with inline formatting."""
    text: str
    bold: bool = False
    italic: bool = False


@dataclass
class ExtractedParagraph:
    """One logical paragraph from the source document."""
    text: str                          # Plain-text content
    style: str = "Normal"             # Word style name (Heading 1, Normal, Quote…)
    runs: list[RichRun] = field(default_factory=list)
    is_bold_line: bool = False         # Entire line is bold (often headings in non-styled docs)
    is_italic_line: bool = False


@dataclass
class ExtractedTable:
    """A table extracted from the document."""
    headers: list[str]
    rows: list[list[str]]
    caption: Optional[str] = None


@dataclass
class DocxExtractResult:
    """Full extraction result from a .docx file."""
    title: str
    author: str
    paragraphs: list[ExtractedParagraph]
    tables: list[ExtractedTable]
    raw_html: str                       # mammoth HTML for fallback parsing
    raw_text: str                       # Plain concatenated text


def extract_docx(file_path: str) -> DocxExtractResult:
    """
    Extract all content from a .docx file.
    Uses python-docx for structure + mammoth for rich HTML.
    """
    import mammoth
    from docx import Document as DocxDocument
    from docx.oxml.ns import qn

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # ── python-docx pass: structure + inline formatting ──────────────────────
    doc = DocxDocument(str(path))

    title = (doc.core_properties.title or "").strip() or path.stem
    author = (doc.core_properties.author or "").strip() or "Unknown Author"

    paragraphs: list[ExtractedParagraph] = []
    tables: list[ExtractedTable] = []

    # Iterate body elements in order (preserves table/para interleaving)
    body = doc.element.body
    for elem in body:
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        # ── Paragraph ────────────────────────────────────────────────────────
        if tag == "p":
            from docx.text.paragraph import Paragraph as DocxPara
            para = DocxPara(elem, doc)
            text = para.text.strip()
            if not text:
                continue

            style_name = para.style.name if para.style else "Normal"

            runs: list[RichRun] = []
            for run in para.runs:
                if run.text:
                    runs.append(RichRun(
                        text=run.text,
                        bold=bool(run.bold),
                        italic=bool(run.italic),
                    ))

            all_bold = bool(runs) and all(r.bold for r in runs if r.text.strip())
            all_italic = bool(runs) and all(r.italic for r in runs if r.text.strip())

            paragraphs.append(ExtractedParagraph(
                text=text,
                style=style_name,
                runs=runs,
                is_bold_line=all_bold,
                is_italic_line=all_italic,
            ))

        # ── Table ────────────────────────────────────────────────────────────
        elif tag == "tbl":
            from docx.table import Table as DocxTable
            tbl = DocxTable(elem, doc)
            if not tbl.rows:
                continue

            raw_rows = []
            for row in tbl.rows:
                raw_rows.append([cell.text.strip() for cell in row.cells])

            # Heuristic: first row is headers if it has bold or ALL-CAPS text
            first_row = raw_rows[0]
            rest = raw_rows[1:]

            is_header = all(c.isupper() or c == "" for c in first_row) or \
                        _row_is_bold(tbl.rows[0])

            tables.append(ExtractedTable(
                headers=first_row if is_header else [f"Col {i+1}" for i in range(len(first_row))],
                rows=rest if is_header else raw_rows,
            ))

    # ── mammoth pass: raw HTML for AI context ───────────────────────────────
    try:
        with open(str(path), "rb") as f:
            result = mammoth.convert_to_html(f)
        raw_html = result.value
        if result.messages:
            logger.debug("mammoth warnings: %s", result.messages)
    except Exception as e:
        logger.warning("mammoth conversion failed: %s", e)
        raw_html = ""

    raw_text = "\n\n".join(p.text for p in paragraphs)

    logger.info(
        "Extracted %d paragraphs, %d tables from %s",
        len(paragraphs), len(tables), path.name
    )

    return DocxExtractResult(
        title=title,
        author=author,
        paragraphs=paragraphs,
        tables=tables,
        raw_html=raw_html,
        raw_text=raw_text,
    )


def _row_is_bold(row) -> bool:
    """Check if all cells in a table row have bold text."""
    try:
        for cell in row.cells:
            for para in cell.paragraphs:
                for run in para.runs:
                    if run.text.strip() and not run.bold:
                        return False
        return True
    except Exception:
        return False


def paragraphs_to_tagged_text(paragraphs: list[ExtractedParagraph]) -> str:
    """
    Convert extracted paragraphs to a tagged plain-text format
    that the AI can parse unambiguously.

    Format:
        [HEADING1] Chapter Title
        [HEADING2] Section Title
        [BOLD] Bold standalone line
        [ITALIC] Italic line (potential quote)
        [PARA] Normal paragraph text
    """
    lines: list[str] = []
    for p in paragraphs:
        style = p.style.lower()
        if "heading 1" in style or "title" in style:
            lines.append(f"[HEADING1] {p.text}")
        elif "heading 2" in style:
            lines.append(f"[HEADING2] {p.text}")
        elif "heading 3" in style:
            lines.append(f"[HEADING3] {p.text}")
        elif "quote" in style or "block" in style:
            lines.append(f"[QUOTE] {p.text}")
        elif p.is_bold_line:
            lines.append(f"[BOLD] {p.text}")
        elif p.is_italic_line:
            lines.append(f"[ITALIC] {p.text}")
        else:
            lines.append(f"[PARA] {p.text}")
    return "\n\n".join(lines)
