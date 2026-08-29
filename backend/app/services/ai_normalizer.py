"""
AI Document Normalizer
Sends extracted manuscript text to DeepSeek via OpenRouter and returns
a fully-structured DocumentAST JSON.

Pipeline:
  1. Phase 1 — Structure Detection: identify chapters and metadata
  2. Phase 2 — Content Parsing: process each chapter's blocks via AI
  3. Merge phases into a validated DocumentAST
"""
from __future__ import annotations

import json
import logging
import re
import textwrap
from typing import Any

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from app.core.config import settings
from app.models.document_ast import (
    BookMetadata,
    CalloutBlock,
    Chapter,
    CompilationSettings,
    ContentBlock,
    DocumentAST,
    FrontMatter,
    Genre,
    Heading2Block,
    Heading3Block,
    HorizontalRuleBlock,
    InteractiveFieldBlock,
    ParagraphBlock,
    PullquoteBlock,
    TableBlock,
    TrimSize,
    DedicationPage,
    CopyrightPage,
    TitlePage,
    TableOfContents,
)
from app.models.job import update_job

logger = logging.getLogger("bookcraft.ai_normalizer")

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_CHUNK_CHARS = 12_000   # ~3000 tokens — safe for DeepSeek context
CHUNK_OVERLAP   = 400      # chars of overlap between chunks


# ── OpenRouter client ─────────────────────────────────────────────────────────

