from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import get_llm_client
from app.jarvis.agents import JARVIS_AGENTS, get_agent
from app.jarvis.collaboration_memory import (
    build_collaboration_memory_prefix,
    is_user_constraint,
    remember_tool_actions,
    remember_user_constraint,
)
from app.jarvis.context_bus import LifeContextBus, get_life_context_bus
from app.jarvis.memory_extractor import build_memory_recall_prefix, extract_and_save_chat_memories
from app.jarvis.tool_runtime import execute_tool_calls, run_agent_turn, to_action_results

logger = structlog.get_logger("jarvis.api")
router = APIRouter(prefix="/jarvis", tags=["jarvis"])


def _chat_error_detail(stage: str, exc: Exception, *, agent_id: str | None = None) -> dict[str, Any]:
    from app.config import settings

    error_text = str(exc) or exc.__class__.__name__
    suggestion = "请查看 AI 服务日志中的同一请求，或把该错误详情发给开发者。"
    lowered = error_text.lower()
    if "401" in error_text or "unauthorized" in lowered:
        suggestion = "LLM Provider 鉴权失败：请检查设置里的 API Key、Base URL 和模型名。"
    elif "404" in error_text or "model" in lowered and "not" in lowered:
        suggestion = "LLM Provider 或模型不可用：请检查设置里的 Base URL 和模型名称是否被当前服务支持。"
    elif "timeout" in lowered or "timed out" in lowered:
        suggestion = "LLM 请求超时：请检查网络、Provider 可用性，或降低模型延迟/增大超时时间。"
    elif "connection" in lowered or "connect" in lowered or "network" in lowered:
        suggestion = "连接 LLM Provider 失败：请检查网络、代理、Base URL 是否可访问。"
    elif "tool registry" in lowered:
        suggestion = "工具注册表未初始化：请重启 AI 服务，确认 startup 日志出现 tool_registry_ready。"

    return {
        "message": f"Jarvis 对话失败：阶段={stage}；原因={error_text}",
        "stage": stage,
        "agent_id": agent_id,
        "error_type": exc.__class__.__name__,
        "error": error_text,
        "suggestion": suggestion,
        "llm": {
            "base_url": settings.llm.base_url,
            "model": settings.llm.model,
            "has_api_key": bool(settings.llm.api_key),
        },
    }


def _build_schedule_intent(message: str, agent_id: str) -> dict[str, Any] | None:
    """Build a formal intent when a non-Maxwell agent receives scheduling work.

    This is intentionally lightweight: the goal is to stop non-secretary agents
    from directly owning schedule/task planning while still preserving the
    user's natural-language request for Maxwell.
    """
    if agent_id == "maxwell":
        return None
    text = message.lower().strip()
    if not text:
        return None

    long_project_keywords = [
        "备考", "雅思", "ielts", "考研", "考试", "长期", "一个月后", "下个月",
        "暑假", "寒假", "旅游", "旅行", "搬家", "作品集", "健身习惯", "长期计划",
        "每周", "每天", "周期", "以后", "未来", "准备", "目标",
    ]
    schedule_action_keywords = [
        "日程", "安排", "提醒", "预约", "开会", "会议", "deadline", "schedule", "待办",
        "帮我", "记得", "加入", "写进", "放到", "规划", "定个", "约",
    ]
    schedule_time_keywords = [
        "明天", "后天", "今天", "今晚", "下午", "上午", "晚上", "几点", "周一", "周二",
        "周三", "周四", "周五", "周六", "周日", "星期", "下周", "本周",
    ]
    matched_long = [keyword for keyword in long_project_keywords if keyword in text]
    matched_schedule_actions = [keyword for keyword in schedule_action_keywords if keyword in text]
    matched_schedule_times = [keyword for keyword in schedule_time_keywords if keyword in text]
    matched_schedule = matched_schedule_actions + [keyword for keyword in matched_schedule_times if keyword not in matched_schedule_actions]
    has_schedule_intent = bool(matched_schedule_actions) or (bool(matched_schedule_times) and any(verb in text for verb in ["去", "做", "办", "见", "练", "学", "整理", "散步", "健身", "复习", "吃饭"]))
    if not matched_long and not has_schedule_intent:
        return None

    intent_kind = "task_intent" if matched_long else "schedule_intent"
    planning_scope = "background_task_plan" if matched_long else "calendar_event"
    matched = matched_long[:4] if matched_long else matched_schedule[:4]
    return {
        "type": intent_kind,
        "source_agent": agent_id,
        "target_agent": "maxwell",
        "planning_scope": planning_scope,
        "status": "routed_to_maxwell",
        "confidence": 0.82 if len(matched) >= 2 else 0.68,
        "matched_keywords": matched,
        "user_message": message,
        "reason": "用户表达了日程/提醒/长期任务规划需求，应由秘书 Maxwell 统一安排和确认。",
    }


def _should_route_to_maxwell(message: str, agent_id: str) -> bool:
    return _build_schedule_intent(message, agent_id) is not None


def get_bus() -> LifeContextBus:
    return get_life_context_bus()


class ContextUpdateRequest(BaseModel):
    stress_level: float | None = None
    schedule_density: float | None = None
    sleep_quality: float | None = None
    mood_trend: str | None = None


class AgentChatRequest(BaseModel):
    agent_id: str
    message: str
    session_id: str


class AgentChatResponse(BaseModel):
    agent_id: str
    agent_name: str
    content: str
    escalation: dict | None = None
    actions: list[dict] | None = None  # structured actions agent executed (calendar etc)
    routing: dict | None = None


class PendingActionUpdateRequest(BaseModel):
    arguments: dict[str, Any] | None = None
    title: str | None = None


class PendingActionConfirmRequest(BaseModel):
    arguments: dict[str, Any] | None = None
    title: str | None = None


class TeamCollaborationRequest(BaseModel):
    goal: str
    user_message: str = ""
    agents: list[str] | None = None
    source_agent: str = "alfred"
    session_id: str | None = None


class DemoRunStartRequest(BaseModel):
    demo_run_id: str
    seed_name: str = "default"
    profile_seed: dict[str, Any] = Field(default_factory=dict)
    reset_existing: bool = False


class DemoTraceEventRequest(BaseModel):
    demo_step_id: str
    event_type: str = "demo_step"
    agent_id: str | None = None
    user_input: str | None = None
    agent_reply: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    memory_events: list[dict[str, Any]] | None = None
    confirmation: dict[str, Any] | None = None
    payload: dict[str, Any] | None = None


class DemoMemoryItemRequest(BaseModel):
    demo_step_id: str
    memory_kind: str
    content: str
    source_text: str | None = None
    sensitivity: str = "normal"
    confidence: float = 0.6
    importance: float = 0.5


class ConversationCreateRequest(BaseModel):
    conversation_id: str
    conversation_type: str
    title: str
    agent_id: str | None = None
    scenario_id: str | None = None
    session_id: str
    route_payload: dict[str, Any] = Field(default_factory=dict)


@router.get("/context")
async def get_context(bus: LifeContextBus = Depends(get_bus)) -> dict[str, Any]:
    ctx = await bus.get_context()
    return ctx.model_dump()


