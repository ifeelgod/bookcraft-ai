"""
PDF compiler service.
Turns a DocumentAST into a formatted, publication-ready PDF using Typst.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Tuple

import typst

from app.core.config import settings
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
    TrimSize,
)
from app.models.job import update_job

logger = logging.getLogger("bookcraft.compiler")

# Trim size → (width_inches, height_inches)
TRIM_DIMENSIONS: dict[TrimSize, Tuple[float, float]] = {
    TrimSize.small: (5.5, 8.5),
    TrimSize.medium: (6.0, 9.0),
    TrimSize.large: (8.5, 11.0),
}


def _escape_typst(text: str) -> str:
    """Escape special characters in Typst."""
    if not text:
        return ""
    for char in ("\\", "$", "#", "*", "_", "`", "<", ">", "@"):
        text = text.replace(char, f"\\{char}")
    return text


async def compile_pdf(
    ast: DocumentAST,
    job_id: str,
) -> Tuple[str, str]:
    """
    Compile a DocumentAST into a PDF file using Typst.
    Returns (output_path, download_url).
    """
    update_job(job_id, progress=10, message="Generating Typst layout…")

    output_dir = Path(settings.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_title = "".join(
        c if c.isalnum() or c in " _-" else "_" for c in ast.metadata.title
    ).strip()
    
    typst_filename = f"{job_id}_{safe_title}.typ"
    pdf_filename = f"{job_id}_{safe_title}.pdf"
    
    typst_path = output_dir / typst_filename
    pdf_path = output_dir / pdf_filename

    # Build Typst document
    update_job(job_id, progress=30, message="Building Typst syntax tree…")
    typst_code = _build_typst_document(ast)
    
    with open(typst_path, "w", encoding="utf-8") as f:
        f.write(typst_code)

    update_job(job_id, progress=60, message="Compiling PDF via Typst engine…")

    try:
        # Run typst compilation
        typst.compile(str(typst_path), output=str(pdf_path))
    except Exception as e:
        logger.error(f"Typst compilation failed: {e}")
        raise RuntimeError(f"Typst engine failed: {e}")

    update_job(job_id, progress=100, message="Compilation finished.")

    download_url = f"/api/download/{pdf_filename}"
    return str(pdf_path), download_url


def _build_typst_document(ast: DocumentAST) -> str:
    """Generate the full Typst markup string from the DocumentAST."""
    lines = []
    
    title = _escape_typst(ast.metadata.title)
    author = _escape_typst(ast.metadata.author)
    cs = ast.compilation_settings
    trim_w, trim_h = TRIM_DIMENSIONS.get(ast.metadata.trim_size, (6.0, 9.0))
    
    # ── Document Setup ────────────────────────────────────────────────────────
    lines.append(f'#set document(title: "{title}", author: "{author}")')
    
    # Page setup with dynamic gutters and headers
    lines.append('#set page(')
    lines.append(f'  width: {trim_w}in, height: {trim_h}in,')
    lines.append('  margin: (inside: 0.75in, outside: 0.5in, top: 0.7in, bottom: 0.7in),')
    
    # Header: Book title on even, Chapter title on odd. Suppressed on chapter openers.
    lines.append('  header: context {')
    lines.append('    let page_num = counter(page).get().first()')
    lines.append('    // Find if the current page has a chapter heading')
    lines.append('    let headings_on_page = query(heading.where(level: 1)).filter(h => h.location().page() == page_num)')
    lines.append('    if page_num > 1 and headings_on_page.len() == 0 [')
    lines.append('      #set text(size: 9pt, style: "italic")')
    lines.append('      #if calc.even(page_num) [')
    lines.append(f'        {title}')
    lines.append('      ] else [')
    lines.append('        #align(right)[#state("chapter_title", "").get()]')
    lines.append('      ]')
    lines.append('    ]')
    lines.append('  },')
    
    # Footer: Page number
    lines.append('  footer: context {')
    lines.append('    align(center)[#counter(page).display()]')
    lines.append('  }')
    lines.append(')')
    
    # Text and Par setup
    lines.append(f'#set text(font: "Linux Libertine", size: {cs.font_size}pt)')
    # Widows/orphans are inherently handled by Typst. Line breaking optimized.
    lines.append(f'#set par(justify: true, leading: {cs.line_height - 1}em, first-line-indent: 1.2em, linebreaks: "optimized")')

    # Heading 1 setup (Chapter openers)
    lines.append('#set heading(numbering: none)')
    lines.append('#show heading.where(level: 1): it => {')
    lines.append('  pagebreak(weak: true)')
    lines.append('  v(30%)')
    lines.append('  text(style: "italic", size: 10pt)[#smallcaps[Chapter ]]')
    lines.append('  v(0.5em)')
    lines.append('  text(size: 28pt, weight: "bold", font: "Linux Libertine")[#it.body]')
    lines.append('}')
    
    # Heading 2 (Subheads)
    lines.append('#show heading.where(level: 2): it => block[')
    lines.append('  #v(1.5em)')
    lines.append('  #text(size: 14pt, weight: "bold")[#it.body]')
    lines.append('  #v(0.75em)')
    lines.append(']')
    
    # Heading 3
    lines.append('#show heading.where(level: 3): it => block[')
    lines.append('  #v(1.2em)')
    lines.append('  #text(size: 12pt, weight: "bold")[#it.body]')
    lines.append('  #v(0.5em)')
    lines.append(']')
    
    # Callout box function
    lines.append('''
#let callout(variant: "info", title: none, body) = {
  let color = rgb("#F3F4F6") // gray
  let bcolor = rgb("#9CA3AF")
  if variant == "tip" { color = rgb("#F0FDF4"); bcolor = rgb("#166534") }
  else if variant == "warning" { color = rgb("#FFFBEB"); bcolor = rgb("#92400E") }
  else if variant == "danger" { color = rgb("#FEF2F2"); bcolor = rgb("#991B1B") }
  else if variant == "info" { color = rgb("#EFF6FF"); bcolor = rgb("#1D4ED8") }
  else if variant == "success" { color = rgb("#F0FDF4"); bcolor = rgb("#166534") }
  
  rect(
    width: 100%,
    fill: color,
    stroke: (left: 3pt + bcolor, rest: 0pt),
    inset: 12pt,
    radius: 0pt
  )[
    #set par(first-line-indent: 0pt)
    #if title != none [*#title*: ]
    #body
  ]
}
''')

    # ── Front Matter ──────────────────────────────────────────────────────────
    if ast.front_matter.title_page.enabled:
        lines.append('#align(center + horizon)[')
        lines.append(f'  #text(size: 24pt, weight: "bold")[{title}]')
        if ast.metadata.subtitle:
            lines.append(f'  #v(1em)')
            lines.append(f'  #text(size: 16pt, style: "italic")[{_escape_typst(ast.metadata.subtitle)}]')
        lines.append(f'  #v(2em)')
        lines.append(f'  #text(size: 14pt)[{author}]')
        lines.append(']')
        lines.append('#pagebreak()')
        
    if ast.front_matter.copyright.enabled:
        c = ast.front_matter.copyright
        lines.append('#align(bottom)[')
        lines.append(f'  Copyright © {c.year} {_escape_typst(c.holder)}\\')
        lines.append('  All rights reserved.')
        lines.append(']')
        lines.append('#pagebreak()')
        
    if ast.front_matter.table_of_contents.enabled:
        lines.append('#outline(title: "Table of Contents")')
        lines.append('#pagebreak()')
        
    if ast.front_matter.dedication.enabled and ast.front_matter.dedication.text:
        lines.append('#align(center + horizon)[')
        lines.append(f'  #text(style: "italic")[{_escape_typst(ast.front_matter.dedication.text)}]')
        lines.append(']')
        lines.append('#pagebreak()')

    # ── Chapters ──────────────────────────────────────────────────────────────
    lines.append('#counter(page).update(1)')
    
    for chapter in ast.chapters:
        ch_title = _escape_typst(chapter.title)
        lines.append(f'#state("chapter_title", "").update("{ch_title}")')
        
        # Trigger the H1 (which handles the 30% sinkage via the show rule)
        lines.append(f'#heading(level: 1)[{ch_title}]')
        
        # Subtitles and Epigraphs
        if chapter.subtitle:
            lines.append(f'#v(1em)')
            lines.append(f'#text(size: 16pt, style: "italic")[{_escape_typst(chapter.subtitle)}]')
            
        if chapter.epigraph:
            lines.append(f'#v(2em)')
            lines.append(f'#align(right)[#box(width: 60%)[')
            lines.append(f'  #text(style: "italic")[{_escape_typst(chapter.epigraph.text)}]')
            if chapter.epigraph.attribution:
                lines.append(f'  \\ --- {_escape_typst(chapter.epigraph.attribution)}')
            lines.append(']]')
            
        lines.append('#v(3em)')
        
        # Content Blocks
        first_para = True
        for block in chapter.content:
            if isinstance(block, ParagraphBlock):
                text = _escape_typst(block.text)
                if first_para:
                    # Small caps lead-in for the very first paragraph of the chapter
                    words = text.split(" ")
                    if len(words) > 3:
                        lead = " ".join(words[:4])
                        rest = " ".join(words[4:])
                        lines.append(f'#set par(first-line-indent: 0pt)')
                        lines.append(f'#smallcaps[{lead}] {rest}')
                        lines.append(f'#set par(first-line-indent: 1.2em)')
                    else:
                        lines.append(text)
                else:
                    lines.append(text)
                    
            elif isinstance(block, Heading2Block):
                lines.append(f'#heading(level: 2)[{_escape_typst(block.text)}]')
                
            elif isinstance(block, Heading3Block):
                lines.append(f'#heading(level: 3)[{_escape_typst(block.text)}]')
                
            elif isinstance(block, PullquoteBlock):
                lines.append('#v(1em)')
                lines.append('#align(center)[#box(width: 80%)[')
                lines.append(f'  #text(size: {cs.font_size + 2}pt, style: "italic", fill: rgb("#555555"))[')
                lines.append(f'    "{_escape_typst(block.text)}" ]')
                if block.attribution:
                    lines.append(f'  \\ #v(0.5em) #text(size: {cs.font_size}pt)[--- {_escape_typst(block.attribution)}]')
                lines.append(']]')
                lines.append('#v(1em)')
                
            elif isinstance(block, CalloutBlock):
                t = f'"{_escape_typst(block.title)}"' if block.title else "none"
                lines.append(f'#callout(variant: "{block.variant}", title: {t})[')
                lines.append(f'  {_escape_typst(block.text)}')
                lines.append(']')
                
            elif isinstance(block, TableBlock):
                cols = len(block.headers)
                lines.append(f'#table(columns: {cols}, fill: (x, y) => if y == 0 {{ rgb("#374151") }} else if calc.odd(y) {{ rgb("#F9FAFB") }} else {{ white }},')
                for h in block.headers:
                    lines.append(f'  [*#text(fill: white)[{_escape_typst(h)}]*],')
                for row in block.rows:
                    for cell in row:
                        lines.append(f'  [{_escape_typst(cell)}],')
                lines.append(')')
                
            elif isinstance(block, InteractiveFieldBlock):
                # Draw visual text fields
                lines.append('#v(1em)')
                lines.append(f'*{_escape_typst(block.label)}*\\ ')
                if block.field_type == "checkbox":
                    for opt in (block.options or []):
                        lines.append(f'#box(width: 10pt, height: 10pt, stroke: 1pt) {_escape_typst(opt)}  ')
                    lines.append('\n')
                else:
                    for _ in range(block.lines or 1):
                        lines.append('#v(0.5em) #line(length: 100%, stroke: 0.5pt + rgb("#9CA3AF"))')
                lines.append('#v(1em)')
                
            elif isinstance(block, PageBreakBlock):
                lines.append('#pagebreak()')
                
            elif isinstance(block, HorizontalRuleBlock):
                lines.append('#v(1em) #line(length: 100%, stroke: 0.5pt + rgb("#D1D5DB")) #v(1em)')
                
            elif isinstance(block, ImageBlock):
                lines.append(f'#align(center)[ [Image Placeholder: {_escape_typst(block.alt or block.src)}] ]')

            lines.append('\n')
            first_para = False

    return "\n".join(lines)
