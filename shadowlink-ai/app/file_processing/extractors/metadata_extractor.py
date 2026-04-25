"""Metadata extractor — extracts document metadata (author, dates, etc.)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class MetadataExtractor:
    """Extracts metadata from files."""

    async def extract(self, file_path: str) -> dict[str, Any]:
        """Extract metadata from a file."""
        path = Path(file_path)
        metadata: dict[str, Any] = {
            "file_name": path.name,
            "file_extension": path.suffix,
        }
        if path.exists():
            stat = path.stat()
            metadata["file_size"] = stat.st_size
            metadata["modified_time"] = stat.st_mtime
        return metadata