@router.post("/context")
async def update_context(
    req: ContextUpdateRequest,
    bus: LifeContextBus = Depends(get_bus),
) -> dict[str, Any]:
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    await bus.update_fields(fields, source="user")
    ctx = await bus.get_context()
    return ctx.model_dump()


# ──────────────────────────────────────────────────────────────────────────
# Demo Memory / Trace Mode
# ──────────────────────────────────────────────────────────────────────────


@router.post("/demo/reset")
async def reset_demo_memory() -> dict[str, Any]:
    from app.jarvis.persistence import reset_demo_data

    deleted = await reset_demo_data()
    return {"deleted": deleted}


@router.post("/demo/runs")
async def start_demo_memory_run(req: DemoRunStartRequest) -> dict[str, Any]:
    from app.jarvis.persistence import reset_demo_data, start_demo_run

    if req.reset_existing:
        await reset_demo_data()
    demo_run = await start_demo_run(
        demo_run_id=req.demo_run_id,
        seed_name=req.seed_name,
        profile_seed=req.profile_seed,
    )
    return {"demo_run": demo_run}


@router.get("/demo/runs")
async def list_demo_memory_runs(limit: int = 20) -> dict[str, Any]:
    from app.jarvis.persistence import list_demo_runs

    return {"demo_runs": await list_demo_runs(limit=limit)}


@router.post("/demo/runs/{demo_run_id}/trace")
async def append_demo_memory_trace(demo_run_id: str, req: DemoTraceEventRequest) -> dict[str, Any]:
    from app.jarvis.persistence import append_demo_trace_event, get_demo_run

    if await get_demo_run(demo_run_id) is None:
        raise HTTPException(status_code=404, detail="Demo run not found")
    trace_event = await append_demo_trace_event(
        demo_run_id=demo_run_id,
        demo_step_id=req.demo_step_id,
        event_type=req.event_type,
        agent_id=req.agent_id,
        user_input=req.user_input,
        agent_reply=req.agent_reply,
        tool_calls=req.tool_calls,
        memory_events=req.memory_events,
        confirmation=req.confirmation,
        payload=req.payload,
    )
    return {"trace_event": trace_event}


@router.post("/demo/runs/{demo_run_id}/memories")
async def save_demo_memory(demo_run_id: str, req: DemoMemoryItemRequest) -> dict[str, Any]:
    from app.jarvis.persistence import get_demo_run, save_demo_memory_item

    if await get_demo_run(demo_run_id) is None:
        raise HTTPException(status_code=404, detail="Demo run not found")
    memory_item = await save_demo_memory_item(
        demo_run_id=demo_run_id,
        demo_step_id=req.demo_step_id,
        memory_kind=req.memory_kind,
        content=req.content,
        source_text=req.source_text,
        sensitivity=req.sensitivity,
        confidence=req.confidence,
        importance=req.importance,
    )
    return {"memory_item": memory_item}


@router.get("/demo/runs/{demo_run_id}/trace")
async def export_demo_memory_trace(demo_run_id: str) -> dict[str, Any]:
    from app.jarvis.persistence import export_demo_trace

    trace = await export_demo_trace(demo_run_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Demo run not found")
    return trace


@router.get("/memories")
async def list_user_memories(memory_kind: str | None = None, limit: int = 50) -> dict[str, Any]:
    from app.jarvis.persistence import list_jarvis_memories

    memories = await list_jarvis_memories(memory_kind=memory_kind, limit=limit)
    return {"memories": memories}


@router.delete("/memories/{memory_id}")
async def delete_user_memory(memory_id: int) -> dict[str, Any]:
    from app.jarvis.persistence import delete_jarvis_memory

    deleted = await delete_jarvis_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"deleted": True, "memory_id": memory_id}


@router.get("/conversation-history")
async def list_conversation_history(limit: int = 30) -> dict[str, Any]:
    from app.jarvis.persistence import list_conversations

    return {"conversations": await list_conversations(limit=limit)}


@router.post("/conversation-history")
async def create_or_update_conversation(req: ConversationCreateRequest) -> dict[str, Any]:
    from app.jarvis.persistence import save_conversation

    if req.conversation_type not in {"private_chat", "roundtable", "brainstorm"}:
        raise HTTPException(status_code=400, detail="Unsupported conversation_type")
    conversation = await save_conversation(
        conversation_id=req.conversation_id,
        conversation_type=req.conversation_type,
        title=req.title,
        agent_id=req.agent_id,
        scenario_id=req.scenario_id,
        session_id=req.session_id,
        route_payload=req.route_payload,
    )
    return {"conversation": conversation}


@router.post("/conversation-history/{conversation_id}/open")
async def open_conversation_history(conversation_id: str) -> dict[str, Any]:
    from app.jarvis.persistence import mark_conversation_opened

    conversation = await mark_conversation_opened(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"conversation": conversation}


@router.delete("/conversation-history/{conversation_id}")
async def delete_conversation_history(conversation_id: str) -> dict[str, Any]:
    from app.jarvis.persistence import delete_conversation

    deleted = await delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True, "conversation_id": conversation_id}


# ──────────────────────────────────────────────────────────────────────────
# User Settings (profile + agent config)
# ──────────────────────────────────────────────────────────────────────────


class ProfilePatchRequest(BaseModel):
    name: str | None = None
    pronouns: str | None = None
    occupation: str | None = None
    location: dict | None = None  # {"lat": ..., "lng": ..., "label": ...}
    sleep_schedule: dict | None = None  # {"bedtime": ..., "wake": ...}
    diet_restrictions: list[str] | None = None
    interests: list[str] | None = None


class AgentConfigPatchRequest(BaseModel):
    enabled: bool | None = None
    interrupt_budget: int | None = None


@router.get("/profile")
async def get_user_profile() -> dict[str, Any]:
    from app.jarvis.user_settings import get_settings
    return get_settings().profile.model_dump()


@router.patch("/profile")
async def patch_user_profile(req: ProfilePatchRequest) -> dict[str, Any]:
    from app.jarvis.user_settings import update_profile
    patch = {k: v for k, v in req.model_dump().items() if v is not None}
    updated = update_profile(patch)
    return updated.profile.model_dump()


@router.get("/agent-config")
async def get_agent_config() -> dict[str, Any]:
    from app.jarvis.user_settings import get_settings
    s = get_settings()
    return {
        "agents": {aid: cfg.model_dump() for aid, cfg in s.agents.items()},
        "shadow_learner_enabled": s.shadow_learner_enabled,
    }


@router.patch("/agent-config/{agent_id}")
async def patch_agent_config(agent_id: str, req: AgentConfigPatchRequest) -> dict[str, Any]:
    from app.jarvis.user_settings import update_agent_config
    # Reject typos and the silent Shadow observer to avoid orphan config rows.
    if agent_id not in JARVIS_AGENTS or agent_id == "shadow":
        valid_ids = [aid for aid in JARVIS_AGENTS if aid != "shadow"]
        raise HTTPException(
            status_code=404,
            detail=f"Unknown agent_id {agent_id!r}. Valid: {valid_ids}",
        )
    patch = {k: v for k, v in req.model_dump().items() if v is not None}
    updated = update_agent_config(agent_id, patch)
    return updated.agents[agent_id].model_dump()


