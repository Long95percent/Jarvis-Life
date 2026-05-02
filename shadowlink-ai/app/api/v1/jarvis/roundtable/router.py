from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import get_llm_client
from .schemas import (
    RoundtableAcceptRequest,
    RoundtableContinueRequest,
    RoundtablePlanRequest,
    RoundtableReturnRequest,
    RoundtableSaveRequest,
    RoundtableStartRequest,
)

router = APIRouter(prefix="/jarvis", tags=["jarvis-roundtable"])


@router.post("/roundtable/start")
async def start_roundtable(req: RoundtableStartRequest, llm_client=Depends(get_llm_client)) -> EventSourceResponse:
    from app.api.v1 import jarvis_router

    return await jarvis_router.start_roundtable(req, llm_client)


@router.post("/roundtable/continue")
async def continue_roundtable(req: RoundtableContinueRequest, llm_client=Depends(get_llm_client)) -> EventSourceResponse:
    from app.api.v1 import jarvis_router

    return await jarvis_router.continue_roundtable(req, llm_client)


@router.get("/roundtable/{session_id}/decision-result")
async def get_roundtable_decision_result(session_id: str) -> dict[str, Any]:
    from app.api.v1 import jarvis_router

    return await jarvis_router.get_roundtable_decision_result(session_id)


@router.get("/roundtable/{session_id}/brainstorm-result")
async def get_roundtable_brainstorm_result(session_id: str) -> dict[str, Any]:
    from app.api.v1 import jarvis_router

    return await jarvis_router.get_roundtable_brainstorm_result(session_id)


@router.post("/roundtable/{session_id}/accept")
async def accept_roundtable_decision(session_id: str, req: RoundtableAcceptRequest) -> dict[str, Any]:
    from app.api.v1 import jarvis_router

    return await jarvis_router.accept_roundtable_decision(session_id, req)


@router.post("/roundtable/{session_id}/save")
async def save_roundtable_brainstorm_memory(session_id: str, req: RoundtableSaveRequest) -> dict[str, Any]:
    from app.api.v1 import jarvis_router

    return await jarvis_router.save_roundtable_brainstorm_memory(session_id, req)


@router.post("/roundtable/{session_id}/plan")
async def convert_roundtable_brainstorm_to_plan(session_id: str, req: RoundtablePlanRequest) -> dict[str, Any]:
    from app.api.v1 import jarvis_router

    return await jarvis_router.convert_roundtable_brainstorm_to_plan(session_id, req)


@router.post("/roundtable/{session_id}/return")
async def return_roundtable_to_private_chat(session_id: str, req: RoundtableReturnRequest) -> dict[str, Any]:
    from app.api.v1 import jarvis_router

    return await jarvis_router.return_roundtable_to_private_chat(session_id, req)


