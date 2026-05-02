from __future__ import annotations

from pydantic import BaseModel


class RoundtableStartRequest(BaseModel):
    scenario_id: str
    user_input: str = ""
    session_id: str
    mode_id: str = "general"
    source_session_id: str | None = None
    source_agent_id: str | None = None


class RoundtableContinueRequest(BaseModel):
    session_id: str
    user_message: str


class RoundtableAcceptRequest(BaseModel):
    result_id: str | None = None
    note: str | None = None


class RoundtableReturnRequest(BaseModel):
    result_id: str | None = None
    user_choice: str | None = None
    note: str | None = None


class RoundtableSaveRequest(BaseModel):
    result_id: str | None = None
    note: str | None = None


class RoundtablePlanRequest(BaseModel):
    result_id: str | None = None
    note: str | None = None

