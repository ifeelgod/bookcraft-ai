"""
PDF compiler service wrapper (backward compatibility).
Delegates to app.services.compilers.pdf_compiler.
"""
from __future__ import annotations
from typing import Tuple

from app.models.document_ast import DocumentAST
from app.services.compilers.pdf_compiler import (
    PdfCompiler,
    TRIM_DIMENSIONS,
    _escape_typst,
    build_typst_document,
)

# Export legacy alias
_build_typst_document = build_typst_document

_default_pdf_compiler = PdfCompiler()


async def compile_pdf(
    ast: DocumentAST,
    job_id: str,
) -> Tuple[str, str]:
    """
    Compile a DocumentAST into a PDF file using Typst.
    Returns (output_path, download_url).
    """
    from pathlib import Path
    from app.core.config import settings
    output_dir = Path(settings.OUTPUT_DIR)
    path, url = await _default_pdf_compiler.compile(ast, job_id, output_dir)
    return str(path), url
