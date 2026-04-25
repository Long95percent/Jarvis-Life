"""Source code parser — extracts code with language detection.

Phase 2+: Tree-sitter AST analysis for function/class extraction.
"""

from __future__ import annotations

from pathlib import Path

from app.models.mcp import ParsedDocument

EXTENSION_LANGUAGE_MAP = {
    ".py": "python",
    ".java": "java",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".rb": "ruby",
    ".sql": "sql",
}


async def parse_code(file_path: str | Path) -> ParsedDocument:
    """Parse a source code file."""
    path = Path(file_path)
    content = path.read_text(encoding="utf-8", errors="replace")
    language = EXTENSION_LANGUAGE_MAP.get(path.suffix, "unknown")

    return ParsedDocument(
        source=str(file_path),
        content=content,
        file_type=path.suffix,
        metadata={
            "language": language,
            "line_count": content.count("\n") + 1,
        },
    )
