import sys
sys.path.insert(0, '.')

import mammoth, fitz, pdfplumber, tenacity
print('mammoth    : OK (no __version__)')
print('pymupdf    :', fitz.__version__)
print('pdfplumber :', pdfplumber.__version__)
print('tenacity   : OK (no __version__)')

from app.services.extractors.docx_extractor import extract_docx, paragraphs_to_tagged_text
from app.services.extractors.pdf_extractor import extract_pdf, pdf_to_tagged_text
from app.services.ai_normalizer import normalize_with_ai, _chunk_text, _safe_parse_json
from app.models.ast_cache import store_ast, get_ast
from app.services.parser import parse_document, ParseError, CorruptFileError
from app.api.endpoints.upload import router

print('extractors      : OK')
print('ai_normalizer   : OK')
print('ast_cache       : OK')
print('parser          : OK')
print('upload router   : OK (%d routes)' % len(router.routes))

chunks = _chunk_text('word ' * 5000)
print('chunker test    : OK (%d chunks)' % len(chunks))

data = _safe_parse_json('{"title": "Test"}')
assert data == {'title': 'Test'}, 'JSON parse failed'
print('json parser     : OK')

print()
print('All Prompt 2 modules verified!')
