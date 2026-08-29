"""
Fixture generator script for BookCraft AI.
Generates all required binary and text fixtures (.docx, .pdf, .md, corrupted files, empty files).
"""
import io
import json
import os
from pathlib import Path
import zipfile

FIXTURES_DIR = Path(__file__).parent.resolve()


def generate_empty_files():
    """Create 0-byte files for boundary testing."""
    for filename in ["empty.md", "empty.docx", "empty.pdf", "empty.txt"]:
        path = FIXTURES_DIR / filename
        path.write_bytes(b"")


def generate_corrupt_files():
    """Create corrupted files that fail format decoders."""
    # Corrupt DOCX: random bytes not a valid zip
    corrupt_docx = FIXTURES_DIR / "corrupt.docx"
    corrupt_docx.write_bytes(b"NOT_A_ZIP_HEADER_MALFORMED_DOCX_CORRUPTED_DATA_1234567890\x00\xff\xfe\xfd")

    # Corrupt PDF: starts without %PDF header or truncated
    corrupt_pdf = FIXTURES_DIR / "corrupt.pdf"
    corrupt_pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\nCORRUPTED_STREAM_ABRUPT_TERMINATION")


def create_minimal_valid_docx(title: str, chapters: list[tuple[str, str]]) -> bytes:
    """
    Build a genuine, valid DOCX OpenXML zip file in-memory without third-party dependencies.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # [Content_Types].xml
        content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
        zf.writestr("[Content_Types].xml", content_types)

        # _rels/.rels
        rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
        zf.writestr("_rels/.rels", rels)

        # word/document.xml
        body_elements = [f'<w:p><w:r><w:rPr><w:b/><w:sz w:val="48"/></w:rPr><w:t>{title}</w:t></w:r></w:p>']
        for ch_title, ch_text in chapters:
            body_elements.append(f'<w:p><w:r><w:rPr><w:b/><w:sz w:val="32"/></w:rPr><w:t>{ch_title}</w:t></w:r></w:p>')
            for p in ch_text.split("\n\n"):
                if p.strip():
                    body_elements.append(f'<w:p><w:r><w:t>{p.strip()}</w:t></w:r></w:p>')

        body_xml = "".join(body_elements)
        document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        {body_xml}
    </w:body>
</w:document>"""
        zf.writestr("word/document.xml", document_xml)

    return buffer.getvalue()


def create_minimal_valid_pdf(title: str, pages_text: list[str]) -> bytes:
    """
    Build a genuine valid PDF 1.4 file format with exact specified pages.
    """
    objects = []
    page_obj_ids = []

    # Object 1: Catalog
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    # Object 2: Pages (placeholder, will fill)
    objects.append("")
    # Object 3: Font
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    current_id = 4
    for p_idx, text in enumerate(pages_text):
        page_id = current_id
        contents_id = current_id + 1
        current_id += 2
        page_obj_ids.append(page_id)

        # Page Object
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {contents_id} 0 R >>")

        # Escaped text stream
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_content = f"BT /F1 14 Tf 72 720 Td ({title} - Page {p_idx+1}) Tj ET\nBT /F1 11 Tf 72 680 Td ({escaped[:80]}) Tj ET"
        stream_bytes = stream_content.encode("latin1")
        stream_obj = f"<< /Length {len(stream_bytes)} >>\nstream\n{stream_content}\nendstream"
        objects.append(stream_obj)

    # Now format Pages object (Object 2)
    kids = " ".join([f"{pid} 0 R" for pid in page_obj_ids])
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_obj_ids)} >>"

    # Assemble PDF with XREF
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for idx, obj in enumerate(objects):
        offsets.append(out.tell())
        out.write(f"{idx+1} 0 obj\n{obj}\nendobj\n".encode("latin1"))

    xref_offset = out.tell()
    out.write(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode("latin1"))
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode("latin1"))

    trailer = f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    out.write(trailer.encode("latin1"))

    return out.getvalue()


def generate_binary_fixtures():
    """Generate .docx and .pdf fixtures for short, 15pages, and long manuscripts."""
    # Short DOCX
    short_docx_bytes = create_minimal_valid_docx(
        title="The Whispering Pines",
        chapters=[
            ("Chapter 1: The Edge of the Woods", "The ancient forest stood silent under the shroud of early morning fog. Eleanor tightened her wool cloak against the damp chill."),
            ("Chapter 2: Footprints in the Frost", "A single set of tracks led toward the hollow trunk of the great elder tree. Not animal tracks—these were clean boot soles."),
        ]
    )
    (FIXTURES_DIR / "sample_short.docx").write_bytes(short_docx_bytes)

    # Long DOCX
    long_chapters = [
        (f"Chapter {i}: Exploration Sector {i}", f"Log entry for stellar quadrant {i}. The survey craft detected anomalous magnetic signatures along the planetary boundary.")
        for i in range(1, 26)
    ]
    long_docx_bytes = create_minimal_valid_docx(
        title="The Encyclopedia of Astronavigation",
        chapters=long_chapters,
    )
    (FIXTURES_DIR / "sample_long.docx").write_bytes(long_docx_bytes)

    # Short PDF (3 pages)
    short_pdf_bytes = create_minimal_valid_pdf(
        title="The Whispering Pines",
        pages_text=[
            "Title and Introduction: Eleanor arrives at the edge of the ancient woods.",
            "Chapter 1: The damp chill rolls off the river valley as fog gathers.",
            "Chapter 2: Boot prints in the frost lead deeper into the hemlock grove.",
        ]
    )
    (FIXTURES_DIR / "sample_short.pdf").write_bytes(short_pdf_bytes)

    # Exact 15-page PDF
    fifteen_pdf_bytes = create_minimal_valid_pdf(
        title="Chronicles of Aethelgard: The Fifteen Seals",
        pages_text=[f"Section {i}: Content and historical annals for realm {i}." for i in range(1, 16)]
    )
    (FIXTURES_DIR / "sample_15pages.pdf").write_bytes(fifteen_pdf_bytes)

    # Long PDF (25 pages)
    long_pdf_bytes = create_minimal_valid_pdf(
        title="The Encyclopedia of Astronavigation",
        pages_text=[f"Module {i}: Deep space telemetry and navigation principles for sector {i}." for i in range(1, 26)]
    )
    (FIXTURES_DIR / "sample_long.pdf").write_bytes(long_pdf_bytes)


def main():
    print(f"Generating test fixtures in: {FIXTURES_DIR}")
    generate_empty_files()
    generate_corrupt_files()
    generate_binary_fixtures()
    print("Test fixtures generated successfully.")


if __name__ == "__main__":
    main()
