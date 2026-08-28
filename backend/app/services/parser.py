"""
Document Parser — Orchestration Layer
Coordinates file extraction → tagged-text conversion → AI normalization.

Flow:
  .docx → DocxExtractor → paragraphs_to_tagged_text → AI Normalizer → DocumentAST
  .pdf  → PdfExtractor  → pdf_to_tagged_text         → AI Normalizer → DocumentAST

If AI normalization fails (e.g. no API key), falls back to a basic
heuristic parser so the upload always succeeds.
"""
from __future__ import annotations
import logging
import re
from pathlib import Path

from app.models.document_ast import (
    BookMetadata,
    Chapter,
    CompilationSettings,
    DocumentAST,
    FrontMatter,
    Genre,
    Heading2Block,
    ParagraphBlock,
    TrimSize,
)
from app.models.job import update_job
from app.models.ast_cache import store_ast

logger = logging.getLogger("bookcraft.parser")


class ParseError(Exception):
    """Raised when a document cannot be parsed."""
    pass


class CorruptFileError(ParseError):
    """Raised when a file appears to be corrupted or unreadable."""
    pass


class UnsupportedFormatError(ParseError):
    """Raised for unsupported file types."""
    pass


async def parse_document(
    file_path: str,
    file_type: str,
    job_id: str,
) -> DocumentAST:
    """
    Main entry point: parse a .docx or .pdf into a DocumentAST.
    Always stores the result in the AST cache.
    Raises ParseError subclasses with friendly messages on failure.
    """
    path = Path(file_path)

    if not path.exists():
        raise CorruptFileError(f"Uploaded file could not be found on disk: {path.name}")

    if path.stat().st_size == 0:
        raise CorruptFileError(f"The uploaded file '{path.name}' is empty.")

    try:
        if file_type == "docx":
            ast = await _parse_docx(file_path, job_id)
        elif file_type == "pdf":
            ast = await _parse_pdf(file_path, job_id)
        else:
            raise UnsupportedFormatError(
                f"File type '.{file_type}' is not supported. "
                "Please upload a .docx or .pdf file."
            )
    except (ParseError, UnsupportedFormatError):
        raise
    except Exception as exc:
        logger.exception("Unexpected error parsing %s: %s", file_path, exc)
        raise ParseError(
            f"Could not parse '{path.name}'. "
            f"The file may be corrupted, password-protected, or in an unsupported format. "
            f"Detail: {exc}"
        )

    # Store in cache for retrieval
    store_ast(job_id, ast)
    return ast


# ── DOCX ──────────────────────────────────────────────────────────────────────

async def _parse_docx(file_path: str, job_id: str) -> DocumentAST:
    """Parse a Word document using extractor + AI normalizer."""
    update_job(job_id, progress=10, message="Reading .docx structure…")

    try:
        from app.services.extractors.docx_extractor import (
            extract_docx,
            paragraphs_to_tagged_text,
        )
        result = extract_docx(file_path)
    except Exception as e:
        raise CorruptFileError(
            f"Could not open the .docx file. "
            f"Make sure it is a valid Word document (not password-protected). "
            f"Detail: {e}"
        )

    if not result.paragraphs:
        raise ParseError(
            "The document appears to be empty or contains no readable text. "
            "Please check the file and try again."
        )

    update_job(job_id, progress=20, message=f"Extracted {len(result.paragraphs)} paragraphs. Starting AI analysis…")

    tagged = paragraphs_to_tagged_text(result.paragraphs)

    # Attempt AI normalization
    try:
        from app.services.ai_normalizer import normalize_with_ai
        from app.core.config import settings

        if not settings.OPENROUTER_API_KEY:
            logger.warning("No OPENROUTER_API_KEY — using heuristic parser.")
            return _heuristic_docx_parse(result, job_id)

        return await normalize_with_ai(
            tagged_text=tagged,
            file_name=Path(file_path).name,
            job_id=job_id,
            fallback_title=result.title,
            fallback_author=result.author,
        )

    except Exception as e:
        logger.warning("AI normalization failed: %s — falling back to heuristic parser.", e)
        return _heuristic_docx_parse(result, job_id)


