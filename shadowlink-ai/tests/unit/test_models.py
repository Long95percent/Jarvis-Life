"""Unit tests for Pydantic data models."""

from __future__ import annotations

import pytest

from app.models.agent import AgentRequest, AgentStrategy, PlanStep, TaskComplexity
from app.models.common import Result, StreamEvent, StreamEventType
from app.models.mcp import ToolCallRequest, ToolInfo
from app.models.rag import RAGChunk, RAGRequest, RetrievalMethod


class TestResult:
    def test_ok(self):
        r = Result.ok(data={"key": "value"})
        assert r.success is True
        assert r.code == 200
        assert r.data == {"key": "value"}
        assert r.timestamp > 0

    def test_fail(self):
        r = Result.fail(code=404, message="Not Found")
        assert r.success is False
        assert r.code == 404
        assert r.message == "Not Found"


class TestAgentModels:
    def test_agent_request_defaults(self):
        req = AgentRequest(session_id="s1", message="hello")
        assert req.mode_id == "general"
        assert req.stream is True
        assert req.max_iterations == 15
        assert req.strategy is None

    def test_agent_request_with_strategy(self):
        req = AgentRequest(session_id="s1", message="plan this", strategy=AgentStrategy.PLAN_EXECUTE)
        assert req.strategy == AgentStrategy.PLAN_EXECUTE

    def test_plan_step(self):
        step = PlanStep(index=0, description="Search for info", tool="web_search")
        assert step.status == "pending"
        assert step.dependencies == []

    def test_task_complexity_enum(self):
        assert TaskComplexity.SIMPLE.value == "simple"
        assert TaskComplexity.MULTI_DOMAIN.value == "multi_domain"


class TestRAGModels:
    def test_rag_request_defaults(self):
        req = RAGRequest(query="test query")
        assert req.top_k == 5
        assert req.retrieval_method == RetrievalMethod.HYBRID
        assert req.rerank is True

    def test_rag_chunk(self):
        chunk = RAGChunk(content="some text", source="doc.pdf", score=0.95)
        assert chunk.score == 0.95
        assert chunk.metadata == {}


class TestMCPModels:
    def test_tool_info(self):
        tool = ToolInfo(name="test_tool", description="A test tool")
        assert tool.timeout_seconds == 30
        assert tool.requires_confirmation is False

    def test_tool_call_request(self):
        req = ToolCallRequest(tool_name="web_search", arguments={"query": "test"})
        assert req.arguments["query"] == "test"


class TestStreamEvent:
    def test_stream_event(self):
        event = StreamEvent(
            event=StreamEventType.TOKEN,
            data={"content": "hello"},
            session_id="s1",
        )
        assert event.event == StreamEventType.TOKEN
        assert event.timestamp > 0
