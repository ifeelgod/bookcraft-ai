"""
BookCraft AI — FastAPI Backend
Entry point: uvicorn main:app --reload
"""
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.api.router import api_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("bookcraft")

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="BookCraft AI",
    description="AI-powered book compilation and formatting API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        settings.NEXT_PUBLIC_API_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all API routes under /api prefix
app.include_router(api_router, prefix="/api")

# Ensure outputs directory exists before mounting
Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

# Serve the outputs directory statically so PDFs can be downloaded/previewed
app.mount("/api/download", StaticFiles(directory=settings.OUTPUT_DIR), name="outputs")

# Serve Frontend (Next.js out folder)
frontend_dist = Path(__file__).parent.parent / "frontend" / "out"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


# ---------------------------------------------------------------------------
# Startup / shutdown hooks
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup() -> None:
    """Create required directories on startup."""
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    logger.info("BookCraft AI backend started.")
    logger.info(f"Upload dir : {Path(settings.UPLOAD_DIR).resolve()}")
    logger.info(f"Output dir : {Path(settings.OUTPUT_DIR).resolve()}")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("BookCraft AI backend shutting down.")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "bookcraft-ai"}
