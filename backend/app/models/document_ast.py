"""
Pydantic models mirroring the DocumentAST JSON Schema.
These are used for request/response validation throughout the API.
"""
from __future__ import annotations
from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Genre(str, Enum):
    fiction = "fiction"
    non_fiction = "non-fiction"
    biography = "biography"
    self_help = "self-help"
    business = "business"
    academic = "academic"
    children = "children"
    poetry = "poetry"
    anthology = "anthology"
    technical = "technical"
    other = "other"


class TrimSize(str, Enum):
    small = "5.5x8.5"
    medium = "6x9"
    large = "8.5x11"


class FontFamily(str, Enum):
    garamond = "Garamond"
    times = "Times New Roman"
    georgia = "Georgia"
    palatino = "Palatino"
    helvetica = "Helvetica"
    arial = "Arial"


# ---------------------------------------------------------------------------
# Content Blocks
# ---------------------------------------------------------------------------

class ParagraphBlock(BaseModel):
    id: Optional[str] = None
    type: Literal["paragraph"]
    text: str
    indent: bool = True
    align: Literal["left", "center", "right", "justify"] = "justify"


class Heading2Block(BaseModel):
    id: Optional[str] = None
    type: Literal["heading2"]
    text: str
    numbering: bool = False


class Heading3Block(BaseModel):
    id: Optional[str] = None
    type: Literal["heading3"]
    text: str


class CalloutBlock(BaseModel):
    id: Optional[str] = None
    type: Literal["callout"]
    variant: Literal["info", "tip", "warning", "danger", "success"] = "info"
    title: Optional[str] = None
    text: str


class PullquoteBlock(BaseModel):
    id: Optional[str] = None
    type: Literal["pullquote"]
    text: str
    attribution: Optional[str] = None
    align: Literal["left", "center", "right"] = "center"


class TableBlock(BaseModel):
    id: Optional[str] = None
    type: Literal["table"]
    caption: Optional[str] = None
    headers: list[str]
    rows: list[list[str]]
    column_alignments: Optional[list[Literal["left", "center", "right"]]] = None
    striped: bool = True


class InteractiveFieldBlock(BaseModel):
    id: Optional[str] = None
    type: Literal["interactive-field"]
    field_type: Literal["text", "multiline", "checkbox", "radio", "date", "signature"]
    label: str
    placeholder: Optional[str] = None
    required: bool = False
    options: Optional[list[str]] = None
    lines: int = 3


class ImageBlock(BaseModel):
    id: Optional[str] = None
    type: Literal["image"]
    src: str
    alt: Optional[str] = None
    caption: Optional[str] = None
    width: Optional[str] = None
    align: Literal["left", "center", "right"] = "center"


class PageBreakBlock(BaseModel):
    id: Optional[str] = None
    type: Literal["page-break"]


class HorizontalRuleBlock(BaseModel):
    id: Optional[str] = None
    type: Literal["horizontal-rule"]
    style: Literal["line", "dots", "asterisks", "ornament"] = "line"


# Discriminated union of all block types
ContentBlock = Union[
    ParagraphBlock,
    Heading2Block,
    Heading3Block,
    CalloutBlock,
    PullquoteBlock,
    TableBlock,
    InteractiveFieldBlock,
    ImageBlock,
    PageBreakBlock,
    HorizontalRuleBlock,
]


# ---------------------------------------------------------------------------
# Chapter
# ---------------------------------------------------------------------------

class Epigraph(BaseModel):
    text: str
    attribution: Optional[str] = None


class Chapter(BaseModel):
    id: Optional[str] = None
    chapter_number: int = Field(ge=1)
    title: str
    subtitle: Optional[str] = None
    epigraph: Optional[Epigraph] = None
    content: list[ContentBlock] = Field(default_factory=list)
    word_count: Optional[int] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Front Matter
# ---------------------------------------------------------------------------

