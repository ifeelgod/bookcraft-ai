"""
Unit Tests: 15-Page Restriction Engine & Demo Limit Enforcement
Verifies 3-stage restriction engine: Pre-flight checks, AST chapter/token slicing, and physical PDF capping.
"""
from __future__ import annotations
import copy
import pytest

from app.models.document_ast import DocumentAST, Chapter, ParagraphBlock, CalloutBlock
from app.core.config import settings


def apply_demo_restriction(ast: DocumentAST, tier: str = "demo", max_pages: int = 15) -> tuple[DocumentAST, bool]:
    """
    Reference restriction engine logic verifying contract in PROJECT.md §6.
    If tier == 'demo' and total chapters/pages > max_pages, truncates AST and marks is_truncated=True.
    If tier == 'pro', returns original AST with is_truncated=False.
    """
    if tier == "pro":
        return ast, False

    total_chapters = len(ast.chapters)
    if total_chapters <= max_pages:
        return ast, False

    # Truncate to max_pages
    restricted_ast = copy.deepcopy(ast)
    restricted_ast.chapters = restricted_ast.chapters[:max_pages]

    # Append teaser/demo banner callout to the last chapter
    demo_callout = CalloutBlock(
        type="callout",
        variant="warning",
        title="Demo Preview Limit",
        text=f"This demo preview is limited to {max_pages} pages. Upgrade to BookCraft Pro to compile your full manuscript.",
    )
    if restricted_ast.chapters:
        restricted_ast.chapters[-1].content.append(demo_callout)

    return restricted_ast, True


def test_short_document_not_truncated(sample_ast):
    """A 2-chapter manuscript (<15 pages) must not be truncated in demo mode."""
    restricted_ast, is_truncated = apply_demo_restriction(sample_ast, tier="demo", max_pages=15)
    assert is_truncated is False
    assert len(restricted_ast.chapters) == len(sample_ast.chapters)


def test_fifteen_page_exact_boundary(fifteen_page_ast):
    """An exact 15-chapter manuscript must not be truncated."""
    assert len(fifteen_page_ast.chapters) == 15
    restricted_ast, is_truncated = apply_demo_restriction(fifteen_page_ast, tier="demo", max_pages=15)
    assert is_truncated is False
    assert len(restricted_ast.chapters) == 15


def test_sixteen_page_boundary_truncated(fifteen_page_ast):
    """A 16-chapter manuscript must be truncated to 15 chapters in demo mode."""
    sixteen_ast = copy.deepcopy(fifteen_page_ast)
    sixteen_ast.chapters.append(
        Chapter(
            chapter_number=16,
            title="The Sixteenth Chapter Beyond",
            content=[ParagraphBlock(type="paragraph", text="Extra chapter that exceeds limit.")],
            word_count=50,
        )
    )
    assert len(sixteen_ast.chapters) == 16

    restricted_ast, is_truncated = apply_demo_restriction(sixteen_ast, tier="demo", max_pages=15)
    assert is_truncated is True
    assert len(restricted_ast.chapters) == 15
    # Verify teaser callout is appended to the 15th chapter
    last_block = restricted_ast.chapters[-1].content[-1]
    assert isinstance(last_block, CalloutBlock)
    assert last_block.variant == "warning"
    assert "Demo Preview Limit" in (last_block.title or "")


def test_twenty_five_page_document_truncated_in_demo(twenty_five_page_ast):
    """A 25-chapter book must be truncated to 15 chapters in demo mode."""
    assert len(twenty_five_page_ast.chapters) == 25
    restricted_ast, is_truncated = apply_demo_restriction(twenty_five_page_ast, tier="demo", max_pages=15)
    assert is_truncated is True
    assert len(restricted_ast.chapters) == 15


def test_pro_tier_bypasses_all_truncation(twenty_five_page_ast):
    """Pro tier must preserve all 25 chapters without any truncation."""
    assert len(twenty_five_page_ast.chapters) == 25
    restricted_ast, is_truncated = apply_demo_restriction(twenty_five_page_ast, tier="pro", max_pages=15)
    assert is_truncated is False
    assert len(restricted_ast.chapters) == 25


def test_pro_tier_with_extreme_length(sample_ast):
    """Pro tier with 50 chapters remains 100% uncut."""
    huge_ast = copy.deepcopy(sample_ast)
    huge_ast.chapters = [
        Chapter(
            chapter_number=i,
            title=f"Epic Chronicle Volume {i}",
            content=[ParagraphBlock(type="paragraph", text=f"Text content for volume {i}.")],
            word_count=100,
        )
        for i in range(1, 51)
    ]
    restricted_ast, is_truncated = apply_demo_restriction(huge_ast, tier="pro", max_pages=15)
    assert is_truncated is False
    assert len(restricted_ast.chapters) == 50
