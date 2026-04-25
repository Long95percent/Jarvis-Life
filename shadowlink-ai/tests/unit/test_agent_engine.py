"""Unit tests for the Agent engine and TaskComplexityRouter."""

from __future__ import annotations

import pytest

from app.agent.engine import AgentEngine, TaskComplexityRouter
from app.models.agent import AgentRequest, AgentStrategy, TaskComplexity


class TestTaskComplexityRouter:
    def setup_method(self):
        self.router = TaskComplexityRouter()

    def test_simple_query(self):
        req = AgentRequest(session_id="s1", message="What is Python?")
        assert self.router.classify(req) == TaskComplexity.SIMPLE

    def test_moderate_query(self):
        req = AgentRequest(session_id="s1", message="Search for the latest news about AI agents and their applications in enterprise software development and summarize the key findings for our team")
        result = self.router.classify(req)
        assert result in (TaskComplexity.MODERATE, TaskComplexity.COMPLEX)

    def test_complex_query_with_plan_indicators(self):
        req = AgentRequest(session_id="s1", message="Please analyze step by step the differences between React and Vue, then summarize your findings in a report")
        assert self.router.classify(req) == TaskComplexity.COMPLEX

    def test_explicit_strategy_override(self):
        req = AgentRequest(session_id="s1", message="Hello", strategy=AgentStrategy.PLAN_EXECUTE)
        assert self.router.select_strategy(req) == AgentStrategy.PLAN_EXECUTE

    def test_auto_route_simple(self):
        req = AgentRequest(session_id="s1", message="Hi there")
        assert self.router.select_strategy(req) == AgentStrategy.DIRECT


class TestAgentEngine:
    @pytest.mark.asyncio
    async def test_execute_placeholder(self):
        engine = AgentEngine()
        req = AgentRequest(session_id="s1", message="Test message")
        response = await engine.execute(req)
        assert response.session_id == "s1"
        assert response.answer  # non-empty
        assert len(response.steps) > 0

    @pytest.mark.asyncio
    async def test_execute_stream_placeholder(self):
        engine = AgentEngine()
        req = AgentRequest(session_id="s1", message="Test stream")
        events = []
        async for event in engine.execute_stream(req):
            events.append(event)
        assert len(events) >= 2  # at least thought + done
        assert events[-1].event.value == "done"
