"""PDF processing plugin — extracts text, tables, and metadata from PDF files.

Uses PyMuPDF (fitz) for fast, accurate PDF text extraction.
Phase 2+: Marker integration for layout-aware extraction.
"""

from __future__ import annotations

from typing import Any

from app.models.mcp import PluginInfo, ToolCategory, ToolInfo
from app.plugins.interface import PluginInterface


class PDFPlugin(PluginInterface):
    """PDF file processing plugin."""

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="pdf_processor",
            version="0.1.0",
            description="Extract text, tables, and metadata from PDF files using PyMuPDF",
            author="ShadowLink",
            supported_formats=[".pdf"],
            tools_provided=["parse_pdf"],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def get_tools(self) -> list[tuple[ToolInfo, Any]]:
        tool_info = ToolInfo(
            name="parse_pdf",
            description="Parse a PDF file and extract text content",
            category=ToolCategory.FILE,
            input_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to PDF file"},
                },
                "required": ["file_path"],
            },
        )
        return [(tool_info, self._parse_pdf)]

    @staticmethod
    async def _parse_pdf(file_path: str) -> str:
        """Extract text from a PDF file."""
        try:
            import fitz

            doc = fitz.open(file_path)
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            doc.close()
            return "\n\n".join(text_parts)
        except ImportError:
            return "Error: PyMuPDF not installed"
        except Exception as exc:
            return f"Error processing PDF: {exc}"


def create_plugin() -> PluginInterface:
    return PDFPlugin()
