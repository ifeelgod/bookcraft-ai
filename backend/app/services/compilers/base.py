"""
Base compiler interface and shared utilities for all BookCraft AI format compilers.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
import re
from pathlib import Path
from typing import Tuple

from app.models.document_ast import DocumentAST


def sanitize_filename(title: str, max_length: int = 64) -> str:
    """
    Sanitize document title for safe filesystem and URL usage.
    Replaces non-alphanumeric characters with underscores, normalizes spaces.
    """
    if not title or not title.strip():
        return "untitled_book"
    # Replace invalid chars with underscore
    safe = re.sub(r'[^a-zA-Z0-9_\-\s]', '_', title.strip())
    # Collapse multiple spaces or underscores
    safe = re.sub(r'[\s_]+', '_', safe)
    # Trim leading/trailing underscores
    safe = safe.strip('_-')
    if not safe:
        safe = "untitled_book"
    return safe[:max_length]


class BaseCompiler(ABC):
    """
    Abstract base class for all document format compilers.
    """

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Name of the format, e.g. 'pdf', 'docx', 'md', 'epub'."""
        pass

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """File extension including dot, e.g. '.pdf', '.docx', '.md', '.epub'."""
        pass

    @property
    @abstractmethod
    def mime_type(self) -> str:
        """MIME type for the format."""
        pass

    def get_output_filename(self, job_id: str, ast: DocumentAST) -> str:
        """Generate standard output filename: {job_id}_{safe_title}{ext}."""
        safe_title = sanitize_filename(ast.metadata.title)
        return f"{job_id}_{safe_title}{self.file_extension}"

    def get_download_url(self, filename: str) -> str:
        """Generate relative API download URL for the compiled artifact."""
        return f"/api/download/{filename}"

    @abstractmethod
    async def compile(
        self,
        ast: DocumentAST,
        job_id: str,
        output_dir: Path,
    ) -> Tuple[Path, str]:
        """
        Compile DocumentAST into target format.
        
        Args:
            ast: Validated DocumentAST data model.
            job_id: Unique identifier for this compilation job.
            output_dir: Path to directory where output artifacts should be written.
            
        Returns:
            Tuple of (output_file_path, download_url).
        """
        pass
