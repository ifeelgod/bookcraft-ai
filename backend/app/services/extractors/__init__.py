# Extractors package
from .docx_extractor import extract_docx, DocxExtractResult, paragraphs_to_tagged_text
from .pdf_extractor import extract_pdf, PdfExtractResult, pdf_to_tagged_text

__all__ = [
    "extract_docx",
    "DocxExtractResult",
    "paragraphs_to_tagged_text",
    "extract_pdf",
    "PdfExtractResult",
    "pdf_to_tagged_text",
]
