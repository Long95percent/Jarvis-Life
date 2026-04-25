"""PDF parser using PyMuPDF (fitz).

Extracts text content page by page with optional table and metadata extraction.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models.mcp import ParsedDocument


async def parse_pdf(file_path: str | Path) -> ParsedDocument:
    """Parse a PDF file and extract text content."""
    try:
        import fitz

        doc = fitz.open(str(file_path))
        pages_text = []
        for page in doc:
            pages_text.append(page.get_text())

        metadata = {
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "page_count": len(doc),
        }

        content = "\n\n".join(pages_text)
        page_count = len(doc)
        doc.close()

        return ParsedDocument(
            source=str(file_path),
            content=content,
            file_type=".pdf",
            pages=page_count,
            metadata=metadata,
        )
    except ImportError:
        return ParsedDocument(source=str(file_path), content="Error: PyMuPDF not installed", file_type=".pdf")
