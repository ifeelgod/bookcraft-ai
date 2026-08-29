"""
EPUB3 Compiler implementation.
Compiles DocumentAST into valid, reflowable EPUB 3 ebook packages with navigation document,
Dublin Core metadata, responsive CSS stylesheets, and structured XHTML chapters.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import html
import logging
import re
import uuid
import zipfile
from pathlib import Path
from typing import List, Tuple

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

logger = logging.getLogger("bookcraft.compiler.epub")

EPUB_CSS = """
/* BookCraft AI Standard EPUB3 Stylesheet */
@charset "UTF-8";

body {
    font-family: "Georgia", "Times New Roman", serif;
    font-size: 1.05em;
    line-height: 1.6;
    margin: 5% 5% 5% 5%;
    padding: 0;
    color: #1a1a1a;
}

h1.book-title {
    font-size: 2.2em;
    font-weight: bold;
    text-align: center;
    margin-top: 25%;
    margin-bottom: 0.3em;
    color: #111827;
}

h2.book-subtitle {
    font-size: 1.3em;
    font-style: italic;
    font-weight: normal;
    text-align: center;
    margin-bottom: 2em;
    color: #4b5563;
}

p.book-author {
    font-size: 1.2em;
    font-weight: bold;
    text-align: center;
    margin-top: 2em;
    color: #1f2937;
}

p.book-publisher {
    font-size: 0.9em;
    text-align: center;
    color: #6b7280;
}

/* Chapter Headers */
.chapter-opener {
    margin-top: 15%;
    margin-bottom: 2em;
}

.chapter-number {
    font-size: 0.9em;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #6b7280;
    margin-bottom: 0.2em;
}

h1.chapter-title {
    font-size: 1.8em;
    font-weight: bold;
    color: #111827;
    margin-top: 0;
    margin-bottom: 0.5em;
}

h2.chapter-subtitle {
    font-size: 1.2em;
    font-style: italic;
    color: #4b5563;
    margin-bottom: 1.5em;
}

/* Epigraph */
.epigraph {
    margin: 1.5em 0 2em 2em;
    padding-left: 1em;
    border-left: 2px solid #d1d5db;
    font-style: italic;
    color: #4b5563;
}

.epigraph-attribution {
    text-align: right;
    font-size: 0.9em;
    color: #6b7280;
    margin-top: 0.5em;
}

/* Paragraphs & Headings */
p {
    margin: 0 0 0.8em 0;
    text-align: justify;
}

h2 {
    font-size: 1.35em;
    font-weight: bold;
    color: #1f2937;
    margin-top: 1.8em;
    margin-bottom: 0.6em;
}

h3 {
    font-size: 1.15em;
    font-weight: bold;
    color: #374151;
    margin-top: 1.4em;
    margin-bottom: 0.4em;
}

/* Callouts */
.callout {
    margin: 1.5em 0;
    padding: 1em 1.2em;
    border-radius: 4px;
    border-left: 4px solid #9ca3af;
    background-color: #f9fafb;
}

.callout-info {
    border-left-color: #2563eb;
    background-color: #eff6ff;
}

.callout-tip {
    border-left-color: #16a34a;
    background-color: #f0fdf4;
}

.callout-warning {
    border-left-color: #d97706;
    background-color: #fffbeb;
}

.callout-danger {
    border-left-color: #dc2626;
    background-color: #fef2f2;
}

.callout-title {
    font-weight: bold;
    margin-bottom: 0.4em;
    color: #111827;
}

/* Pullquotes */
.pullquote {
    margin: 2em 1.5em;
    padding: 0.8em 0;
    border-top: 1px solid #e5e7eb;
    border-bottom: 1px solid #e5e7eb;
    text-align: center;
    font-size: 1.15em;
    font-style: italic;
    color: #374151;
}

.pullquote-attribution {
    display: block;
    font-size: 0.85em;
    color: #6b7280;
    margin-top: 0.5em;
    font-style: normal;
}

/* Tables */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 1.5em 0;
    font-size: 0.9em;
}

th {
    background-color: #374151;
    color: #ffffff;
    padding: 0.6em 0.8em;
    text-align: left;
    font-weight: bold;
}

td {
    padding: 0.5em 0.8em;
    border-bottom: 1px solid #e5e7eb;
}

tr:nth-child(even) td {
    background-color: #f9fafb;
}

/* Interactive & Forms */
.interactive-field {
    margin: 1.2em 0;
    padding: 0.8em 1em;
    background-color: #f3f4f6;
    border-radius: 4px;
}

