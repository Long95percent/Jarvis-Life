"""Word document processing plugin — extracts text from .docx files."""

from __future__ import annotations

from typing import Any

from app.models.mcp import PluginInfo, ToolCategory, ToolInfo
from app.plugins.interface import PluginInterface


class DocxPlugin(PluginInterface):
    """Word document processing plugin."""

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="docx_processor",
            version="0.1.0",
            description="Extract text from Word documents using python-docx",
            author="ShadowLink",
            supported_formats=[".docx"],
            tools_provided=["parse_docx"],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def get_tools(self) -> list[tuple[ToolInfo, Any]]:
        tool_info = ToolInfo(
            name="parse_docx",
            description="Parse a Word document and extract text content",
            category=ToolCategory.FILE,
            input_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to .docx file"},
                },
                "required": ["file_path"],
            },
        )
        return [(tool_info, self._parse_docx)]

    @staticmethod
    async def _parse_docx(file_path: str) -> str:
        try:
            from docx import Document

            doc = Document(file_path)
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            return "Error: python-docx not installed"
        except Exception as exc:
            return f"Error processing DOCX: {exc}"


def create_plugin() -> PluginInterface:
    return DocxPlugin()
