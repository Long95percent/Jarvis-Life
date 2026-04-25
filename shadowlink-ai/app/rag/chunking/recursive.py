"""Recursive character-based chunking with overlap.

The most common chunking strategy: split text recursively using a
hierarchy of separators (paragraphs -> sentences -> words) while
maintaining configurable overlap for context continuity.
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = structlog.get_logger("rag.chunking.recursive")


class RecursiveChunker:
    """Recursive text splitter with configurable chunk size and overlap."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64, separators: list[str] | None = None):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators or ["\n\n", "\n", "。", ".", " ", ""],
            length_function=len,
        )

    def chunk(self, text: str, metadata: dict[str, Any] | None = None) -> list[Document]:
        """Split text into chunks."""
        docs = self.splitter.create_documents(
            texts=[text],
            metadatas=[metadata or {}],
        )
        # Add chunk index to metadata
        for i, doc in enumerate(docs):
            doc.metadata["chunk_index"] = i
        return docs

    def chunk_documents(self, documents: list[Document]) -> list[Document]:
        """Split a list of documents into chunks."""
        return self.splitter.split_documents(documents)
