"""Unit tests for the memory system."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.memory.short_term import ShortTermMemory


class TestShortTermMemory:
    def setup_method(self):
        self.memory = ShortTermMemory(max_messages=5)

    def test_add_and_get(self):
        self.memory.add("s1", HumanMessage(content="Hello"))
        self.memory.add("s1", AIMessage(content="Hi there"))
        messages = self.memory.get("s1")
        assert len(messages) == 2

    def test_max_messages(self):
        for i in range(10):
            self.memory.add("s1", HumanMessage(content=f"Message {i}"))
        messages = self.memory.get("s1")
        assert len(messages) == 5  # Capped at max

    def test_get_recent(self):
        for i in range(5):
            self.memory.add("s1", HumanMessage(content=f"Message {i}"))
        recent = self.memory.get_recent("s1", n=2)
        assert len(recent) == 2
        assert recent[-1].content == "Message 4"

    def test_clear(self):
        self.memory.add("s1", HumanMessage(content="Hello"))
        self.memory.clear("s1")
        assert self.memory.get("s1") == []

    def test_separate_sessions(self):
        self.memory.add("s1", HumanMessage(content="Session 1"))
        self.memory.add("s2", HumanMessage(content="Session 2"))
        assert len(self.memory.get("s1")) == 1
        assert len(self.memory.get("s2")) == 1

    def test_to_context(self):
        self.memory.add("s1", HumanMessage(content="Hello"))
        ctx = self.memory.to_context("s1")
        assert "short_term" in ctx
        assert ctx["message_count"] == 1

    def test_to_context_empty(self):
        ctx = self.memory.to_context("nonexistent")
        assert ctx == {}
