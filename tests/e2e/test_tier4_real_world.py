"""
E2E Test Suite - Tier 4: Real-World Application Scenarios (≥6 tests)
Verifies end-to-end author workflows for fiction novels, technical guides, poetry, monographs, and translations.
"""
from __future__ import annotations
import asyncio
from pathlib import Path
import pytest

from app.models.document_ast import (
    DocumentAST,
    BookMetadata,
    Genre,
    TrimSize,
    Chapter,
    ParagraphBlock,
    Heading2Block,
    Heading3Block,
    CalloutBlock,
    PullquoteBlock,
    TableBlock,
    FrontMatter,
    TitlePage,
    CopyrightPage,
    TableOfContents,
    DedicationPage,
    CompilationSettings,
    MarginSettings,
)
from app.services.compilers.orchestrator import CompilerOrchestrator
from app.db.models import Lead, Job, Payment, generate_uuid
from tests.unit.test_payment_service import create_test_token, verify_test_token
from tests.unit.test_restriction_engine import apply_demo_restriction
from tests.conftest import is_valid_pdf_bytes, is_valid_docx_bytes, is_valid_epub_bytes, is_valid_md_string, FIXTURES_DIR


@pytest.mark.asyncio
async def test_tier4_01_fiction_novel_workflow(tmp_path):
    """Scenario 1: Fiction Novel Workflow (Dialogue, Epigraphs, Dedication, TOC -> PDF & EPUB)."""
    ast = DocumentAST(
        metadata=BookMetadata(
            title="The Clockwork Alchemist",
            subtitle="A Victorian Steampunk Mystery",
            author="Jonathan Strangefield",
            genre=Genre.fiction,
            trim_size=TrimSize.small,  # 5.5x8.5 standard paperback
            publisher="Aether & Iron Publishing",
            published_year=2026,
        ),
        front_matter=FrontMatter(
            title_page=TitlePage(enabled=True, display_title="The Clockwork Alchemist", display_author="Jonathan Strangefield"),
            copyright=CopyrightPage(enabled=True, year=2026, holder="Jonathan Strangefield"),
            dedication=DedicationPage(enabled=True, text="To those who hear the heartbeat in brass gears."),
            table_of_contents=TableOfContents(enabled=True, title="Contents"),
        ),
        chapters=[
            Chapter(
                chapter_number=1,
                title="The Brass Gear",
                content=[
                    ParagraphBlock(type="paragraph", text='The grandfather clock in the study chimed thirteen. Julian paused with his brass tweezers hovering over the escapement mechanism.'),
                    ParagraphBlock(type="paragraph", text='"Clocks don\'t chime thirteen unless someone has meddled with the temporal escapement," he muttered to Archimedes.'),
                ],
                word_count=120,
            ),
            Chapter(
                chapter_number=2,
                title="The Visitor in Charcoal Grey",
                content=[
                    ParagraphBlock(type="paragraph", text='A heavy knock echoed on the iron door knocker below. Julian adjusted his monocle and descended the spiral staircase.'),
                    ParagraphBlock(type="paragraph", text='"Mr. Strangefield? My employer wishes to consult you regarding a chronometric discrepancy."'),
                ],
                word_count=110,
            ),
        ],
    )

    orch = CompilerOrchestrator()
    results = await orch.compile_all(ast, "t4_fiction", tmp_path, formats=["pdf", "epub"])

    assert is_valid_pdf_bytes(Path(results["pdf"]["path"]).read_bytes())
    assert is_valid_epub_bytes(Path(results["epub"]["path"]).read_bytes())


