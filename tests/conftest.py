"""
BookCraft AI - Pytest Conftest & Shared Test Fixtures
"""
from __future__ import annotations
import asyncio
import io
import json
import os
from pathlib import Path
import sys
import zipfile
import pytest

# Ensure project root and backend directory are on sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from tests.fixtures import FIXTURES_DIR
from tests.fixtures.generate_fixtures import (
    create_minimal_valid_docx,
    create_minimal_valid_pdf,
    generate_empty_files,
    generate_corrupt_files,
    generate_binary_fixtures,
)

# Ensure binary fixtures exist on test startup
generate_empty_files()
generate_corrupt_files()
generate_binary_fixtures()


@pytest.fixture(scope="session")
def event_loop():
    """Create session-wide event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def sample_ast_data() -> dict:
    """Load the canonical sample_multi_chapter.json AST dictionary."""
    ast_path = FIXTURES_DIR / "sample_multi_chapter.json"
    with open(ast_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_ast(sample_ast_data: dict):
    """Return a validated DocumentAST instance."""
    from app.models.document_ast import DocumentAST
    return DocumentAST(**sample_ast_data)


@pytest.fixture
def minimal_ast():
    """Return a minimal valid DocumentAST instance."""
    from app.models.document_ast import DocumentAST, BookMetadata, Genre, TrimSize, Chapter, ParagraphBlock
    return DocumentAST(
        metadata=BookMetadata(
            title="Minimal Test Book",
            author="Test Author",
            genre=Genre.fiction,
            trim_size=TrimSize.medium,
        ),
        chapters=[
            Chapter(
                chapter_number=1,
                title="Chapter One",
                content=[
                    ParagraphBlock(type="paragraph", text="This is a minimal test paragraph.")
                ],
                word_count=6,
            )
        ],
    )


@pytest.fixture
def fifteen_page_ast():
    """Return a DocumentAST with exactly 15 chapters (15 page equivalents)."""
    from app.models.document_ast import DocumentAST, BookMetadata, Genre, TrimSize, Chapter, ParagraphBlock
    chapters = [
        Chapter(
            chapter_number=i,
            title=f"Seal of Epoch {i}",
            content=[
                ParagraphBlock(
                    type="paragraph",
                    text=f"Historical chronicle and lore for epoch {i}. The scribes recorded the annals with care and precision.",
                )
            ],
            word_count=50,
        )
        for i in range(1, 16)
    ]
    return DocumentAST(
        metadata=BookMetadata(
            title="Chronicles of Aethelgard: The Fifteen Seals",
            author="Master Chronicler Brandon",
            genre=Genre.fiction,
            trim_size=TrimSize.medium,
        ),
        chapters=chapters,
    )


@pytest.fixture
def twenty_five_page_ast():
    """Return a DocumentAST with 25 chapters (>15 pages)."""
    from app.models.document_ast import DocumentAST, BookMetadata, Genre, TrimSize, Chapter, ParagraphBlock
    chapters = [
        Chapter(
            chapter_number=i,
            title=f"Sector Navigation Module {i}",
            content=[
                ParagraphBlock(
                    type="paragraph",
                    text=f"Deep space astronavigation telemetry and guidance protocols for sector {i}. Relativistic drift compensation vectors mapped.",
                )
            ],
            word_count=60,
        )
        for i in range(1, 26)
    ]
    return DocumentAST(
        metadata=BookMetadata(
            title="The Encyclopedia of Astronavigation",
            author="Dr. Victoria Chen",
            genre=Genre.technical,
            trim_size=TrimSize.medium,
        ),
        chapters=chapters,
    )


@pytest.fixture
def unicode_ast():
    """Return a DocumentAST with unicode, emojis, and multilingual scripts."""
    from app.models.document_ast import DocumentAST, BookMetadata, Genre, TrimSize, Chapter, ParagraphBlock, Heading2Block
    return DocumentAST(
        metadata=BookMetadata(
            title="✨ Le Guide Épique 2026: 宇宙 & Приключения 🚀",
            author="José Müller & 桜井 健太",
            genre=Genre.non_fiction,
            trim_size=TrimSize.large,
        ),
        chapters=[
            Chapter(
                chapter_number=1,
                title="L'Aventure Multilingue — 日本語と宇宙",
                content=[
                    ParagraphBlock(
                        type="paragraph",
                        text="Dans un univers infini, l'exploration spatiale unit toutes les cultures terrestres. 🌟 🪐 🛰️",
                    ),
                    Heading2Block(
                        type="heading2",
                        text="Символы и Формулы (Спектральный анализ)",
                    ),
                    ParagraphBlock(
                        type="paragraph",
                        text="Добро пожаловать в будущее книгоиздания! 欢迎使用智能排版系统。",
                    ),
                ],
                word_count=45,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Verification Helpers
# ---------------------------------------------------------------------------

def is_valid_pdf_bytes(data: bytes) -> bool:
    """Verify data has %PDF header and %%EOF trailer."""
    if len(data) < 32:
        return False
    return data.startswith(b"%PDF-") and (b"%%EOF" in data or b"stream" in data)


def is_valid_docx_bytes(data: bytes) -> bool:
    """Verify data is a valid zip containing OpenXML document structure."""
    if len(data) < 30:
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            namelist = zf.namelist()
            return "word/document.xml" in namelist or "[Content_Types].xml" in namelist
    except Exception:
        return False


def is_valid_epub_bytes(data: bytes) -> bool:
    """Verify data is a valid zip containing mimetype and META-INF/container.xml."""
    if len(data) < 30:
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            namelist = zf.namelist()
            return "mimetype" in namelist or "META-INF/container.xml" in namelist
    except Exception:
        return False


def is_valid_md_string(text: str) -> bool:
    """Verify text is a valid markdown representation."""
    if not isinstance(text, str) or len(text.strip()) == 0:
        return False
    return ("#" in text or "==" in text or "\n" in text)