class ShadowTogglePayload(BaseModel):
    enabled: bool


@router.patch("/agent-config/shadow/toggle")
async def toggle_shadow_learner(req: ShadowTogglePayload) -> dict[str, Any]:
    from app.jarvis.user_settings import update_shadow_enabled
    updated = update_shadow_enabled(req.enabled)
    return {"shadow_learner_enabled": updated.shadow_learner_enabled}


# ──────────────────────────────────────────────────────────────────────────
# LLM status / diagnostics
# ──────────────────────────────────────────────────────────────────────────


@router.get("/llm-status")
async def llm_status(llm_client=Depends(get_llm_client)) -> dict[str, Any]:
    """Report the currently-active LLM provider settings and test connectivity.

    Useful for debugging cases where the user updated API key in Settings
    but the running client still has stale credentials.
    """
    from app.config import settings as app_settings

    def _mask(key: str) -> str:
        if not key:
            return "(empty)"
        if len(key) <= 8:
            return "*" * len(key)
        return f"{key[:4]}...{key[-4:]}"

    # Probe current runtime settings (these get mutated by _apply_provider)
    live_config = {
        "base_url": app_settings.llm.base_url,
        "model": app_settings.llm.model,
        "api_key_masked": _mask(app_settings.llm.api_key),
        "api_key_present": bool(app_settings.llm.api_key),
    }

    # Try a minimal chat call to verify
    test_result: dict[str, Any] = {"ok": False, "error": None, "reply_preview": None}
    try:
        reply = await llm_client.chat(
            message="Reply with just the word OK",
            system_prompt="You are a test responder. Reply with at most 2 words.",
            temperature=0,
            max_tokens=10,
        )
        test_result["ok"] = True
        test_result["reply_preview"] = (reply or "").strip()[:120]
    except Exception as exc:
        test_result["error"] = str(exc)[:300]

    return {"live_config": live_config, "test_result": test_result}


