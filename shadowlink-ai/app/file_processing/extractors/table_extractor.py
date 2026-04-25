"""Table extractor — identifies and extracts tables from documents.

Phase 1+: Uses Camelot/pdfplumber for PDF tables, openpyxl for Excel.
"""

from __future__ import annotations

from app.models.mcp import ExtractedTable


class TableExtractor:
    """Extracts tables from parsed documents."""

    async def extract(self, content: str, file_type: str) -> list[ExtractedTable]:
        """Extract tables from document content.

        Phase 0: Placeholder. Phase 1+: Format-specific extraction.
        """
        return []
