# BookCraft AI

AI-powered book formatting and PDF compilation platform.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router, TypeScript, Tailwind CSS, Lucide) |
| Backend | Python 3.11+, FastAPI, Uvicorn |
| AI | DeepSeek via OpenRouter API |
| PDF Engine | ReportLab |
| Parser | python-docx, pypdf |

## Project Structure

```
bookcraft-ai/
├── .env                        # Active environment variables (fill in API key)
├── .env.template               # Template for .env
├── shared/
│   └── schemas/
│       └── document-ast.schema.json   # JSON Schema for DocumentAST
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── requirements.txt        # Python dependencies
│   └── app/
│       ├── api/
│       │   ├── router.py
│       │   └── endpoints/
│       │       ├── upload.py   # POST /api/upload
│       │       ├── status.py   # GET  /api/status/{job_id}
│       │       └── compile.py  # POST /api/compile
│       ├── models/
│       │   ├── document_ast.py # Pydantic DocumentAST models
│       │   └── job.py          # Job tracking
│       ├── services/
│       │   ├── parser.py       # .docx / .pdf → DocumentAST
│       │   └── compiler.py     # DocumentAST → PDF (ReportLab)
│       └── core/
│           └── config.py       # Settings from .env
└── frontend/
    ├── package.json
    ├── next.config.js
    ├── tailwind.config.js
    └── src/
        ├── app/
        │   ├── layout.tsx
        │   ├── page.tsx        # Landing page
        │   ├── upload/page.tsx # Upload & parse page
        │   └── editor/page.tsx # DocumentAST editor + compile
        ├── components/
        │   └── providers/
        │       └── QueryProvider.tsx
        ├── lib/
        │   └── api.ts          # API client
        └── types/
            └── api.ts          # TypeScript types
```

## Quick Start

### Option A — Start Everything At Once
```powershell
.\scripts\start-all.ps1
```

### Option B — Start Separately

**Backend:**
```powershell
.\scripts\start-backend.ps1
```

**Frontend (in a separate terminal):**
```powershell
.\scripts\start-frontend.ps1
```

### URLs
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Setup

1. Copy `.env.template` to `.env`
2. Add your `OPENROUTER_API_KEY`
3. Run the startup scripts above

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload `.docx` or `.pdf` file |
| `GET` | `/api/status/{job_id}` | Poll job progress (0–100%) |
| `GET` | `/api/jobs` | List all jobs (debug) |
| `POST` | `/api/compile` | Compile DocumentAST → PDF |
| `GET` | `/health` | Health check |

## DocumentAST

The `DocumentAST` is the unified data model representing a complete book:

```json
{
  "metadata": { "title": "...", "author": "...", "genre": "non-fiction", "trim_size": "6x9" },
  "front_matter": { "title_page": {...}, "copyright": {...}, "table_of_contents": {...} },
  "chapters": [
    {
      "chapter_number": 1,
      "title": "Introduction",
      "content": [
        { "type": "paragraph", "text": "..." },
        { "type": "heading2", "text": "..." },
        { "type": "callout", "variant": "tip", "text": "..." }
      ]
    }
  ]
}
```

### Content Block Types
- `paragraph` · `heading2` · `heading3`
- `callout` (info / tip / warning / danger / success)
- `pullquote` · `table` · `interactive-field`
- `image` · `page-break` · `horizontal-rule`

### Trim Sizes
- `5.5x8.5` — Standard trade paperback
- `6x9` — Common trade paperback
- `8.5x11` — Workbook / textbook