class TitlePage(BaseModel):
    enabled: bool = True
    display_title: Optional[str] = None
    display_subtitle: Optional[str] = None
    display_author: Optional[str] = None
    display_publisher: Optional[str] = None


class CopyrightPage(BaseModel):
    enabled: bool = True
    year: Optional[int] = None
    holder: Optional[str] = None
    statement: Optional[str] = None
    rights_reserved: bool = True
    printed_in: Optional[str] = None
    edition: Optional[str] = None
    disclaimer: Optional[str] = None


class TableOfContents(BaseModel):
    enabled: bool = True
    title: str = "Table of Contents"
    include_subheadings: bool = False
    max_depth: int = Field(default=1, ge=1, le=3)


class DedicationPage(BaseModel):
    enabled: bool = False
    text: Optional[str] = None


class ForewordPage(BaseModel):
    enabled: bool = False
    author: Optional[str] = None
    content: list[ContentBlock] = Field(default_factory=list)


class PrefacePage(BaseModel):
    enabled: bool = False
    content: list[ContentBlock] = Field(default_factory=list)


class AcknowledgementsPage(BaseModel):
    enabled: bool = False
    content: list[ContentBlock] = Field(default_factory=list)


class FrontMatter(BaseModel):
    title_page: TitlePage = Field(default_factory=TitlePage)
    copyright: CopyrightPage = Field(default_factory=CopyrightPage)
    table_of_contents: TableOfContents = Field(default_factory=TableOfContents)
    dedication: DedicationPage = Field(default_factory=DedicationPage)
    foreword: ForewordPage = Field(default_factory=ForewordPage)
    preface: PrefacePage = Field(default_factory=PrefacePage)
    acknowledgements: AcknowledgementsPage = Field(default_factory=AcknowledgementsPage)


# ---------------------------------------------------------------------------
# Book Metadata
# ---------------------------------------------------------------------------

class BookMetadata(BaseModel):
    title: str
    subtitle: Optional[str] = None
    author: str
    co_authors: list[str] = Field(default_factory=list)
    genre: Genre
    trim_size: TrimSize
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    published_year: Optional[int] = None
    edition: Optional[str] = None
    language: str = "en"
    keywords: list[str] = Field(default_factory=list)
    cover_image_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Compilation Settings
# ---------------------------------------------------------------------------

class MarginSettings(BaseModel):
    top: float = 1.0
    bottom: float = 1.0
    inner: float = 1.25
    outer: float = 0.75


class HeaderFooterSettings(BaseModel):
    show_page_numbers: bool = True
    show_chapter_title: bool = True
    show_book_title: bool = True


class CompilationSettings(BaseModel):
    font_family: FontFamily = FontFamily.garamond
    font_size: int = Field(default=11, ge=8, le=16)
    line_height: float = Field(default=1.5, ge=1.0, le=3.0)
    margins: MarginSettings = Field(default_factory=MarginSettings)
    chapter_start_page: Literal["any", "recto", "verso"] = "recto"
    header_footer: HeaderFooterSettings = Field(default_factory=HeaderFooterSettings)


# ---------------------------------------------------------------------------
# Root DocumentAST
# ---------------------------------------------------------------------------

class DocumentAST(BaseModel):
    """
    The unified document representation for BookCraft AI.
    Maps 1-to-1 with document-ast.schema.json.
    """
    metadata: BookMetadata
    front_matter: FrontMatter = Field(default_factory=FrontMatter)
    chapters: list[Chapter] = Field(default_factory=list)
    compilation_settings: CompilationSettings = Field(default_factory=CompilationSettings)

    class Config:
        json_schema_extra = {
            "example": {
                "metadata": {
                    "title": "My First Book",
                    "author": "Jane Doe",
                    "genre": "non-fiction",
                    "trim_size": "6x9",
                },
                "chapters": [
                    {
                        "chapter_number": 1,
                        "title": "Introduction",
                        "content": [
                            {"type": "paragraph", "text": "Welcome to my book."}
                        ],
                    }
                ],
            }
        }
