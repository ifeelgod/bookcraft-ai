import asyncio
from app.services.ai_normalizer import normalize_with_ai
from app.services.extractors.pdf_extractor import extract_pdf, pdf_to_tagged_text
import uuid
import logging

logging.basicConfig(level=logging.INFO)

async def test():
    file_path = "uploads/113e46d7-f0f5-4dfe-8621-8a139b899533_Facebook Live Mastery - Training Guide.pdf"
    result = extract_pdf(file_path)
    tagged = pdf_to_tagged_text(result)
    
    ast = await normalize_with_ai(tagged, file_path, str(uuid.uuid4()))
    
    print(f"Chapters: {len(ast.chapters)}")
    for ch in ast.chapters:
        print(f"Chapter: {ch.title}")

if __name__ == "__main__":
    asyncio.run(test())