.interactive-label {
    font-weight: bold;
    margin-bottom: 0.4em;
}

.interactive-checkbox {
    margin: 0.3em 0 0.3em 1em;
}

/* Dividers */
hr {
    border: none;
    border-top: 1px solid #d1d5db;
    margin: 2em 0;
}

.ornament {
    text-align: center;
    margin: 1.5em 0;
    color: #9ca3af;
    letter-spacing: 0.3em;
}

/* Navigation & Frontmatter */
nav#toc ol {
    list-style-type: decimal;
    padding-left: 1.5em;
}

nav#toc li {
    margin-bottom: 0.6em;
}

.dedication {
    margin-top: 25%;
    text-align: center;
    font-style: italic;
}

.copyright-page {
    margin-top: 40%;
    font-size: 0.85em;
    color: #4b5563;
}
"""


def _inline_md_to_xhtml(text: str) -> str:
    """Convert markdown inline bold/italic/code/links to safe valid XHTML."""
    if not text:
        return ""

    # Escape HTML special chars first
    escaped = html.escape(text)

    # Convert ***bold-italic***
    escaped = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', escaped)
    # Convert **bold**
    escaped = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escaped)
    # Convert *italic*
    escaped = re.sub(r'\*(.+?)\*', r'<em>\1</em>', escaped)
    # Convert `code`
    escaped = re.sub(r'`(.+?)`', r'<code>\1</code>', escaped)

    return escaped


def _wrap_xhtml(title: str, body_content: str) -> str:
    """Wrap XHTML body in standard EPUB 3 document envelope."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="en" lang="en">
