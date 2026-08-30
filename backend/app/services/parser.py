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

_TAG_RE = re.compile(r"\[(?:PARA|HEADING_CANDIDATE|HEADING1|HEADING2|HEADING3|BOLD|ITALIC|QUOTE|LIST_ITEM)\]\s*")


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
        if file_type == "docx" or file_type == "doc":
            ast = await _parse_docx(file_path, job_id)
        elif file_type == "pdf":
            ast = await _parse_pdf(file_path, job_id)
        elif file_type == "md" or file_type == "markdown":
            ast = await _parse_md(file_path, job_id)
        else:
            raise UnsupportedFormatError(
                f"File type '.{file_type}' is not supported. "
                "Please upload a .doc, .docx, .pdf, or .md file."
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
        return _heuristic_docx_parse(result, job_id, tagged)


def _heuristic_docx_parse(result, job_id: str, tagged_text: str = "") -> DocumentAST:
    """Fallback: simple style-based DOCX parser (no AI)."""
    update_job(job_id, progress=75, message="Running heuristic parser.")

    chapters: list[Chapter] = []
    current_chapter: Chapter | None = None
    chapter_counter = 0
    blocks = []
    
    # If we have tagged text, use it to detect chapters better
    lines = tagged_text.split('\n') if tagged_text else []
    
    if not lines:
        for p in result.paragraphs:
            text = p.text.strip()
            if text:
                if "heading 1" in p.style.lower() or "title" in p.style.lower():
                    lines.append(f"[HEADING1] {text}")
                elif "heading 2" in p.style.lower():
                    lines.append(f"[HEADING2] {text}")
                elif p.is_bold_line:
                    lines.append(f"[BOLD] {text}")
                else:
                    lines.append(f"[PARA] {text}")

    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        is_heading1 = line.startswith("[HEADING1]")
        is_bold = line.startswith("[BOLD]")
        is_heading = is_heading1 or is_bold
        text = _TAG_RE.sub("", line).strip()
        
        if not text:
            continue
            
        lower_text = text.lower()
        is_chapter_kw = lower_text.startswith("chapter ") or lower_text.startswith("module ")
        
        # Split chapter if it's HEADING1, or a BOLD line that has 'chapter/module' in the name,
        # or it's the very first heading we've seen.
        is_chapter = is_heading1 or (is_bold and is_chapter_kw) or (is_heading and current_chapter is None and len(text) < 50)
        
        if is_chapter:
            if current_chapter is not None or blocks:
                if current_chapter is None:
                    current_chapter = Chapter(chapter_number=1, title=result.title, content=blocks)
                else:
                    current_chapter.content = blocks
                chapters.append(current_chapter)
            
            chapter_counter += 1
            current_chapter = Chapter(chapter_number=chapter_counter, title=text, content=[])
            blocks = []
        else:
            if line.startswith("[HEADING2]") or line.startswith("[HEADING3]"):
                blocks.append(Heading2Block(type="heading2", text=text))
            elif line.startswith("[BOLD]"):
                blocks.append(ParagraphBlock(type="paragraph", text=f"**{text}**"))
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
        logger.warning("AI normalization failed: %s - falling back to heuristic parser.", e)
        return _heuristic_pdf_parse(result, job_id, tagged)


def _heuristic_pdf_parse(result, job_id: str, tagged_text: str = "") -> DocumentAST:
    """Fallback: simple paragraph-based PDF parser (no AI)."""
    update_job(job_id, progress=75, message="Running heuristic parser.")

    chapters: list[Chapter] = []
    current_chapter: Chapter | None = None
    chapter_counter = 0
    blocks = []
    
    # If we have tagged text, use it to detect chapters better
    lines = tagged_text.split('\n') if tagged_text else []
    
    if not lines:
        for page in result.pages:
            for para in page.text.split("\n\n"):
                cleaned = para.strip()
                if cleaned:
                    lines.append(f"[PARA] {cleaned}")

    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        is_heading1 = line.startswith("[HEADING1]")
        is_heading_cand = line.startswith("[HEADING_CANDIDATE]")
        is_heading = is_heading1 or is_heading_cand
        text = _TAG_RE.sub("", line).strip()
        
        if not text:
            continue
            
        lower_text = text.lower()
        is_chapter_kw = lower_text.startswith("chapter ") or lower_text.startswith("module ")
        
        # Split chapter if it's HEADING1, or a HEADING_CANDIDATE that has 'chapter/module' in the name,
        # or it's the very first heading we've seen.
        is_chapter = is_heading1 or (is_heading_cand and is_chapter_kw) or (is_heading and current_chapter is None and len(text) < 50)
        
        if is_chapter:
            if current_chapter is not None or blocks:
                if current_chapter is None:
                    current_chapter = Chapter(chapter_number=1, title=result.title, content=blocks)
                else:
                    current_chapter.content = blocks
                chapters.append(current_chapter)
            
            chapter_counter += 1
            current_chapter = Chapter(chapter_number=chapter_counter, title=text, content=[])
            blocks = []
        else:
            if is_heading:
                blocks.append(Heading2Block(type="heading2", text=text))
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

# ==========================================
# MARKDOWN
# ==========================================

async def _parse_md(file_path: str, job_id: str) -> DocumentAST:
    """Parse a Markdown document using extractor + AI normalizer."""
    update_job(job_id, progress=10, message="Reading Markdown file.")

    try:
        from app.services.extractors.md_extractor import extract_md, md_to_tagged_text
        result = extract_md(file_path)
    except Exception as e:
        raise CorruptFileError(f"Could not open the Markdown file. Detail: {e}")

    if not result.raw_text.strip():
        raise ParseError("The markdown document is empty.")

    update_job(job_id, progress=20, message="Extracted markdown text. Starting AI analysis.")

    tagged = md_to_tagged_text(result)

    try:
        from app.services.ai_normalizer import normalize_with_ai
        from app.core.config import settings

        if not settings.OPENROUTER_API_KEY:
            logger.warning("No OPENROUTER_API_KEY - using heuristic parser for MD.")
            return _heuristic_md_parse(result, job_id)

        return await normalize_with_ai(
            tagged_text=tagged,
            file_name=Path(file_path).name,
            job_id=job_id,
            fallback_title=result.title,
            fallback_author=result.author,
        )
    except Exception as e:
        logger.warning("AI normalization failed: %s - falling back to heuristic MD parser.", e)
        return _heuristic_md_parse(result, job_id)

def _heuristic_md_parse(result, job_id: str) -> DocumentAST:
    """Fallback parser for Markdown."""
    update_job(job_id, progress=75, message="Running heuristic parser.")

    chapters = []
    current_chapter = None
    blocks = []
    chapter_counter = 0

    for block in result.raw_text.split('\n\n'):
        block = block.strip()
        if not block:
            continue
            
        if block.startswith('# '):
            if current_chapter is not None:
                current_chapter.content = blocks
                chapters.append(current_chapter)
            chapter_counter += 1
            current_chapter = Chapter(chapter_number=chapter_counter, title=block[2:].strip(), content=[])
            blocks = []
        elif block.startswith('## '):
            blocks.append(Heading2Block(type="heading2", text=block[3:].strip()))
        elif block.startswith('### '):
            blocks.append(Heading3Block(type="heading3", text=block[4:].strip()))
        elif block.startswith('> '):
            blocks.append(ParagraphBlock(type="paragraph", text=block))
        else:
            blocks.append(ParagraphBlock(type="paragraph", text=block))
            
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
