"""Unit tests for the RAG engine."""

from __future__ import annotations

import pytest

from app.models.rag import QueryClassification, RAGRequest
from app.rag.engine import RAGEngine


class TestRAGEngine:
    def setup_method(self):
        self.engine = RAGEngine()

    @pytest.mark.asyncio
    async def test_query_returns_response(self):
        req = RAGRequest(query="What is machine learning?")
        response = await self.engine.query(req)
        assert response.trace is not None
        assert response.trace.original_query == "What is machine learning?"

    @pytest.mark.asyncio
    async def test_query_classification_factual(self):
        classification = await self.engine._classify_query("What is the capital of France?")
        assert classification == QueryClassification.FACTUAL

    @pytest.mark.asyncio
    async def test_query_classification_creative(self):
        classification = await self.engine._classify_query("Write a poem about the sea")
        assert classification == QueryClassification.CREATIVE

    @pytest.mark.asyncio
    async def test_query_classification_code(self):
        classification = await self.engine._classify_query("How to implement a binary search function")
        assert classification == QueryClassification.CODE

    @pytest.mark.asyncio
    async def test_ingest_placeholder(self):
        from app.models.rag import IngestRequest

        req = IngestRequest(file_paths=["/tmp/test.pdf"], mode_id="research")
        response = await self.engine.ingest(req)
        assert response.total_documents == 1
        assert response.index_name == "idx_research"
