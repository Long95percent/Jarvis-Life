# ShadowLink AI Service

Enterprise-grade AI service layer for ShadowLink — Agent orchestration, RAG pipeline, MCP protocol, and tool execution.

## Quick Start

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Start the service
uvicorn app.main:app --reload --port 8000
```

## Architecture

- **Agent Engine**: ReAct / Plan-and-Execute / MultiAgent with TaskComplexityRouter
- **RAG Pipeline**: 9-step pipeline (classify → rewrite → retrieve → fuse → rerank → quality gate → assemble → generate → trace)
- **MCP Protocol**: Model Context Protocol for tool interoperability
- **LLM Client**: Multi-provider support (OpenAI, DeepSeek, Ollama, Anthropic)
- **File Processing**: PDF, DOCX, XLSX, PPTX, Markdown, Code, Image
- **Plugin System**: Dynamic plugin loading for extensibility