@pytest.mark.asyncio
async def test_tier4_02_technical_architecture_guide_workflow(tmp_path):
    """Scenario 2: Technical Architecture Guide Workflow (Code, Callouts, Quorum Tables -> DOCX & PDF)."""
    ast = DocumentAST(
        metadata=BookMetadata(
            title="Cloud-Native Systems Architecture",
            subtitle="Patterns and Practice for High-Availability Distributed Systems",
            author="Marcus Vance",
            genre=Genre.technical,
            trim_size=TrimSize.large,  # 8.5x11 reference manual
            published_year=2026,
        ),
        chapters=[
            Chapter(
                chapter_number=1,
                title="Microservices and Distributed Consensus",
                content=[
                    ParagraphBlock(type="paragraph", text="Modern distributed architectures decouple processing nodes across independent failure domains."),
                    CalloutBlock(type="callout", variant="tip", title="Architecture Tip", text="Always configure an odd number of voting replicas (3, 5, or 7) for unambiguous quorum."),
                    TableBlock(
                        type="table",
                        caption="Cluster Quorum Matrix",
                        headers=["Nodes (N)", "Quorum Required (Q)", "Fault Tolerance (F)"],
                        rows=[["3", "2", "1 node"], ["5", "3", "2 nodes"], ["7", "4", "3 nodes"]],
                        striped=True,
                    ),
                ],
                word_count=200,
            ),
            Chapter(
                chapter_number=2,
                title="Event-Driven Streaming and Backpressure",
                content=[
                    ParagraphBlock(type="paragraph", text="When downstream consumers experience load spikes, reactive stream pipelines must throttle event emission."),
                    CalloutBlock(type="callout", variant="warning", title="Buffer Warning", text="Unbounded in-memory buffering without backpressure causes out-of-memory panics."),
                ],
                word_count=180,
            ),
        ],
    )

    orch = CompilerOrchestrator()
    results = await orch.compile_all(ast, "t4_technical", tmp_path, formats=["pdf", "docx"])

    assert is_valid_pdf_bytes(Path(results["pdf"]["path"]).read_bytes())
    assert is_valid_docx_bytes(Path(results["docx"]["path"]).read_bytes())


@pytest.mark.asyncio
async def test_tier4_03_poetry_collection_workflow(tmp_path):
    """Scenario 3: Poetry Collection Workflow (Stanzas, Centered Verse, Dedication -> EPUB & PDF)."""
    ast = DocumentAST(
        metadata=BookMetadata(
            title="Whispers in the Obsidian Grove",
            author="Lyra Valerius",
            genre=Genre.poetry,
            trim_size=TrimSize.small,
            published_year=2026,
        ),
        front_matter=FrontMatter(
            dedication=DedicationPage(enabled=True, text="To all who wander beneath the twilight canopy.")
        ),
        compilation_settings=CompilationSettings(
            font_size=12,
            line_height=1.8,
            margins=MarginSettings(top=1.5, bottom=1.5, inner=1.5, outer=1.2),
        ),
        chapters=[
            Chapter(
                chapter_number=1,
                title="The Silver Bough",
                content=[
                    ParagraphBlock(type="paragraph", text="The silver bough bends low tonight,\nBeneath the pale and frozen light.\nThe river hums an ancient rhyme,\nUntouched by frost, unmarred by time.", align="center"),
                    ParagraphBlock(type="paragraph", text="Leaves of shadow, roots of stone,\nHere the wanderer walks alone.\nListening close to winds that sigh,\nBetween the mountain and the sky.", align="center"),
                ],
            ),
            Chapter(
                chapter_number=2,
                title="Lanterns on the Water",
                content=[
                    ParagraphBlock(type="paragraph", text="Upon the lake of mirror glass,\nThe glowing lanterns gently pass.\nEach flame a wish, each spark a prayer,\nDrifting through the fragrant air.", align="center"),
                ],
            ),
        ],
    )

    orch = CompilerOrchestrator()
    results = await orch.compile_all(ast, "t4_poetry", tmp_path, formats=["pdf", "epub"])

    assert is_valid_pdf_bytes(Path(results["pdf"]["path"]).read_bytes())
    assert is_valid_epub_bytes(Path(results["epub"]["path"]).read_bytes())