async def _call_openrouter(
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> str:
    """
    Call the OpenRouter chat completions API.
    Returns the assistant message content string.
    """
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. "
            "Add it to your .env file before using AI parsing."
        )

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://bookcraftai.dev",
        "X-Title": "BookCraft AI",
    }

    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def _call_openrouter_with_retry(
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> str:
    return await _call_openrouter(messages, temperature, max_tokens)


# ── Text chunking ─────────────────────────────────────────────────────────────

def _chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks at paragraph boundaries.
    Prefers splitting on double-newlines (paragraph breaks).
    """
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    paragraphs = text.split("\n\n")
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para) + 2  # +2 for "\n\n"
        if current_len + para_len > max_chars and current:
            chunks.append("\n\n".join(current))
            # Keep last N chars as overlap
            overlap_text = "\n\n".join(current)[-overlap:]
            current = [overlap_text] if overlap_text else []
            current_len = len(overlap_text)
        current.append(para)
        current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks


# ── Phase 1: Structure Detection ──────────────────────────────────────────────

_STRUCTURE_SYSTEM_PROMPT = textwrap.dedent("""
You are an expert manuscript editor and book formatter.
Your task is to analyze a tagged manuscript excerpt and extract its high-level structure.

Return ONLY valid JSON in this exact format — no commentary, no markdown fences:
{
  "title": "Book title or best guess",
  "author": "Author name or 'Unknown'",
  "genre": "one of: fiction|non-fiction|biography|self-help|business|academic|children|poetry|anthology|technical|other",
  "chapter_titles": [
    {"number": 1, "title": "Chapter title", "start_marker": "first few words of chapter content"}
  ],
  "has_dedication": true or false,
  "dedication_text": "text if found, else null",
  "trim_size_guess": "6x9"
}

Tag legend used in the text:
  [HEADING1] = likely a chapter title
  [HEADING2] = section heading
  [BOLD]     = bold standalone line (often a heading in poorly-styled docs)
  [ITALIC]   = italic line (often a quote)
  [QUOTE]    = block quote
  [PARA]     = normal paragraph
  [HEADING_CANDIDATE] = short line that might be a heading (PDFs)
""").strip()


async def _phase1_detect_structure(tagged_text: str) -> dict:
    """
    Phase 1: Ask DeepSeek to identify book-level metadata and chapter boundaries.
    Works on the first MAX_CHUNK_CHARS chars (usually enough for structure).
    """
    sample = tagged_text[:MAX_CHUNK_CHARS]
    messages = [
        {"role": "system", "content": _STRUCTURE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Analyze this manuscript:\n\n{sample}"},
    ]

    raw = await _call_openrouter_with_retry(messages, temperature=0.1, max_tokens=1024)
    return _safe_parse_json(raw, default={})


# ── Phase 2: Content Block Parsing ───────────────────────────────────────────

_CONTENT_SYSTEM_PROMPT = textwrap.dedent("""
You are an expert manuscript formatter for BookCraft AI.
Your task is to parse a tagged manuscript chunk and return structured content blocks.

DETECTION RULES — apply these carefully:
1. CHAPTER BREAK: [HEADING1] or [BOLD] line that looks like a chapter title.
2. SECTION HEADING: [HEADING2] or short [BOLD] line inside a chapter (heading2 block).
3. SUB-HEADING: [HEADING3] (heading3 block).
4. PULL-QUOTE: A [QUOTE] or [ITALIC] block, or any inspiring/standalone quote — use "pullquote" type.
5. CALLOUT BOX (action steps / takeaways): A paragraph starting with action words like
   "Action Step", "Takeaway", "Remember", "Key Insight", "Pro Tip", "Note:" — use "callout" type
   with appropriate variant (tip/info/warning/success/danger).
6. INTERACTIVE FIELD (fill-in-the-blank): A line with blanks (___), a question prompt asking
   the reader to write/reflect, or "Your answer:", "Write here:", etc. — use "interactive-field" type
   with field_type "multiline" and label = the prompt text.
7. TABLE: [TABLE] markers or clearly tabular data.
8. NORMAL PARAGRAPH: everything else → "paragraph" type.

Return ONLY valid JSON — no markdown, no commentary:
{
  "blocks": [
    {"type": "paragraph", "text": "..."},
    {"type": "heading2", "text": "..."},
    {"type": "pullquote", "text": "...", "attribution": "optional source"},
    {"type": "callout", "variant": "tip", "title": "Action Step", "text": "..."},
    {"type": "interactive-field", "field_type": "multiline", "label": "Reflect: What does this mean to you?", "lines": 4},
    {"type": "heading3", "text": "..."}
  ]
}

Valid block types: paragraph, heading2, heading3, callout, pullquote, table, interactive-field, image, page-break, horizontal-rule
Valid callout variants: info, tip, warning, danger, success
Valid interactive-field field_type values: text, multiline, checkbox, radio, date, signature
""").strip()


async def _phase2_parse_chunk(
    chunk: str,
    chapter_context: str = "",
) -> list[dict]:
    """
    Phase 2: Parse a single text chunk into content blocks.
    Returns a list of raw block dicts.
    """
    context_note = f"This chunk is from the chapter: {chapter_context}\n\n" if chapter_context else ""
    messages = [
        {"role": "system", "content": _CONTENT_SYSTEM_PROMPT},
        {"role": "user", "content": f"{context_note}Parse this manuscript chunk into blocks:\n\n{chunk}"},
    ]

    raw = await _call_openrouter_with_retry(messages, temperature=0.15, max_tokens=4096)
    parsed = _safe_parse_json(raw, default={})
    return parsed.get("blocks", [])


# ── Block assembler ───────────────────────────────────────────────────────────

def _build_content_block(raw: dict) -> ContentBlock | None:
    """Convert a raw AI-returned block dict into a typed ContentBlock."""
    block_type = raw.get("type", "paragraph")
    text = str(raw.get("text", "")).strip()

    try:
        if block_type == "paragraph":
            if not text:
                return None
            return ParagraphBlock(type="paragraph", text=text)

        elif block_type == "heading2":
            return Heading2Block(type="heading2", text=text or raw.get("heading", ""))

        elif block_type == "heading3":
            return Heading3Block(type="heading3", text=text or raw.get("heading", ""))

        elif block_type == "pullquote":
            return PullquoteBlock(
                type="pullquote",
                text=text,
                attribution=raw.get("attribution") or None,
                align=raw.get("align", "center"),
            )

        elif block_type == "callout":
            return CalloutBlock(
                type="callout",
                variant=raw.get("variant", "info"),
                title=raw.get("title") or None,
                text=text,
            )

        elif block_type == "interactive-field":
            return InteractiveFieldBlock(
                type="interactive-field",
                field_type=raw.get("field_type", "multiline"),
                label=raw.get("label", text or "Your response"),
                placeholder=raw.get("placeholder") or None,
                lines=int(raw.get("lines", 3)),
                options=raw.get("options") or None,
            )

        elif block_type == "table":
            headers = raw.get("headers", [])
            rows = raw.get("rows", [])
            if not headers:
                return None
            return TableBlock(
                type="table",
                caption=raw.get("caption") or None,
                headers=[str(h) for h in headers],
                rows=[[str(c) for c in row] for row in rows],
            )

        elif block_type == "horizontal-rule":
            return HorizontalRuleBlock(type="horizontal-rule")

        elif block_type == "page-break":
            from app.models.document_ast import PageBreakBlock
            return PageBreakBlock(type="page-break")

        else:
            # Unknown type → treat as paragraph
            if text:
                return ParagraphBlock(type="paragraph", text=text)
            return None

    except Exception as e:
        logger.warning("Failed to build block from %s: %s", raw, e)
        if text:
            return ParagraphBlock(type="paragraph", text=text)
        return None


# ── Chapter splitter ─────────────────────────────────────────────────────────

def _split_into_chapter_texts(
    tagged_text: str,
    chapter_titles: list[dict],
) -> list[tuple[int, str, str]]:
    """
    Split tagged text into per-chapter sections based on tags.
    Returns list of (chapter_number, title, chapter_text).
    (Phase 1 chapter_titles are used as a fallback if heuristics fail)
    """
    lines = tagged_text.split('\n') if tagged_text else []
    
    chapters: list[tuple[int, str, str]] = []
    current_chapter_title = None
    current_chapter_lines = []
    chapter_num = 0
    
    front_matter_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
            
        is_heading1 = stripped.startswith("[HEADING1]")
        is_heading_cand = stripped.startswith("[HEADING_CANDIDATE]")
        is_bold = stripped.startswith("[BOLD]")
        
        is_heading = is_heading1 or is_heading_cand or is_bold
        
        text = stripped.replace("[HEADING1]", "").replace("[HEADING_CANDIDATE]", "").replace("[BOLD]", "").replace("[HEADING2]", "").replace("[HEADING3]", "").replace("[PARA]", "").replace("[LIST_ITEM]", "").strip()
        
        if not text:
            if current_chapter_title is not None:
                current_chapter_lines.append(line)
            else:
                front_matter_lines.append(line)
            continue
            
        lower_text = text.lower()
        is_chapter_kw = lower_text.startswith("chapter ") or lower_text.startswith("module ")
        
        # Split condition: HEADING1, or (CANDIDATE/BOLD with chapter keyword), or it's the very first heading.
        is_chapter = is_heading1 or (is_heading and is_chapter_kw) or (is_heading and current_chapter_title is None and len(text) < 50)
        
        if is_chapter:
            if current_chapter_title is not None:
                chapters.append((chapter_num, current_chapter_title, "\n".join(current_chapter_lines)))
            
            chapter_num += 1
            current_chapter_title = text
            # We also include the heading line in the chapter content so AI can parse it
            current_chapter_lines = [line]
        else:
            if current_chapter_title is not None:
                current_chapter_lines.append(line)
            else:
                front_matter_lines.append(line)
                
    if current_chapter_title is not None:
        chapters.append((chapter_num, current_chapter_title, "\n".join(current_chapter_lines)))
        
    if len(chapters) <= 1 and chapter_titles:
        # Heuristics failed to find multiple chapters, but AI Phase 1 found them.
        # Let's try to split by the AI's chapter titles, searching loosely.
        import re
        ai_chapters = []
        ai_split_points = []
        for ch in chapter_titles:
            title = ch.get("title", "")
            num = ch.get("number", 1)
            marker = ch.get("start_marker", "")
            
            if title:
                pattern = re.compile(r"\[(?:HEADING1|HEADING_CANDIDATE|BOLD)\]\s*" + re.escape(title[:30]), re.IGNORECASE)
                m = pattern.search(tagged_text)
                if m:
                    ai_split_points.append((m.start(), num, title))
                    continue
            
            if marker:
                marker_pattern = re.compile(re.escape(marker[:40]), re.IGNORECASE)
                m2 = marker_pattern.search(tagged_text)
                if m2:
                    ai_split_points.append((m2.start(), num, title))
                    
        if len(ai_split_points) > 1:
            ai_split_points.sort(key=lambda x: x[0])
            for i, (offset, num, title) in enumerate(ai_split_points):
                end = ai_split_points[i + 1][0] if i + 1 < len(ai_split_points) else len(tagged_text)
                chapter_text = tagged_text[offset:end].strip()
                ai_chapters.append((num, title, chapter_text))
            
            if ai_split_points[0][0] > 100:
                front_text = tagged_text[:ai_split_points[0][0]].strip()
                if front_text:
                    ai_chapters.insert(0, (0, "__front_matter__", front_text))
                    
            return ai_chapters

    results = []
    if front_matter_lines:
        results.append((0, "__front_matter__", "\n".join(front_matter_lines)))
        
    if chapters:
        results.extend(chapters)
    else:
        # Fallback to single chapter
        results.append((1, chapter_titles[0].get("title", "Chapter 1") if chapter_titles else "Chapter 1", tagged_text))
        
    return results


# ── Main entry point ──────────────────────────────────────────────────────────

async def normalize_with_ai(
    tagged_text: str,
    file_name: str,
    job_id: str,
    fallback_title: str = "Untitled",
    fallback_author: str = "Unknown Author",
) -> DocumentAST:
    """
    Full AI normalization pipeline.
    Converts tagged extracted text into a validated DocumentAST.
    """
    update_job(job_id, progress=25, message="AI: Detecting document structure…")

    # ── Phase 1: Structure detection ─────────────────────────────────────────
    structure: dict = {}
    try:
        structure = await _phase1_detect_structure(tagged_text)
        logger.info("Structure detected: %s chapters, title=%s",
                    len(structure.get("chapter_titles", [])),
                    structure.get("title"))
    except Exception as e:
        logger.warning("Phase 1 structure detection failed: %s — continuing with heuristics", e)

    title = structure.get("title") or fallback_title
    author = structure.get("author") or fallback_author
    genre_raw = structure.get("genre", "other")
    try:
        genre = Genre(genre_raw)
    except ValueError:
        genre = Genre.other

    trim_size_raw = structure.get("trim_size_guess", "6x9")
    try:
        trim_size = TrimSize(trim_size_raw)
    except ValueError:
        trim_size = TrimSize.medium

    chapter_titles = structure.get("chapter_titles", [])
    has_dedication = structure.get("has_dedication", False)
    dedication_text = structure.get("dedication_text")

    update_job(job_id, progress=35, message=f"AI: Found {len(chapter_titles)} chapter(s). Parsing content…")

    # ── Phase 2: Split into chapters and parse each ─────────────────────────
    chapter_sections = _split_into_chapter_texts(tagged_text, chapter_titles)

    total_sections = len([s for s in chapter_sections if s[0] != 0])
    processed = 0

    current_dyn_ch_title = None
    dyn_chapters: list[Chapter] = []
    front_matter_extra_blocks: list[ContentBlock] = []
    chapter_counter = 0

    for (ch_num, ch_title, ch_text) in chapter_sections:
        is_front = ch_num == 0 or ch_title == "__front_matter__"

        # Chunk the chapter text
        chunks = _chunk_text(ch_text)
        all_blocks: list[ContentBlock] = []
        
        current_dyn_ch_title = ch_title if not is_front else None

        for chunk_idx, chunk in enumerate(chunks):
            pct = 35 + int(((processed + chunk_idx / len(chunks)) / max(total_sections, 1)) * 50)
            update_job(
                job_id,
                progress=min(pct, 84),
                message=f"AI: Parsing {'front matter' if is_front else f'chapter {chapter_counter+1}'} ({chunk_idx+1}/{len(chunks)})."
            )

            try:
                raw_blocks = await _phase2_parse_chunk(
                    chunk,
                    chapter_context=ch_title if not is_front else "front matter",
                )
                for rb in raw_blocks:
                    # Check if Phase 2 emitted a new chapter_title for this block
                    new_ch_title = rb.get("chapter_title")
                    if new_ch_title and new_ch_title != current_dyn_ch_title and not is_front:
                        # Finalize the previous chapter and start a new one dynamically
                        if all_blocks:
                            word_count = sum(len(b.text.split()) for b in all_blocks if hasattr(b, "text"))
                            chapter_counter += 1
                            dyn_chapters.append(Chapter(
                                id=_slugify(current_dyn_ch_title),
                                chapter_number=chapter_counter,
                                title=current_dyn_ch_title,
                                content=all_blocks,
                                word_count=word_count,
                            ))
                            all_blocks = []
                        current_dyn_ch_title = new_ch_title
                    
                    block = _build_content_block(rb)
                    if block is not None:
                        all_blocks.append(block)
            except Exception as e:
                logger.warning("Phase 2 chunk parse failed: %s - using plain paragraphs", e)
                # Graceful fallback: emit each paragraph as-is
                for para in chunk.split("\n\n"):
                    para = re.sub(r"^\[.*?\]\s*", "", para).strip()
                    if para:
                        all_blocks.append(ParagraphBlock(type="paragraph", text=para))

        if is_front:
            front_matter_extra_blocks = all_blocks
        else:
            if all_blocks:
                word_count = sum(len(b.text.split()) for b in all_blocks if hasattr(b, "text"))
                chapter_counter += 1
                dyn_chapters.append(Chapter(
                    id=_slugify(current_dyn_ch_title or f"Chapter {chapter_counter}"),
                    chapter_number=chapter_counter,
                    title=current_dyn_ch_title or f"Chapter {chapter_counter}",
                    content=all_blocks,
                    word_count=word_count,
                ))
            processed += 1

    chapters = dyn_chapters

    if not chapters and tagged_text:
        update_job(job_id, progress=60, message="AI: Parsing full document as single chapter…")
        chunks = _chunk_text(tagged_text)
        all_blocks: list[ContentBlock] = []
        current_dyn_ch_title = title
        
        for i, chunk in enumerate(chunks):
            update_job(job_id, progress=60 + int((i / len(chunks)) * 25), message=f"Parsing chunk {i+1}/{len(chunks)}…")
            try:
                raw_blocks = await _phase2_parse_chunk(chunk, chapter_context=current_dyn_ch_title)
                for rb in raw_blocks:
                    new_ch_title = rb.get("chapter_title")
                    if new_ch_title and new_ch_title != current_dyn_ch_title:
                        if all_blocks:
                            word_count = sum(len(b.text.split()) for b in all_blocks if hasattr(b, "text"))
                            chapter_counter += 1
                            chapters.append(Chapter(
                                id=_slugify(current_dyn_ch_title),
                                chapter_number=chapter_counter,
                                title=current_dyn_ch_title,
                                content=all_blocks,
                                word_count=word_count,
                            ))
                            all_blocks = []
                        current_dyn_ch_title = new_ch_title
                    
                    block = _build_content_block(rb)
                    if block is not None:
                        all_blocks.append(block)
            except Exception as e:
                logger.warning("Single-chapter chunk parse failed: %s", e)
                for para in chunk.split("\n\n"):
                    para = re.sub(r"^\[.*?\]\s*", "", para).strip()
                    if para:
                        all_blocks.append(ParagraphBlock(type="paragraph", text=para))

        if all_blocks:
            word_count = sum(len(b.text.split()) for b in all_blocks if hasattr(b, "text"))
            chapter_counter += 1
            chapters.append(Chapter(
                id=_slugify(current_dyn_ch_title),
                chapter_number=chapter_counter,
                title=current_dyn_ch_title,
                content=all_blocks,
                word_count=word_count,
            ))

    update_job(job_id, progress=88, message="Building final DocumentAST…")

    # ── Assemble DocumentAST ─────────────────────────────────────────────────
    front_matter = FrontMatter(
        title_page=TitlePage(enabled=True),
        copyright=CopyrightPage(enabled=True),
        table_of_contents=TableOfContents(enabled=True),
        dedication=DedicationPage(
            enabled=has_dedication,
            text=dedication_text or None,
        ),
    )

    ast = DocumentAST(
        metadata=BookMetadata(
            title=title,
            author=author,
            genre=genre,
            trim_size=trim_size,
        ),
        front_matter=front_matter,
        chapters=chapters,
        compilation_settings=CompilationSettings(),
    )

    total_words = sum(c.word_count or 0 for c in chapters)
    logger.info(
        "AI normalization complete: %d chapters, ~%d words, title=%r",
        len(chapters), total_words, title,
    )

    return ast


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_parse_json(raw: str, default: Any = None) -> Any:
    """Parse JSON robustly, stripping markdown fences if present."""
    if not raw:
        return default

    # Strip markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r"```\s*$", "", raw.strip(), flags=re.MULTILINE)
    raw = raw.strip()

    # Find JSON object/array
    for pattern in [r"\{.*\}", r"\[.*\]"]:
        m = re.search(pattern, raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("JSON parse failed: %s — raw=%r", e, raw[:200])
        return default


def _slugify(text: str) -> str:
    """Convert a title to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text[:64] or "chapter"