<head>
    <meta charset="UTF-8"/>
    <title>{html.escape(title)}</title>
    <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
{body_content}
</body>
</html>"""


class EpubCompiler(BaseCompiler):
    """EPUB 3 Compiler generating reflowable ebook packages."""

    @property
    def format_name(self) -> str:
        return "epub"

    @property
    def file_extension(self) -> str:
        return ".epub"

    @property
    def mime_type(self) -> str:
        return "application/epub+zip"

    async def compile(
        self,
        ast: DocumentAST,
        job_id: str,
        output_dir: Path,
    ) -> Tuple[Path, str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_title = sanitize_filename(ast.metadata.title)
        epub_filename = f"{job_id}_{safe_title}.epub"
        epub_path = output_dir / epub_filename

        def _build_epub():
            self._create_epub_archive(ast, epub_path)

        try:
            await asyncio.to_thread(_build_epub)
        except Exception as e:
            logger.error(f"EPUB compilation failed: {e}")
            raise RuntimeError(f"EPUB compiler failed: {e}")

        download_url = self.get_download_url(epub_filename)
        return epub_path, download_url

    def _create_epub_archive(self, ast: DocumentAST, output_path: Path) -> None:
        """Construct a complete, standard-compliant EPUB3 zip archive."""
        book_id = f"urn:uuid:{uuid.uuid4()}"
        iso_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        title = ast.metadata.title
        author = ast.metadata.author
        language = ast.metadata.language or "en"

        manifest_items: List[Tuple[str, str, str, str]] = []  # (id, href, media_type, properties)
        spine_items: List[str] = []                             # item ids
        nav_toc_items: List[Tuple[str, str]] = []               # (title, href)

        # We will collect all files in a dict: relative_path -> bytes
        archive_files: dict[str, bytes] = {}

        # 1. mimetype (must be first, uncompressed)
        archive_files["mimetype"] = b"application/epub+zip"

        # 2. META-INF/container.xml
        container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>"""
        archive_files["META-INF/container.xml"] = container_xml.encode("utf-8")

        # 3. Stylesheet
        archive_files["OEBPS/style.css"] = EPUB_CSS.strip().encode("utf-8")
        manifest_items.append(("style", "style.css", "text/css", ""))

        # 4. Front Matter: Title Page
        fm = ast.front_matter
        if fm.title_page.enabled:
            tp_body = f'<h1 class="book-title">{html.escape(title)}</h1>\n'
            if ast.metadata.subtitle:
                tp_body += f'<h2 class="book-subtitle">{html.escape(ast.metadata.subtitle)}</h2>\n'
            tp_body += f'<p class="book-author">By {html.escape(author)}</p>\n'
            if ast.metadata.publisher:
                tp_body += f'<p class="book-publisher">{html.escape(ast.metadata.publisher)}</p>\n'
            
            archive_files["OEBPS/titlepage.xhtml"] = _wrap_xhtml("Title Page", tp_body).encode("utf-8")
            manifest_items.append(("titlepage", "titlepage.xhtml", "application/xhtml+xml", ""))
            spine_items.append("titlepage")

        # 5. Front Matter: Copyright Page
        if fm.copyright.enabled:
            c = fm.copyright
            cp_body = '<div class="copyright-page">\n'
            cp_body += f'<p><strong>Copyright &#169; {c.year or 2026} {html.escape(c.holder or author)}</strong></p>\n'
            cp_body += '<p>All rights reserved.</p>\n'
            if c.statement:
                cp_body += f'<p>{html.escape(c.statement)}</p>\n'
            if c.edition:
                cp_body += f'<p>Edition: {html.escape(c.edition)}</p>\n'
            if ast.metadata.isbn:
                cp_body += f'<p>ISBN: {html.escape(ast.metadata.isbn)}</p>\n'
            if c.disclaimer:
                cp_body += f'<p><em>{html.escape(c.disclaimer)}</em></p>\n'
            cp_body += '</div>\n'

            archive_files["OEBPS/copyright.xhtml"] = _wrap_xhtml("Copyright", cp_body).encode("utf-8")
            manifest_items.append(("copyright", "copyright.xhtml", "application/xhtml+xml", ""))
            spine_items.append("copyright")

        # 6. Front Matter: Dedication
        if fm.dedication.enabled and fm.dedication.text:
            ded_body = f'<div class="dedication"><p><em>{html.escape(fm.dedication.text)}</em></p></div>\n'
            archive_files["OEBPS/dedication.xhtml"] = _wrap_xhtml("Dedication", ded_body).encode("utf-8")
            manifest_items.append(("dedication", "dedication.xhtml", "application/xhtml+xml", ""))
            spine_items.append("dedication")

        # 7. Chapters
        for idx, ch in enumerate(ast.chapters, start=1):
            ch_id = f"chapter_{idx}"
            ch_href = f"chapter_{idx}.xhtml"
            ch_label = f"Chapter {ch.chapter_number}: {ch.title}"
            nav_toc_items.append((ch_label, ch_href))

            ch_body = '<section epub:type="chapter" class="chapter">\n'
            ch_body += '<div class="chapter-opener">\n'
            ch_body += f'<div class="chapter-number">Chapter {ch.chapter_number}</div>\n'
            ch_body += f'<h1 class="chapter-title">{html.escape(ch.title)}</h1>\n'
            if ch.subtitle:
                ch_body += f'<h2 class="chapter-subtitle">{html.escape(ch.subtitle)}</h2>\n'
            ch_body += '</div>\n'

            if ch.epigraph:
                ch_body += '<div class="epigraph">\n'
                ch_body += f'<p>&#8220;{html.escape(ch.epigraph.text)}&#8221;</p>\n'
                if ch.epigraph.attribution:
                    ch_body += f'<div class="epigraph-attribution">&#8212; {html.escape(ch.epigraph.attribution)}</div>\n'
                ch_body += '</div>\n'

            for block in ch.content:
                if isinstance(block, ParagraphBlock):
                    ch_body += f'<p>{_inline_md_to_xhtml(block.text)}</p>\n'

                elif isinstance(block, Heading2Block):
                    ch_body += f'<h2>{_inline_md_to_xhtml(block.text)}</h2>\n'

                elif isinstance(block, Heading3Block):
                    ch_body += f'<h3>{_inline_md_to_xhtml(block.text)}</h3>\n'

                elif isinstance(block, CalloutBlock):
                    variant = block.variant or "info"
                    ch_body += f'<div class="callout callout-{html.escape(variant)}">\n'
                    if block.title:
                        ch_body += f'<div class="callout-title">{_inline_md_to_xhtml(block.title)}</div>\n'
                    ch_body += f'<div class="callout-body">{_inline_md_to_xhtml(block.text)}</div>\n'
                    ch_body += '</div>\n'

                elif isinstance(block, PullquoteBlock):
                    ch_body += '<blockquote class="pullquote">\n'
                    ch_body += f'<p>&#8220;{_inline_md_to_xhtml(block.text)}&#8221;</p>\n'
                    if block.attribution:
                        ch_body += f'<span class="pullquote-attribution">&#8212; {html.escape(block.attribution)}</span>\n'
                    ch_body += '</blockquote>\n'

                elif isinstance(block, TableBlock):
                    ch_body += '<table>\n<thead>\n<tr>\n'
                    for h in block.headers:
                        ch_body += f'<th>{_inline_md_to_xhtml(h)}</th>\n'
                    ch_body += '</tr>\n</thead>\n<tbody>\n'
                    for row in block.rows:
                        ch_body += '<tr>\n'
                        for cell in row:
                            ch_body += f'<td>{_inline_md_to_xhtml(cell)}</td>\n'
                        ch_body += '</tr>\n'
                    ch_body += '</tbody>\n</table>\n'

                elif isinstance(block, InteractiveFieldBlock):
                    ch_body += '<div class="interactive-field">\n'
                    ch_body += f'<div class="interactive-label">{html.escape(block.label)}</div>\n'
                    if block.field_type == "checkbox":
                        for opt in (block.options or ["Option 1", "Option 2"]):
                            ch_body += f'<div class="interactive-checkbox">&#9633; {html.escape(opt)}</div>\n'
                    else:
                        ch_body += '<p>________________________________________________________</p>\n'
                    ch_body += '</div>\n'

                elif isinstance(block, HorizontalRuleBlock):
                    ch_body += '<div class="ornament">&#9733; &#9733; &#9733;</div>\n'

                elif isinstance(block, PageBreakBlock):
                    ch_body += '<hr style="page-break-after: always; visibility: hidden; margin: 0;"/>\n'

                elif isinstance(block, ImageBlock):
                    ch_body += f'<figure><figcaption>{html.escape(block.alt or block.caption or "Illustration")}</figcaption></figure>\n'

            ch_body += '</section>\n'

            archive_files[f"OEBPS/{ch_href}"] = _wrap_xhtml(ch_label, ch_body).encode("utf-8")
            manifest_items.append((ch_id, ch_href, "application/xhtml+xml", ""))
            spine_items.append(ch_id)

        # 8. Navigation Document (nav.xhtml - EPUB3 requirement)
        nav_body = '<nav epub:type="toc" id="toc">\n<h1>Table of Contents</h1>\n<ol>\n'
        for nav_title, nav_href in nav_toc_items:
            nav_body += f'  <li><a href="{nav_href}">{html.escape(nav_title)}</a></li>\n'
        nav_body += '</ol>\n</nav>\n'
        archive_files["OEBPS/nav.xhtml"] = _wrap_xhtml("Table of Contents", nav_body).encode("utf-8")
        manifest_items.append(("nav", "nav.xhtml", "application/xhtml+xml", "nav"))

        # 9. EPUB 2 NCX Navigation (toc.ncx)
        ncx_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="{book_id}"/>
        <meta name="dtb:depth" content="1"/>
        <meta name="dtb:totalPageCount" content="0"/>
        <meta name="dtb:maxPageNumber" content="0"/>
    </head>
    <docTitle><text>{html.escape(title)}</text></docTitle>
    <navMap>
