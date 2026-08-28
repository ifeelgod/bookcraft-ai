"""
AST Cache
In-memory store for parsed DocumentAST objects, keyed by job_id.
Allows the frontend to retrieve the full AST after parsing completes.
"""
from __future__ import annotations
from typing import Dict, Optional
from app.models.document_ast import DocumentAST

_ast_cache: Dict[str, DocumentAST] = {}


def store_ast(job_id: str, ast: DocumentAST) -> None:
    """Store a DocumentAST for a given job_id."""
    _ast_cache[job_id] = ast


def get_ast(job_id: str) -> Optional[DocumentAST]:
    """Retrieve a DocumentAST by job_id, or None if not found."""
    return _ast_cache.get(job_id)


def delete_ast(job_id: str) -> None:
    """Remove an AST from the cache."""
    _ast_cache.pop(job_id, None)


def list_cached_jobs() -> list[str]:
    """Return list of job_ids that have a cached AST."""
    return list(_ast_cache.keys())
