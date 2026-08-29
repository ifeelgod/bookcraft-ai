"""
Markdown (.md) Compiler implementation.
Compiles DocumentAST into clean, standard GitHub-Flavored Markdown with YAML frontmatter,
callouts, pullquotes, tables, interactive checkboxes, and front matter.
"""
from __future__ import annotations
import asyncio
import logging
import re
from pathlib import Path
from typing import Tuple

from app.models.document_ast import (
    CalloutBlock,
    Chapter,
    DocumentAST,
    Heading2Block,
    Heading3Block,
    HorizontalRuleBlock,
    ImageBlock,
    InteractiveFieldBlock,
    PageBreakBlock,
    ParagraphBlock,
    PullquoteBlock,
    TableBlock,
)
from app.services.compilers.base import BaseCompiler, sanitize_filename

logger = logging.getLogger("bookcraft.compiler.md")

CALLOUT_GFM_MAP = {
    "info": "NOTE",
    "tip": "TIP",
    "warning": "WARNING",
    "danger": "CAUTION",
    "success": "TIP",
}


def _slugify(text: str) -> str:
    """Create a Markdown anchor slug from heading text."""
    slug = re.sub(r'[^\w\s-]', '', text.lower()).strip()
    return re.sub(r'[-\s]+', '-', slug)


def _escape_md_table_cell(text: str) -> str:
    """Escape pipe characters within table cells."""
    return str(text).replace("|", "\\|").replace("\n", "<br>")


