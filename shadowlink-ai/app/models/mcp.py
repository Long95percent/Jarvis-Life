"""MCP protocol and tool-related data models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "ToolInfo",
    "ToolCallRequest",
    "ToolCallResponse",
    "ToolCategory",
    "PluginInfo",
    "PluginStatus",
    "FileProcessingRequest",
    "FileProcessingResponse",
    "ParsedDocument",
    "ExtractedTable",
]


class ToolCategory(str, Enum):
    """Tool categories for organization and filtering."""

    SEARCH = "search"
    CODE = "code"
    FILE = "file"
    KNOWLEDGE = "knowledge"
    SYSTEM = "system"
    MCP_EXTERNAL = "mcp_external"
    PLUGIN = "plugin"


class ToolInfo(BaseModel):
    """Metadata describing an available tool."""

    name: str = Field(description="Unique tool identifier")
    description: str = Field(default="", description="Human-readable description")
    category: ToolCategory = Field(default=ToolCategory.SYSTEM)
    input_schema: dict[str, Any] = Field(default_factory=dict, description="JSON Schema for tool input")
    is_async: bool = Field(default=False, description="Whether tool runs asynchronously")
    timeout_seconds: int = Field(default=30, description="Execution timeout")
    requires_confirmation: bool = Field(default=False, description="Whether user confirmation is needed")


class ToolCallRequest(BaseModel):
    """Request to call a tool."""

    tool_name: str = Field(description="Tool identifier")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool input arguments")
    session_id: str = Field(default="")
    mode_id: str = Field(default="general")
    timeout_seconds: int | None = None


class ToolCallResponse(BaseModel):
    """Response from a tool call."""

    tool_name: str
    success: bool = True
    output: str = ""
    error: str | None = None
    latency_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class PluginStatus(str, Enum):
    """Plugin lifecycle status."""

    LOADED = "loaded"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"


class PluginInfo(BaseModel):
    """Plugin metadata."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    status: PluginStatus = PluginStatus.LOADED
    supported_formats: list[str] = Field(default_factory=list)
    tools_provided: list[str] = Field(default_factory=list)


class FileProcessingRequest(BaseModel):
    """Request to process a file through the parsing pipeline."""

    file_path: str = Field(description="Path to the file to process")
    extract_tables: bool = Field(default=True)
    extract_metadata: bool = Field(default=True)
    ocr_enabled: bool = Field(default=False, description="Enable OCR for image-based content")
    language: str = Field(default="auto", description="Document language hint")


class FileProcessingResponse(BaseModel):
    """Response from file processing."""

    file_path: str
    file_type: str = ""
    content: str = Field(default="", description="Extracted text content")
    pages: int = 0
    tables: list[ExtractedTable] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = 0.0


class ParsedDocument(BaseModel):
    """A fully parsed document ready for chunking."""

    source: str = Field(description="Source file path")
    content: str = Field(default="", description="Full text content")
    file_type: str = ""
    pages: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    tables: list[ExtractedTable] = Field(default_factory=list)


class ExtractedTable(BaseModel):
    """An extracted table from a document."""

    page_number: int = 0
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    caption: str = ""