def _heuristic_docx_parse(result, job_id: str) -> DocumentAST:
    """Fallback: simple style-based DOCX parser (no AI)."""
    from app.services.extractors.docx_extractor import ExtractedParagraph

    update_job(job_id, progress=75, message="Running heuristic parser…")

    chapters: list[Chapter] = []
    current_chapter: Chapter | None = None
    chapter_counter = 0
    blocks = []

    for p in result.paragraphs:
        style = p.style.lower()
        text = p.text.strip()
        if not text:
            continue

        # Check for chapter boundaries
        is_heading_1 = "heading 1" in style
        is_chapter_text = text.lower().startswith("chapter ") or text.lower().startswith("module ")
        
        # We start a new chapter if it's heading 1, starts with "Chapter X", or if it's a short ALL CAPS line and we have no chapters yet
        if is_heading_1 or is_chapter_text or (not chapters and text.isupper() and len(text.split()) < 10):
            if current_chapter is not None:
                current_chapter.content = blocks
                chapters.append(current_chapter)
            chapter_counter += 1
            current_chapter = Chapter(chapter_number=chapter_counter, title=text, content=[])
            blocks = []
            
        elif "heading 2" in style or (p.is_bold_line and len(text.split()) <= 12 and not text.endswith('.')):
            blocks.append(Heading2Block(type="heading2", text=text))
            
        elif "heading 3" in style:
            blocks.append(Heading3Block(type="heading3", text=text))
            
        else:
            blocks.append(ParagraphBlock(type="paragraph", text=text))

    if current_chapter is not None:
        current_chapter.content = blocks
        chapters.append(current_chapter)
    elif blocks:
        chapters.append(Chapter(chapter_number=1, title=result.title, content=blocks))

    return DocumentAST(
        metadata=BookMetadata(
            title=result.title,
            author=result.author,
            genre=Genre.other,
            trim_size=TrimSize.medium,
        ),
        front_matter=FrontMatter(),
        chapters=chapters,
        compilation_settings=CompilationSettings(),
    )


# ── PDF ───────────────────────────────────────────────────────────────────────

async def _parse_pdf(file_path: str, job_id: str) -> DocumentAST:
    """Parse a PDF using extractor + AI normalizer."""
    update_job(job_id, progress=10, message="Reading PDF pages…")

    try:
        from app.services.extractors.pdf_extractor import extract_pdf, pdf_to_tagged_text
        result = extract_pdf(file_path)
    except Exception as e:
        raise CorruptFileError(
            f"Could not open the PDF file. "
            f"Make sure it is not password-protected, encrypted, or a scanned image-only PDF. "
            f"Detail: {e}"
        )

    if not result.raw_text.strip():
        raise ParseError(
            "No readable text was found in the PDF. "
            "If this is a scanned document, please run OCR first and re-upload."
        )

    update_job(
        job_id, progress=20,
        message=f"Extracted {result.page_count} pages ({len(result.raw_text):,} chars). Starting AI analysis…"
    )

    tagged = pdf_to_tagged_text(result)

    # Attempt AI normalization
    try:
        from app.services.ai_normalizer import normalize_with_ai
        from app.core.config import settings

        if not settings.OPENROUTER_API_KEY:
            logger.warning("No OPENROUTER_API_KEY — using heuristic parser.")
            return _heuristic_pdf_parse(result, job_id)

        return await normalize_with_ai(
            tagged_text=tagged,
            file_name=Path(file_path).name,
            job_id=job_id,
            fallback_title=result.title,
            fallback_author=result.author,
        )

    except Exception as e:
        logger.warning("AI normalization failed: %s — falling back to heuristic parser.", e)
        return _heuristic_pdf_parse(result, job_id)


def _heuristic_pdf_parse(result, job_id: str) -> DocumentAST:
    """Fallback: simple paragraph-based PDF parser (no AI)."""
    update_job(job_id, progress=75, message="Running heuristic parser…")

    blocks: list[ParagraphBlock] = []
    for page in result.pages:
        for para in page.text.split("\n\n"):
            cleaned = para.strip()
            if cleaned:
                blocks.append(ParagraphBlock(type="paragraph", text=cleaned))

    return DocumentAST(
        metadata=BookMetadata(
            title=result.title,
            author=result.author,
            genre=Genre.other,
            trim_size=TrimSize.medium,
        ),
        front_matter=FrontMatter(),
        chapters=[Chapter(chapter_number=1, title=result.title, content=blocks)],
        compilation_settings=CompilationSettings(),
    )