def build_markdown_document(ast: DocumentAST) -> str:
    """Generate clean Markdown document with YAML frontmatter from DocumentAST."""
    sections = []

    # ── 1. YAML Frontmatter ───────────────────────────────────────────────────
    meta = ast.metadata
    yaml_lines = [
        "---",
        f'title: "{meta.title}"',
    ]
    if meta.subtitle:
        yaml_lines.append(f'subtitle: "{meta.subtitle}"')
    yaml_lines.append(f'author: "{meta.author}"')
    if meta.co_authors:
        yaml_lines.append(f'co_authors: [{", ".join(repr(a) for a in meta.co_authors)}]')
    if hasattr(meta.genre, 'value'):
        yaml_lines.append(f'genre: "{meta.genre.value}"')
    elif meta.genre:
        yaml_lines.append(f'genre: "{meta.genre}"')
    if hasattr(meta.trim_size, 'value'):
        yaml_lines.append(f'trim_size: "{meta.trim_size.value}"')
    elif meta.trim_size:
        yaml_lines.append(f'trim_size: "{meta.trim_size}"')
    if meta.language:
        yaml_lines.append(f'language: "{meta.language}"')
    if meta.isbn:
        yaml_lines.append(f'isbn: "{meta.isbn}"')
    if meta.publisher:
        yaml_lines.append(f'publisher: "{meta.publisher}"')
    yaml_lines.append("---")
    yaml_lines.append("")
    sections.append("\n".join(yaml_lines))

    # ── 2. Front Matter ───────────────────────────────────────────────────────
    fm = ast.front_matter

    # Title Page
    if fm.title_page.enabled:
        tp_lines = [
            f"# {meta.title}",
            "",
        ]
        if meta.subtitle:
            tp_lines.extend([f"*{meta.subtitle}*", ""])
        tp_lines.extend([f"**By {meta.author}**", ""])
        if meta.publisher:
            tp_lines.extend([f"*{meta.publisher}*", ""])
        tp_lines.append("---\n")
        sections.append("\n".join(tp_lines))

    # Copyright Page
    if fm.copyright.enabled:
        c = fm.copyright
        year = c.year or 2026
        holder = c.holder or meta.author
        cp_lines = [
            f"**Copyright © {year} {holder}**",
            "",
            "All rights reserved.",
            "",
        ]
        if c.statement:
            cp_lines.extend([c.statement, ""])
        if c.edition:
            cp_lines.extend([f"**Edition:** {c.edition}", ""])
        if meta.isbn:
            cp_lines.extend([f"**ISBN:** {meta.isbn}", ""])
        if c.disclaimer:
            cp_lines.extend([f"*{c.disclaimer}*", ""])
        cp_lines.append("---\n")
        sections.append("\n".join(cp_lines))

    # Table of Contents
    if fm.table_of_contents.enabled:
        toc_title = fm.table_of_contents.title or "Table of Contents"
        toc_lines = [
            f"## {toc_title}",
            "",
        ]
        for ch in ast.chapters:
            ch_heading = f"Chapter {ch.chapter_number}: {ch.title}"
            slug = _slugify(ch_heading)
            toc_lines.append(f"- [{ch_heading}](#{slug})")
        toc_lines.append("\n---\n")
        sections.append("\n".join(toc_lines))

    # Dedication
    if fm.dedication.enabled and fm.dedication.text:
        ded_lines = [
            "> *" + fm.dedication.text.replace("\n", "\n> ") + "*",
            "",
            "---\n",
        ]
        sections.append("\n".join(ded_lines))

    # ── 3. Chapters ───────────────────────────────────────────────────────────
    for ch in ast.chapters:
        ch_lines = []
        ch_heading = f"Chapter {ch.chapter_number}: {ch.title}"
        ch_lines.extend([f"# {ch_heading}", ""])

        if ch.subtitle:
            ch_lines.extend([f"*{ch.subtitle}*", ""])

        if ch.epigraph:
            epi_text = ch.epigraph.text.replace("\n", "\n> ")
            ch_lines.append(f"> *\"{epi_text}\"*")
            if ch.epigraph.attribution:
                ch_lines.append(f">\n> — *{ch.epigraph.attribution}*")
            ch_lines.append("")

        for block in ch.content:
            if isinstance(block, ParagraphBlock):
                ch_lines.extend([block.text, ""])

            elif isinstance(block, Heading2Block):
                ch_lines.extend([f"## {block.text}", ""])

            elif isinstance(block, Heading3Block):
                ch_lines.extend([f"### {block.text}", ""])

            elif isinstance(block, CalloutBlock):
                alert_type = CALLOUT_GFM_MAP.get(block.variant, "NOTE")
                ch_lines.append(f"> [!{alert_type}]")
                if block.title:
                    ch_lines.append(f"> **{block.title}**")
                body_lines = block.text.split("\n")
                for bl in body_lines:
                    ch_lines.append(f"> {bl}")
                ch_lines.append("")

            elif isinstance(block, PullquoteBlock):
                pq_text = block.text.replace("\n", " ")
                ch_lines.append(f'> ### *"{pq_text}"*')
                if block.attribution:
                    ch_lines.append(f'> — *{block.attribution}*')
                ch_lines.append("")

            elif isinstance(block, TableBlock):
                headers = [_escape_md_table_cell(h) for h in block.headers]
                ch_lines.append("| " + " | ".join(headers) + " |")

                # Alignments
                align_row = []
                for idx in range(len(headers)):
                    align = block.column_alignments[idx] if block.column_alignments and idx < len(block.column_alignments) else "left"
                    if align == "center":
                        align_row.append(":---:")
                    elif align == "right":
                        align_row.append("---:")
                    else:
                        align_row.append(":---")
                ch_lines.append("| " + " | ".join(align_row) + " |")

                # Rows
                for r in block.rows:
                    row_cells = [_escape_md_table_cell(cell) for cell in r]
                    # Pad if needed
                    while len(row_cells) < len(headers):
                        row_cells.append("")
                    ch_lines.append("| " + " | ".join(row_cells[:len(headers)]) + " |")

                if block.caption:
                    ch_lines.extend(["", f"*{block.caption}*"])
                ch_lines.append("")

            elif isinstance(block, InteractiveFieldBlock):
                ch_lines.append(f"**{block.label}**\n")
                if block.field_type == "checkbox":
                    for opt in (block.options or ["Option 1", "Option 2"]):
                        ch_lines.append(f"- [ ] {opt}")
                elif block.field_type in ("text", "multiline", "signature", "date"):
                    num_lines = block.lines if block.lines and block.lines > 0 else 2
                    for _ in range(num_lines):
                        ch_lines.append("________________________________________________________\n")
                ch_lines.append("")

            elif isinstance(block, PageBreakBlock):
                ch_lines.extend(["<!-- pagebreak -->", ""])

            elif isinstance(block, HorizontalRuleBlock):
                ch_lines.extend(["---", ""])

            elif isinstance(block, ImageBlock):
                alt = block.alt or "Illustration"
                src = block.src
                caption = f"\n*{block.caption}*" if block.caption else ""
                ch_lines.extend([f"![{alt}]({src}){caption}", ""])

        sections.append("\n".join(ch_lines))

    return "\n\n".join(sections).strip() + "\n"


class MdCompiler(BaseCompiler):
    """Markdown (.md) Compiler generating clean GitHub-Flavored Markdown."""

    @property
    def format_name(self) -> str:
        return "md"

    @property
    def file_extension(self) -> str:
        return ".md"

    @property
    def mime_type(self) -> str:
        return "text/markdown; charset=utf-8"

    async def compile(
        self,
        ast: DocumentAST,
        job_id: str,
        output_dir: Path,
    ) -> Tuple[Path, str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_title = sanitize_filename(ast.metadata.title)
        md_filename = f"{job_id}_{safe_title}.md"
        md_path = output_dir / md_filename

        md_content = build_markdown_document(ast)

        def _save_md():
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)

        try:
            await asyncio.to_thread(_save_md)
        except Exception as e:
            logger.error(f"Markdown compilation failed: {e}")
            raise RuntimeError(f"Markdown compiler failed: {e}")

        download_url = self.get_download_url(md_filename)
        return md_path, download_url