@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_agent(
    req: AgentChatRequest,
    llm_client=Depends(get_llm_client),
) -> AgentChatResponse:
    schedule_intent = _build_schedule_intent(req.message, req.agent_id)
    routed_agent_id = "maxwell" if schedule_intent else req.agent_id
    try:
        agent = get_agent(routed_agent_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent {routed_agent_id!r} not found")

    try:
        from app.jarvis.persistence import save_conversation

        await save_conversation(
            conversation_id=f"private:{req.session_id}:{routed_agent_id}",
            conversation_type="private_chat",
            title=f"{agent['name']} 私聊",
            agent_id=routed_agent_id,
            session_id=req.session_id,
            route_payload={"mode": "private_chat", "agent_id": routed_agent_id},
        )
    except Exception as exc:
        logger.warning("jarvis.chat.conversation_save_failed", agent_id=routed_agent_id, error=str(exc))

    try:
        from app.jarvis.user_settings import build_profile_prefix
        from app.jarvis.persistence import get_chat_history, save_chat_turn
        profile_prefix = build_profile_prefix()

        ctx = await get_life_context_bus().get_context()
        context_summary = (
            f"[Life context: stress={ctx.stress_level}/10, "
            f"schedule_density={ctx.schedule_density}/10, "
            f"sleep={ctx.sleep_quality}/10, mood={ctx.mood_trend}]"
        )

        history = await get_chat_history(routed_agent_id, limit=12)
        history_text = ""
        if history:
            lines = []
            for turn in history:
                prefix = "User" if turn["role"] == "user" else agent["name"]
                lines.append(f"{prefix}: {turn['content']}")
            history_text = "## 最近对话\n" + "\n".join(lines) + "\n\n"

        collaboration_text = await build_collaboration_memory_prefix(routed_agent_id, limit=6)
        memory_text = await build_memory_recall_prefix(routed_agent_id, limit=6)

        from zoneinfo import ZoneInfo
        from app.jarvis.user_settings import get_settings

        profile_location = get_settings().profile.location.label or "Asia/Shanghai"
        try:
            local_tz = ZoneInfo("Asia/Shanghai")
            local_now = datetime.now(local_tz)
            timezone_label = local_now.strftime("%Z") or "Asia/Shanghai"
        except Exception:
            local_now = datetime.now(timezone(timedelta(hours=8)))
            timezone_label = "UTC+08:00"
        time_context = (
            "## 当前时间\n"
            f"本地参考时间: {local_now.strftime('%Y-%m-%d %H:%M:%S')} {timezone_label}\n"
            f"用户位置标签: {profile_location}\n"
            "制定今天/明天/几点到几点的计划时，必须参考这个当前时间；不要安排已经过去的时间段。\n\n"
        )
    except Exception as exc:
        detail = _chat_error_detail("prepare_context", exc, agent_id=req.agent_id)
        logger.error("jarvis.api.chat_prepare_failed", **detail)
        raise HTTPException(status_code=500, detail=detail) from exc

    common_rules = (
        "## 交互规则\n"
        "如需读取最新信息或执行操作，请优先使用你的专属工具包。\n"
        "涉及日程或生活状态的写操作，只能在用户明确要求执行时提出工具调用。\n"
        "日程新增、修改、删除、完成标记会先生成待确认卡片，用户确认后才会真正写入。\n"
        "用户要求规划日程时，应尽量根据当前时间给出开始和结束时间；如果用户没有给时间，请由你先做合理规划，不要强迫用户提供严格格式。\n"
        "如果不需要工具，直接回答。\n\n"
    )
    intent_context = ""
    if schedule_intent:
        intent_label = "长期/后台任务规划" if schedule_intent.get("type") == "task_intent" else "短期日程安排"
        intent_context = (
            "## 路由接管说明\n"
            f"用户原本正在和 {req.agent_id} 对话，但系统识别到这是{intent_label}需求。\n"
            "你是秘书 Maxwell，请正式接管：判断是生成待确认日程卡、长期任务计划卡，还是先追问必要信息。\n"
            f"结构化意图: {json.dumps(schedule_intent, ensure_ascii=False)}\n\n"
        )
    full_message = (
        f"{profile_prefix}{context_summary}\n\n"
        f"{time_context}"
        f"{common_rules}"
        f"{intent_context}"
        f"{memory_text}"
        f"{collaboration_text}"
        f"{history_text}"
        f"User: {req.message}"
    )

    try:
        response, tool_results = await run_agent_turn(
            agent_id=routed_agent_id,
            llm_client=llm_client,
            message=full_message,
            system_prompt=agent["system_prompt"],
            temperature=0.7,
        )
    except Exception as exc:
        detail = _chat_error_detail("run_agent_turn", exc, agent_id=routed_agent_id)
        logger.error("jarvis.api.chat_failed", **detail)
        raise HTTPException(status_code=502, detail=detail) from exc

    clean_reply = (response or "").strip()
    if schedule_intent and not tool_results:
        fallback_tool_name = "jarvis_task_plan_decompose" if schedule_intent.get("type") == "task_intent" else "jarvis_calendar_add"
        fallback_arguments: dict[str, Any] = {"user_request": req.message, "source_agent": req.agent_id}
        if fallback_tool_name == "jarvis_calendar_add":
            fallback_arguments = {
                "title": req.message[:30] or "待安排日程",
                "start": (local_now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0).isoformat(),
                "end": (local_now + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0).isoformat(),
                "stress_weight": 1.0,
                "created_reason": "跨 Agent 日程意图由 Maxwell 兜底生成，用户确认后才写入。",
            }
            if not clean_reply:
                clean_reply = "我先接管这条日程需求，给你生成一个待确认卡；时间不合适可以先取消再补充具体时间。"
        tool_results = await execute_tool_calls(routed_agent_id, [{"tool_name": fallback_tool_name, "arguments": fallback_arguments}])
    action_results = to_action_results(tool_results)
    if schedule_intent:
        action_results.insert(0, {
            "type": schedule_intent["type"],
            "ok": True,
            "pending_confirmation": False,
            "description": schedule_intent["reason"],
            "arguments": schedule_intent,
        })
    for action in action_results:
        if not action.get("pending_confirmation"):
            continue
        try:
            from app.jarvis.persistence import save_pending_action

            arguments = action.get("arguments") if isinstance(action.get("arguments"), dict) else {}
            plan = arguments.get("plan") if isinstance(arguments.get("plan"), dict) else {}
            title = str(arguments.get("title") or plan.get("title") or action.get("title") or action.get("type") or "待确认操作")
            saved = await save_pending_action(
                pending_id=str(action.get("confirmation_id")),
                action_type=str(action.get("type")),
                tool_name=str(action.get("tool_name") or ""),
                agent_id=routed_agent_id,
                session_id=req.session_id,
                title=title,
                arguments=arguments,
            )
            action["pending_action_id"] = saved.get("id")
        except Exception as exc:
            logger.warning(
                "jarvis.chat.pending_action_save_failed",
                agent_id=req.agent_id,
                action_type=action.get("type"),
                error=str(exc),
            )
            action["ok"] = False
            action["error"] = f"待确认动作保存失败：{exc}"

    try:
        if is_user_constraint(req.message):
            await remember_user_constraint(req.message, source_agent=routed_agent_id)
        await remember_tool_actions(routed_agent_id, tool_results)
        await extract_and_save_chat_memories(
            user_message=req.message,
            agent_reply=clean_reply,
            source_agent=routed_agent_id,
            session_id=req.session_id,
            llm_client=llm_client,
        )
    except Exception as exc:
        logger.warning("jarvis.chat.memory_save_failed", agent_id=req.agent_id, error=str(exc))

    # Persist both sides of the exchange so the next request has history
    try:
        await save_chat_turn(agent_id=routed_agent_id, role="user", content=req.message)
        await save_chat_turn(agent_id=routed_agent_id, role="agent", content=clean_reply, actions=action_results)
    except Exception as exc:
        logger.warning("jarvis.chat.persist_failed", agent_id=req.agent_id, error=str(exc))

    # Evaluate whether this message should auto-escalate to a roundtable
    from app.jarvis.escalation import evaluate_escalation
    hint = None
    try:
        ctx_for_eval = await get_life_context_bus().get_context()
        hint = evaluate_escalation(
            user_message=req.message,
            agent_id=req.agent_id,
            context=ctx_for_eval,
        )
    except Exception as exc:
        logger.warning("jarvis.chat.escalation_eval_failed", agent_id=req.agent_id, error=str(exc))
    escalation_payload = None
    if hint is not None:
        escalation_payload = {
            "scenario_id": hint.scenario_id,
            "severity": hint.severity,
            "reason": hint.reason,
            "countdown_seconds": hint.countdown_seconds,
        }

    # Feed observation to Shadow (if enabled)
    from app.jarvis.user_settings import get_settings as _get_jarvis_settings
    if _get_jarvis_settings().shadow_learner_enabled:
        from app.core.lifespan import get_preference_learner
        learner = get_preference_learner()
        if learner is not None:
            try:
                await learner.observe(
                    agent_id=req.agent_id,
                    user_message=req.message,
                    agent_response=clean_reply,
                )
            except Exception as exc:
                logger.warning("jarvis.shadow.observe_failed", error=str(exc))

    return AgentChatResponse(
        agent_id=routed_agent_id,
        agent_name=agent["name"],
        content=clean_reply,
        escalation=escalation_payload,
        actions=action_results if action_results else None,
        routing=schedule_intent,
    )


@router.get("/chat/{agent_id}/history")
async def get_agent_chat_history(agent_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Return recent 1:1 chat turns for an agent (chronological, oldest first)."""
    if agent_id not in JARVIS_AGENTS or agent_id == "shadow":
        raise HTTPException(status_code=404, detail=f"Unknown agent_id {agent_id!r}")
    from app.jarvis.persistence import get_chat_history
    return await get_chat_history(agent_id, limit=limit)


@router.delete("/chat/{agent_id}/history")
async def clear_agent_chat_history(agent_id: str) -> dict[str, Any]:
    """Wipe chat history for a specific agent."""
    if agent_id not in JARVIS_AGENTS or agent_id == "shadow":
        raise HTTPException(status_code=404, detail=f"Unknown agent_id {agent_id!r}")
    from app.jarvis.persistence import clear_chat_history
    cleared = await clear_chat_history(agent_id)
    return {"agent_id": agent_id, "cleared": cleared}


@router.get("/local-life")
async def get_local_life(force: bool = False) -> dict[str, Any]:
    """Return the latest aggregated local-life snapshot."""
    from app.jarvis.local_life_aggregator import refresh_local_life
    snapshot = await refresh_local_life(force=force)
    return {
        "weather": snapshot.weather,
        "activities": snapshot.activities,
        "news": snapshot.news,
        "upcoming_events": snapshot.upcoming_events,
        "schedule_density": snapshot.schedule_density,
        "fetched_at": snapshot.fetched_at,
        "sources": snapshot.sources,
    }


@router.get("/messages")
async def get_proactive_messages() -> list[dict[str, Any]]:
    from app.core.lifespan import get_proactive_engine
    engine = get_proactive_engine()
    if engine is None:
        return []
    msgs = engine.pop_pending_messages()
    return [m.model_dump() for m in msgs]


# ──────────────────────────────────────────────────────────────────────────
# Demo proactive trigger controls
# ──────────────────────────────────────────────────────────────────────────


class ProactiveFireRequest(BaseModel):
    trigger_name: str  # e.g. "stress_spike", "schedule_overload", ...


@router.post("/proactive/fire")
async def fire_proactive_trigger(req: ProactiveFireRequest) -> dict[str, Any]:
    """Force a proactive trigger to fire immediately (bypass cooldown + schedule).

    Useful for demo: a stage button can hit this to show the inter-agent
    Shadow Roundtable producing a proactive message within seconds.
    """
    from app.core.lifespan import get_proactive_engine
    engine = get_proactive_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Proactive engine not running")

    # Find the rule by name and clear its cooldown, then run one check
    matched = None
    for rule in engine.rules:
        if rule.name == req.trigger_name:
            rule._last_fired = None  # reset cooldown
            matched = rule
            break

    if matched is None:
        raise HTTPException(status_code=404, detail=f"Unknown trigger: {req.trigger_name!r}")

    # Force-mutate the LifeContextBus so the rule predicate will fire
    bus = get_life_context_bus()
    synth_fields: dict[str, Any] = {}
    if req.trigger_name == "stress_spike":
        synth_fields["stress_level"] = 9.0
    elif req.trigger_name == "schedule_overload":
        synth_fields["schedule_density"] = 9.0
    elif req.trigger_name == "sleep_poor":
        synth_fields["sleep_quality"] = 3.0
    elif req.trigger_name == "free_window_detected":
        from datetime import datetime, timedelta
        from app.jarvis.models import TimeWindow
        now = datetime.utcnow()
        synth_fields["free_windows"] = [
            TimeWindow(start=now + timedelta(hours=1), end=now + timedelta(hours=3), label="Demo window")
        ]
        synth_fields["stress_level"] = 2.0  # rule also requires low stress
    elif req.trigger_name == "mood_declining":
        synth_fields["mood_trend"] = "negative"

    if synth_fields:
        await bus.update_fields(synth_fields, source="demo_trigger")

    await engine.check_triggers()
    pending = engine.pop_pending_messages()

    return {
        "trigger": req.trigger_name,
        "message_count": len(pending),
        "messages": [m.model_dump() for m in pending],
    }


@router.get("/proactive/triggers")
async def list_proactive_triggers() -> list[dict[str, Any]]:
    """List available trigger names for the demo panel."""
    from app.core.lifespan import get_proactive_engine
    engine = get_proactive_engine()
    if engine is None:
        return []
    return [
        {"name": r.name, "cooldown_minutes": r.cooldown_minutes, "participants": r.participating_agents}
        for r in engine.rules
    ]


# ──────────────────────────────────────────────────────────────────────────
# Shadow learned profile
# ──────────────────────────────────────────────────────────────────────────


@router.get("/shadow/profile")
async def get_shadow_profile() -> dict[str, Any]:
    from app.core.lifespan import get_preference_learner
    learner = get_preference_learner()
    if learner is None:
        return {"interaction_count": 0, "preferences": {}, "last_updated": None}
    profile = learner.get_profile()
    return profile.model_dump()


@router.get("/agents")
async def list_agents() -> list[dict[str, Any]]:
    return [
        {
            "id": aid,
            "name": a["name"],
            "role": a["role"],
            "color": a["color"],
            "icon": a["icon"],
        }
        for aid, a in JARVIS_AGENTS.items()
        if aid != "shadow"
    ]


@router.post("/team/collaborate")
async def team_collaborate(
    req: TeamCollaborationRequest,
    llm_client=Depends(get_llm_client),
) -> dict[str, Any]:
    """Run a real lightweight team collaboration round and persist the result.

    This is the first production Team Collaboration Layer endpoint: it consults
    selected Jarvis specialists, asks Alfred to synthesize, and stores the
    coordination summary in collaboration memory for future private chats.
    """
    import json as _json
    from app.jarvis.collaboration_memory import remember_coordination_summary
    from app.tools.jarvis_tools import _parse_json_object

    allowed = [agent_id for agent_id in (req.agents or ["maxwell", "nora", "mira", "leo"]) if agent_id in JARVIS_AGENTS and agent_id != "shadow"]
    selected = allowed[:5]
    if not selected:
        raise HTTPException(status_code=400, detail="No valid collaboration agents selected")

    ctx = await get_life_context_bus().get_context()
    context_text = (
        f"Life context: stress={ctx.stress_level}/10, schedule_density={ctx.schedule_density}/10, "
        f"sleep={ctx.sleep_quality}/10, mood={ctx.mood_trend}"
    )
    specialist_outputs: list[dict[str, Any]] = []
    for agent_id in selected:
        agent = get_agent(agent_id)
        prompt = (
            f"## Team collaboration task\n{req.goal}\n\n"
            f"## Latest user message\n{req.user_message or '(none)'}\n\n"
            f"## Context\n{context_text}\n\n"
            f"You are {agent['name']} ({agent['role']}). Respond as this specialist only.\n"
            "Return JSON only with this shape:\n"
            f'{{"agent_id":"{agent_id}","agent_name":"{agent["name"]}","focus":"...","priority":"low|medium|high","advice":["..."],"needs_from":["agent_id or user"],"risk":"..."}}'
        )
        try:
            raw = await llm_client.chat(message=prompt, system_prompt=agent["system_prompt"], temperature=0.3)
            parsed = _parse_json_object(raw or "")
        except Exception as exc:
            parsed = {"agent_id": agent_id, "agent_name": agent["name"], "focus": "error", "priority": "medium", "advice": [], "needs_from": [], "risk": str(exc)}
        parsed.setdefault("agent_id", agent_id)
        parsed.setdefault("agent_name", agent["name"])
        specialist_outputs.append(parsed)

    synthesis_prompt = (
        f"## Team collaboration task\n{req.goal}\n\n"
        f"## Latest user message\n{req.user_message or '(none)'}\n\n"
        f"## Context\n{context_text}\n\n"
        "## Specialist outputs\n"
        f"{_json.dumps(specialist_outputs, ensure_ascii=False, indent=2)}\n\n"
        "As Alfred, synthesize the team result. Return JSON only:\n"
        '{"summary":"...","aligned_actions":["..."],"conflicts":["..."],"followups":["..."],"handoffs":[{"from":"agent_id","to":"agent_id","reason":"..."}]}'
    )
    try:
        synthesis_raw = await llm_client.chat(message=synthesis_prompt, system_prompt=get_agent("alfred")["system_prompt"], temperature=0.2)
        synthesis = _parse_json_object(synthesis_raw or "")
    except Exception as exc:
        synthesis = {"summary": f"团队协作汇总失败：{exc}", "aligned_actions": [], "conflicts": [], "followups": [], "handoffs": []}

    await remember_coordination_summary(
        source_agent=req.source_agent if req.source_agent in JARVIS_AGENTS else "alfred",
        participant_agents=sorted(set([req.source_agent, "alfred", *selected])),
        goal=req.goal,
        summary=str(synthesis.get("summary") or req.goal),
        payload={
            "session_id": req.session_id,
            "user_message": req.user_message,
            "specialists": specialist_outputs,
            "aligned_actions": synthesis.get("aligned_actions", []),
            "conflicts": synthesis.get("conflicts", []),
            "followups": synthesis.get("followups", []),
            "handoffs": synthesis.get("handoffs", []),
        },
    )
    return {
        "type": "team.collaboration",
        "ok": True,
        "goal": req.goal,
        "participants": selected,
        "specialists": specialist_outputs,
        "summary": synthesis.get("summary", ""),
        "aligned_actions": synthesis.get("aligned_actions", []),
        "conflicts": synthesis.get("conflicts", []),
        "followups": synthesis.get("followups", []),
        "handoffs": synthesis.get("handoffs", []),
        "memory_saved": True,
    }


@router.get("/pending-actions")
async def list_pending_action_items(status: str = "pending") -> list[dict[str, Any]]:
    from app.jarvis.persistence import list_pending_actions

    return await list_pending_actions(status=status or None)


@router.get("/background-tasks")
async def list_background_task_items(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    from app.jarvis.persistence import list_background_tasks

    return await list_background_tasks(status=status, limit=limit)


@router.patch("/pending-actions/{pending_id}")
async def update_pending_action_item(pending_id: str, req: PendingActionUpdateRequest) -> dict[str, Any]:
    from app.jarvis.persistence import update_pending_action

    updated = await update_pending_action(
        pending_id,
        arguments=req.arguments,
        title=req.title,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Pending action {pending_id!r} not found")
    return updated


@router.post("/pending-actions/{pending_id}/cancel")
async def cancel_pending_action_item(pending_id: str) -> dict[str, Any]:
    from app.jarvis.persistence import update_pending_action

    updated = await update_pending_action(pending_id, status="cancelled")
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Pending action {pending_id!r} not found")
    return updated


@router.post("/pending-actions/{pending_id}/confirm")
async def confirm_pending_action_item(pending_id: str, req: PendingActionConfirmRequest) -> dict[str, Any]:
    from app.jarvis.persistence import get_pending_action, update_pending_action

    item = await get_pending_action(pending_id)
    if item is None:
        arguments = req.arguments or {}
        title = str(arguments.get("title") or req.title or "")
        start = arguments.get("start")
        end = arguments.get("end")
        if not title or not start or not end:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Pending action {pending_id!r} not found, and the confirm request did not include "
                    "enough calendar fields for fallback writing"
                ),
            )
        event_req = CalendarEventRequest(
            title=title,
            start=datetime.fromisoformat(str(start).replace("Z", "+00:00")),
            end=datetime.fromisoformat(str(end).replace("Z", "+00:00")),
            stress_weight=float(arguments.get("stress_weight") or 1.0),
            location=arguments.get("location") if isinstance(arguments.get("location"), str) else None,
            notes=arguments.get("notes") if isinstance(arguments.get("notes"), str) else None,
            source="agent_pending_confirmation_fallback",
            source_agent=None,
            created_reason=arguments.get("created_reason") if isinstance(arguments.get("created_reason"), str) else "用户确认了 Agent 建议的日程安排",
            status="confirmed",
            route_required=bool(arguments.get("route_required") or False),
        )
        result = await add_calendar_event(event_req)
        return {"pending_action": None, "result": result, "fallback": True}
    if item.get("status") != "pending":
        raise HTTPException(status_code=409, detail=f"Pending action {pending_id!r} is already {item.get('status')}")

    arguments = req.arguments if req.arguments is not None else item.get("arguments", {})
    if item.get("action_type") == "task.plan":
        from app.jarvis.persistence import get_background_task, save_background_task

        plan = arguments.get("plan") if isinstance(arguments.get("plan"), dict) else arguments
        task_id = str(plan.get("id") or arguments.get("task_id") or pending_id)
        user_filled_fields = plan.get("user_filled_fields") if isinstance(plan.get("user_filled_fields"), dict) else arguments.get("user_filled_fields")
        notes = "用户确认了 Maxwell 的长期/后台任务拆解计划"
        if isinstance(user_filled_fields, dict) and user_filled_fields:
            filled_parts = [f"{key}={value}" for key, value in user_filled_fields.items() if value]
            if filled_parts:
                notes = f"{notes}；用户补充：" + "；".join(filled_parts)
        saved_task = await save_background_task(
            task_id=task_id,
            title=str(plan.get("title") or arguments.get("title") or item.get("title") or "后台任务"),
            task_type=str(plan.get("type") or arguments.get("classification") or "long_project"),
            status="active",
            source_agent=plan.get("source_agent") if isinstance(plan.get("source_agent"), str) else item.get("agent_id"),
            original_user_request=str(plan.get("original_user_request") or arguments.get("user_request") or ""),
            goal=str(plan.get("goal") or plan.get("title") or item.get("title") or ""),
            time_horizon=plan.get("time_horizon") if isinstance(plan.get("time_horizon"), dict) else {},
            milestones=plan.get("milestones") if isinstance(plan.get("milestones"), list) else [],
            subtasks=plan.get("subtasks") if isinstance(plan.get("subtasks"), list) else [],
            calendar_candidates=plan.get("calendar_candidates") if isinstance(plan.get("calendar_candidates"), list) else [],
            notes=notes,
        )
        persisted_task = await get_background_task(task_id)
        if persisted_task is None:
            raise HTTPException(
                status_code=500,
                detail=f"后台任务 {task_id!r} 保存后回读失败：请检查 jarvis.db/background_tasks 写入。",
            )
        updated = await update_pending_action(pending_id, status="confirmed", arguments=arguments, title=saved_task.get("title"))
        return {"pending_action": updated, "result": {"task": persisted_task, "persisted": True}, "fallback": False}

    if item.get("action_type") != "calendar.add":
        raise HTTPException(status_code=400, detail="Only calendar.add pending actions can be confirmed in this MVP")

    title = str(arguments.get("title") or req.title or item.get("title") or "")
    start = arguments.get("start")
    end = arguments.get("end")
    if not title or not start or not end:
        raise HTTPException(status_code=400, detail="Calendar pending action requires title, start, and end")

    event_req = CalendarEventRequest(
        title=title,
        start=datetime.fromisoformat(str(start).replace("Z", "+00:00")),
        end=datetime.fromisoformat(str(end).replace("Z", "+00:00")),
        stress_weight=float(arguments.get("stress_weight") or 1.0),
        location=arguments.get("location") if isinstance(arguments.get("location"), str) else None,
        notes=arguments.get("notes") if isinstance(arguments.get("notes"), str) else None,
        source="agent_pending_confirmation",
        source_agent=item.get("agent_id"),
        created_reason=arguments.get("created_reason") if isinstance(arguments.get("created_reason"), str) else "用户确认了 Agent 建议的日程安排",
        status="confirmed",
        route_required=bool(arguments.get("route_required") or False),
    )
    result = await add_calendar_event(event_req)
    updated = await update_pending_action(
        pending_id,
        status="confirmed",
        arguments=arguments,
        title=title,
    )
    return {"pending_action": updated, "result": result}


class CalendarEventRequest(BaseModel):
    title: str
    start: datetime
    end: datetime
    stress_weight: float = 1.0
    location: str | None = None
    notes: str | None = None
    source: str = "user_ui"
    source_agent: str | None = None
    created_reason: str | None = None
    status: str = "confirmed"
    route_required: bool = False


class CalendarEventUpdate(BaseModel):
    title: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    stress_weight: float | None = None
    location: str | None = None
    notes: str | None = None
    source: str | None = None
    source_agent: str | None = None
    created_reason: str | None = None
    status: str | None = None
    route_required: bool | None = None


@router.get("/calendar/events")
async def list_calendar_events(
    hours_ahead: int = 24,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    """List upcoming events or events overlapping an explicit time window."""
    from app.mcp.adapters.calendar_adapter import get_events_between, get_upcoming_events

    if start is not None and end is not None:
        return [e.model_dump() for e in get_events_between(start, end)]
    return [e.model_dump() for e in get_upcoming_events(hours_ahead=hours_ahead)]


@router.post("/calendar/events")
async def add_calendar_event(req: CalendarEventRequest) -> dict[str, Any]:
    from app.mcp.adapters.calendar_adapter import add_event, compute_schedule_density, get_upcoming_events
    event = add_event(
        req.title,
        req.start,
        req.end,
        req.stress_weight,
        location=req.location,
        notes=req.notes,
        source=req.source,
        source_agent=req.source_agent,
        created_reason=req.created_reason,
        status=req.status,
        route_required=req.route_required,
    )
    density = compute_schedule_density()
    await get_life_context_bus().update_fields(
        {"schedule_density": density, "active_events": get_upcoming_events(hours_ahead=24)},
        source="user_ui",
    )
    return {"event_id": event.id, "new_schedule_density": density, "event": event.model_dump()}


@router.delete("/calendar/events/{event_id}")
async def delete_calendar_event(event_id: str) -> dict[str, Any]:
    from app.mcp.adapters.calendar_adapter import compute_schedule_density, delete_event
    ok = delete_event(event_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Event {event_id!r} not found")
    density = compute_schedule_density()
    await get_life_context_bus().update_fields(
        {"schedule_density": density}, source="user_ui"
    )
    return {"deleted": event_id, "new_schedule_density": density}


@router.put("/calendar/events/{event_id}")
async def update_calendar_event(event_id: str, req: CalendarEventUpdate) -> dict[str, Any]:
    from app.mcp.adapters.calendar_adapter import compute_schedule_density, update_event
    patch = req.model_dump(exclude_unset=True)
    event = update_event(event_id, **patch)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id!r} not found")
    density = compute_schedule_density()
    await get_life_context_bus().update_fields(
        {"schedule_density": density}, source="user_ui"
    )
    return {"event": event.model_dump(), "new_schedule_density": density}


@router.get("/messages/stream")
async def stream_proactive_messages() -> EventSourceResponse:
    """SSE endpoint — client subscribes to receive proactive messages in real-time."""
    from app.core.lifespan import get_proactive_engine

    async def event_generator():
        while True:
            engine = get_proactive_engine()
            if engine:
                msgs = engine.pop_pending_messages()
                for msg in msgs:
                    yield {"data": json.dumps(msg.model_dump())}
            await asyncio.sleep(10)

    return EventSourceResponse(event_generator())


# ──────────────────────────────────────────────────────────────────────────
# Scenario roundtable
# ──────────────────────────────────────────────────────────────────────────


class RoundtableStartRequest(BaseModel):
    scenario_id: str
    user_input: str = ""
    session_id: str
    mode_id: str = "general"


@router.get("/scenarios")
async def list_jarvis_scenarios() -> list[dict[str, Any]]:
    from app.jarvis.scenarios import list_scenarios
    return list_scenarios()


@router.post("/roundtable/start")
async def start_roundtable(
    req: RoundtableStartRequest,
    llm_client=Depends(get_llm_client),
) -> EventSourceResponse:
    """Start a scenario-based roundtable discussion, streamed as SSE.

    Jarvis-roster scenarios use an inline sequential loop.
    Brainstorm-roster scenarios delegate to BrainstormExecutor (diverge/converge).
    """
    from app.jarvis.scenarios import get_scenario

    try:
        scenario = get_scenario(req.scenario_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {req.scenario_id}")

    from app.jarvis.user_settings import build_profile_prefix, get_enabled_agents
    profile_prefix = build_profile_prefix()

    ctx = await get_life_context_bus().get_context()
    context_prefix = (
        f"[当前生活状态: 压力{ctx.stress_level:.1f}/10, "
        f"日程密度{ctx.schedule_density:.1f}/10, "
        f"心情{ctx.mood_trend}]\n\n"
    )
    user_ask = req.user_input or "(用户未具体说明,请根据当前状态主动展开)"
    composed_message = (
        f"{profile_prefix}{context_prefix}{scenario.opening_prompt}\n\n用户诉求: {user_ask}"
    )

    # ── Work Brainstorm: delegate to BrainstormExecutor ─────────────
    if scenario.agent_roster == "brainstorm":
        try:
            from app.jarvis.persistence import save_conversation

            await save_conversation(
                conversation_id=f"brainstorm:{req.session_id}",
                conversation_type="brainstorm",
                title=f"{scenario.name} · Brainstorm",
                scenario_id=scenario.id,
                session_id=req.session_id,
                route_payload={"mode": "roundtable", "scenario_id": scenario.id, "user_input": req.user_input, "mode_id": req.mode_id},
            )
        except Exception as exc:
            logger.warning("jarvis.roundtable.conversation_save_failed", session_id=req.session_id, error=str(exc))

        from app.agent.brainstorm.executor import BrainstormExecutor
        from app.models.agent import AgentRequest

        executor = BrainstormExecutor(llm_client=llm_client)
        agent_req = AgentRequest(
            session_id=req.session_id,
            message=composed_message,
            mode_id=req.mode_id,
        )

        async def bs_event_gen():
            async for ev in executor.execute_stream(agent_req):
                event_name = ev.event.value if hasattr(ev.event, "value") else str(ev.event)
                yield {"event": event_name, "data": ev.model_dump_json()}

        return EventSourceResponse(bs_event_gen())

    # ── Jarvis-roster scenarios: inline sequential loop ─────────────
    # Determine participating agents (filter to those that actually exist in the roster
    # AND are enabled by the user in their agent config).
    enabled_ids = get_enabled_agents(list(scenario.agents))
    participants = [aid for aid in enabled_ids if aid in JARVIS_AGENTS]
    if not participants:
        # Fall back to Alfred so the stream is never empty.
        participants = ["alfred"]

    try:
        from app.jarvis.persistence import save_conversation

        await save_conversation(
            conversation_id=f"roundtable:{req.session_id}",
            conversation_type="roundtable",
            title=f"{scenario.name} · 圆桌",
            scenario_id=scenario.id,
            session_id=req.session_id,
            route_payload={"mode": "roundtable", "scenario_id": scenario.id, "user_input": req.user_input, "mode_id": req.mode_id},
        )
    except Exception as exc:
        logger.warning("jarvis.roundtable.conversation_save_failed", session_id=req.session_id, error=str(exc))

    # Create session for multi-turn continuation
    from app.jarvis.roundtable_sessions import add_turn_async, create_session_async
    session = await create_session_async(
        session_id=req.session_id,
        scenario_id=scenario.id,
        scenario_name=scenario.name,
        participants=participants,
        agent_roster="jarvis",
    )
    # Seed the transcript with the user's initial request (if any)
    if req.user_input:
        await add_turn_async(session, "user", "You", req.user_input)
    session.round_count = 1

    return EventSourceResponse(
        _run_roundtable_round(
            llm_client=llm_client,
            session_id=req.session_id,
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            scenario_icon=scenario.icon,
            participants=participants,
            opening_prompt=scenario.opening_prompt,
            profile_prefix=profile_prefix,
            context_prefix=context_prefix,
            phase_label="open",
        )
    )


# ──────────────────────────────────────────────────────────────────────────
# Continue a roundtable with a user interjection
# ──────────────────────────────────────────────────────────────────────────


class RoundtableContinueRequest(BaseModel):
    session_id: str
    user_message: str


@router.post("/roundtable/continue")
async def continue_roundtable(
    req: RoundtableContinueRequest,
    llm_client=Depends(get_llm_client),
) -> EventSourceResponse:
    """Continue an existing roundtable after user sends a message.

    The session_id must correspond to a previously-started roundtable
    (/roundtable/start). Each participating agent will see the full
    transcript plus the user's new message, then respond in turn.
    """
    from app.jarvis.roundtable_sessions import get_session
    from app.jarvis.scenarios import get_scenario

    session = get_session(req.session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session {req.session_id!r} not found. Start a roundtable first.",
        )
    if not req.user_message.strip():
        raise HTTPException(status_code=400, detail="Empty user message")

    # Record the user's interjection into the transcript (persisted)
    from app.jarvis.roundtable_sessions import add_turn_async
    session.round_count += 1
    await add_turn_async(session, "user", "You", req.user_message.strip())

    # Feed observation to Shadow (if enabled) — observe against the last speaker
    from app.jarvis.user_settings import get_settings as _get_jarvis_settings
    if _get_jarvis_settings().shadow_learner_enabled:
        from app.core.lifespan import get_preference_learner
        learner = get_preference_learner()
        if learner is not None:
            try:
                # Observe against the last speaker if any, otherwise Alfred
                last_agent = next(
                    (t.role for t in reversed(session.transcript) if t.role != "user"),
                    "alfred",
                )
                last_reply = next(
                    (t.content for t in reversed(session.transcript) if t.role != "user"),
                    "",
                )
                await learner.observe(
                    agent_id=last_agent,
                    user_message=req.user_message,
                    agent_response=last_reply,
                )
            except Exception as exc:
                logger.warning("jarvis.shadow.observe_failed", error=str(exc))

    # Lookup the scenario to get the opening prompt (used as discussion anchor)
    try:
        scenario = get_scenario(session.scenario_id)
    except KeyError:
        scenario = None

    from app.jarvis.user_settings import build_profile_prefix
    profile_prefix = build_profile_prefix()
    ctx = await get_life_context_bus().get_context()
    context_prefix = (
        f"[当前生活状态: 压力{ctx.stress_level:.1f}/10, "
        f"日程密度{ctx.schedule_density:.1f}/10, "
        f"心情{ctx.mood_trend}]\n\n"
    )

    return EventSourceResponse(
        _run_roundtable_round(
            llm_client=llm_client,
            session_id=req.session_id,
            scenario_id=session.scenario_id,
            scenario_name=session.scenario_name,
            scenario_icon=scenario.icon if scenario else "🗣️",
            participants=session.participants,
            opening_prompt=scenario.opening_prompt if scenario else "继续讨论",
            profile_prefix=profile_prefix,
            context_prefix=context_prefix,
            phase_label="user_turn",
        )
    )


async def _run_roundtable_round(
    *,
    llm_client,
    session_id: str,
    scenario_id: str,
    scenario_name: str,
    scenario_icon: str,
    participants: list[str],
    opening_prompt: str,
    profile_prefix: str,
    context_prefix: str,
    phase_label: str,
):
    """Shared generator for both /start and /continue.

    Emits phase_change, then for each participant: agent_speak + token, then done.
    """
    from app.jarvis.roundtable_sessions import get_session

    session = get_session(session_id)

    yield {
        "event": "phase_change",
        "data": json.dumps({
            "phase": phase_label,
            "scenario_id": scenario_id,
            "scenario_name": scenario_name,
            "participants": participants,
            "session_id": session_id,
            "round_count": session.round_count if session else 1,
        }),
    }

    for agent_id in participants:
        agent = JARVIS_AGENTS.get(agent_id)
        if agent is None:
            continue

        yield {
            "event": "agent_speak",
            "data": json.dumps({
                "phase": "speaking",
                "agent_id": agent_id,
                "agent_name": agent["name"],
                "agent_role": agent["role"],
                "agent_icon": agent["icon"],
                "agent_color": agent["color"],
                "session_id": session_id,
            }),
        }

        # Build the full-context prompt for this agent
        transcript_text = session.format_for_prompt() if session else "(无历史)"

        prompt = (
            f"## 场景: {scenario_icon} {scenario_name}\n"
            f"{profile_prefix}{context_prefix}"
            f"## 场景引导\n{opening_prompt}\n\n"
            f"## 完整讨论记录（按时间顺序）\n{transcript_text}\n"
            f"## 你的回合\n"
            f"作为 {agent['name']}（{agent['role']}）,"
            f"请回应用户的最新诉求,或对其他 agent 的观点做补充。"
            f"保持简洁（3-5 句）,针对性强,不要重复已有的观点。"
        )

        try:
            reply, _tool_results = await run_agent_turn(
                agent_id=agent_id,
                llm_client=llm_client,
                message=prompt,
                system_prompt=agent["system_prompt"],
                temperature=0.7,
            )
            content = (reply or "").strip()
        except Exception as exc:
            error_text = str(exc) or exc.__class__.__name__
            logger.error(
                "jarvis.roundtable.agent_failed",
                scenario=scenario_id,
                agent_id=agent_id,
                error=error_text,
            )
            if "401" in error_text or "Unauthorized" in error_text:
                content = (
                    f"{agent['name']} cannot reply right now: LLM provider authentication failed. "
                    "Please check API Key, Base URL, and model name in Settings."
                )
            else:
                content = f"{agent['name']} cannot reply right now: {error_text[:180]}"


        # Record this agent's turn in the session transcript (persisted)
        if session is not None:
            from app.jarvis.roundtable_sessions import add_turn_async
            await add_turn_async(
                session,
                agent_id,
                f"{agent['name']}（{agent['role']}）",
                content,
            )

        yield {
            "event": "token",
            "data": json.dumps({
                "agent_id": agent_id,
                "agent_name": agent["name"],
                "content": content,
                "session_id": session_id,
            }),
        }

    yield {
        "event": "done",
        "data": json.dumps({
            "phase": "round_complete",
            "scenario_id": scenario_id,
            "participants": participants,
            "session_id": session_id,
            "round_count": session.round_count if session else 1,
        }),
    }


# ──────────────────────────────────────────────────────────────────────────
# Persisted session history (SQLite-backed)
# ──────────────────────────────────────────────────────────────────────────


@router.get("/sessions")
async def list_past_sessions(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent roundtable sessions persisted in SQLite (newest first)."""
    from app.jarvis.persistence import list_sessions
    return await list_sessions(limit=limit)


@router.get("/sessions/{session_id}/turns")
async def get_past_session_turns(session_id: str) -> list[dict[str, Any]]:
    """Return the full transcript for a past session (oldest turn first)."""
    from app.jarvis.persistence import get_session_turns
    return await get_session_turns(session_id)


