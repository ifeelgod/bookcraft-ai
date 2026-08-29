"""
Integration tests for compile and download endpoints.
Verifies multi-format output compilation via FastAPI test client.
"""
import asyncio
import io
import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from app.models.job import get_job
from tests.conftest import (
    is_valid_docx_bytes,
    is_valid_epub_bytes,
    is_valid_md_string,
    is_valid_pdf_bytes,
)


@pytest.mark.asyncio
async def test_compile_endpoint_triggers_multi_format_job(sample_ast_data):
    """Verify POST /api/compile accepts DocumentAST and returns job_id."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/compile", json=sample_ast_data)
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] in ("pending", "processing")
        assert data["book_title"] == sample_ast_data["metadata"]["title"]

        job_id = data["job_id"]

        # Poll status until completed (max 20 seconds)
        completed = False
        status_data = None
        for _ in range(40):
            await asyncio.sleep(0.5)
            status_res = await client.get(f"/api/status/{job_id}")
            assert status_res.status_code == 200
            status_data = status_res.json()
            if status_data["status"] == "completed":
                completed = True
                break
            elif status_data["status"] == "failed":
                pytest.fail(f"Job failed with error: {status_data.get('error')}")

        assert completed, f"Compilation job did not complete in time. Last state: {status_data}"
        assert status_data["progress"] == 100
        assert "download_urls" in status_data

        urls = status_data["download_urls"]
        assert "pdf" in urls
        assert "docx" in urls
        assert "md" in urls
        assert "epub" in urls

        # Verify downloading each format works and returns valid bytes
        for fmt, url in urls.items():
            dl_res = await client.get(url)
            assert dl_res.status_code == 200, f"Failed to download {fmt} at {url}"
            content = dl_res.content
            assert len(content) > 0, f"Downloaded {fmt} file is empty"

            if fmt == "pdf":
                assert is_valid_pdf_bytes(content)
            elif fmt == "docx":
                assert is_valid_docx_bytes(content)
            elif fmt == "epub":
                assert is_valid_epub_bytes(content)
            elif fmt == "md":
                assert is_valid_md_string(content.decode("utf-8"))


@pytest.mark.asyncio
async def test_compile_endpoint_invalid_ast_returns_422():
    """Verify POST /api/compile rejects invalid payloads with 422 Unprocessable Entity."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        invalid_payload = {
            "metadata": {
                # Missing required 'author' and 'genre' and 'trim_size'
                "title": "Incomplete Book"
            }
        }
        response = await client.post("/api/compile", json=invalid_payload)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_status_endpoint_not_found():
    """Verify GET /api/status/{non_existent_job_id} returns 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/status/non-existent-uuid-9999")
        assert response.status_code == 404
