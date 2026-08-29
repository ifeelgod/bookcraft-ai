"""
Multi-format Compiler Orchestrator.
Coordinates concurrent generation of PDF, Word (.docx), Markdown (.md), and EPUB ebook formats.
"""
from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.models.document_ast import DocumentAST
from app.models.job import update_job
from app.services.compilers.base import BaseCompiler
from app.services.compilers.docx_compiler import DocxCompiler
from app.services.compilers.epub_compiler import EpubCompiler
from app.services.compilers.md_compiler import MdCompiler
from app.services.compilers.pdf_compiler import PdfCompiler

logger = logging.getLogger("bookcraft.compilers.orchestrator")


class CompilerOrchestrator:
    """
    Manages and coordinates execution of all document format compilers.
    """

    def __init__(self, compilers: Optional[List[BaseCompiler]] = None):
        if compilers is not None:
            self._compilers = {c.format_name: c for c in compilers}
        else:
            self._compilers = {
                "pdf": PdfCompiler(),
                "docx": DocxCompiler(),
                "md": MdCompiler(),
                "epub": EpubCompiler(),
            }

    def register_compiler(self, compiler: BaseCompiler) -> None:
        """Register or override a format compiler."""
        self._compilers[compiler.format_name] = compiler

    def get_compiler(self, format_name: str) -> Optional[BaseCompiler]:
        """Retrieve a format compiler by name."""
        return self._compilers.get(format_name.lower())

    async def compile_all(
        self,
        ast: DocumentAST,
        job_id: str,
        output_dir: Optional[Path] = None,
        formats: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compile DocumentAST into all specified formats.
        
        Args:
            ast: Validated DocumentAST instance.
            job_id: Unique job ID.
            output_dir: Directory where artifacts are saved (defaults to settings.OUTPUT_DIR).
            formats: List of formats to compile (defaults to all registered formats).
            
        Returns:
            Dict mapping format_name -> {"path": str, "url": str, "mime_type": str, "size_bytes": int}
        """
        out_dir = output_dir or Path(settings.OUTPUT_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)

        target_formats = formats or list(self._compilers.keys())
        results: Dict[str, Dict[str, Any]] = {}

        update_job(job_id, progress=15, message="Starting multi-format compilation…")

        async def _compile_format(fmt: str, compiler: BaseCompiler):
            try:
                path, url = await compiler.compile(ast=ast, job_id=job_id, output_dir=out_dir)
                size = path.stat().st_size if path.exists() else 0
                return fmt, {
                    "path": str(path),
                    "url": url,
                    "mime_type": compiler.mime_type,
                    "size_bytes": size,
                }, None
            except Exception as e:
                logger.exception(f"Compiler for format '{fmt}' failed: {e}")
                return fmt, None, e

        tasks = []
        for fmt in target_formats:
            compiler = self._compilers.get(fmt)
            if compiler:
                tasks.append(_compile_format(fmt, compiler))
            else:
                logger.warning(f"No compiler registered for requested format '{fmt}'")

        update_job(job_id, progress=40, message="Compiling PDF, Word DOCX, Markdown, and EPUB in parallel…")

        # Run all compilers concurrently
        completed_tasks = await asyncio.gather(*tasks)

        errors = []
        for fmt, result, err in completed_tasks:
            if err:
                errors.append(f"{fmt}: {err}")
            elif result:
                results[fmt] = result

        if errors and not results:
            error_summary = "; ".join(errors)
            raise RuntimeError(f"All format compilers failed: {error_summary}")

        if "pdf" not in results and "pdf" in target_formats:
            error_summary = "; ".join(errors)
            raise RuntimeError(f"Core PDF compilation failed: {error_summary}")

        update_job(job_id, progress=90, message="Finalizing multi-format compilation…")
        return results


# Default singleton instance
orchestrator = CompilerOrchestrator()


async def compile_all_formats(
    ast: DocumentAST,
    job_id: str,
    output_dir: Optional[Path] = None,
    formats: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Helper shortcut to compile all formats using the default orchestrator."""
    return await orchestrator.compile_all(
        ast=ast,
        job_id=job_id,
        output_dir=output_dir,
        formats=formats,
    )