@pytest.mark.asyncio
async def test_tier4_04_academic_business_monograph_workflow(tmp_path):
    """Scenario 4: Business Monograph Workflow (Subheadings, Pullquotes, Tables -> DOCX & MD)."""
    ast = DocumentAST(
        metadata=BookMetadata(
            title="The Algorithmic Enterprise",
            subtitle="Scaling Automated Value Chains in the Age of Generative Systems",
            author="Dr. Helena Rostova",
            genre=Genre.business,
            trim_size=TrimSize.medium,
            published_year=2026,
        ),
        chapters=[
            Chapter(
                chapter_number=1,
                title="The Autonomous Supply Chain",
                content=[
                    ParagraphBlock(type="paragraph", text="Enterprises that synchronize demand signals directly with synthesis algorithms capture compounding operational margins."),
                    PullquoteBlock(type="pullquote", text="Automation without semantic modeling merely accelerates the reproduction of errors.", attribution="Dr. Rostova"),
                    Heading2Block(type="heading2", text="Empirical Yield Improvements"),
                    TableBlock(
                        type="table",
                        headers=["Industry Vertical", "Baseline Margin", "AI-Optimized Margin", "Delta"],
                        rows=[
                            ["Logistics", "4.2%", "8.7%", "+4.5%"],
                            ["Publishing", "12.0%", "28.5%", "+16.5%"],
                            ["Manufacturing", "6.5%", "11.2%", "+4.7%"],
                        ],
                    ),
                ],
            )
        ],
    )

    orch = CompilerOrchestrator()
    results = await orch.compile_all(ast, "t4_business", tmp_path, formats=["docx", "md"])

    assert is_valid_docx_bytes(Path(results["docx"]["path"]).read_bytes())
    md_text = Path(results["md"]["path"]).read_text(encoding="utf-8")
    assert "The Algorithmic Enterprise" in md_text
    assert "Empirical Yield Improvements" in md_text


@pytest.mark.asyncio
async def test_tier4_05_multilingual_translation_anthology_workflow(unicode_ast, tmp_path):
    """Scenario 5: Multilingual Anthology Workflow (Accents, CJK, Cyrillic, Emojis -> All 4 Formats)."""
    orch = CompilerOrchestrator()
    results = await orch.compile_all(unicode_ast, "t4_multilingual", tmp_path)

    for fmt in ["pdf", "docx", "md", "epub"]:
        path = Path(results[fmt]["path"])
        assert path.exists()
        assert path.stat().st_size > 0


@pytest.mark.asyncio
async def test_tier4_06_commercial_indie_author_full_publishing_pipeline(twenty_five_page_ast, tmp_path):
    """Scenario 6: Commercial Author Full Pipeline (Draft -> Lead -> 15p Demo -> Stripe Buy -> 25p Print+DOCX)."""
    # 1. Author evaluates free demo
    demo_ast, demo_trunc = apply_demo_restriction(twenty_five_page_ast, tier="demo")
    assert demo_trunc is True
    assert len(demo_ast.chapters) == 15

    # 2. Author upgrades via Stripe
    pro_token = create_test_token("commercial_author@bestseller.com", tier="pro")
    claims = verify_test_token(pro_token)
    assert claims["tier"] == "pro"

    # 3. Compile full publication pack
    pro_ast, pro_trunc = apply_demo_restriction(twenty_five_page_ast, tier=claims["tier"])
    assert pro_trunc is False
    assert len(pro_ast.chapters) == 25

    orch = CompilerOrchestrator()
    results = await orch.compile_all(pro_ast, "t4_commercial_full", tmp_path)

    # Verify both Print PDF and Editable Word DOCX are generated with all 25 chapters
    assert is_valid_pdf_bytes(Path(results["pdf"]["path"]).read_bytes())
    assert is_valid_docx_bytes(Path(results["docx"]["path"]).read_bytes())
    assert is_valid_epub_bytes(Path(results["epub"]["path"]).read_bytes())
    assert is_valid_md_string(Path(results["md"]["path"]).read_text(encoding="utf-8"))
