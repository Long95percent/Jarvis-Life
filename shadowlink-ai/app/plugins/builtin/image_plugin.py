"""Image processing plugin — OCR text extraction from images.

Phase 0: Placeholder. Phase 2+: PaddleOCR/Tesseract integration.
"""

from __future__ import annotations

from typing import Any

from app.models.mcp import PluginInfo, ToolCategory, ToolInfo
from app.plugins.interface import PluginInterface


class ImagePlugin(PluginInterface):
    """Image OCR processing plugin."""

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="image_processor",
            version="0.1.0",
            description="Extract text from images using OCR",
            author="ShadowLink",
            supported_formats=[".png", ".jpg", ".jpeg", ".bmp", ".tiff"],
            tools_provided=["ocr_image"],
        )

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def get_tools(self) -> list[tuple[ToolInfo, Any]]:
        tool_info = ToolInfo(
            name="ocr_image",
            description="Extract text from an image using OCR",
            category=ToolCategory.FILE,
            input_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to image file"},
                    "language": {"type": "string", "description": "OCR language (default: ch_sim+en)"},
                },
                "required": ["file_path"],
            },
        )
        return [(tool_info, self._ocr_image)]

    @staticmethod
    async def _ocr_image(file_path: str, language: str = "ch_sim+en") -> str:
        """OCR an image. Phase 2+: PaddleOCR/Tesseract."""
        return f"[OCR] Image text extraction for '{file_path}' (Phase 2+ implementation)"


def create_plugin() -> PluginInterface:
    return ImagePlugin()
