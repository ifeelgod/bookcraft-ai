"""
Markdown Extractor
Extracts text from Markdown (.md) files.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("bookcraft.extractor.md")


@dataclass
class ExtractedMdResult:
    title: str
    author: str
    raw_text: str


def extract_md(file_path: str) -> ExtractedMdResult:
    """
    Extract text from a Markdown file.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    title = path.stem
    author = "Unknown Author"

    return ExtractedMdResult(
        title=title,
        author=author,
        raw_text=text,
    )


def md_to_tagged_text(result: ExtractedMdResult) -> str:
    """
    Convert Markdown text to tagged text for AI parsing.
    """
    lines: list[str] = []
    
    # Split by double newlines for paragraph separation
    blocks = result.raw_text.split("\n\n")
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
            
        if block.startswith("# "):
            lines.append(f"[HEADING1] {block[2:].strip()}")
        elif block.startswith("## "):
            lines.append(f"[HEADING2] {block[3:].strip()}")
        elif block.startswith("### "):
            lines.append(f"[HEADING3] {block[4:].strip()}")
        elif block.startswith("> "):
            # Strip > from blockquote
            clean_quote = "\n".join(line.lstrip("> ") for line in block.split("\n"))
            lines.append(f"[QUOTE] {clean_quote}")
        elif block.startswith("- ") or block.startswith("* "):
            lines.append(f"[PARA] {block}")
        else:
            lines.append(f"[PARA] {block}")

    return "\n\n".join(lines)
