"""Agent API endpoints — chat, stream, and execution management."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.agent.engine import AgentEngine
from app.core.dependencies import get_agent_engine
from app.models.agent import AgentRequest, AgentResponse
from app.models.common import Result

router = APIRouter()


@router.post("/chat")
async def agent_chat(
    request: AgentRequest,
    engine: Any = Depends(get_agent_engine),
) -> Result[AgentResponse]:
    """Execute an agent task (non-streaming).

    Automatically routes to the optimal strategy based on task complexity:
    - Simple -> Direct LLM
    - Moderate -> ReAct loop
    - Complex -> Plan-and-Execute
    - Multi-domain -> Supervisor MultiAgent
    """
    agent = engine or AgentEngine()
    response = await agent.execute(request)
    return Result.ok(data=response)


@router.post("/chat/stream")
@router.post("/stream")
async def agent_chat_stream(
    request: AgentRequest,
    engine: Any = Depends(get_agent_engine),
) -> EventSourceResponse:
    """Stream agent execution events via SSE.

    Event types: thought, action, observation, tool_call, tool_result, token, done, error
    Both /chat/stream (Java proxy) and /stream (direct Vite proxy) are supported.
    """

    async def event_generator():
        agent = engine or AgentEngine()
        async for event in agent.execute_stream(request):
            yield {
                "event": event.event.value,
                "data": json.dumps(event.model_dump(), ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


@router.post("/cancel/{session_id}")
async def cancel_execution(session_id: str) -> Result[None]:
    """Cancel a running agent execution. Phase 1+ implementation."""
    return Result.ok(message=f"Cancellation requested for session {session_id}")
