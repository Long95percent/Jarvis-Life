"""Formula extractor — identifies LaTeX/math formulas in documents.

Phase 2+: Uses regex patterns and OCR for formula detection.
"""

from __future__ import annotations


class FormulaExtractor:
    """Extracts mathematical formulas from documents."""

    async def extract(self, content: str) -> list[str]:
        """Extract LaTeX formulas from content.

        Phase 0: Placeholder. Phase 2+: Regex + OCR extraction.
        """
        return []
