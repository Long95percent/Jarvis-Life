"""Image parser with OCR support.

Phase 0: Placeholder. Phase 2+: PaddleOCR/Tesseract integration.
"""

from __future__ import annotations

from pathlib import Path

from app.models.mcp import ParsedDocument


async def parse_image(file_path: str | Path, language: str = "ch_sim+en") -> ParsedDocument:
    """Parse an image file, optionally extracting text via OCR."""
    path = Path(file_path)
    return ParsedDocument(
        source=str(file_path),
        content=f"[Image file: {path.name}] OCR extraction pending Phase 2+ implementation",
        file_type=path.suffix,
        metadata={"file_size": path.stat().st_size if path.exists() else 0},
    )
