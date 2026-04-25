"""Markdown and plain text parser."""

from __future__ import annotations

from pathlib import Path

from app.models.mcp import ParsedDocument


async def parse_markdown(file_path: str | Path) -> ParsedDocument:
    """Parse a Markdown or plain text file."""
    path = Path(file_path)
    content = path.read_text(encoding="utf-8", errors="replace")
    return ParsedDocument(
        source=str(file_path),
        content=content,
        file_type=path.suffix,
        metadata={"line_count": content.count("\n") + 1, "char_count": len(content)},
    )
