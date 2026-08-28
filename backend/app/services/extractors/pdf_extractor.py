"""
PDF Extractor
Extracts clean, sentence-coherent text from PDF files using PyMuPDF (fitz)
with pdfplumber as a fallback for complex layouts.
"""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bookcraft.extractor.pdf")


@dataclass
class ExtractedPage:
    """Text and metadata from a single PDF page."""
    page_number: int          # 1-based
    text: str                 # Cleaned, sentence-coherent text
    has_image: bool = False
    font_sizes: list[float] = field(default_factory=list)  # dominant font sizes on page


@dataclass
class PdfExtractResult:
    """Full extraction result from a PDF file."""
    title: str
    author: str
    pages: list[ExtractedPage]
    raw_text: str              # Full concatenated cleaned text
    page_count: int


def extract_pdf(file_path: str) -> PdfExtractResult:
    """
    Extract clean text from a PDF file.
    Tries PyMuPDF first (best results), falls back to pdfplumber.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        return _extract_with_pymupdf(str(path))
    except ImportError:
        logger.warning("PyMuPDF not available, falling back to pdfplumber")
        return _extract_with_pdfplumber(str(path))
    except Exception as e:
        logger.warning("PyMuPDF failed (%s), falling back to pdfplumber", e)
        return _extract_with_pdfplumber(str(path))


def _extract_with_pymupdf(file_path: str) -> PdfExtractResult:
    """
    Primary PDF extractor using PyMuPDF (fitz).
    Preserves paragraph structure by detecting line-height gaps.
    Avoids broken sentence fragments from mid-line page wrapping.
    """
    import fitz  # PyMuPDF

    path = Path(file_path)
    doc = fitz.open(file_path)

    # ── Metadata ─────────────────────────────────────────────────────────────
    meta = doc.metadata or {}
    title = (meta.get("title") or "").strip() or path.stem
    author = (meta.get("author") or "").strip() or "Unknown Author"

    pages: list[ExtractedPage] = []
    all_text_chunks: list[str] = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Extract blocks — each block is a paragraph/image
        blocks = page.get_text("blocks", sort=True)  # sorted top-to-bottom
        page_texts: list[str] = []
        font_sizes: list[float] = []
        has_image = False

        for block in blocks:
            # block = (x0, y0, x1, y1, text, block_no, block_type)
            block_type = block[6]

            if block_type == 1:  # image block
                has_image = True
                continue

            raw = block[4]
            if not raw.strip():
                continue

            # Clean the raw block text
            cleaned = _clean_pdf_block(raw)
            if cleaned:
                page_texts.append(cleaned)

        # Collect font size info for heading detection
        try:
            page_dict = page.get_text("dict")
            for blk in page_dict.get("blocks", []):
                for line in blk.get("lines", []):
                    for span in line.get("spans", []):
                        sz = span.get("size", 0)
                        if sz > 0:
                            font_sizes.append(sz)
        except Exception:
            pass

        page_text = "\n\n".join(page_texts)
        pages.append(ExtractedPage(
            page_number=page_num + 1,
            text=page_text,
            has_image=has_image,
            font_sizes=font_sizes,
        ))
        if page_text:
            all_text_chunks.append(page_text)

    doc.close()

    raw_text = "\n\n".join(all_text_chunks)

    logger.info(
        "PyMuPDF: extracted %d pages from %s (%d chars)",
        len(pages), path.name, len(raw_text)
    )

    return PdfExtractResult(
        title=title,
        author=author,
        pages=pages,
        raw_text=raw_text,
        page_count=len(pages),
    )


def _extract_with_pdfplumber(file_path: str) -> PdfExtractResult:
    """
    Fallback PDF extractor using pdfplumber.
    Better at handling tables and columns.
    """
    import pdfplumber

    path = Path(file_path)

    with pdfplumber.open(file_path) as pdf:
        meta = pdf.metadata or {}
        title = (meta.get("Title") or meta.get("title") or "").strip() or path.stem
        author = (meta.get("Author") or meta.get("author") or "").strip() or "Unknown Author"

        pages: list[ExtractedPage] = []
        all_chunks: list[str] = []

        for i, page in enumerate(pdf.pages):
            raw = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            cleaned = _clean_pdf_block(raw)
            pages.append(ExtractedPage(
                page_number=i + 1,
                text=cleaned,
                has_image=False,
            ))
            if cleaned:
                all_chunks.append(cleaned)

    raw_text = "\n\n".join(all_chunks)

    logger.info(
        "pdfplumber: extracted %d pages from %s (%d chars)",
        len(pages), path.name, len(raw_text)
    )

    return PdfExtractResult(
        title=title,
        author=author,
        pages=pages,
        raw_text=raw_text,
        page_count=len(pages),
    )


# ── Text cleaning utilities ───────────────────────────────────────────────────

# Patterns that indicate broken line wraps (line ends mid-sentence)
_HARD_WRAP = re.compile(r"(?<![.!?\"'])\n(?=[a-z\"])")
# Multiple blank lines → single paragraph break
_MULTI_BLANK = re.compile(r"\n{3,}")
# Page numbers: lone digits on a line
_PAGE_NUM = re.compile(r"^\s*\d{1,4}\s*$", re.MULTILINE)
# Running headers/footers: short repeated lines (detected heuristically)
_SHORT_LINE = re.compile(r"^.{1,40}$", re.MULTILINE)


def _clean_pdf_block(text: str) -> str:
    """
    Clean a raw PDF text block:
    - Rejoin broken line wraps (mid-sentence newlines)
    - Remove lone page numbers
    - Normalize whitespace
    """
    if not text:
        return ""

    # Remove lone page numbers
    text = _PAGE_NUM.sub("", text)

    # Rejoin lines broken mid-sentence (soft wraps)
    text = _HARD_WRAP.sub(" ", text)

    # Collapse 3+ newlines to double
    text = _MULTI_BLANK.sub("\n\n", text)

    # Normalize spaces
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\t+", " ", text)

    return text.strip()


def pdf_to_tagged_text(result: PdfExtractResult) -> str:
    """
    Convert PDF extraction result to tagged text for AI parsing.
    Uses font-size heuristics to tag potential headings.
    """
    if not result.pages:
        return result.raw_text

    # Compute median font size across all pages for heading detection
    all_sizes: list[float] = []
    for page in result.pages:
        all_sizes.extend(page.font_sizes)

    if all_sizes:
        all_sizes.sort()
        median_size = all_sizes[len(all_sizes) // 2]
        large_threshold = median_size * 1.3  # 30% bigger = likely heading
    else:
        median_size = 12.0
        large_threshold = 15.0

    # For now, output paragraphs with [PARA] tags since we don't have
    # per-paragraph font sizes from the block extraction
    lines: list[str] = []
    for page in result.pages:
        if page.text:
            for para in page.text.split("\n\n"):
                para = para.strip()
                if not para:
                    continue
                # Heuristics: short lines (< 60 chars) without period are likely headings
                words = para.split()
                if len(words) <= 8 and not para.endswith((".", "!", "?", ",")):
                    lines.append(f"[HEADING_CANDIDATE] {para}")
                else:
                    lines.append(f"[PARA] {para}")

    return "\n".join(lines)