"""
        for play_order, (nav_title, nav_href) in enumerate(nav_toc_items, start=1):
            ncx_xml += f"""        <navPoint id="np_{play_order}" playOrder="{play_order}">
            <navLabel><text>{html.escape(nav_title)}</text></navLabel>
            <content src="{nav_href}"/>
        </navPoint>
"""
        ncx_xml += """    </navMap>
</ncx>"""
        archive_files["OEBPS/toc.ncx"] = ncx_xml.encode("utf-8")
        manifest_items.append(("ncx", "toc.ncx", "application/x-dtbncx+xml", ""))

        # 10. Package OPF (content.opf)
        manifest_xml_entries = "\n".join(
            f'        <item id="{item_id}" href="{href}" media-type="{mtype}"' +
            (f' properties="{props}"' if props else '') + '/>'
            for item_id, href, mtype, props in manifest_items
        )

        spine_xml_entries = "\n".join(
            f'        <itemref idref="{item_id}"/>'
            for item_id in spine_items
        )

        content_opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="pub-id">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:identifier id="pub-id">{book_id}</dc:identifier>
        <dc:title>{html.escape(title)}</dc:title>
        <dc:creator>{html.escape(author)}</dc:creator>
        <dc:language>{html.escape(language)}</dc:language>
        <meta property="dcterms:modified">{iso_now}</meta>
    </metadata>
    <manifest>
{manifest_xml_entries}
    </manifest>
    <spine toc="ncx">
{spine_xml_entries}
    </spine>
</package>"""
        archive_files["OEBPS/content.opf"] = content_opf.encode("utf-8")

        # Write to zip file
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 1. mimetype MUST be first and stored uncompressed
            zf.writestr("mimetype", archive_files["mimetype"], compress_type=zipfile.ZIP_STORED)

            # 2. Write all other files
            for rel_path, data in archive_files.items():
                if rel_path == "mimetype":
                    continue
                zf.writestr(rel_path, data, compress_type=zipfile.ZIP_DEFLATED)
