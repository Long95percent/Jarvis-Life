from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
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
from app.jarvis.agent_consultation import run_agent_consultations
from app.jarvis.context_bus import LifeContextBus, get_life_context_bus
from app.jarvis.memory_extractor import extract_and_save_chat_memories
from app.jarvis.memory_compactor import maybe_compact_old_raw_memories


def _raise_planner_guard_violation(exc: ValueError) -> None:
    raise HTTPException(
        status_code=422,
        detail={"code": "planner_guard_violation", "message": str(exc), "recoverable": True},
    ) from exc


from app.jarvis.memory_recall import build_bounded_memory_recall_prefix
from app.jarvis.preference_learner import build_preference_profile_prefix
from app.jarvis.intent_router import plan_agent_intent, plan_roundtable_intent
from app.jarvis.tool_runtime import execute_tool_calls, format_tool_results, run_agent_turn, to_action_results
from app.llm.background_client import get_background_llm_client

logger = structlog.get_logger("jarvis.api")
router = APIRouter(prefix="/jarvis", tags=["jarvis"])


def _build_private_chat_strategy_prompt(
    *,
    agent_id: str,
    message: str,
    local_now: datetime,
    memory_text: str = "",
    preference_text: str = "",
    collaboration_text: str = "",
    local_life_context: str = "",
) -> str:
    return (
        "## 私聊策略路由\n"
        f"当前角色: {agent_id}\n"
        f"当前时间: {local_now.isoformat()}\n"
        "请根据用户意图选择最合适的执行策略，必须只输出 JSON。\n"
        "可选 strategy: direct / react / plan_execute。\n"
        "规则：\n"
        "1. 普通闲聊、解释、轻量建议 -> direct\n"
        "2. 需要查询、验证、调用一个或少量工具 -> react\n"
        "3. 涉及复杂日程、长期计划、批量修改/删除、需要多轮推理或重排 -> plan_execute\n"
        "4. 涉及日程类意图时，优先不要选 direct。\n"
        "5. 如果不确定，优先选 react；如果明显是复杂日程，优先选 plan_execute。\n"
        "返回格式：{\"domain\":\"schedule|chat|care|study|other\",\"strategy\":\"direct|react|plan_execute\",\"confidence\":0-1,\"needs_tool\":true/false,\"reason\":\"...\"}\n\n"
        f"用户消息: {message}\n\n"
        f"{local_life_context}"
        f"{collaboration_text}"
        f"{memory_text}"
        f"{preference_text}"
    )


def _parse_private_chat_strategy_router(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty_llm_strategy_response")
    start = text.find("{")
    end = text.rfind("}")
    payload = text[start : end + 1] if start != -1 and end != -1 and end > start else text
    data = json.loads(payload)
    strategy = str(data.get("strategy") or "react").strip()
    if strategy not in {"direct", "react", "plan_execute"}:
        strategy = "react"
    domain = str(data.get("domain") or "other").strip() or "other"
    confidence = data.get("confidence")
    try:
        confidence_value = float(confidence)
    except Exception:
        confidence_value = 0.5
    confidence_value = max(0.0, min(1.0, confidence_value))
    needs_tool = bool(data.get("needs_tool"))
    reason = str(data.get("reason") or "").strip()
    return {
        "domain": domain,
        "strategy": strategy,
        "confidence": confidence_value,
        "needs_tool": needs_tool,
        "reason": reason,
    }


async def _select_private_chat_strategy(
    *,
    llm_client: Any,
    agent_id: str,
    message: str,
    local_now: datetime,
    memory_text: str = "",
    preference_text: str = "",
    collaboration_text: str = "",
    local_life_context: str = "",
) -> dict[str, Any]:
    prompt = _build_private_chat_strategy_prompt(
        agent_id=agent_id,
        message=message,
        local_now=local_now,
        memory_text=memory_text,
        preference_text=preference_text,
        collaboration_text=collaboration_text,
        local_life_context=local_life_context,
    )
    try:
        raw = await llm_client.chat(
            message=prompt,
            system_prompt="你是一个只负责路由策略的控制器，必须输出严格 JSON。",
            temperature=0.0,
        )
        parsed = _parse_private_chat_strategy_router(raw)
    except Exception as exc:
        logger.warning("jarvis.chat.strategy_router_failed", agent_id=agent_id, error=str(exc))
        parsed = {
            "domain": "other",
            "strategy": "react",
            "confidence": 0.0,
            "needs_tool": False,
            "reason": "router_fallback",
        }

    intent_text = _normalize_private_chat_intent_text(message)
    if _force_complex_schedule_strategy(intent_text, agent_id):
        parsed.update({"domain": "schedule", "strategy": "plan_execute", "needs_tool": True, "reason": "complex_schedule_guard"})
    elif parsed["strategy"] == "direct" and _is_schedule_intent(intent_text):
        parsed["strategy"] = "react"
        parsed["domain"] = parsed.get("domain") or "schedule"
        parsed["needs_tool"] = True
        parsed["reason"] = parsed.get("reason") or "schedule_prefers_react"
    return parsed


def _normalize_private_chat_intent_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _is_schedule_intent(text: str) -> bool:
    markers = ["日程", "安排", "计划", "日历", "时间", "修改", "删除", "延后", "重排", "replan", "calendar", "schedule"]
    return any(marker in text for marker in markers)


def _force_complex_schedule_strategy(text: str, agent_id: str) -> bool:
    if agent_id != "maxwell":
        return False
    complex_markers = ["一个月", "长期", "多天", "批量", "全部", "重排", "延期", "推迟", "删除所有", "修改所有", "重构", "长期任务"]
    return _is_schedule_intent(text) and any(marker in text for marker in complex_markers)


def _build_user_visible_reply_contract() -> str:
    return (
        "## 用户可见回复契约\n"
        "主人反复强调：不要把 function_call、tool_name、arguments、JSON 指令、<tool_call>、<jarvis-tool> "
        "等内部工具调用内容直接发到聊天框。\n"
        "所有带尖括号的协议标签都不是用户可见回复，例如 <invoke>、<parameter>、<tool_call>、<tool_calls>、"
        "<jarvis-tool>、<jarvis-action>、<execute_bash>；这些只能交给后端解析执行，不能原样发给用户。\n"
        "如果需要操作，必须通过后端工具协议执行；最终给用户看的回复只能是自然语言总结。\n"
        "如果工具没有真实执行成功，不要说已经完成；如果需要继续调用工具，请输出后端可解析的工具协议，而不是给用户看的 JSON。\n"
        "回复前自检：1）我有没有把内部工具参数暴露给用户；2）我有没有声称完成但没有工具结果；"
        "3）我有没有把 function_call JSON 当成最终回复。\n\n"
    )


def _mentions_tool_json_leakage(message: str) -> bool:
    text = _normalize_private_chat_intent_text(message)
    leak_markers = ["function_call", "tool_name", "arguments", "json", "工具调用", "指令", "前端返回", "聊天框"]
    complaint_markers = ["不要", "别", "错误", "不小心", "总是", "根本没有实际执行", "返回给我", "发给我"]
    return any(marker in text for marker in leak_markers) and any(marker in text for marker in complaint_markers)


async def _fetch_weather_for_location(lat: float, lng: float) -> dict[str, Any]:
    from app.mcp.adapters import weather_adapter

    return await weather_adapter.get_current_weather(latitude=lat, longitude=lng)


async def _fetch_browser_location_metadata(lat: float, lng: float) -> dict[str, Any]:
    from app.jarvis.geocoding import reverse_geocode

    label = ""
    label_error = ""
    geocoding: dict[str, Any] = {}
    try:
        resolved = await reverse_geocode(lat, lng)
        if resolved:
            geocoding = resolved.to_dict()
            label = resolved.label
    except Exception as exc:
        label_error = str(exc)
        label = ""
    weather: dict[str, Any] = {}
    try:
        weather = await _fetch_weather_for_location(lat, lng)
    except Exception as exc:
        weather = {"error": str(exc), "is_good_weather": False}
    return {"label": label, "label_error": label_error, "weather": weather, "geocoding": geocoding}


async def _persist_task_plan_result(
    *,
    arguments: dict[str, Any],
    source_agent: str | None,
    source_pending_id: str | None = None,
    confirmed_by_user: bool = False,
) -> dict[str, Any]:
    from app.jarvis.persistence import (
        find_active_background_task_by_identity,
        get_background_task,
        list_jarvis_plan_days,
        save_background_task,
        save_background_task_days,
        save_jarvis_plan,
    )

    plan = arguments.get("plan") if isinstance(arguments.get("plan"), dict) else arguments
    task_title = str(plan.get("title") or arguments.get("title") or "后台任务")
    raw_task_type = str(plan.get("type") or arguments.get("classification") or "long_project")
    task_type = "long_project" if raw_task_type in {"future_project", "recurring_plan"} else raw_task_type
    original_user_request = str(plan.get("original_user_request") or arguments.get("user_request") or "")
    goal = str(plan.get("goal") or plan.get("title") or task_title)
    existing_task = await find_active_background_task_by_identity(
        title=task_title,
        task_type=task_type,
        goal=goal,
        original_user_request=original_user_request,
    )
    fallback_id = source_pending_id or str(plan.get("id") or arguments.get("task_id") or f"task_{int(time.time() * 1000)}")
    task_id = str((existing_task or {}).get("id") or plan.get("id") or arguments.get("task_id") or fallback_id)
    user_filled_fields = plan.get("user_filled_fields") if isinstance(plan.get("user_filled_fields"), dict) else arguments.get("user_filled_fields")
    notes = "用户确认了 Maxwell 的长期/后台任务拆解计划" if confirmed_by_user else "Maxwell 自动写入长期/后台任务拆解计划"
    if isinstance(user_filled_fields, dict) and user_filled_fields:
        filled_parts = [f"{key}={value}" for key, value in user_filled_fields.items() if value]
        if filled_parts:
            notes = f"{notes}；用户补充：" + "；".join(filled_parts)
    await save_background_task(
        task_id=task_id,
        title=task_title,
        task_type=task_type,
        status="active",
        source_agent=plan.get("source_agent") if isinstance(plan.get("source_agent"), str) else source_agent,
        original_user_request=original_user_request,
        goal=goal,
        time_horizon=plan.get("time_horizon") if isinstance(plan.get("time_horizon"), dict) else {},
        milestones=plan.get("milestones") if isinstance(plan.get("milestones"), list) else [],
        subtasks=plan.get("subtasks") if isinstance(plan.get("subtasks"), list) else [],
        calendar_candidates=plan.get("calendar_candidates") if isinstance(plan.get("calendar_candidates"), list) else [],
        notes=notes,
    )
    persisted_task = await get_background_task(task_id)
    if persisted_task is None:
        raise HTTPException(status_code=500, detail=f"后台任务 {task_id!r} 保存后回读失败：请检查 jarvis.db/background_tasks 写入。")

    daily_plan = plan.get("daily_plan") if isinstance(plan.get("daily_plan"), list) else []
    persisted_days = await save_background_task_days(task_id=task_id, daily_plan=daily_plan)
    if daily_plan and not persisted_days:
        raise HTTPException(status_code=500, detail=f"后台任务 {task_id!r} 已保存，但每日任务写入失败：请检查 background_task_days 写入。")

    distinct_dates = {str(day.get("date") or day.get("plan_date") or "")[:10] for day in daily_plan if isinstance(day, dict)}
    plan_type = "short_term" if len(distinct_dates) <= 1 else "long_term"
    plan_days_payload = []
    for day in persisted_days:
        payload = dict(day)
        payload["source_task_day_id"] = day.get("id")
        plan_days_payload.append(payload)
    persisted_plan = await save_jarvis_plan(
        plan_id=str((f"plan_{task_id}" if existing_task else plan.get("plan_id")) or f"plan_{task_id}"),
        title=str(plan.get("title") or arguments.get("title") or task_title),
        plan_type=plan_type,
        status="active",
        source_agent=plan.get("source_agent") if isinstance(plan.get("source_agent"), str) else source_agent,
        source_pending_id=source_pending_id,
        source_background_task_id=task_id,
        original_user_request=original_user_request,
        goal=goal,
        time_horizon=plan.get("time_horizon") if isinstance(plan.get("time_horizon"), dict) else {},
        raw_payload=plan,
        days=plan_days_payload,
    )
    saved_plan_days = await list_jarvis_plan_days(plan_id=persisted_plan["id"], limit=2000)
    projected_calendar = []
    for plan_day in saved_plan_days:
        projected = await _project_plan_day_to_calendar(plan_day, source_agent=persisted_plan.get("source_agent"), reason="长期计划自动写入日历")
        if projected:
            projected_calendar.append(projected)
    return {
        "task": persisted_task,
        "task_days": persisted_days,
        "task_day_count": len(persisted_days),
        "plan": persisted_plan,
        "plan_day_count": len(plan_days_payload),
        "calendar_projection_count": len(projected_calendar),
        "calendar_projection": projected_calendar,
        "persisted": True,
    }


async def _persist_task_plan_actions(action_results: list[dict[str, Any]], source_agent: str) -> None:
    for action in action_results:
        if action.get("type") != "task.plan" or not action.get("ok") or action.get("persisted"):
            continue
        try:
            result = await _persist_task_plan_result(arguments=action, source_agent=source_agent)
            action.update(result)
            action["persisted"] = True
        except Exception as exc:
            logger.warning("jarvis.chat.task_plan_auto_persist_failed", agent_id=source_agent, error=str(exc))
            action["ok"] = False
            action["error"] = f"长期计划自动写入失败：{exc}"


async def _save_background_completion_notice(*, kind: str, count: int, source_agent: str) -> None:
    if count <= 0:
        return
    try:
        from app.jarvis.models import ProactiveMessage
        from app.jarvis.persistence import save_proactive_message

        label = "长期记忆提取" if kind == "memory" else "偏好学习"
        await save_proactive_message(
            ProactiveMessage(
                agent_id="shadow",
                agent_name="Shadow",
                content=f"{label}已完成：本轮更新 {count} 条后台资料。",
                trigger=f"{kind}_background_complete",
                priority="low",
            )
        )
    except Exception as exc:
        logger.warning("jarvis.chat.background_notice_failed", kind=kind, source_agent=source_agent, error=str(exc))


async def _run_chat_background_tasks(
    *,
    user_message: str,
    agent_reply: str,
    source_agent: str,
    session_id: str,
    tool_results: list[dict[str, Any]],
) -> None:
    async def memory_job() -> None:
        saved_count = 0
        try:
            if is_user_constraint(user_message):
                await remember_user_constraint(user_message, source_agent=source_agent)
            if _mentions_tool_json_leakage(user_message):
                await remember_user_constraint(
                    "主人反复强调：不要把 function_call、tool_name、arguments、JSON 指令或任何带尖括号的协议标签（例如 <invoke>、<parameter>、<tool_call>、<tool_calls>、<jarvis-tool>、<jarvis-action>、<execute_bash>）直接发到聊天框。需要操作时必须通过后端工具协议执行；最终回复只给用户自然语言总结，并且只能基于真实工具结果说明已完成。",
                    source_agent=source_agent,
                )
            await remember_tool_actions(source_agent, tool_results)
            saved = await extract_and_save_chat_memories(
                user_message=user_message,
                agent_reply=agent_reply,
                source_agent=source_agent,
                session_id=session_id,
                llm_client=get_background_llm_client(),
            )
            saved_count = len(saved or [])
            await maybe_compact_old_raw_memories(cutoff_days=7, min_interval_seconds=3600)
        except Exception as exc:
            logger.warning("jarvis.chat.memory_save_failed", agent_id=source_agent, error=str(exc))
        await _save_background_completion_notice(kind="memory", count=saved_count, source_agent=source_agent)

    async def preference_job() -> None:
        changed = False
        try:
            from app.jarvis.user_settings import get_settings as _get_jarvis_settings
            from app.core.lifespan import get_preference_learner

            if not _get_jarvis_settings().shadow_learner_enabled:
                return
            learner = get_preference_learner()
            if learner is not None:
                if hasattr(learner, "set_llm_client"):
                    learner.set_llm_client(get_background_llm_client())
                changed = bool(await learner.observe(
                    agent_id=source_agent,
                    user_message=user_message,
                    agent_response=agent_reply,
                ))
        except Exception as exc:
            logger.warning("jarvis.shadow.observe_failed", error=str(exc))
        await _save_background_completion_notice(kind="preference", count=1 if changed else 0, source_agent=source_agent)

    await asyncio.gather(memory_job(), preference_job())


def _chat_error_detail(stage: str, exc: Exception, *, agent_id: str | None = None) -> dict[str, Any]:
    from app.llm.runtime_config import LLMRuntimeError, current_llm_config

    config = current_llm_config()
    error_text = str(exc) or exc.__class__.__name__
    error_code = getattr(exc, "code", None)
    suggestion = getattr(exc, "suggestion", None) or "请查看 AI 服务日志中的同一请求，或把该错误详情发给开发者。"
    lowered = error_text.lower()
    if not isinstance(exc, LLMRuntimeError):
        if "401" in error_text or "unauthorized" in lowered:
            error_code = error_code or "LLM_PROVIDER_AUTH_FAILED"
            suggestion = "LLM Provider 鉴权失败：请检查设置里的 API Key、Base URL 和模型名。"
        elif "404" in error_text or "model" in lowered and "not" in lowered:
            error_code = error_code or "LLM_PROVIDER_MODEL_NOT_FOUND"
            suggestion = "LLM Provider 或模型不可用：请检查设置里的 Base URL 和模型名称是否被当前服务支持。"
        elif "timeout" in lowered or "timed out" in lowered:
            error_code = error_code or "LLM_PROVIDER_TIMEOUT"
            suggestion = "LLM 请求超时：请检查网络、Provider 可用性，或降低模型延迟/增大超时时间。"
        elif "connection" in lowered or "connect" in lowered or "network" in lowered:
            error_code = error_code or "LLM_PROVIDER_UNREACHABLE"
            suggestion = "连接 LLM Provider 失败：请检查网络、代理、Base URL 是否可访问。"
        elif "tool registry" in lowered:
            suggestion = "工具注册表未初始化：请重启 AI 服务，确认 startup 日志出现 tool_registry_ready。"

    return {
        "message": f"Jarvis 对话失败：阶段={stage}；原因={error_text}",
        "stage": stage,
        "agent_id": agent_id,
        "error_code": error_code,
        "error_type": exc.__class__.__name__,
        "error": error_text,
        "suggestion": suggestion,
        "llm": config.summary(),
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
        "删除", "删掉", "移除", "清掉", "取消", "delete", "remove", "clear", "cancel",
    ]
    schedule_time_keywords = [
        "明天", "后天", "今天", "今晚", "下午", "上午", "晚上", "几点", "周一", "周二",
        "周三", "周四", "周五", "周六", "周日", "星期", "下周", "本周",
    ]
    matched_long = [keyword for keyword in long_project_keywords if keyword in text]
    matched_schedule_actions = [keyword for keyword in schedule_action_keywords if keyword in text]
    matched_schedule_times = [keyword for keyword in schedule_time_keywords if keyword in text]
    matched_schedule = matched_schedule_actions + [keyword for keyword in matched_schedule_times if keyword not in matched_schedule_actions]
    has_schedule_intent = bool(matched_schedule_actions) or (
        bool(matched_schedule_times)
        and any(verb in text for verb in ["做", "办", "见", "练", "学", "整理", "散步", "健身", "复习", "吃饭"])
    )
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
    browser_timezone: str | None = None


class AgentChatResponse(BaseModel):
    agent_id: str
    agent_name: str
    content: str
    escalation: dict | None = None
    actions: list[dict] | None = None  # structured actions agent executed (calendar etc)
    routing: dict | None = None
    timing: dict | None = None
    metadata: dict[str, Any] | None = None


_CHAT_STEP_LABELS = {
    "route_decided": "确认负责的智能体",
    "activity_marked": "记录本次用户活动",
    "conversation_persisted": "保存会话入口",
    "base_context": "读取基础上下文和历史对话",
    "memory_context": "检索长期记忆、偏好和协作记忆",
    "consult": "判断是否需要其他智能体协助",
    "local_life_context": "读取本地生活上下文",
    "llm_strategy": "选择私聊执行策略",
    "local_intent": "判断是否需要调用工具",
    "llm_turn": "生成智能体回复并执行工具",
    "actions_built": "整理工具执行结果",
    "background_scheduled": "安排旁路记忆和偏好学习",
    "persist_final_turns": "保存最终对话记录",
    "escalation_eval": "评估是否需要进入圆桌",
}


def _chat_step_from_name(name: str, *, status: str = "running") -> dict[str, Any]:
    return {
        "id": name,
        "label": _CHAT_STEP_LABELS.get(name, name.replace("_", " ")),
        "status": status,
        "duration_ms": None,
        "detail": None,
        "metadata": {},
    }


def _chat_step_from_span(span: dict[str, Any]) -> dict[str, Any]:
    name = str(span.get("name") or "step")
    return {
        "id": name,
        "label": _CHAT_STEP_LABELS.get(name, name.replace("_", " ")),
        "status": "done",
        "duration_ms": span.get("duration_ms"),
        "detail": _chat_step_detail(name, span),
        "metadata": {key: value for key, value in span.items() if key not in {"name", "duration_ms"}},
    }


def _chat_step_detail(name: str, span: dict[str, Any]) -> str | None:
    if name == "route_decided":
        agent_id = span.get("routed_agent_id")
        return f"由 {agent_id} 处理" if agent_id else None
    if name == "base_context":
        return f"读取 {span.get('history_turns', 0)} 条历史对话"
    if name == "memory_context":
        return (
            f"记忆 {span.get('memory_chars', 0)} 字，"
            f"偏好 {span.get('preference_chars', 0)} 字，"
            f"协作记忆 {span.get('collaboration_chars', 0)} 字"
        )
    if name == "consult":
        return f"收集 {span.get('actions', 0)} 条协作建议"
    if name == "local_intent":
        intent = span.get("intent")
        planned_tools = span.get("planned_tools", 0)
        return f"意图 {intent}，计划工具 {planned_tools} 个" if intent else None
    if name == "llm_turn":
        return f"工具调用 {span.get('tool_calls', 0)} 个，预计划工具 {span.get('planned_tool_calls', 0)} 个"
    if name == "actions_built":
        return f"整理 {span.get('actions', 0)} 个动作，待确认 {span.get('pending', 0)} 个"
    if name == "escalation_eval":
        return "建议进入圆桌" if span.get("escalated") else "无需进入圆桌"
    return None


class BehaviorEventRequest(BaseModel):
    session_id: str | None = None
    agent_id: str
    observation_type: str
    duration_minutes: int | None = None
    occurred_at: float | None = None
    session_started_at: float | None = None


class PendingActionUpdateRequest(BaseModel):
    arguments: dict[str, Any] | None = None
    title: str | None = None


class PendingActionConfirmRequest(BaseModel):
    arguments: dict[str, Any] | None = None
    title: str | None = None


class PlanCreateRequest(BaseModel):
    title: str
    plan_type: str = "long_term"
    status: str = "active"
    original_user_request: str = ""
    goal: str | None = None
    time_horizon: dict[str, Any] = Field(default_factory=dict)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class PlanUpdateRequest(BaseModel):
    title: str | None = None
    plan_type: str | None = None
    status: str | None = None
    original_user_request: str | None = None
    goal: str | None = None
    time_horizon: dict[str, Any] | None = None
    raw_payload: dict[str, Any] | None = None


class PlanMergeRequest(BaseModel):
    source_plan_id: str
    target_plan_id: str
    reason: str | None = None


class PlanSplitRequest(BaseModel):
    title: str
    plan_day_ids: list[str] = Field(default_factory=list)
    reason: str | None = None


class PlanDayUpdateRequest(BaseModel):
    plan_date: str | None = None
    title: str | None = None
    description: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    estimated_minutes: int | None = None
    status: str | None = None
    reschedule_reason: str | None = None


class PlanDayMoveRequest(BaseModel):
    plan_date: str
    start_time: str | None = None
    end_time: str | None = None
    reason: str | None = None


class PlanDayBulkUpdateRequest(BaseModel):
    day_ids: list[str] = Field(default_factory=list)
    status: str | None = None
    shift_days: int | None = None
    reason: str | None = None


class BackgroundTaskUpdateRequest(BaseModel):
    status: str | None = None
    notes: str | None = None


class MaxwellRescheduleRequest(BaseModel):
    item_type: str
    item_id: str
    action: str = "postpone_one_day"
    reason: str | None = None
    today: str | None = None


class PlanRescheduleRequest(BaseModel):
    days: list[PlanDayMoveRequest] = Field(default_factory=list)
    reason: str | None = None


class SecretaryPlanRequest(BaseModel):
    intent: str
    message: str
    today: str | None = None
    plan_id: str | None = None
    plan_day_ids: list[str] = Field(default_factory=list)
    timezone: str | None = None
    auto_project_calendar: bool = True



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


class TimeContextRequest(BaseModel):
    browser_timezone: str | None = None


class BrowserLocationRequest(BaseModel):
    lat: float
    lng: float
    browser_timezone: str | None = None
    current_label: str | None = None


class CityLocationRequest(BaseModel):
    city_name: str
    browser_timezone: str | None = None


class AgentConfigPatchRequest(BaseModel):
    enabled: bool | None = None
    interrupt_budget: int | None = None


@router.get("/profile")
async def get_user_profile() -> dict[str, Any]:
    from app.jarvis.user_settings import get_settings
    return get_settings().profile.model_dump()


@router.get("/time/context")
async def get_time_context(browser_timezone: str | None = None) -> dict[str, Any]:
    from app.jarvis.time_context import build_time_context

    try:
        return build_time_context(browser_timezone=browser_timezone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/time/context")
async def post_time_context(req: TimeContextRequest) -> dict[str, Any]:
    return await get_time_context(browser_timezone=req.browser_timezone)


@router.post("/time/browser-location")
async def suggest_browser_location(req: BrowserLocationRequest) -> dict[str, Any]:
    from app.jarvis.time_context import suggest_location_from_browser_coordinates

    try:
        metadata = await _fetch_browser_location_metadata(req.lat, req.lng)
        result = suggest_location_from_browser_coordinates(
            lat=req.lat,
            lng=req.lng,
            browser_timezone=req.browser_timezone,
            current_label=req.current_label,
            reverse_geocode=lambda _lat, _lng: metadata.get("label") or "",
            label_error=metadata.get("label_error") or None,
        )
        result["weather"] = metadata.get("weather") or {}
        result["geocoding"] = metadata.get("geocoding") or {}
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/time/city-location")
async def suggest_city_location(req: CityLocationRequest) -> dict[str, Any]:
    from app.jarvis.time_context import suggest_location_from_city_name
    from app.jarvis.geocoding import geocode_city

    try:
        resolved: dict[str, Any] | None = None
        try:
            geocoded = await geocode_city(req.city_name)
            resolved = geocoded.to_dict() if geocoded else None
        except Exception as exc:
            logger.warning("jarvis.time.city_geocode_failed", city=req.city_name, error=str(exc))
            resolved = None
        result = suggest_location_from_city_name(
            city_name=req.city_name,
            browser_timezone=req.browser_timezone,
            geocode=lambda _city: resolved,
        )
        result["geocoding"] = resolved or {}
        try:
            result["weather"] = await _fetch_weather_for_location(result["lat"], result["lng"])
        except Exception as exc:
            result["weather"] = {"error": str(exc), "is_good_weather": False}
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


class PsychologicalTrackingTogglePayload(BaseModel):
    enabled: bool


class CareFeedbackRequest(BaseModel):
    feedback: str
    snooze_minutes: int | None = None


@router.patch("/agent-config/shadow/toggle")
async def toggle_shadow_learner(req: ShadowTogglePayload) -> dict[str, Any]:
    from app.jarvis.user_settings import update_shadow_enabled
    updated = update_shadow_enabled(req.enabled)
    return {"shadow_learner_enabled": updated.shadow_learner_enabled}


@router.patch("/care/settings/tracking")
async def toggle_psychological_tracking(req: PsychologicalTrackingTogglePayload) -> dict[str, Any]:
    from app.jarvis.user_settings import update_psychological_tracking_enabled

    updated = update_psychological_tracking_enabled(req.enabled)
    return {"psychological_tracking_enabled": updated.psychological_tracking_enabled}


@router.get("/care/settings")
async def get_care_settings() -> dict[str, Any]:
    from app.jarvis.user_settings import get_settings

    return {"psychological_tracking_enabled": get_settings().psychological_tracking_enabled}


@router.delete("/care/data")
async def clear_care_data() -> dict[str, Any]:
    from app.jarvis.persistence import clear_psychological_care_data

    return {"deleted": await clear_psychological_care_data()}


# ──────────────────────────────────────────────────────────────────────────
# LLM status / diagnostics
# ──────────────────────────────────────────────────────────────────────────


@router.get("/llm-status")
async def llm_status(
    probe: bool = Query(default=False, description="When true, perform a real provider probe."),
) -> dict[str, Any]:
    """Report LLM runtime config and optionally probe provider connectivity."""
    from app.llm.runtime_config import LLMRuntimeError, current_llm_config

    config = current_llm_config()
    response: dict[str, Any] = {
        "ok": True,
        "config": config.summary(),
        "probe": {"enabled": probe, "ok": None, "reply_preview": None},
        "error_code": None,
        "error": None,
        "suggestion": None,
    }

    try:
        config.validate()
    except LLMRuntimeError as exc:
        response.update({"ok": False, **exc.to_dict()})
        return response

    if not probe:
        return response

    try:
        llm_client = await get_llm_client()
        reply = await llm_client.chat(
            message="Reply with just the word OK",
            system_prompt="You are a test responder. Reply with at most 2 words.",
            temperature=0,
            max_tokens=10,
        )
        response["probe"] = {"enabled": True, "ok": True, "reply_preview": (reply or "").strip()[:120]}
    except LLMRuntimeError as exc:
        response.update({"ok": False, **exc.to_dict()})
        response["probe"] = {"enabled": True, "ok": False, "reply_preview": None}
    except Exception as exc:
        response.update({
            "ok": False,
            "error_code": "LLM_PROVIDER_HTTP_ERROR",
            "error": str(exc)[:300],
            "suggestion": "LLM Provider 探测失败：请检查 AI 服务日志和 Provider 控制台。",
        })
        response["probe"] = {"enabled": True, "ok": False, "reply_preview": None}
    return response


@router.get("/care/snapshots")
async def list_care_mood_snapshots(
    start: str | None = None,
    end: str | None = None,
    limit: int = 60,
) -> list[dict[str, Any]]:
    """Return daily mood snapshots for the psychological-care MVP."""
    from app.jarvis.user_settings import is_psychological_tracking_enabled

    if not is_psychological_tracking_enabled():
        return []
    from app.jarvis.persistence import list_mood_snapshots

    return await list_mood_snapshots(start=start, end=end, limit=limit)


@router.get("/care/behavior-observations")
async def list_care_behavior_observations(
    date: str | None = None,
    session_id: str | None = None,
    observation_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return behavior observations for psychological-care debugging and MVP UI."""
    from app.jarvis.user_settings import is_psychological_tracking_enabled

    if not is_psychological_tracking_enabled():
        return []
    from app.jarvis.persistence import list_behavior_observations

    return await list_behavior_observations(
        date=date,
        session_id=session_id,
        observation_type=observation_type,
        limit=limit,
    )


@router.post("/care/behavior-events")
async def record_care_behavior_event(req: BehaviorEventRequest) -> dict[str, Any]:
    """Record frontend lifecycle behavior signals such as heartbeat or close."""
    from app.jarvis.user_settings import is_psychological_tracking_enabled

    if not is_psychological_tracking_enabled():
        return {"observation": None, "tracking_enabled": False}
    if req.agent_id not in JARVIS_AGENTS or req.agent_id == "shadow":
        raise HTTPException(status_code=404, detail=f"Unknown agent_id {req.agent_id!r}")
    allowed = {
        "heartbeat",
        "closed",
        "visibility_hidden",
        "visibility_visible",
        "idle_start",
        "idle_end",
        "sleep",
        "resume",
        "app_opened",
        "app_closed",
        "app_minimized",
        "app_activated",
        "app_restored",
    }
    if req.observation_type not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported observation_type {req.observation_type!r}")

    from app.jarvis.behavior_observation import record_behavior_event

    observation = await record_behavior_event(
        session_id=req.session_id,
        agent_id=req.agent_id,
        observation_type=req.observation_type,
        occurred_at=datetime.fromtimestamp(req.occurred_at) if req.occurred_at else None,
        session_started_at=datetime.fromtimestamp(req.session_started_at) if req.session_started_at else None,
        duration_minutes=req.duration_minutes,
    )
    return {"observation": observation}


@router.get("/care/stress-signals")
async def list_care_stress_signals(
    date: str | None = None,
    signal_type: str | None = None,
    refresh: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return schedule pressure signals for psychological-care debugging and MVP UI."""
    from app.jarvis.user_settings import is_psychological_tracking_enabled

    if not is_psychological_tracking_enabled():
        return []
    from app.jarvis.persistence import list_stress_signals
    from app.jarvis.stress_observation import aggregate_schedule_pressure_signals

    if refresh and date:
        return await aggregate_schedule_pressure_signals(date)
    return await list_stress_signals(date=date, signal_type=signal_type, limit=limit)


@router.get("/care/trends")
async def get_care_trends(
    range: str = Query(default="week", pattern="^(week|month|year)$"),
    end: str | None = None,
) -> dict[str, Any]:
    """Return mood/stress/energy/sleep/schedule pressure trend series."""
    from app.jarvis.user_settings import is_psychological_tracking_enabled

    if not is_psychological_tracking_enabled():
        from app.jarvis.care_trends import empty_care_trends

        return empty_care_trends(range_name=range, end=end, tracking_enabled=False)
    from app.jarvis.care_trends import build_care_trends

    try:
        return await build_care_trends(range_name=range, end=end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/care/days/{day}")
async def get_care_day_detail(day: str) -> dict[str, Any]:
    """Return explainable evidence for one psychological-care day."""
    from app.jarvis.user_settings import is_psychological_tracking_enabled

    try:
        parsed_day = datetime.fromisoformat(day[:10]).date().isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="day must be YYYY-MM-DD") from exc
    if not is_psychological_tracking_enabled():
        from app.jarvis.care_trends import empty_care_trends

        empty = empty_care_trends(range_name="week", end=parsed_day, tracking_enabled=False)
        return empty["details"].get(parsed_day) or {
            "date": parsed_day,
            "snapshot": {"date": parsed_day},
            "emotion_observations": [],
            "stress_signals": [],
            "behavior_observations": [],
            "care_triggers": [],
            "positive_events": [],
            "negative_events": [],
            "explanations": ["心理趋势追踪已关闭。"],
        }
    from app.jarvis.care_trends import build_care_day_detail

    return await build_care_day_detail(parsed_day)


@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_agent(
    req: AgentChatRequest,
    llm_client=Depends(get_llm_client),
    step_callback: Any | None = None,
) -> AgentChatResponse:
    timing_started = time.perf_counter()
    timing_spans: list[dict[str, Any]] = []

    def start_span(name: str) -> float:
        started = time.perf_counter()
        if step_callback is not None:
            step_callback(_chat_step_from_name(name, status="running"))
        return started

    def mark_span(name: str, started: float, **extra: Any) -> None:
        span = {"name": name, "duration_ms": round((time.perf_counter() - started) * 1000, 1)}
        if extra:
            span.update(extra)
        timing_spans.append(span)
        if step_callback is not None:
            step_callback(_chat_step_from_span(span))

    route_started = start_span("route_decided")
    schedule_intent = _build_schedule_intent(req.message, req.agent_id)
    routed_agent_id = str(schedule_intent.get("target_agent") or req.agent_id) if schedule_intent else req.agent_id
    try:
        agent = get_agent(routed_agent_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Jarvis 智能体不存在：{routed_agent_id}",
                "stage": "route_agent",
                "agent_id": routed_agent_id,
                "error_type": "AgentNotFound",
                "error": f"Agent {routed_agent_id!r} not found",
                "suggestion": "请刷新页面；如果仍出现该问题，请清理浏览器 localStorage 中的旧 Jarvis 会话状态。",
            },
        )
    mark_span("route_decided", route_started, routed_agent_id=routed_agent_id, routed=bool(schedule_intent))

    activity_started = start_span("activity_marked")
    try:
        await get_life_context_bus().update_fields({}, source="user_chat")
    except Exception as exc:
        logger.warning("jarvis.chat.activity_mark_failed", agent_id=req.agent_id, error=str(exc))
    mark_span("activity_marked", activity_started)

    conversation_started = start_span("conversation_persisted")
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
    mark_span("conversation_persisted", conversation_started)

    try:
        from app.jarvis.user_settings import build_profile_prefix
        from app.jarvis.persistence import get_chat_history, save_chat_turn
        context_started = start_span("base_context")
        profile_prefix = build_profile_prefix()
        from app.jarvis.mood_care import detect_mood_snapshot_enhanced

        mood_snapshot = await detect_mood_snapshot_enhanced(req.message, llm_client=llm_client) if routed_agent_id == "mira" or req.agent_id == "mira" else None

        ctx = await get_life_context_bus().get_context()
        context_summary = (
            f"[Life context: stress={ctx.stress_level}/10, "
            f"schedule_density={ctx.schedule_density}/10, "
            f"sleep={ctx.sleep_quality}/10, mood={ctx.mood_trend}]"
        )
        mood_context = ""
        if mood_snapshot is not None:
            mood_context = (
                "## Mira 心理陪伴上下文\n"
                f"识别到的状态: {json.dumps(mood_snapshot.to_dict(), ensure_ascii=False)}\n"
                "请只做陪伴、状态记录、轻量建议和必要时求助提醒；不要做医疗诊断。"
                "如果风险较高，优先安全提示和联系可信任的人/当地紧急求助渠道。\n\n"
            )

        history = await get_chat_history(routed_agent_id, limit=12, session_id=req.session_id)
        history_text = ""
        if history:
            lines = []
            for turn in history:
                prefix = "User" if turn["role"] == "user" else agent["name"]
                lines.append(f"{prefix}: {turn['content']}")
            history_text = "## 最近对话\n" + "\n".join(lines) + "\n\n"
        mark_span("base_context", context_started, history_turns=len(history or []))

        memory_started = start_span("memory_context")
        collaboration_text, memory_text, preference_text = await asyncio.gather(
            build_collaboration_memory_prefix(routed_agent_id, limit=6),
            build_bounded_memory_recall_prefix(routed_agent_id, req.message, limit=6),
            build_preference_profile_prefix(routed_agent_id, limit=6),
        )
        mark_span(
            "memory_context",
            memory_started,
            memory_chars=len(memory_text),
            preference_chars=len(preference_text),
            collaboration_chars=len(collaboration_text),
        )
        consult_started = start_span("consult")
        consult_result = await run_agent_consultations(
            source_agent=routed_agent_id,
            user_message=req.message,
            session_id=req.session_id,
            llm_client=llm_client,
            context_summary=context_summary,
        )
        mark_span("consult", consult_started, actions=len(consult_result.actions), prefix_chars=len(consult_result.prompt_prefix))

        from app.jarvis.user_settings import get_settings
        from app.jarvis.time_context import build_time_context, build_time_prompt_line, resolve_timezone

        profile = get_settings().profile
        time_payload = build_time_context(profile=profile, browser_timezone=req.browser_timezone)
        local_now = datetime.fromisoformat(time_payload["local_iso"])
        local_tz = resolve_timezone(time_payload["timezone"])
        local_now = local_now.astimezone(local_tz)
        time_context = (
            "## 当前时间\n"
            f"{build_time_prompt_line(profile=profile, browser_timezone=req.browser_timezone)}"
            "制定今天/明天/几点到几点的计划时，必须参考这个当前时间；不要安排已经过去的时间段。\n\n"
        )
        local_life_started = start_span("local_life_context")
        local_life_context = await _build_local_life_context_prefix(now=local_now, limit=5)
        mark_span("local_life_context", local_life_started, chars=len(local_life_context))
    except Exception as exc:
        detail = _chat_error_detail("prepare_context", exc, agent_id=req.agent_id)
        logger.error("jarvis.api.chat_prepare_failed", **detail)
        raise HTTPException(status_code=500, detail=detail) from exc

    common_rules = (
        "## 交互规则\n"
        "如需读取最新信息或执行操作，请优先使用你的专属工具包。\n"
        "涉及日程或生活状态的写操作，只能在用户明确要求执行时提出工具调用。\n"
        "长期计划和明确要求写入的多日计划会自动生成可编辑日程；单次日程修改、删除等高风险操作仍可生成待确认卡片。\n"
        "用户要求规划日程时，应尽量根据当前时间给出开始和结束时间；如果用户没有给时间，请由你先做合理规划，不要强迫用户提供严格格式。\n"
        "如果不需要工具，直接回答。\n\n"
    )
    user_visible_reply_contract = _build_user_visible_reply_contract()
    intent_context = ""
    planned_tool_results: list[dict[str, Any]] = []
    intent_started = start_span("local_intent")
    try:
        intent_decision = plan_agent_intent(routed_agent_id, req.message, local_now=local_now)
        if intent_decision.next_action in {"call_tool", "pending_confirmation"} and intent_decision.tool_name:
            planned_tool_results = await execute_tool_calls(
                routed_agent_id,
                [{"tool_name": intent_decision.tool_name, "arguments": intent_decision.slots}],
            )
            intent_context = (
                "## 私聊意图识别\n"
                f"当前角色: {routed_agent_id}\n"
                f"识别意图: {intent_decision.intent}\n"
                f"计划工具: {intent_decision.tool_name}\n"
                f"下一步: {intent_decision.next_action}\n"
                f"原因: {intent_decision.reason}\n\n"
                f"提取槽位: {json.dumps(intent_decision.slots, ensure_ascii=False, default=str)}\n\n"
                f"{format_tool_results(planned_tool_results)}\n\n"
                "你已经拿到了上面的工具结果。请直接基于结果自然回复用户；"
                "如果工具结果已持久化，请直接说明已写入完整计划；只有工具结果明确 pending_confirmation 时才提示用户确认。\n\n"
            )
        elif intent_decision.next_action == "ask_missing_slots":
            missing = "、".join(intent_decision.missing_slots)
            intent_context = (
                "## 私聊意图识别\n"
                f"当前角色: {routed_agent_id}\n"
                f"识别意图: {intent_decision.intent}\n"
                f"计划工具: {intent_decision.tool_name}\n"
                f"缺少槽位: {missing}\n"
                f"已提取槽位: {json.dumps(intent_decision.slots, ensure_ascii=False, default=str)}\n"
                "请保持当前角色身份，用一句自然的话向用户补齐这些信息；"
                "不要切换到其他角色，也不要假装已经执行工具。\n\n"
            )
        mark_span(
            "local_intent",
            intent_started,
            intent=intent_decision.intent,
            next_action=intent_decision.next_action,
            planned_tools=len(planned_tool_results),
        )
    except Exception as exc:
        logger.warning("jarvis.chat.local_intent_failed", agent_id=routed_agent_id, error=str(exc))
        mark_span("local_intent", intent_started, intent="error", planned_tools=0)

    strategy_started = start_span("llm_strategy")
    llm_strategy = await _select_private_chat_strategy(
        llm_client=llm_client,
        agent_id=routed_agent_id,
        message=req.message,
        local_now=local_now,
        memory_text=memory_text,
        preference_text=preference_text,
        collaboration_text=collaboration_text,
        local_life_context=local_life_context,
    )
    strategy_context = (
        "## 私聊执行策略\n"
        f"domain: {llm_strategy['domain']}\n"
        f"strategy: {llm_strategy['strategy']}\n"
        f"needs_tool: {json.dumps(llm_strategy['needs_tool'], ensure_ascii=False)}\n"
        f"confidence: {llm_strategy['confidence']}\n"
        f"reason: {llm_strategy['reason']}\n"
        "执行要求：\n"
        "- direct：直接回答，不要伪造工具结果。\n"
        "- react：先观察可用上下文，必要时调用工具，基于真实结果回复。\n"
        "- plan_execute：先制定简短执行计划，再分步调用工具查询/修改/校验，最后汇总真实结果。\n"
        "- 日程领域必须先查询或调用工具确认真实状态；不要只凭语言承诺已完成。\n\n"
    )
    mark_span(
        "llm_strategy",
        strategy_started,
        domain=llm_strategy.get("domain"),
        strategy=llm_strategy.get("strategy"),
        confidence=llm_strategy.get("confidence"),
    )

    full_message = (
        f"{profile_prefix}{context_summary}\n\n"
        f"{time_context}"
        f"{common_rules}"
        f"{user_visible_reply_contract}"
        f"{strategy_context}"
        f"{intent_context}"
        f"{mood_context}"
        f"{consult_result.prompt_prefix}"
        f"{local_life_context}"
        f"{preference_text}"
        f"{memory_text}"
        f"{collaboration_text}"
        f"{history_text}"
        f"User: {req.message}"
    )

    llm_started = start_span("llm_turn")
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
        detail["timing"] = {
            "total_ms": round((time.perf_counter() - timing_started) * 1000, 1),
            "spans": timing_spans,
        }
        logger.error("jarvis.api.chat_failed", **detail)
        raise HTTPException(status_code=502, detail=detail) from exc
    all_tool_results = [*planned_tool_results, *(tool_results or [])]
    mark_span("llm_turn", llm_started, tool_calls=len(tool_results or []), planned_tool_calls=len(planned_tool_results))

    actions_started = start_span("actions_built")
    clean_reply = (response or "").strip()
    user_turn_id: int | None = None
    care_actions: list[dict[str, Any]] = []
    from app.jarvis.user_settings import is_psychological_tracking_enabled
    psychological_tracking_enabled = is_psychological_tracking_enabled()
    if psychological_tracking_enabled and "mood_snapshot" in locals() and mood_snapshot is not None:
        try:
            from app.jarvis.mood_care import persist_mood_care

            user_turn_id = await save_chat_turn(agent_id=routed_agent_id, role="user", content=req.message, session_id=req.session_id)
            care_actions = await persist_mood_care(
                mood_snapshot,
                user_message=req.message,
                session_id=req.session_id,
                source_agent=routed_agent_id,
                turn_id=user_turn_id,
            )
        except Exception as exc:
            logger.warning("jarvis.chat.mood_care_failed", agent_id=req.agent_id, error=str(exc))
    action_results = [*care_actions, *consult_result.actions, *to_action_results(all_tool_results)]
    await _persist_task_plan_actions(action_results, routed_agent_id)
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
    mark_span("actions_built", actions_started, actions=len(action_results), pending=sum(1 for action in action_results if action.get("pending_confirmation")))

    background_started = start_span("background_scheduled")
    asyncio.create_task(_run_chat_background_tasks(
        user_message=req.message,
        agent_reply=clean_reply,
        source_agent=routed_agent_id,
        session_id=req.session_id,
        tool_results=all_tool_results,
    ))
    mark_span("background_scheduled", background_started)

    # Persist both sides of the exchange so the next request has history
    persist_started = start_span("persist_final_turns")
    try:
        if user_turn_id is None:
            user_turn_id = await save_chat_turn(agent_id=routed_agent_id, role="user", content=req.message, session_id=req.session_id)
        try:
            from app.jarvis.behavior_observation import record_chat_activity_observations

            if psychological_tracking_enabled:
                await record_chat_activity_observations(session_id=req.session_id, agent_id=routed_agent_id)
        except Exception as exc:
            logger.warning("jarvis.chat.behavior_observation_failed", agent_id=req.agent_id, error=str(exc))
        await save_chat_turn(
            agent_id=routed_agent_id,
            role="agent",
            content=clean_reply,
            actions=action_results,
            session_id=req.session_id,
        )
    except Exception as exc:
        logger.warning("jarvis.chat.persist_failed", agent_id=req.agent_id, error=str(exc))
    mark_span("persist_final_turns", persist_started)

    # Evaluate whether this message should auto-escalate to a roundtable
    from app.jarvis.escalation import evaluate_escalation
    hint = None
    escalation_started = start_span("escalation_eval")
    try:
        ctx_for_eval = await get_life_context_bus().get_context()
        hint = evaluate_escalation(
            user_message=req.message,
            agent_id=req.agent_id,
            context=ctx_for_eval,
        )
    except Exception as exc:
        logger.warning("jarvis.chat.escalation_eval_failed", agent_id=req.agent_id, error=str(exc))
    mark_span("escalation_eval", escalation_started, escalated=hint is not None)
    escalation_payload = None
    if hint is not None:
        escalation_payload = {
            "scenario_id": hint.scenario_id,
            "severity": hint.severity,
            "reason": hint.reason,
            "countdown_seconds": hint.countdown_seconds,
        }

    total_ms = round((time.perf_counter() - timing_started) * 1000, 1)
    timing_payload = {
        "total_ms": total_ms,
        "spans": timing_spans,
    }
    logger.info(
        "jarvis.chat.timing",
        agent_id=req.agent_id,
        routed_agent_id=routed_agent_id,
        session_id=req.session_id,
        total_ms=total_ms,
        spans=timing_spans,
    )

    return AgentChatResponse(
        agent_id=routed_agent_id,
        agent_name=agent["name"],
        content=clean_reply,
        escalation=escalation_payload,
        actions=action_results if action_results else None,
        routing=schedule_intent,
        timing=timing_payload,
        metadata={"llm_strategy": llm_strategy},
    )


async def _chat_stream_events(req: AgentChatRequest, llm_client: Any):
    started = time.perf_counter()
    step_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    def emit_step(step: dict[str, Any]) -> None:
        step_queue.put_nowait(step)

    async def run_chat() -> AgentChatResponse:
        try:
            return await chat_with_agent(req, llm_client=llm_client, step_callback=emit_step)
        finally:
            step_queue.put_nowait(None)

    yield {
        "event": "chat_status",
        "data": json.dumps({"stage": "accepted", "agent_id": req.agent_id, "session_id": req.session_id}, ensure_ascii=False),
    }
    yield {
        "event": "chat_step",
        "data": json.dumps({
            "id": "accepted",
            "label": "后端已接收请求",
            "status": "done",
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "detail": f"会话 {req.session_id}",
            "metadata": {"agent_id": req.agent_id},
        }, ensure_ascii=False, default=str),
    }
    chat_task = asyncio.create_task(run_chat())
    try:
        while True:
            step = await step_queue.get()
            if step is None:
                break
            yield {
                "event": "chat_step",
                "data": json.dumps(step, ensure_ascii=False, default=str),
            }
        response = await chat_task
        yield {
            "event": "chat_result",
            "data": json.dumps(jsonable_encoder(response), ensure_ascii=False),
        }
        yield {
            "event": "chat_done",
            "data": json.dumps({
                "ok": True,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                "response_ready_ms": response.timing.get("total_ms") if response.timing else None,
            }, ensure_ascii=False),
        }
    except Exception as exc:
        if not chat_task.done():
            chat_task.cancel()
        yield {
            "event": "chat_error",
            "data": json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False),
        }


@router.post("/chat/stream")
async def stream_chat_with_agent(
    req: AgentChatRequest,
    llm_client=Depends(get_llm_client),
) -> EventSourceResponse:
    """SSE chat endpoint for lower perceived latency in private-chat mode."""

    return EventSourceResponse(_chat_stream_events(req, llm_client))


@router.get("/chat/{agent_id}/history")
async def get_agent_chat_history(agent_id: str, limit: int = 50, session_id: str | None = None) -> list[dict[str, Any]]:
    """Return recent 1:1 chat turns for an agent (chronological, oldest first)."""
    if agent_id not in JARVIS_AGENTS or agent_id == "shadow":
        raise HTTPException(status_code=404, detail=f"Unknown agent_id {agent_id!r}")
    from app.jarvis.persistence import get_chat_history
    return await get_chat_history(agent_id, limit=limit, session_id=session_id)


@router.delete("/chat/{agent_id}/history")
async def clear_agent_chat_history(agent_id: str, session_id: str | None = None) -> dict[str, Any]:
    """Wipe chat history for a specific agent."""
    if agent_id not in JARVIS_AGENTS or agent_id == "shadow":
        raise HTTPException(status_code=404, detail=f"Unknown agent_id {agent_id!r}")
    from app.jarvis.persistence import clear_chat_history
    cleared = await clear_chat_history(agent_id, session_id=session_id)
    return {"agent_id": agent_id, "session_id": session_id, "cleared": cleared}


@router.get("/local-life")
async def get_local_life(force: bool = False) -> dict[str, Any]:
    """Return the latest aggregated local-life snapshot."""
    from app.jarvis.local_life_aggregator import refresh_local_life
    snapshot = await refresh_local_life(force=force)
    return {
        "weather": snapshot.weather,
        "activities": snapshot.activities,
        "opportunities": snapshot.opportunities,
        "news": snapshot.news,
        "upcoming_events": snapshot.upcoming_events,
        "schedule_density": snapshot.schedule_density,
        "fetched_at": snapshot.fetched_at,
        "sources": snapshot.sources,
    }


@router.get("/messages")
async def get_proactive_messages(
    include_read: bool = False,
    limit: int = 50,
    agent_id: str | None = None,
) -> list[dict[str, Any]]:
    from app.jarvis.persistence import list_proactive_messages

    return await list_proactive_messages(
        include_read=include_read,
        limit=max(1, min(limit, 200)),
        agent_id=agent_id,
    )


@router.post("/messages/{message_id}/read")
async def mark_proactive_message_read_endpoint(message_id: str) -> dict[str, Any]:
    from app.jarvis.persistence import mark_proactive_message_read

    msg = await mark_proactive_message_read(message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail=f"Proactive message {message_id!r} not found")
    return msg


@router.post("/messages/{message_id}/dismiss")
async def dismiss_proactive_message_endpoint(message_id: str) -> dict[str, Any]:
    from app.jarvis.persistence import dismiss_proactive_message

    msg = await dismiss_proactive_message(message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail=f"Proactive message {message_id!r} not found")
    return msg


@router.post("/messages/{message_id}/care-feedback")
async def care_message_feedback_endpoint(message_id: str, req: CareFeedbackRequest) -> dict[str, Any]:
    allowed = {"helpful", "too_frequent", "not_needed", "snooze", "handled"}
    if req.feedback not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported feedback {req.feedback!r}")
    from app.jarvis.persistence import snooze_proactive_message, update_care_intervention_feedback

    status = "resolved" if req.feedback in {"helpful", "handled"} else "dismissed"
    snoozed_until = None
    message = None
    if req.feedback == "snooze":
        status = "snoozed"
        snooze_minutes = req.snooze_minutes or 120
        snoozed_until = time.time() + max(15, snooze_minutes) * 60
        message = await snooze_proactive_message(message_id, snoozed_until)
    intervention = await update_care_intervention_feedback(
        message_id=message_id,
        feedback=req.feedback,
        status=status,
        snoozed_until=snoozed_until,
    )
    if message is None:
        if status == "resolved":
            from app.jarvis.persistence import mark_proactive_message_read

            message = await mark_proactive_message_read(message_id)
        else:
            from app.jarvis.persistence import dismiss_proactive_message

            message = await dismiss_proactive_message(message_id)
    if intervention is None and message is None:
        raise HTTPException(status_code=404, detail="Care message not found")
    return {"message": message, "intervention": intervention}


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

    from app.jarvis.persistence import list_proactive_messages

    before_ids = {m["id"] for m in await list_proactive_messages(include_read=False, limit=200)}
    await engine.check_triggers()
    pending = [
        m for m in await list_proactive_messages(include_read=False, limit=200)
        if m["id"] not in before_ids
    ]

    return {
        "trigger": req.trigger_name,
        "message_count": len(pending),
        "messages": pending,
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

    allowed = [agent_id for agent_id in (req.agents or ["maxwell", "nora", "mira", "leo", "athena"]) if agent_id in JARVIS_AGENTS and agent_id != "shadow"]
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


@router.patch("/background-tasks/{task_id}")
async def update_background_task_item(task_id: str, req: BackgroundTaskUpdateRequest) -> dict[str, Any]:
    from app.jarvis.persistence import hard_delete_background_task, list_jarvis_plan_days, mark_plans_for_background_task, update_background_task

    patch = req.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="No background task fields provided")
    if "status" in patch and patch["status"] not in {"active", "paused", "completed", "archived", "deleted"}:
        raise HTTPException(status_code=400, detail="Unsupported background task status")
    if patch.get("status") == "deleted":
        deleted = await hard_delete_background_task(task_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Background task {task_id!r} not found")
        return deleted
    updated = await update_background_task(task_id, patch)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Background task {task_id!r} not found")
    if patch.get("status") == "archived":
        target_status = "cancelled"
        linked_plans = await mark_plans_for_background_task(task_id, target_status)
        for plan in linked_plans:
            for day in await list_jarvis_plan_days(plan_id=str(plan["id"]), limit=2000):
                _sync_plan_day_calendar_event(day, {"status": target_status})
    return updated


@router.get("/background-tasks/{task_id}/days")
async def list_background_task_day_items(task_id: str, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    from app.jarvis.persistence import list_background_task_days

    return await list_background_task_days(task_id=task_id, status=status, limit=limit)


@router.get("/background-task-days")
async def list_all_background_task_day_items(
    task_id: str | None = None,
    status: str | None = None,
    plan_date: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    from app.jarvis.persistence import list_background_task_days

    return await list_background_task_days(task_id=task_id, status=status, plan_date=plan_date, limit=limit)


@router.post("/background-task-days/{day_id}/complete")
async def complete_background_task_day_item(day_id: str) -> dict[str, Any]:
    from app.jarvis.persistence import update_background_task_day_status

    updated = await update_background_task_day_status(day_id, "completed")
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Background task day {day_id!r} not found")
    return {"task_day": updated}


@router.delete("/background-task-days/{day_id}")
async def delete_background_task_day_item(day_id: str) -> dict[str, Any]:
    from app.jarvis.persistence import hard_delete_background_task_day

    updated = await hard_delete_background_task_day(day_id)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Background task day {day_id!r} not found")
    return {"task_day": updated}


@router.post("/maxwell/reschedule-task")
async def maxwell_reschedule_task(req: MaxwellRescheduleRequest) -> dict[str, Any]:
    from app.jarvis.persistence import request_maxwell_task_reschedule

    try:
        return await request_maxwell_task_reschedule(
            item_type=req.item_type,
            item_id=req.item_id,
            action=req.action,
            reason=req.reason,
            today=req.today,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "maxwell_reschedule_invalid", "message": str(exc), "recoverable": False}) from exc


@router.get("/maxwell/workbench-items")
async def list_maxwell_workbench_items(
    status: str | None = None,
    plan_date: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    from app.jarvis.persistence import list_maxwell_workbench_items

    return await list_maxwell_workbench_items(status=status, plan_date=plan_date, limit=limit)


@router.post("/maxwell/workbench/push-daily-tasks")
async def push_maxwell_daily_tasks(plan_date: str | None = None) -> dict[str, Any]:
    from app.jarvis.time_context import build_time_context
    from app.jarvis.persistence import push_planner_days_to_workbench

    effective_date = plan_date or build_time_context()["local_date"]
    items = await push_planner_days_to_workbench(effective_date)
    return {"plan_date": effective_date[:10], "pushed_count": len(items), "items": items}


@router.post("/background-task-days/mark-overdue-missed")
async def mark_overdue_background_task_day_items(today: str | None = None) -> dict[str, Any]:
    from app.jarvis.time_context import build_time_context
    from app.jarvis.persistence import mark_overdue_planner_days_missed

    effective_today = today or build_time_context()["local_date"]
    missed = await mark_overdue_planner_days_missed(effective_today)
    total = len(missed["background_task_days"]) + len(missed["plan_days"])
    return {"today": effective_today[:10], "missed_count": total, **missed}


@router.post("/planner/mark-overdue-missed")
async def mark_overdue_planner_day_items(today: str | None = None) -> dict[str, Any]:
    return await mark_overdue_background_task_day_items(today=today)






@router.post("/planner/daily-maintenance")
async def run_planner_daily_maintenance_item(
    today: str | None = None,
    auto_reschedule: bool = True,
    push_today: bool = True,
    llm_client: Any = Depends(get_llm_client),
) -> dict[str, Any]:
    from app.jarvis.time_context import build_time_context
    from app.jarvis.planner_maintenance import run_planner_daily_maintenance

    effective_today = today or build_time_context()["local_date"]
    return await run_planner_daily_maintenance(
        today=effective_today,
        llm_client=llm_client,
        auto_reschedule=auto_reschedule,
        push_today=push_today,
    )


@router.post("/planner/daily-maintenance/once")
async def run_planner_daily_maintenance_once_item(
    today: str | None = None,
    auto_reschedule: bool = True,
    push_today: bool = True,
    llm_client: Any = Depends(get_llm_client),
) -> dict[str, Any]:
    from app.jarvis.time_context import build_time_context
    from app.jarvis.planner_maintenance import run_planner_daily_maintenance_once

    effective_today = today or build_time_context()["local_date"]
    return await run_planner_daily_maintenance_once(
        today=effective_today,
        llm_client=llm_client,
        auto_reschedule=auto_reschedule,
        push_today=push_today,
    )


def _combine_plan_day_datetime(plan_day: dict[str, Any], time_value: str | None, fallback: datetime | None = None) -> datetime | None:
    if not time_value:
        return fallback
    try:
        return datetime.fromisoformat(f"{str(plan_day.get('plan_date') or '')[:10]}T{time_value[:5]}:00")
    except ValueError:
        return fallback


def _sync_plan_day_calendar_event(plan_day: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any] | None:
    from app.jarvis.planner_calendar_projection import sync_plan_day_calendar_event

    return sync_plan_day_calendar_event(plan_day, patch)



def _plan_day_has_time(day: dict[str, Any]) -> bool:
    from app.jarvis.planner_calendar_projection import plan_day_has_projectable_time

    return plan_day_has_projectable_time(day)


async def _project_plan_day_to_calendar(day: dict[str, Any], *, source_agent: str | None = None, reason: str = "?? day ?????") -> dict[str, Any] | None:
    from app.jarvis.planner_calendar_projection import project_plan_day_to_calendar

    return await project_plan_day_to_calendar(day, source_agent=source_agent, reason=reason)

@router.get("/plans")
async def list_plan_items(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    from app.jarvis.persistence import list_jarvis_plans

    return await list_jarvis_plans(status=status, limit=limit)


@router.post("/plans")
async def create_plan_item(req: PlanCreateRequest) -> dict[str, Any]:
    from uuid import uuid4

    from app.jarvis.persistence import save_jarvis_plan

    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Plan title is required")
    return await save_jarvis_plan(
        plan_id=f"plan_manual_{uuid4().hex}",
        title=title,
        plan_type=req.plan_type or "long_term",
        status=req.status or "active",
        source_agent="user_ui",
        original_user_request=req.original_user_request or title,
        goal=req.goal,
        time_horizon=req.time_horizon,
        raw_payload={**req.raw_payload, "source": "manual_plan_form"},
        days=None,
    )


@router.patch("/plans/{plan_id}")
async def update_plan_item(plan_id: str, req: PlanUpdateRequest) -> dict[str, Any]:
    from app.jarvis.persistence import update_jarvis_plan

    patch = req.model_dump(exclude_unset=True)
    if "title" in patch:
        patch["title"] = str(patch["title"]).strip()
        if not patch["title"]:
            raise HTTPException(status_code=400, detail="Plan title is required")
    updated = await update_jarvis_plan(plan_id, patch)
    if not updated:
        raise HTTPException(status_code=404, detail="Plan not found")
    return updated


@router.post("/plans/merge")
async def merge_plan_items(req: PlanMergeRequest) -> dict[str, Any]:
    from app.jarvis.persistence import merge_jarvis_plans

    result = await merge_jarvis_plans(req.source_plan_id, req.target_plan_id, req.reason)
    if not result:
        raise HTTPException(status_code=400, detail="Unable to merge plans")
    return result


@router.post("/plans/{plan_id}/split")
async def split_plan_item(plan_id: str, req: PlanSplitRequest) -> dict[str, Any]:
    from app.jarvis.persistence import split_jarvis_plan

    result = await split_jarvis_plan(plan_id, title=req.title, plan_day_ids=req.plan_day_ids, reason=req.reason)
    if not result:
        raise HTTPException(status_code=400, detail="Unable to split plan")
    return result


@router.get("/plans/{plan_id}/events")
async def list_plan_agent_events(plan_id: str, event_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    from app.jarvis.persistence import list_agent_events

    return await list_agent_events(plan_id=plan_id, event_type=event_type, limit=limit)


@router.get("/planner/tasks")
async def list_planner_task_items(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    from app.jarvis.persistence import list_background_tasks, list_jarvis_plans

    plans = await list_jarvis_plans(status=status, limit=limit)
    linked_task_ids = {plan.get("source_background_task_id") for plan in plans if plan.get("source_background_task_id")}
    tasks = [task for task in await list_background_tasks(status=status, limit=limit) if task.get("id") not in linked_task_ids]
    items: list[dict[str, Any]] = []
    for plan in plans:
        items.append({
            "item_type": "plan",
            "id": plan["id"],
            "title": plan["title"],
            "status": plan["status"],
            "task_type": plan.get("plan_type") or "long_term",
            "source_agent": plan.get("source_agent"),
            "source_background_task_id": plan.get("source_background_task_id"),
            "original_user_request": plan.get("original_user_request") or "",
            "goal": plan.get("goal"),
            "time_horizon": plan.get("time_horizon") if isinstance(plan.get("time_horizon"), dict) else {},
            "created_at": plan.get("created_at"),
            "updated_at": plan.get("updated_at"),
            "payload": plan,
        })
    for task in tasks:
        items.append({
            "item_type": "background_task",
            "id": task["id"],
            "title": task["title"],
            "status": task["status"],
            "task_type": task.get("task_type") or "background_task",
            "source_agent": task.get("source_agent"),
            "source_background_task_id": None,
            "original_user_request": task.get("original_user_request") or "",
            "goal": task.get("goal"),
            "time_horizon": task.get("time_horizon") if isinstance(task.get("time_horizon"), dict) else {},
            "created_at": task.get("created_at"),
            "updated_at": task.get("updated_at"),
            "payload": task,
        })
    return sorted(
        items,
        key=lambda item: (0 if item.get("item_type") == "plan" else 1, -float(item.get("updated_at") or 0)),
    )[:limit]


@router.post("/planner/tasks/cleanup-duplicates")
async def cleanup_duplicate_planner_tasks(execute: bool = False) -> dict[str, Any]:
    from app.jarvis.persistence import cleanup_duplicate_background_tasks, preview_duplicate_background_tasks

    preview = await preview_duplicate_background_tasks()
    if not execute:
        return {"execute": False, "deleted_tasks": 0, **preview}
    result = await cleanup_duplicate_background_tasks()
    return {
        "execute": True,
        "duplicate_group_count": preview.get("duplicate_group_count", 0),
        "duplicate_task_count": preview.get("duplicate_task_count", 0),
        "groups": preview.get("groups", []),
        **result,
    }


@router.get("/plan-days")
async def list_plan_day_items(
    plan_id: str | None = None,
    status: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    from app.jarvis.persistence import list_jarvis_plan_days

    return await list_jarvis_plan_days(plan_id=plan_id, status=status, start=start, end=end, limit=limit)




def _item_start_end(item: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    try:
        if item.get("item_type") == "calendar_event":
            return datetime.fromisoformat(str(item.get("start"))), datetime.fromisoformat(str(item.get("end")))
        date = str(item.get("date") or "")[:10]
        start_time = item.get("start_time")
        end_time = item.get("end_time")
        if date and start_time and end_time:
            return datetime.fromisoformat(f"{date}T{str(start_time)[:5]}:00"), datetime.fromisoformat(f"{date}T{str(end_time)[:5]}:00")
    except ValueError:
        return None, None
    return None, None


def _as_naive_local(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone().replace(tzinfo=None)


def _normalize_event_title(title: str) -> str:
    return "".join(ch.lower() for ch in title.strip() if not ch.isspace() and ch not in "，,。.!！?？:：；;")


def _calendar_event_time_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    left_start = _as_naive_local(a_start)
    left_end = _as_naive_local(a_end)
    right_start = _as_naive_local(b_start)
    right_end = _as_naive_local(b_end)
    return left_start < right_end and right_start < left_end


def _find_duplicate_calendar_events(req: "CalendarEventRequest") -> list[dict[str, Any]]:
    if req.source == "planner_projection":
        return []
    normalized_title = _normalize_event_title(req.title)
    if not normalized_title:
        return []
    from app.mcp.adapters.calendar_adapter import get_events_between

    request_day = _as_naive_local(req.start).date()
    window_start = datetime.combine(request_day, datetime.min.time())
    window_end = window_start + timedelta(days=1)
    duplicates = []
    for event in get_events_between(window_start, window_end):
        if event.status in {"deleted", "cancelled"}:
            continue
        if _normalize_event_title(event.title) != normalized_title:
            continue
        if _as_naive_local(event.start).date() != request_day:
            continue
        duplicates.append({
            "id": event.id,
            "title": event.title,
            "start": event.start.isoformat(),
            "end": event.end.isoformat(),
            "status": event.status,
            "same_time": _calendar_event_time_overlap(req.start, req.end, event.start, event.end),
        })
    return duplicates


def _build_planner_conflicts_and_free_windows(items: list[dict[str, Any]], start: datetime, end: datetime) -> dict[str, Any]:
    timed = []
    window_start = _as_naive_local(start)
    window_end = _as_naive_local(end)
    for item in items:
        if item.get("status") in {"completed", "cancelled", "deleted"}:
            continue
        start_dt, end_dt = _item_start_end(item)
        if start_dt is not None:
            start_dt = _as_naive_local(start_dt)
        if end_dt is not None:
            end_dt = _as_naive_local(end_dt)
        if start_dt is None or end_dt is None or end_dt <= start_dt:
            continue
        timed.append({"item": item, "start": start_dt, "end": end_dt})
    timed.sort(key=lambda row: row["start"])
    conflicts = []
    for index, current in enumerate(timed):
        for other in timed[index + 1:]:
            if other["start"] >= current["end"]:
                break
            conflicts.append({
                "start": max(current["start"], other["start"]).isoformat(),
                "end": min(current["end"], other["end"]).isoformat(),
                "items": [current["item"], other["item"]],
                "reason": "time_overlap",
            })
    free_windows = []
    cursor = window_start
    for row in timed:
        if row["start"] > cursor and (row["start"] - cursor).total_seconds() >= 30 * 60:
            free_windows.append({"start": cursor.isoformat(), "end": row["start"].isoformat(), "minutes": int((row["start"] - cursor).total_seconds() / 60)})
        if row["end"] > cursor:
            cursor = row["end"]
    if window_end > cursor and (window_end - cursor).total_seconds() >= 30 * 60:
        free_windows.append({"start": cursor.isoformat(), "end": window_end.isoformat(), "minutes": int((window_end - cursor).total_seconds() / 60)})
    return {"conflicts": conflicts, "free_windows": free_windows}

@router.get("/planner/calendar-items")
async def list_planner_calendar_items(start: datetime, end: datetime) -> dict[str, Any]:
    from app.jarvis.persistence import list_background_task_days, list_jarvis_plan_days
    from app.mcp.adapters.calendar_adapter import get_events_between

    start_day = start.date().isoformat()
    end_day = end.date().isoformat()
    events = [
        {"item_type": "calendar_event", "id": event.id, "date": event.start.date().isoformat(), "start": event.start.isoformat(), "end": event.end.isoformat(), "title": event.title, "status": event.status, "source": event.source, "payload": event.model_dump()}
        for event in get_events_between(start, end)
    ]
    plan_days = await list_jarvis_plan_days(start=start_day, end=end_day, limit=1000)
    plan_items = [
        {"item_type": "plan_day", "id": day["id"], "date": day["plan_date"], "start_time": day.get("start_time"), "end_time": day.get("end_time"), "title": day["title"], "status": day["status"], "plan_id": day["plan_id"], "calendar_event_id": day.get("calendar_event_id"), "payload": day}
        for day in plan_days
        if not day.get("calendar_event_id")
    ]
    background_days = await list_background_task_days(limit=1000)
    plan_source_task_day_ids = {
        str(day.get("source_task_day_id"))
        for day in plan_days
        if day.get("source_task_day_id") and day.get("calendar_event_id")
    }
    background_items = [
        {"item_type": "background_task_day", "id": day["id"], "date": day["plan_date"], "start_time": day.get("start_time"), "end_time": day.get("end_time"), "title": day["title"], "status": day["status"], "task_id": day["task_id"], "calendar_event_id": day.get("calendar_event_id"), "payload": day}
        for day in background_days
        if start_day <= str(day.get("plan_date") or "")[:10] <= end_day and str(day.get("id")) not in plan_source_task_day_ids
    ]
    items = sorted([*events, *plan_items, *background_items], key=lambda item: (item.get("date") or "", item.get("start") or item.get("start_time") or ""))
    availability = _build_planner_conflicts_and_free_windows(items, start, end)
    return {"start": start.isoformat(), "end": end.isoformat(), "items": items, **availability}


@router.get("/planner/availability")
async def get_planner_availability(start: datetime, end: datetime) -> dict[str, Any]:
    calendar = await list_planner_calendar_items(start=start, end=end)
    return {"start": calendar["start"], "end": calendar["end"], "conflicts": calendar.get("conflicts", []), "free_windows": calendar.get("free_windows", [])}


@router.post("/planner/secretary-plan")
async def create_secretary_plan(req: SecretaryPlanRequest, llm_client=Depends(get_llm_client)) -> dict[str, Any]:
    from app.jarvis.secretary_planning_service import run_secretary_plan_request

    today = (req.today or date.today().isoformat())[:10]
    try:
        return await run_secretary_plan_request(
            intent=req.intent,
            message=req.message,
            today=today,
            llm_client=llm_client,
            plan_id=req.plan_id,
            plan_day_ids=req.plan_day_ids,
            timezone=req.timezone,
            auto_project_calendar=req.auto_project_calendar,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "secretary_plan_failed", "message": str(exc), "recoverable": True}) from exc


@router.patch("/plan-days/{day_id}")
async def update_plan_day_item(day_id: str, req: PlanDayUpdateRequest) -> dict[str, Any]:
    from app.jarvis.persistence import list_jarvis_plan_days, update_jarvis_plan_day
    from app.jarvis.planner_guard import validate_plan_day_move

    patch = req.model_dump(exclude_unset=True)
    if any(key in patch for key in ("plan_date", "start_time", "end_time")):
        existing = next((day for day in await list_jarvis_plan_days(limit=5000) if day.get("id") == day_id), None)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Plan day {day_id!r} not found")
        try:
            validate_plan_day_move(existing, patch, today=date.today().isoformat())
        except ValueError as exc:
            _raise_planner_guard_violation(exc)
    updated = await update_jarvis_plan_day(day_id, patch, event_type="plan_day.updated")
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Plan day {day_id!r} not found")
    calendar_event = _sync_plan_day_calendar_event(updated, patch)
    return {"plan_day": updated, "calendar_event": calendar_event}


@router.post("/plan-days/{day_id}/complete")
async def complete_plan_day_item(day_id: str) -> dict[str, Any]:
    from app.jarvis.persistence import update_jarvis_plan_day

    patch = {"status": "completed"}
    updated = await update_jarvis_plan_day(day_id, patch, event_type="day.completed")
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Plan day {day_id!r} not found")
    calendar_event = _sync_plan_day_calendar_event(updated, patch)
    return {"plan_day": updated, "calendar_event": calendar_event}


@router.delete("/plan-days/{day_id}")
async def delete_plan_day_item(day_id: str) -> dict[str, Any]:
    from app.jarvis.persistence import hard_delete_jarvis_plan_day

    updated = await hard_delete_jarvis_plan_day(day_id)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Plan day {day_id!r} not found")
    return {"plan_day": updated, "calendar_event": None}


@router.post("/plan-days/{day_id}/move")
async def move_plan_day_item(day_id: str, req: PlanDayMoveRequest) -> dict[str, Any]:
    from app.jarvis.persistence import append_maxwell_workbench_log, list_jarvis_plan_days, update_jarvis_plan_day
    from app.jarvis.planner_guard import validate_plan_day_move

    patch = {"plan_date": req.plan_date[:10], "start_time": req.start_time, "end_time": req.end_time, "status": "rescheduled", "reschedule_reason": req.reason or "??????/??"}
    existing = next((day for day in await list_jarvis_plan_days(limit=5000) if day.get("id") == day_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Plan day {day_id!r} not found")
    try:
        validate_plan_day_move(existing, patch, today=date.today().isoformat())
    except ValueError as exc:
        _raise_planner_guard_violation(exc)
    updated = await update_jarvis_plan_day(
        day_id,
        patch,
        event_type="plan.rescheduled",
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Plan day {day_id!r} not found")
    calendar_event = _sync_plan_day_calendar_event(updated, patch)
    await append_maxwell_workbench_log(
        plan_day_id=updated.get("id"),
        event="移动到新时间",
        detail=f"{existing.get('plan_date')} 调整到 {updated.get('plan_date')}；原因：{patch.get('reschedule_reason')}",
        category="manual_edit",
        source="schedule_api",
    )
    return {"plan_day": updated, "calendar_event": calendar_event}


@router.post("/plan-days/bulk-update")
async def bulk_update_plan_day_items(req: PlanDayBulkUpdateRequest) -> dict[str, Any]:
    from app.jarvis.persistence import get_jarvis_plan, list_jarvis_plan_days, record_agent_event, update_jarvis_plan_day
    from app.jarvis.planner_guard import validate_plan_day_move

    day_ids = [day_id for day_id in dict.fromkeys(req.day_ids) if isinstance(day_id, str) and day_id.strip()]
    if not day_ids:
        raise HTTPException(status_code=400, detail="day_ids is required")
    if req.status is None and req.shift_days is None:
        raise HTTPException(status_code=400, detail="status or shift_days is required")
    changed: list[dict[str, Any]] = []
    calendar_events: list[dict[str, Any]] = []
    for day_id in day_ids:
        existing = (await list_jarvis_plan_days(limit=5000))
        day = next((item for item in existing if item.get("id") == day_id), None)
        if not day:
            continue
        patch: dict[str, Any] = {}
        if req.status is not None:
            patch["status"] = req.status
        if req.shift_days is not None:
            try:
                shifted = datetime.fromisoformat(f"{str(day.get('plan_date') or '')[:10]}T00:00:00") + timedelta(days=req.shift_days)
            except ValueError:
                continue
            patch["plan_date"] = shifted.date().isoformat()
            patch["reschedule_reason"] = req.reason or "batch plan day shift"
        try:
            validate_plan_day_move(day, patch, today=date.today().isoformat())
        except ValueError as exc:
            _raise_planner_guard_violation(exc)
        updated = await update_jarvis_plan_day(day_id, patch, event_type="plan_day.bulk_updated")
        if updated:
            changed.append(updated)
            if (event := _sync_plan_day_calendar_event(updated, patch)) is not None:
                calendar_events.append(event)
    plan_ids = sorted({str(day.get("plan_id")) for day in changed if day.get("plan_id")})
    for plan_id in plan_ids:
        if await get_jarvis_plan(plan_id):
            await record_agent_event(event_type="plan_day.bulk_updated", agent_id="user_ui", plan_id=plan_id, payload={"day_ids": [day["id"] for day in changed if day.get("plan_id") == plan_id], "status": req.status, "shift_days": req.shift_days, "reason": req.reason})
    return {"changed_count": len(changed), "changed": changed, "calendar_events": calendar_events}


@router.post("/plans/{plan_id}/cancel")
async def cancel_plan_item(plan_id: str) -> dict[str, Any]:
    from app.jarvis.persistence import cancel_jarvis_plan, list_jarvis_plan_days

    cancelled = await cancel_jarvis_plan(plan_id)
    if cancelled is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id!r} not found")
    days = await list_jarvis_plan_days(plan_id=plan_id, limit=2000)
    synced_events = [
        event
        for day in days
        if (event := _sync_plan_day_calendar_event(day, {"status": "cancelled"})) is not None
    ]
    return {"plan": cancelled, "cancelled_days": days, "calendar_events": synced_events}


@router.delete("/plans/{plan_id}")
async def delete_plan_item(plan_id: str) -> dict[str, Any]:
    from app.jarvis.persistence import hard_delete_jarvis_plan

    deleted = await hard_delete_jarvis_plan(plan_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id!r} not found")
    return {"plan": deleted, "deleted_days": [], "calendar_events": []}


@router.post("/plans/{plan_id}/project-calendar")
async def project_plan_calendar_items(plan_id: str) -> dict[str, Any]:
    from app.jarvis.persistence import get_jarvis_plan, list_jarvis_plan_days

    plan = await get_jarvis_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id!r} not found")
    days = await list_jarvis_plan_days(plan_id=plan_id, limit=2000)
    projected = []
    skipped = []
    for day in days:
        if day.get("status") in {"completed", "cancelled", "missed"}:
            skipped.append({"id": day["id"], "reason": "????????"})
            continue
        result = await _project_plan_day_to_calendar(day, source_agent=plan.get("source_agent"), reason="?????????????????")
        if result is None:
            skipped.append({"id": day["id"], "reason": "???????????"})
        else:
            projected.append(result)
    return {"plan": plan, "projected_count": len(projected), "projected": projected, "skipped": skipped}


@router.post("/plans/{plan_id}/reschedule")
async def reschedule_plan_days(plan_id: str, req: PlanRescheduleRequest) -> dict[str, Any]:
    from app.jarvis.persistence import list_jarvis_plan_days, record_agent_event, update_jarvis_plan_day
    from app.jarvis.planner_guard import validate_plan_day_move

    existing_days = await list_jarvis_plan_days(plan_id=plan_id, limit=2000)
    if not existing_days:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id!r} has no days")
    active_days = [day for day in existing_days if day.get("status") not in {"completed", "cancelled"}]
    updates = req.days[:len(active_days)]
    if not updates:
        raise HTTPException(status_code=400, detail="Reschedule requires at least one future day")
    changed = []
    for day, move in zip(active_days, updates):
        patch = {"plan_date": move.plan_date[:10], "start_time": move.start_time, "end_time": move.end_time, "status": "rescheduled", "reschedule_reason": move.reason or req.reason or "??/Maxwell ????"}
        try:
            validate_plan_day_move(day, patch, today=date.today().isoformat())
        except ValueError as exc:
            _raise_planner_guard_violation(exc)
        updated = await update_jarvis_plan_day(day["id"], patch, event_type="plan.rescheduled")
        if updated:
            calendar_event = _sync_plan_day_calendar_event(updated, patch)
            changed.append({"plan_day": updated, "calendar_event": calendar_event})
    await record_agent_event(event_type="plan.rescheduled", agent_id="maxwell", plan_id=plan_id, payload={"reason": req.reason, "changed_count": len(changed)})
    return {"plan_id": plan_id, "changed_count": len(changed), "changed": changed}


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
        result = await _persist_task_plan_result(
            arguments=arguments,
            source_agent=item.get("agent_id") if isinstance(item.get("agent_id"), str) else None,
            source_pending_id=pending_id,
            confirmed_by_user=True,
        )
        updated = await update_pending_action(pending_id, status="confirmed", arguments=arguments, title=result["task"].get("title"))
        return {
            "pending_action": updated,
            "result": result,
            "fallback": False,
        }

    if item.get("action_type") != "calendar.add":
        raise HTTPException(status_code=400, detail="Only task.plan and calendar.add pending actions can be confirmed")

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
    from app.jarvis.persistence import save_jarvis_plan, update_jarvis_plan_day

    plan_day_result = None
    if isinstance(arguments.get("plan_day_id"), str):
        plan_day_result = await update_jarvis_plan_day(
            arguments["plan_day_id"],
            {"calendar_event_id": result["event_id"], "status": "scheduled"},
            event_type="calendar.changed",
        )
    else:
        plan_date = datetime.fromisoformat(str(start).replace("Z", "+00:00")).date().isoformat()
        plan = await save_jarvis_plan(
            plan_id=str(arguments.get("plan_id") or f"plan_{pending_id}"),
            title=title,
            plan_type="short_term",
            status="active",
            source_agent=item.get("agent_id"),
            source_pending_id=pending_id,
            original_user_request=str(arguments.get("created_reason") or item.get("title") or title),
            goal=title,
            time_horizon={"start": str(start), "end": str(end)},
            raw_payload=arguments,
            days=[{
                "id": str(arguments.get("plan_day_id") or f"planday_{pending_id}"),
                "date": plan_date,
                "title": title,
                "description": arguments.get("notes"),
                "start_time": datetime.fromisoformat(str(start).replace("Z", "+00:00")).time().isoformat(timespec="minutes"),
                "end_time": datetime.fromisoformat(str(end).replace("Z", "+00:00")).time().isoformat(timespec="minutes"),
                "status": "scheduled",
                "calendar_event_id": result["event_id"],
            }],
        )
        from app.jarvis.persistence import list_jarvis_plan_days
        plan_days = await list_jarvis_plan_days(plan_id=plan["id"], limit=5)
        plan_day_result = plan_days[0] if plan_days else None
    updated = await update_pending_action(
        pending_id,
        status="confirmed",
        arguments=arguments,
        title=title,
    )
    return {"pending_action": updated, "result": {**result, "plan_day": plan_day_result}}

    


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
    duplicates = _find_duplicate_calendar_events(req)
    if duplicates:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_calendar_event",
                "message": "已存在同名日程，避免重复安排。请修改已有日程或换一个标题。",
                "duplicates": duplicates,
            },
        )
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
    plan_day = None
    if req.source == "user_ui":
        from app.jarvis.persistence import list_jarvis_plan_days, save_jarvis_plan

        plan = await save_jarvis_plan(
            plan_id=f"plan_calendar_{event.id}",
            title=req.title,
            plan_type="short_term",
            status="active",
            source_agent=req.source_agent,
            original_user_request=req.created_reason or "????????",
            goal=req.title,
            time_horizon={"start": req.start.isoformat(), "end": req.end.isoformat()},
            raw_payload={"calendar_event": event.model_dump()},
            days=[{
                "id": f"planday_calendar_{event.id}",
                "date": req.start.date().isoformat(),
                "title": req.title,
                "description": req.notes,
                "start_time": req.start.time().isoformat(timespec="minutes"),
                "end_time": req.end.time().isoformat(timespec="minutes"),
                "status": "scheduled",
                "calendar_event_id": event.id,
            }],
        )
        plan_days = await list_jarvis_plan_days(plan_id=plan["id"], limit=1)
        plan_day = plan_days[0] if plan_days else None
    density = compute_schedule_density()
    await get_life_context_bus().update_fields(
        {"schedule_density": density, "active_events": get_upcoming_events(hours_ahead=24)},
        source="user_ui",
    )
    return {"event_id": event.id, "new_schedule_density": density, "event": event.model_dump(), "plan_day": plan_day}


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
    from app.mcp.adapters.calendar_adapter import compute_schedule_density, get_upcoming_events, update_event
    from app.jarvis.persistence import sync_plan_day_from_calendar_event
    patch = req.model_dump(exclude_unset=True)
    event = update_event(event_id, **patch)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id!r} not found")
    plan_day = await sync_plan_day_from_calendar_event(event.model_dump())
    density = compute_schedule_density()
    await get_life_context_bus().update_fields(
        {"schedule_density": density, "active_events": get_upcoming_events(hours_ahead=24)}, source="user_ui"
    )
    return {"event": event.model_dump(), "new_schedule_density": density, "plan_day": plan_day}


@router.get("/messages/stream")
async def stream_proactive_messages() -> EventSourceResponse:
    """SSE endpoint — client subscribes to receive proactive messages in real-time."""
    from app.jarvis.persistence import list_proactive_messages, mark_proactive_messages_delivered

    async def event_generator():
        seen: set[str] = set()
        while True:
            msgs = await list_proactive_messages(include_read=False, limit=50)
            fresh = [msg for msg in reversed(msgs) if msg["id"] not in seen]
            if fresh:
                await mark_proactive_messages_delivered([msg["id"] for msg in fresh])
            for msg in fresh:
                seen.add(msg["id"])
                yield {"data": json.dumps(jsonable_encoder(msg), ensure_ascii=False)}
            await asyncio.sleep(10)

    return EventSourceResponse(event_generator())


# ──────────────────────────────────────────────────────────────────────────
# Scenario roundtable
# ──────────────────────────────────────────────────────────────────────────


from app.api.v1.jarvis.roundtable.schemas import (
    RoundtableAcceptRequest,
    RoundtableContinueRequest,
    RoundtablePlanRequest,
    RoundtableReturnRequest,
    RoundtableSaveRequest,
    RoundtableStartRequest,
)


@router.get("/scenarios")
async def list_jarvis_scenarios() -> list[dict[str, Any]]:
    from app.jarvis.scenarios import list_scenarios
    return list_scenarios()


def _roundtable_mode_for_scenario(scenario_id: str) -> str:
    return "decision" if scenario_id in {"study_energy_decision", "schedule_coord"} else "brainstorm"


_ROUNDTABLE_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".py",
    ".json",
    ".csv",
    ".log",
    ".yaml",
    ".yml",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".java",
}

_ROUNDTABLE_DEFER_CONFIRMATION_TOOLS = {"jarvis_task_plan_decompose"}

def _roundtable_document_search_dirs(search_dirs: list[str | Path] | None = None) -> list[Path]:
    if search_dirs is not None:
        raw_dirs = [Path(item) for item in search_dirs]
    else:
        from app.config import settings

        repo_root = Path(__file__).resolve().parents[3].parent
        raw_dirs = [
            Path(settings.data_dir),
            Path(settings.file_processing.upload_dir),
            repo_root / "docs",
        ]

    dirs: list[Path] = []
    seen: set[str] = set()
    for raw_dir in raw_dirs:
        try:
            resolved = raw_dir.expanduser().resolve()
        except Exception:
            continue
        key = str(resolved)
        if key not in seen and resolved.exists() and resolved.is_dir():
            dirs.append(resolved)
            seen.add(key)
    return dirs


def _normalize_roundtable_filename_text(value: str) -> str:
    return re.sub(r"[\s_/\\]+", "", value.casefold())


def _roundtable_document_query_tokens(message: str) -> list[str]:
    raw_tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,}|[\u4e00-\u9fff]{2,}", message.casefold())
    tokens: list[str] = []
    for token in raw_tokens:
        normalized = _normalize_roundtable_filename_text(token)
        if not normalized:
            continue
        tokens.append(normalized)
    return tokens


def _score_roundtable_document_candidate(path: Path, message: str, tokens: list[str]) -> int:
    query = _normalize_roundtable_filename_text(message)
    name = _normalize_roundtable_filename_text(path.name)
    stem = _normalize_roundtable_filename_text(path.stem)
    score = 0
    if name and name in query:
        score += 120
    if stem and stem in query:
        score += 100
    for token in tokens:
        if token and token in name:
            score += max(8, len(token))
        elif token and token in stem:
            score += max(6, len(token))
    return score


async def _resolve_roundtable_document_context(
    message: str,
    *,
    search_dirs: list[str | Path] | None = None,
    max_chars: int = 12000,
    participants: list[str] | None = None,
    intent_decision: Any | None = None,
) -> dict[str, Any]:
    decision = intent_decision or plan_roundtable_intent(participants or [], message)
    if decision.intent != "document_read" or decision.tool_name != "file_read":
        return {"status": "none"}

    roots = _roundtable_document_search_dirs(search_dirs)
    if not roots:
        return {"status": "not_found", "reason": "no_search_dirs"}

    filename_query = str(decision.slots.get("filename_query") or message)
    max_chars = int(decision.slots.get("max_chars") or max_chars)
    tokens = _roundtable_document_query_tokens(filename_query)
    candidates: list[tuple[int, Path]] = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.casefold() not in _ROUNDTABLE_TEXT_EXTENSIONS:
                continue
            score = _score_roundtable_document_candidate(path, filename_query, tokens)
            if score > 0:
                candidates.append((score, path))

    if not candidates:
        return {"status": "not_found", "searched_dirs": [str(item) for item in roots]}

    candidates.sort(key=lambda item: (-item[0], len(str(item[1]))))
    top_score = candidates[0][0]
    top_path_len = len(str(candidates[0][1]))
    top_matches = [path for score, path in candidates if score == top_score and len(str(path)) == top_path_len][:5]
    if len(top_matches) > 1:
        return {
            "status": "ambiguous",
            "matches": [str(path) for path in top_matches],
            "searched_dirs": [str(item) for item in roots],
        }

    selected = top_matches[0]
    from app.tools.file_ops import FileReadTool

    reader = FileReadTool(allowed_dirs=[str(item) for item in roots])
    content = await reader.safe_arun(path=str(selected), max_lines=1000)
    truncated = len(content) > max_chars
    if truncated:
        content = content[:max_chars].rstrip()

    return {
        "status": "attached",
        "file_path": str(selected),
        "file_name": selected.name,
        "content": content,
        "truncated": truncated,
        "chars": len(content),
        "intent": decision.intent,
        "intent_agent_id": decision.agent_id,
        "intent_confidence": decision.confidence,
    }


def _append_roundtable_document_context(context_prefix: str, document_context: dict[str, Any] | None) -> str:
    if not document_context or document_context.get("status") != "attached":
        return context_prefix
    file_name = str(document_context.get("file_name") or "unknown")
    file_path = str(document_context.get("file_path") or "")
    content = str(document_context.get("content") or "").strip()
    if not content:
        return context_prefix
    truncated_note = "\n（内容已按上下文长度截断。）" if document_context.get("truncated") else ""
    block = (
        "\n\n## 临时文档上下文\n"
        f"来源文件: {file_name}\n"
        f"路径: {file_path}\n"
        f"{truncated_note}\n"
        "```text\n"
        f"{content}\n"
        "```\n"
        "请后续圆桌发言基于这份临时文档上下文进行总结、引用和讨论；不要声称已经读取其它未提供的文件。\n"
    )
    return f"{context_prefix}{block}"


def _roundtable_deferred_action_result(decision: Any) -> dict[str, Any]:
    tool_name = str(decision.tool_name or "")
    arguments = dict(decision.slots or {})
    title = str(arguments.get("title") or arguments.get("user_request") or decision.intent or "圆桌待确认操作")[:80]
    return {
        "type": "task.plan" if tool_name == "jarvis_task_plan_decompose" else tool_name,
        "ok": True,
        "pending_confirmation": True,
        "confirmation_id": f"rt_defer_{uuid4().hex}",
        "tool_name": tool_name,
        "title": title,
        "arguments": arguments,
        "description": "圆桌中识别到写入型工具意图，已改为待确认动作，未直接执行。",
    }


async def _persist_roundtable_intent_pending_actions(
    *,
    session_id: str | None,
    agent_id: str,
    action_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not session_id:
        return action_results
    persisted: list[dict[str, Any]] = []
    for action in action_results:
        if not action.get("pending_confirmation"):
            persisted.append(action)
            continue
        try:
            from app.jarvis.persistence import save_pending_action

            arguments = action.get("arguments") if isinstance(action.get("arguments"), dict) else {}
            plan = arguments.get("plan") if isinstance(arguments.get("plan"), dict) else {}
            title = str(arguments.get("title") or plan.get("title") or action.get("title") or action.get("type") or "圆桌待确认操作")
            saved = await save_pending_action(
                pending_id=str(action.get("confirmation_id")),
                action_type=str(action.get("type")),
                tool_name=str(action.get("tool_name") or ""),
                agent_id=agent_id,
                session_id=session_id,
                title=title,
                arguments=arguments,
            )
            enriched = {**action, "pending_action_id": saved.get("id")}
            persisted.append(enriched)
        except Exception as exc:
            logger.warning(
                "jarvis.roundtable.intent_pending_action_save_failed",
                agent_id=agent_id,
                session_id=session_id,
                action_type=action.get("type"),
                error=str(exc),
            )
            persisted.append({**action, "ok": False, "error": f"圆桌待确认动作保存失败：{exc}"})
    return persisted


async def _resolve_roundtable_intent_context(
    message: str,
    *,
    participants: list[str],
    session_id: str | None = None,
    intent_decision: Any | None = None,
) -> dict[str, Any]:
    decision = intent_decision or plan_roundtable_intent(participants, message)
    intent_payload = {
        "agent_id": decision.agent_id,
        "intent": decision.intent,
        "tool_name": decision.tool_name,
        "confidence": decision.confidence,
        "next_action": decision.next_action,
        "reason": decision.reason,
        "slots": decision.slots,
    }
    if decision.intent == "chat_only":
        return {"status": "none", "intent": intent_payload}
    if decision.intent == "document_read":
        return {"status": "document_read", "intent": intent_payload}
    if decision.next_action == "ask_missing_slots":
        return {
            "status": "missing_slots",
            "intent": intent_payload,
            "missing_slots": list(decision.missing_slots),
            "direct_mutation": False,
        }
    if decision.next_action not in {"call_tool", "pending_confirmation"} or not decision.tool_name:
        return {"status": "none", "intent": intent_payload}

    if decision.tool_name in _ROUNDTABLE_DEFER_CONFIRMATION_TOOLS:
        action_results = await _persist_roundtable_intent_pending_actions(
            session_id=session_id,
            agent_id=decision.agent_id,
            action_results=[_roundtable_deferred_action_result(decision)],
        )
        return {
            "status": "pending_confirmation",
            "intent": intent_payload,
            "tool_results": [],
            "action_results": action_results,
            "direct_mutation": False,
        }

    tool_results = await execute_tool_calls(
        decision.agent_id,
        [{"tool_name": decision.tool_name, "arguments": decision.slots}],
    )
    action_results = await _persist_roundtable_intent_pending_actions(
        session_id=session_id,
        agent_id=decision.agent_id,
        action_results=to_action_results(tool_results),
    )
    has_pending = any(action.get("pending_confirmation") for action in action_results)
    return {
        "status": "pending_confirmation" if has_pending else "tool_executed",
        "intent": intent_payload,
        "tool_results": tool_results,
        "action_results": action_results,
        "direct_mutation": False,
    }


def _append_roundtable_intent_context(context_prefix: str, intent_context: dict[str, Any] | None) -> str:
    if not intent_context:
        return context_prefix
    status = intent_context.get("status")
    if status in {None, "none", "document_read"}:
        return context_prefix

    intent = intent_context.get("intent") if isinstance(intent_context.get("intent"), dict) else {}
    lines = [
        "\n\n## 圆桌意图识别与工具结果",
        f"识别角色: {intent.get('agent_id')}",
        f"识别意图: {intent.get('intent')}",
        f"计划工具: {intent.get('tool_name')}",
        f"下一步: {intent.get('next_action')}",
        f"原因: {intent.get('reason')}",
        "圆桌必须基于下面结果继续讨论；写操作只生成待确认动作，不要声称已经修改日程、计划或生活状态。",
    ]
    if status == "missing_slots":
        lines.append(f"缺少槽位: {', '.join(str(item) for item in intent_context.get('missing_slots') or [])}")
        lines.append(f"已提取槽位: {json.dumps(intent.get('slots') or {}, ensure_ascii=False, default=str)}")
        lines.append("请本轮圆桌围绕如何补齐这些信息继续讨论，必要时由 Alfred/Maxwell 向用户澄清。")
    else:
        tool_results = intent_context.get("tool_results") if isinstance(intent_context.get("tool_results"), list) else []
        action_results = intent_context.get("action_results") if isinstance(intent_context.get("action_results"), list) else []
        lines.append(format_tool_results(tool_results))
        if action_results:
            lines.append("## 圆桌待确认动作")
            lines.append(json.dumps(action_results, ensure_ascii=False, indent=2, default=str))
    return f"{context_prefix}" + "\n".join(lines) + "\n"


def _build_brainstorm_result(session_id: str, scenario_id: str, topic: str, synthesis: str, ideas: list[dict[str, Any]]) -> dict[str, Any]:
    cleaned_ideas = []
    for idx, idea in enumerate(ideas[:8], start=1):
        title = str(idea.get("content") or idea.get("title") or "").strip()
        if not title:
            continue
        cleaned_ideas.append({
            "id": idea.get("id") or f"idea_{idx}",
            "title": title[:140],
            "source_agent": idea.get("agent_id") or idea.get("source_agent"),
            "round": idea.get("round"),
        })
    if not cleaned_ideas and synthesis:
        for idx, line in enumerate([line.strip("- 0123456789.、") for line in synthesis.splitlines() if line.strip()][:5], start=1):
            cleaned_ideas.append({"id": f"synthesis_{idx}", "title": line[:140], "source_agent": "moderator"})
    themes = [
        {"title": "核心方向", "summary": synthesis[:220] if synthesis else "围绕当前主题继续发散。"},
        {"title": "可探索想法", "summary": f"已沉淀 {len(cleaned_ideas)} 条候选想法。"},
    ]
    tensions = []
    lowered = synthesis.lower()
    if any(keyword in lowered for keyword in ["risk", "风险", "问题", "挑战", "但是", "however"]):
        tensions.append({"title": "创意与可行性", "description": "部分想法需要进一步验证成本、风险和执行条件。"})
    else:
        tensions.append({"title": "发散与收敛", "description": "当前结果偏发散，转计划前需要用户选择优先方向。"})
    return {
        "id": f"rt_result_{session_id}",
        "session_id": session_id,
        "mode": "brainstorm",
        "status": "draft",
        "summary": synthesis or "Brainstorm 已结束，结果可保存为灵感或转交 Maxwell 生成待确认计划。",
        "themes": themes,
        "ideas": cleaned_ideas,
        "tensions": tensions,
        "followup_questions": [
            "你最想优先推进哪一个方向？",
            "这些想法里哪些只是灵感，哪些需要转成计划？",
            "有没有预算、时间或风险边界需要补充？",
        ],
        "save_as_memory": False,
        "handoff_target": "maxwell",
        "context": {"topic": topic, "scenario_id": scenario_id, "raw_idea_count": len(ideas)},
    }


async def _prepare_decision_context() -> dict[str, Any]:
    from app.jarvis.time_context import build_time_context
    from app.jarvis.persistence import list_background_task_days, list_maxwell_workbench_items, list_mood_snapshots, list_stress_signals
    from app.mcp.adapters.calendar_adapter import get_events_between

    today = datetime.fromisoformat(build_time_context()["local_iso"]).date()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())
    snapshots = await list_mood_snapshots(start=today.isoformat(), end=today.isoformat(), limit=1)
    stress_signals = await list_stress_signals(date=today.isoformat(), limit=20)
    task_days = await list_background_task_days(plan_date=today.isoformat(), limit=20)
    workbench_items = await list_maxwell_workbench_items(status="pending", plan_date=today.isoformat(), limit=20)
    events = [event.model_dump() for event in get_events_between(start, end)]
    local_life_prefix = await _build_local_life_context_prefix(now=datetime.combine(today, datetime.min.time()), limit=5)
    return {
        "date": today.isoformat(),
        "psychological_snapshot": snapshots[0] if snapshots else None,
        "schedule_pressure": stress_signals,
        "today_tasks": task_days,
        "calendar_events": events,
        "maxwell_workbench_items": workbench_items,
        "local_life_context": local_life_prefix,
        "rag_summary": "MVP: 使用当前心理快照、压力信号、今日任务和日程事件作为决策上下文。",
    }


def _build_decision_context_prefix(context: dict[str, Any]) -> str:
    snapshot = context.get("psychological_snapshot") or {}
    stress = context.get("schedule_pressure") or []
    tasks = context.get("today_tasks") or []
    events = context.get("calendar_events") or []
    return (
        "## Decision 预取上下文\n"
        f"- 心理快照: mood={snapshot.get('mood_score', 'n/a')}, stress={snapshot.get('stress_score', 'n/a')}, "
        f"energy={snapshot.get('energy_score', 'n/a')}, flags={snapshot.get('risk_flags', [])}\n"
        f"- 日程压力信号: {len(stress)} 条；今日任务: {len(tasks)} 条；日程事件: {len(events)} 条\n"
        f"- RAG 摘要: {context.get('rag_summary')}\n\n"
        f"{context.get('local_life_context') or ''}"
    )


async def _build_local_life_context_prefix(
    *,
    now: datetime | None = None,
    limit: int = 5,
    category: str | None = None,
    radius_m: int = 3000,
    window_days: int = 14,
) -> str:
    from app.jarvis.local_life_search import list_cached_local_life_opportunities

    items = await list_cached_local_life_opportunities(
        now=now,
        category=category,
        radius_m=radius_m,
        window_days=window_days,
        limit=limit,
    )
    if not items:
        return ""

    lines = [
        "## 近期本地生活机会",
        "以下是缓存中的附近近期活动/本地信息，只在与用户目标相关时使用；不要声称已经实时搜索。",
    ]
    for item in items[:limit]:
        data = item.to_dict()
        distance = data.get("distance_m")
        distance_text = f"{distance}m" if distance is not None else "距离未知"
        when = data.get("starts_at") or data.get("expires_at") or "时间待确认"
        tags = ", ".join(data.get("fit_tags") or [])
        venue = data.get("venue") or data.get("address") or "地点待确认"
        lines.append(
            f"- {data.get('title')}｜{venue}｜{distance_text}｜{when}｜"
            f"tags={tags or data.get('category', 'general')}｜source={data.get('source_url')}"
        )
    return "\n".join(lines) + "\n\n"


def _build_decision_result(session_id: str, scenario_id: str, user_input: str, transcript: str, context: dict[str, Any]) -> dict[str, Any]:
    snapshot = context.get("psychological_snapshot") or {}
    stress = float(snapshot.get("stress_score") or 0)
    energy = float(snapshot.get("energy_score") or 5)
    pressure = float(snapshot.get("schedule_pressure_score") or 0)
    tasks = context.get("today_tasks") or []
    events = context.get("calendar_events") or []
    overloaded = stress >= 7 or pressure >= 7 or len(tasks) + len(events) >= 5
    recommended = "缩小学习任务 + 安排恢复窗口" if overloaded or energy <= 4 else "继续学习但降低强度"
    context_explanation = {
        "psychological": {
            "label": "心理状态",
            "summary": f"压力 {stress:g}/10，能量 {energy:g}/10；用于判断是否需要降低强度。",
            "impact": "压力高或能量低时，圆桌优先保护恢复边界。",
        },
        "schedule": {
            "label": "日程压力",
            "summary": f"压力信号 {len(context.get('schedule_pressure') or [])} 条，今日日程 {len(events)} 条。",
            "impact": "日程/压力越密集，越倾向拆小任务而不是追加承诺。",
        },
        "plan": {
            "label": "今日计划",
            "summary": f"今日任务 {len(tasks)} 条，Maxwell 工作台 {len(context.get('maxwell_workbench_items') or [])} 条。",
            "impact": "任务较多时，建议只保留最小可完成动作，并交给 Maxwell 生成待确认调整。",
        },
    }
    actions = [
        {"title": "先做 25 分钟低强度学习", "owner": "athena", "duration_minutes": 25},
        {"title": "插入 20 分钟恢复休息", "owner": "mira", "duration_minutes": 20},
        {"title": "由 Maxwell 生成待确认日程调整卡", "owner": "maxwell", "requires_confirmation": True},
    ]
    return {
        "id": f"rt_result_{session_id}",
        "session_id": session_id,
        "mode": "decision",
        "status": "draft",
        "summary": "圆桌建议先保护恢复边界，再保留一个可完成的最小学习动作；这不是心理诊断，也不会直接改动日程。",
        "options": [
            {"id": "continue_light", "title": "继续但降强度", "description": "只做最小学习块，避免把疲惫扩大成挫败感。"},
            {"id": "recover_first", "title": "先恢复再学习", "description": "先休息，再重新确认是否还有精力学习。"},
            {"id": "reschedule", "title": "改到明天", "description": "让 Maxwell 生成待确认调整，不直接修改日程。"},
        ],
        "recommended_option": recommended,
        "tradeoffs": [
            {"option": "继续但降强度", "pros": ["保留学习连续性"], "cons": ["仍会消耗精力"]},
            {"option": "先恢复再学习", "pros": ["降低过载风险"], "cons": ["今晚学习产出更少"]},
        ],
        "actions": actions,
        "handoff_target": "maxwell",
        "context": {**context, "user_input": user_input, "transcript_excerpt": transcript[-1200:], "scenario_id": scenario_id, "context_explanation": context_explanation},
    }


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
    roundtable_mode = _roundtable_mode_for_scenario(scenario.id)
    decision_context = await _prepare_decision_context() if roundtable_mode == "decision" else None
    context_prefix = (
        f"[当前生活状态: 压力{ctx.stress_level:.1f}/10, "
        f"日程密度{ctx.schedule_density:.1f}/10, "
        f"心情{ctx.mood_trend}]\n\n"
    )
    context_prefix += await _build_local_life_context_prefix(limit=5)
    if decision_context is not None:
        context_prefix += _build_decision_context_prefix(decision_context)
    roundtable_extra_context: dict[str, Any] = {}
    if req.user_input:
        roundtable_intent = plan_roundtable_intent(list(scenario.agents), req.user_input)
        document_context = await _resolve_roundtable_document_context(
            req.user_input,
            participants=list(scenario.agents),
            intent_decision=roundtable_intent,
        )
        intent_context = await _resolve_roundtable_intent_context(
            req.user_input,
            participants=list(scenario.agents),
            session_id=req.session_id,
            intent_decision=roundtable_intent,
        )
        context_prefix = _append_roundtable_document_context(context_prefix, document_context)
        context_prefix = _append_roundtable_intent_context(context_prefix, intent_context)
        if document_context.get("status") == "attached":
            roundtable_extra_context["document_context"] = document_context
        if intent_context.get("status") not in {"none", "document_read"}:
            roundtable_extra_context["intent_context"] = intent_context
        if decision_context is not None and roundtable_extra_context:
            decision_context = {**decision_context, **roundtable_extra_context}
    user_ask = req.user_input or "(用户未具体说明,请根据当前状态主动展开)"
    composed_message = (
        f"{profile_prefix}{context_prefix}{scenario.opening_prompt}\n\n用户诉求: {user_ask}"
    )

    # ── Work Brainstorm: LangGraph workshop with human checkpoints ──
    if scenario.agent_roster == "brainstorm":
        try:
            from app.jarvis.persistence import save_conversation

            await save_conversation(
                conversation_id=f"brainstorm:{req.session_id}",
                conversation_type="brainstorm",
                title=f"{scenario.name} · Brainstorm",
                scenario_id=scenario.id,
                session_id=req.session_id,
                route_payload={"mode": "roundtable", "scenario_id": scenario.id, "user_input": req.user_input, "mode_id": req.mode_id, "source_session_id": req.source_session_id, "source_agent_id": req.source_agent_id},
            )
        except Exception as exc:
            logger.warning("jarvis.roundtable.conversation_save_failed", session_id=req.session_id, error=str(exc))

        from app.jarvis.roundtable_sessions import add_turn_async, create_session_async

        session = await create_session_async(
            session_id=req.session_id,
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            participants=list(scenario.agents),
            agent_roster="brainstorm",
            mode="brainstorm",
            source_session_id=req.source_session_id,
            source_agent_id=req.source_agent_id,
            title=f"{scenario.name}：{req.user_input[:40]}" if req.user_input else scenario.name,
            user_prompt=req.user_input,
        )
        if req.user_input:
            await add_turn_async(session, "user", "You", req.user_input)
        session.round_count = 1

        return EventSourceResponse(
            _run_work_brainstorm_graph_round(
                llm_client=llm_client,
                session_id=req.session_id,
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                scenario_icon=scenario.icon,
                participants=list(scenario.agents),
                opening_prompt=scenario.opening_prompt,
                profile_prefix=profile_prefix,
                context_prefix=context_prefix,
                phase_label="open",
                mode="brainstorm",
                initial_user_input=req.user_input,
                decision_context=roundtable_extra_context or None,
            )
        )

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
            route_payload={"mode": "roundtable", "scenario_id": scenario.id, "user_input": req.user_input, "mode_id": req.mode_id, "source_session_id": req.source_session_id, "source_agent_id": req.source_agent_id},
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
        mode=roundtable_mode,
        source_session_id=req.source_session_id,
        source_agent_id=req.source_agent_id,
        title=f"{scenario.name}：{req.user_input[:40]}" if req.user_input else scenario.name,
        user_prompt=req.user_input,
    )
    # Seed the transcript with the user's initial request (if any)
    if req.user_input:
        await add_turn_async(session, "user", "You", req.user_input)
    session.round_count = 1

    return EventSourceResponse(
        _run_graph_or_legacy_round(
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
            mode=roundtable_mode,
            initial_user_input=req.user_input,
            decision_context=decision_context or roundtable_extra_context or None,
        )
    )


# ──────────────────────────────────────────────────────────────────────────
# Continue a roundtable with a user interjection
# ──────────────────────────────────────────────────────────────────────────



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
    context_prefix += await _build_local_life_context_prefix(limit=5)
    roundtable_intent = plan_roundtable_intent(session.participants, req.user_message)
    document_context = await _resolve_roundtable_document_context(
        req.user_message,
        participants=session.participants,
        intent_decision=roundtable_intent,
    )
    intent_context = await _resolve_roundtable_intent_context(
        req.user_message,
        participants=session.participants,
        session_id=req.session_id,
        intent_decision=roundtable_intent,
    )
    context_prefix = _append_roundtable_document_context(context_prefix, document_context)
    context_prefix = _append_roundtable_intent_context(context_prefix, intent_context)
    roundtable_mode = _roundtable_mode_for_scenario(session.scenario_id)
    round_context = await _prepare_decision_context() if roundtable_mode == "decision" else {}
    if document_context.get("status") == "attached":
        round_context = {**(round_context or {}), "document_context": document_context}
    if intent_context.get("status") not in {"none", "document_read"}:
        round_context = {**(round_context or {}), "intent_context": intent_context}

    return EventSourceResponse(
        _run_graph_or_legacy_round(
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
            mode=roundtable_mode,
            initial_user_input=req.user_message,
            decision_context=round_context or None,
        )
    )


async def get_roundtable_decision_result(session_id: str) -> dict[str, Any]:
    from app.jarvis.persistence import get_latest_roundtable_result

    result = await get_latest_roundtable_result(session_id, mode="decision")
    if result is None:
        raise HTTPException(status_code=404, detail=f"Decision result for session {session_id!r} not found")
    return result


def _public_brainstorm_result(result: dict[str, Any]) -> dict[str, Any]:
    context = result.get("context") if isinstance(result.get("context"), dict) else {}
    result_json = result.get("result_json") if isinstance(result.get("result_json"), dict) else {}
    return {
        **result,
        "themes": context.get("themes") if isinstance(context.get("themes"), list) else result.get("options", []),
        "ideas": context.get("ideas") if isinstance(context.get("ideas"), list) else [],
        "tensions": context.get("tensions") if isinstance(context.get("tensions"), list) else result.get("tradeoffs", []),
        "followup_questions": context.get("followup_questions") if isinstance(context.get("followup_questions"), list) else [],
        "c_artifacts": context.get("c_artifacts") if isinstance(context.get("c_artifacts"), dict) else result_json.get("c_artifacts"),
        "ranked_activities": context.get("ranked_activities") if isinstance(context.get("ranked_activities"), list) else result_json.get("ranked_activities", []),
        "risks": context.get("risks") if isinstance(context.get("risks"), list) else result_json.get("risks", []),
        "minimum_validation_steps": context.get("minimum_validation_steps") if isinstance(context.get("minimum_validation_steps"), list) else result_json.get("minimum_validation_steps", []),
        "save_as_memory": bool(context.get("save_as_memory")),
    }


async def get_roundtable_brainstorm_result(session_id: str) -> dict[str, Any]:
    from app.jarvis.persistence import get_latest_roundtable_result

    result = await get_latest_roundtable_result(session_id, mode="brainstorm")
    if result is None:
        raise HTTPException(status_code=404, detail=f"Brainstorm result for session {session_id!r} not found")
    return _public_brainstorm_result(result)


async def accept_roundtable_decision(session_id: str, req: RoundtableAcceptRequest) -> dict[str, Any]:
    from uuid import uuid4

    from app.jarvis.persistence import get_latest_roundtable_result, get_roundtable_result, save_pending_action, save_roundtable_result

    result = await get_roundtable_result(req.result_id) if req.result_id else await get_latest_roundtable_result(session_id, mode="decision")
    if result is None:
        raise HTTPException(status_code=404, detail=f"Decision result for session {session_id!r} not found")
    if result.get("mode") != "decision":
        raise HTTPException(status_code=400, detail="Only decision roundtable results can be accepted")
    pending_id = result.get("pending_action_id") or f"pending_roundtable_{uuid4().hex}"
    context = result.get("context") if isinstance(result.get("context"), dict) else {}
    pending = await save_pending_action(
        pending_id=pending_id,
        action_type="calendar.add",
        tool_name="calendar.add",
        agent_id=str(result.get("handoff_target") or "maxwell"),
        session_id=session_id,
        title=f"待确认：{result.get('recommended_option') or '圆桌日程调整'}",
        arguments={
            "title": "低强度学习 + 恢复休息",
            "start": context.get("suggested_start") or f"{context.get('date') or datetime.now().date().isoformat()}T20:00:00+08:00",
            "end": context.get("suggested_end") or f"{context.get('date') or datetime.now().date().isoformat()}T20:45:00+08:00",
            "stress_weight": 0.6,
            "notes": "由 Decision 圆桌接受后生成，仍需用户在待确认卡上最终确认；不会自动改日程。",
            "created_reason": f"用户接受圆桌建议：{result.get('recommended_option')}",
            "route_required": False,
            "roundtable_result_id": result.get("id"),
            "decision_actions": result.get("actions", []),
            "user_note": req.note,
        },
    )
    updated_result = await save_roundtable_result(
        result_id=str(result["id"]),
        session_id=session_id,
        mode="decision",
        status="accepted",
        summary=str(result.get("summary") or ""),
        options=result.get("options") if isinstance(result.get("options"), list) else [],
        recommended_option=str(result.get("recommended_option") or ""),
        tradeoffs=result.get("tradeoffs") if isinstance(result.get("tradeoffs"), list) else [],
        actions=result.get("actions") if isinstance(result.get("actions"), list) else [],
        handoff_target=str(result.get("handoff_target") or "maxwell"),
        context=context,
        pending_action_id=pending_id,
        user_choice="accepted",
        handoff_status="pending",
    )
    return {"result": updated_result, "pending_action": pending, "direct_calendar_mutation": False}


async def save_roundtable_brainstorm_memory(session_id: str, req: RoundtableSaveRequest) -> dict[str, Any]:
    from app.jarvis.persistence import get_latest_roundtable_result, get_roundtable_result, save_jarvis_memory, save_roundtable_result

    result = await get_roundtable_result(req.result_id) if req.result_id else await get_latest_roundtable_result(session_id, mode="brainstorm")
    if result is None:
        raise HTTPException(status_code=404, detail=f"Brainstorm result for session {session_id!r} not found")
    if result.get("mode") != "brainstorm":
        raise HTTPException(status_code=400, detail="Only brainstorm roundtable results can be saved as inspiration")
    public_result = _public_brainstorm_result(result)
    content = "\n".join([
        "Brainstorm 灵感保存",
        f"主题：{public_result.get('context', {}).get('topic', '')}" if isinstance(public_result.get("context"), dict) else "",
        f"总结：{public_result.get('summary', '')}",
        "想法：" + "；".join(str(item.get("title") or "") for item in public_result.get("ideas", [])[:6] if isinstance(item, dict)),
    ]).strip()
    memory = await save_jarvis_memory(
        memory_kind="brainstorm_inspiration",
        content=content,
        source_agent="brainstorm",
        session_id=session_id,
        source_text=req.note,
        structured_payload=public_result,
        sensitivity="normal",
        confidence=0.75,
        importance=0.7,
        memory_tier="raw",
        visibility="global",
    )
    context = result.get("context") if isinstance(result.get("context"), dict) else {}
    updated = await save_roundtable_result(
        result_id=str(result["id"]),
        session_id=session_id,
        mode="brainstorm",
        status="saved",
        summary=str(result.get("summary") or ""),
        options=result.get("options") if isinstance(result.get("options"), list) else [],
        recommended_option=str(result.get("recommended_option") or ""),
        tradeoffs=result.get("tradeoffs") if isinstance(result.get("tradeoffs"), list) else [],
        actions=result.get("actions") if isinstance(result.get("actions"), list) else [],
        handoff_target=str(result.get("handoff_target") or "maxwell"),
        context={**context, "save_as_memory": True, "memory_id": memory.get("id")},
        user_choice="save_as_memory",
        handoff_status="saved_memory",
    )
    return {"result": _public_brainstorm_result(updated), "memory": memory, "direct_calendar_mutation": False, "direct_plan_mutation": False}


async def convert_roundtable_brainstorm_to_plan(session_id: str, req: RoundtablePlanRequest) -> dict[str, Any]:
    from uuid import uuid4

    from app.jarvis.persistence import get_latest_roundtable_result, get_roundtable_result, save_pending_action, save_roundtable_result

    result = await get_roundtable_result(req.result_id) if req.result_id else await get_latest_roundtable_result(session_id, mode="brainstorm")
    if result is None:
        raise HTTPException(status_code=404, detail=f"Brainstorm result for session {session_id!r} not found")
    if result.get("mode") != "brainstorm":
        raise HTTPException(status_code=400, detail="Only brainstorm results can be converted to a Maxwell plan")
    public_result = _public_brainstorm_result(result)
    pending_id = result.get("pending_action_id") or f"pending_brainstorm_{uuid4().hex}"
    topic = public_result.get("context", {}).get("topic", "Brainstorm 转计划") if isinstance(public_result.get("context"), dict) else "Brainstorm 转计划"
    pending = await save_pending_action(
        pending_id=pending_id,
        action_type="task.plan",
        tool_name="maxwell.plan_from_brainstorm",
        agent_id="maxwell",
        session_id=session_id,
        title=f"待确认：将 Brainstorm 转成计划 - {str(topic)[:40]}",
        arguments={
            "plan": {
                "id": f"brainstorm_plan_{uuid4().hex}",
                "title": str(topic)[:80] or "Brainstorm 转计划",
                "type": "brainstorm_followup",
                "source_agent": "maxwell",
                "original_user_request": str(topic),
                "goal": "把已选择的 brainstorm 灵感转成可执行计划。",
                "time_horizon": {"type": "user_confirmed_later"},
                "milestones": [],
                "subtasks": [
                    {"title": str(item.get("title") or "待细化想法"), "source": item.get("source_agent")}
                    for item in public_result.get("ideas", [])[:6]
                    if isinstance(item, dict)
                ],
                "calendar_candidates": [],
                "daily_plan": [],
            },
            "roundtable_result_id": result.get("id"),
            "brainstorm_result": public_result,
            "user_note": req.note,
        },
    )
    context = result.get("context") if isinstance(result.get("context"), dict) else {}
    updated = await save_roundtable_result(
        result_id=str(result["id"]),
        session_id=session_id,
        mode="brainstorm",
        status="handoff_pending",
        summary=str(result.get("summary") or ""),
        options=result.get("options") if isinstance(result.get("options"), list) else [],
        recommended_option=str(result.get("recommended_option") or ""),
        tradeoffs=result.get("tradeoffs") if isinstance(result.get("tradeoffs"), list) else [],
        actions=result.get("actions") if isinstance(result.get("actions"), list) else [],
        handoff_target="maxwell",
        context=context,
        pending_action_id=pending_id,
        user_choice="convert_to_plan",
        handoff_status="pending",
    )
    return {"result": _public_brainstorm_result(updated), "pending_action": pending, "direct_calendar_mutation": False, "direct_plan_mutation": False}


async def return_roundtable_to_private_chat(session_id: str, req: RoundtableReturnRequest) -> dict[str, Any]:
    from app.jarvis.persistence import (
        get_latest_roundtable_result,
        get_roundtable_result,
        get_roundtable_session,
        get_session_turns,
        save_chat_turn,
        save_roundtable_result,
        save_session,
    )

    session_record = await get_roundtable_session(session_id)
    if session_record is None:
        raise HTTPException(status_code=404, detail=f"Roundtable session {session_id!r} not found")
    result = await get_roundtable_result(req.result_id) if req.result_id else await get_latest_roundtable_result(session_id)
    source_session_id = session_record.get("source_session_id") or (result or {}).get("source_session_id")
    source_agent_id = session_record.get("source_agent_id") or (result or {}).get("source_agent_id") or "alfred"
    if not source_session_id:
        raise HTTPException(status_code=400, detail="This roundtable has no source private chat session to return to")

    turns = await get_session_turns(session_id)
    recent_points = [f"- {item.get('speaker_name')}: {str(item.get('content') or '').strip()}" for item in turns[-6:] if str(item.get("content") or "").strip()]
    summary = str((result or {}).get("summary") or "").strip()
    if not summary:
        summary = "圆桌已结束：" + ("\n" + "\n".join(recent_points) if recent_points else "已回到原私聊继续处理。")
    return_note = (
        f"圆桌讨论总结\n\n{summary}\n\n"
        f"用户选择：{req.user_choice or '回到原私聊继续'}"
        + (f"\n补充说明：{req.note}" if req.note else "")
    )
    actions = [{
        "type": "roundtable.return_summary",
        "title": "圆桌讨论已带回私聊",
        "description": summary,
        "arguments": {
            "roundtable_session_id": session_id,
            "roundtable_result_id": (result or {}).get("id"),
            "source_session_id": source_session_id,
            "user_choice": req.user_choice,
        },
    }]
    turn_id = await save_chat_turn(
        agent_id=str(source_agent_id),
        role="agent",
        content=return_note,
        actions=actions,
        session_id=str(source_session_id),
    )
    updated_result = None
    if result is not None:
        context = result.get("context") if isinstance(result.get("context"), dict) else {}
        updated_result = await save_roundtable_result(
            result_id=str(result["id"]),
            session_id=session_id,
            mode=str(result.get("mode") or "decision"),
            status="returned",
            summary=str(result.get("summary") or summary),
            options=result.get("options") if isinstance(result.get("options"), list) else [],
            recommended_option=str(result.get("recommended_option") or ""),
            tradeoffs=result.get("tradeoffs") if isinstance(result.get("tradeoffs"), list) else [],
            actions=result.get("actions") if isinstance(result.get("actions"), list) else [],
            handoff_target=str(result.get("handoff_target") or source_agent_id or "alfred"),
            context={**context, "returned_to_session_id": source_session_id, "return_turn_id": turn_id},
            source_session_id=str(source_session_id),
            source_agent_id=str(source_agent_id),
            pending_action_id=result.get("pending_action_id"),
            result_json=result.get("result_json") if isinstance(result.get("result_json"), dict) else None,
            user_choice=req.user_choice or result.get("user_choice") or "return_to_private_chat",
            handoff_status="returned",
        )
    await save_session(
        session_id=session_id,
        scenario_id=str(session_record.get("scenario_id") or "roundtable"),
        scenario_name=str(session_record.get("scenario_name") or "Roundtable"),
        participants=session_record.get("participants") if isinstance(session_record.get("participants"), list) else [],
        agent_roster=str(session_record.get("agent_roster") or "jarvis"),
        round_count=int(session_record.get("round_count") or 0),
        title=str(session_record.get("title") or session_record.get("scenario_name") or "Roundtable"),
        user_prompt=str(session_record.get("user_prompt") or ""),
        mode=str(session_record.get("mode") or "decision"),
        source_session_id=str(source_session_id),
        source_agent_id=str(source_agent_id),
        status="returned",
    )
    return {
        "source_session_id": source_session_id,
        "source_agent_id": source_agent_id,
        "return_turn_id": turn_id,
        "summary": return_note,
        "result": updated_result,
    }


def _is_schedule_coord_finalize_request(message: str) -> bool:
    normalized = message.strip().lower()
    return normalized in {"/finalize", "finalize", "收敛", "直接收敛", "直接结论", "给我结论", "生成结论"}


def _graph_roundtable_scenario_id(scenario_id: str) -> str | None:
    return scenario_id if scenario_id in {"schedule_coord", "local_lifestyle", "emotional_care", "study_energy_decision", "weekend_recharge", "work_brainstorm"} else None


def _build_graph_round_context(
    *,
    session,
    decision_context: dict[str, Any] | None,
    context_prefix: str,
    opening_prompt: str,
    profile_prefix: str,
    scenario_name: str,
    scenario_icon: str,
) -> dict[str, Any]:
    previous_discussion = session.format_for_prompt(max_chars=6000) if session else ""
    return {
        **(decision_context or {}),
        "context_prefix": context_prefix,
        "opening_prompt": opening_prompt,
        "profile_prefix_present": bool(profile_prefix),
        "scenario_name": scenario_name,
        "scenario_icon": scenario_icon,
        "previous_discussion": previous_discussion,
    }


async def _run_graph_or_legacy_round(**kwargs):
    graph_scenario_id = _graph_roundtable_scenario_id(str(kwargs.get("scenario_id") or ""))
    if graph_scenario_id == "schedule_coord":
        async for event in _run_schedule_coord_graph_round(**kwargs):
            yield event
        return
    if graph_scenario_id == "study_energy_decision":
        async for event in _run_study_energy_decision_graph_round(**kwargs):
            yield event
        return
    if graph_scenario_id == "local_lifestyle":
        async for event in _run_local_lifestyle_graph_round(**kwargs):
            yield event
        return
    if graph_scenario_id == "emotional_care":
        async for event in _run_emotional_care_graph_round(**kwargs):
            yield event
        return
    if graph_scenario_id == "weekend_recharge":
        async for event in _run_weekend_recharge_graph_round(**kwargs):
            yield event
        return
    if graph_scenario_id == "work_brainstorm":
        async for event in _run_work_brainstorm_graph_round(**kwargs):
            yield event
        return
    async for event in _run_roundtable_round(**kwargs):
        yield event


async def _run_decision_graph_round(
    *,
    executor,
    graph_scenario_id: str,
    graph_strategy: str,
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
    mode: str = "decision",
    initial_user_input: str = "",
    decision_context: dict[str, Any] | None = None,
):
    from app.jarvis.persistence import save_roundtable_result
    from app.jarvis.roundtable_sessions import add_turn_async, get_session

    timing_started = time.perf_counter()
    session = get_session(session_id)
    feedback_history = [
        turn.content
        for turn in (session.transcript if session else [])
        if turn.role == "user" and turn.content.strip()
    ]
    original_goal = feedback_history[0] if feedback_history else (initial_user_input or "")
    context = _build_graph_round_context(
        session=session,
        decision_context=decision_context,
        context_prefix=context_prefix,
        opening_prompt=opening_prompt,
        profile_prefix=profile_prefix,
        scenario_name=scenario_name,
        scenario_icon=scenario_icon,
    )

    yield {
        "event": "phase_change",
        "data": json.dumps(
            {
                "phase": phase_label,
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "participants": participants,
                "session_id": session_id,
                "round_count": session.round_count if session else 1,
                "mode": mode,
            },
            ensure_ascii=False,
        ),
    }

    if phase_label == "user_turn" and _is_schedule_coord_finalize_request(initial_user_input):
        event_iter = executor.finalize(
            session_id=session_id,
            user_goal=original_goal,
            context=context,
            feedback_history=feedback_history,
        )
    elif phase_label == "user_turn":
        event_iter = executor.continue_round(
            session_id=session_id,
            user_goal=original_goal,
            context=context,
            feedback_history=feedback_history,
            round_index=session.round_count if session else 1,
            participants=participants,
        )
    else:
        event_iter = executor.start_round(
            session_id=session_id,
            user_goal=original_goal,
            context=context,
            round_index=session.round_count if session else 1,
            feedback_history=feedback_history[1:],
            participants=participants,
        )

    done_event: dict[str, str] | None = None
    async for event in event_iter:
        if event.get("event") == "done":
            done_event = event
            continue
        if event.get("event") == "role_completed" and session is not None:
            payload = json.loads(event.get("data") or "{}")
            agent_id = str(payload.get("agent_id") or "")
            agent = JARVIS_AGENTS.get(agent_id)
            content = str(payload.get("content") or "").strip()
            if agent_id and content:
                await add_turn_async(
                    session,
                    agent_id,
                    f"{payload.get('agent_name') or agent_id}（{payload.get('agent_role') or (agent or {}).get('role') or '专家'}）",
                    content,
                )
        elif event.get("event") == "decision_result":
            payload = json.loads(event.get("data") or "{}")
            saved_result = await save_roundtable_result(
                result_id=str(payload["id"]),
                session_id=session_id,
                mode="decision",
                status=str(payload.get("status") or "draft"),
                summary=str(payload.get("summary") or ""),
                options=payload.get("options") if isinstance(payload.get("options"), list) else [],
                recommended_option=str(payload.get("recommended_option") or ""),
                tradeoffs=payload.get("tradeoffs") if isinstance(payload.get("tradeoffs"), list) else [],
                actions=payload.get("actions") if isinstance(payload.get("actions"), list) else [],
                handoff_target=str(payload.get("handoff_target") or "maxwell"),
                context=payload.get("context") if isinstance(payload.get("context"), dict) else {},
                result_json=payload,
            )
            event = {"event": "decision_result", "data": json.dumps(jsonable_encoder(saved_result), ensure_ascii=False)}
        yield event

    yield {
        "event": "roundtable_timing",
        "data": json.dumps(
            {
                "total_ms": round((time.perf_counter() - timing_started) * 1000, 1),
                "spans": [{"name": f"{graph_scenario_id}_graph_round", "ms": round((time.perf_counter() - timing_started) * 1000, 1)}],
                "mode": "decision",
                "strategy": graph_strategy,
            },
            ensure_ascii=False,
        ),
    }
    if done_event is not None:
        yield done_event


async def _run_schedule_coord_graph_round(
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
    mode: str = "decision",
    initial_user_input: str = "",
    decision_context: dict[str, Any] | None = None,
):
    from app.jarvis.schedule_coord_graph import ScheduleCoordGraphExecutor

    async for event in _run_decision_graph_round(
        executor=ScheduleCoordGraphExecutor(llm_client=llm_client),
        graph_scenario_id="schedule_coord",
        graph_strategy="langgraph_schedule_coord_v1",
        llm_client=llm_client,
        session_id=session_id,
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        scenario_icon=scenario_icon,
        participants=participants,
        opening_prompt=opening_prompt,
        profile_prefix=profile_prefix,
        context_prefix=context_prefix,
        phase_label=phase_label,
        mode=mode,
        initial_user_input=initial_user_input,
        decision_context=decision_context,
    ):
        yield event


async def _run_study_energy_decision_graph_round(
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
    mode: str = "decision",
    initial_user_input: str = "",
    decision_context: dict[str, Any] | None = None,
):
    from app.jarvis.study_energy_decision_graph import StudyEnergyDecisionGraphExecutor

    async for event in _run_decision_graph_round(
        executor=StudyEnergyDecisionGraphExecutor(llm_client=llm_client),
        graph_scenario_id="study_energy_decision",
        graph_strategy="langgraph_study_energy_decision_v1",
        llm_client=llm_client,
        session_id=session_id,
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        scenario_icon=scenario_icon,
        participants=participants,
        opening_prompt=opening_prompt,
        profile_prefix=profile_prefix,
        context_prefix=context_prefix,
        phase_label=phase_label,
        mode=mode,
        initial_user_input=initial_user_input,
        decision_context=decision_context,
    ):
        yield event


async def _run_brainstorm_graph_round(
    *,
    executor,
    graph_scenario_id: str,
    graph_strategy: str,
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
    mode: str = "brainstorm",
    initial_user_input: str = "",
    decision_context: dict[str, Any] | None = None,
):
    from app.jarvis.persistence import save_roundtable_result
    from app.jarvis.roundtable_sessions import add_turn_async, get_session

    timing_started = time.perf_counter()
    session = get_session(session_id)
    feedback_history = [
        turn.content
        for turn in (session.transcript if session else [])
        if turn.role == "user" and turn.content.strip()
    ]
    original_goal = feedback_history[0] if feedback_history else (initial_user_input or "")
    context = _build_graph_round_context(
        session=session,
        decision_context=decision_context,
        context_prefix=context_prefix,
        opening_prompt=opening_prompt,
        profile_prefix=profile_prefix,
        scenario_name=scenario_name,
        scenario_icon=scenario_icon,
    )

    yield {
        "event": "phase_change",
        "data": json.dumps(
            {
                "phase": phase_label,
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "participants": participants,
                "session_id": session_id,
                "round_count": session.round_count if session else 1,
                "mode": "brainstorm",
            },
            ensure_ascii=False,
        ),
    }

    if phase_label == "user_turn" and _is_schedule_coord_finalize_request(initial_user_input):
        event_iter = executor.finalize(
            session_id=session_id,
            user_goal=original_goal,
            context=context,
            feedback_history=feedback_history,
        )
    elif phase_label == "user_turn":
        event_iter = executor.continue_round(
            session_id=session_id,
            user_goal=original_goal,
            context=context,
            feedback_history=feedback_history,
            round_index=session.round_count if session else 1,
            participants=participants,
        )
    else:
        event_iter = executor.start_round(
            session_id=session_id,
            user_goal=original_goal,
            context=context,
            round_index=session.round_count if session else 1,
            feedback_history=feedback_history[1:],
            participants=participants,
        )

    done_event: dict[str, str] | None = None
    async for event in event_iter:
        if event.get("event") == "done":
            done_event = event
            continue
        if event.get("event") == "role_completed" and session is not None:
            payload = json.loads(event.get("data") or "{}")
            agent_id = str(payload.get("agent_id") or "")
            agent = JARVIS_AGENTS.get(agent_id)
            content = str(payload.get("content") or "").strip()
            if agent_id and content:
                await add_turn_async(
                    session,
                    agent_id,
                    f"{payload.get('agent_name') or agent_id}（{payload.get('agent_role') or (agent or {}).get('role') or '专家'}）",
                    content,
                )
        elif event.get("event") == "brainstorm_result":
            payload = json.loads(event.get("data") or "{}")
            context_payload = payload.get("context") if isinstance(payload.get("context"), dict) else {}
            saved_result = await save_roundtable_result(
                result_id=str(payload["id"]),
                session_id=session_id,
                mode="brainstorm",
                status=str(payload.get("status") or "draft"),
                summary=str(payload.get("summary") or ""),
                options=payload.get("themes") if isinstance(payload.get("themes"), list) else [],
                recommended_option="",
                tradeoffs=payload.get("tensions") if isinstance(payload.get("tensions"), list) else [],
                actions=[
                    {"type": "save_as_memory", "enabled": False},
                    {"type": "handoff_to_maxwell", "enabled": False},
                ],
                handoff_target=str(payload.get("handoff_target") or "maxwell"),
                context=context_payload,
                result_json=payload,
            )
            event = {"event": "brainstorm_result", "data": json.dumps(jsonable_encoder(_public_brainstorm_result(saved_result)), ensure_ascii=False)}
        yield event

    yield {
        "event": "roundtable_timing",
        "data": json.dumps(
            {
                "total_ms": round((time.perf_counter() - timing_started) * 1000, 1),
                "spans": [{"name": f"{graph_scenario_id}_graph_round", "ms": round((time.perf_counter() - timing_started) * 1000, 1)}],
                "mode": "brainstorm",
                "strategy": graph_strategy,
            },
            ensure_ascii=False,
        ),
    }
    if done_event is not None:
        yield done_event


async def _run_local_lifestyle_graph_round(
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
    mode: str = "brainstorm",
    initial_user_input: str = "",
    decision_context: dict[str, Any] | None = None,
):
    from app.jarvis.local_lifestyle_graph import LocalLifestyleGraphExecutor

    async for event in _run_brainstorm_graph_round(
        executor=LocalLifestyleGraphExecutor(llm_client=llm_client),
        graph_scenario_id="local_lifestyle",
        graph_strategy="langgraph_local_lifestyle_v1",
        llm_client=llm_client,
        session_id=session_id,
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        scenario_icon=scenario_icon,
        participants=participants,
        opening_prompt=opening_prompt,
        profile_prefix=profile_prefix,
        context_prefix=context_prefix,
        phase_label=phase_label,
        mode=mode,
        initial_user_input=initial_user_input,
        decision_context=decision_context,
    ):
        yield event


async def _run_emotional_care_graph_round(
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
    mode: str = "brainstorm",
    initial_user_input: str = "",
    decision_context: dict[str, Any] | None = None,
):
    from app.jarvis.emotional_care_graph import EmotionalCareGraphExecutor

    async for event in _run_brainstorm_graph_round(
        executor=EmotionalCareGraphExecutor(llm_client=llm_client),
        graph_scenario_id="emotional_care",
        graph_strategy="langgraph_emotional_care_v1",
        llm_client=llm_client,
        session_id=session_id,
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        scenario_icon=scenario_icon,
        participants=participants,
        opening_prompt=opening_prompt,
        profile_prefix=profile_prefix,
        context_prefix=context_prefix,
        phase_label=phase_label,
        mode=mode,
        initial_user_input=initial_user_input,
        decision_context=decision_context,
    ):
        yield event


async def _run_weekend_recharge_graph_round(
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
    mode: str = "brainstorm",
    initial_user_input: str = "",
    decision_context: dict[str, Any] | None = None,
):
    from app.jarvis.weekend_recharge_graph import WeekendRechargeGraphExecutor

    async for event in _run_brainstorm_graph_round(
        executor=WeekendRechargeGraphExecutor(llm_client=llm_client),
        graph_scenario_id="weekend_recharge",
        graph_strategy="langgraph_weekend_recharge_v1",
        llm_client=llm_client,
        session_id=session_id,
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        scenario_icon=scenario_icon,
        participants=participants,
        opening_prompt=opening_prompt,
        profile_prefix=profile_prefix,
        context_prefix=context_prefix,
        phase_label=phase_label,
        mode=mode,
        initial_user_input=initial_user_input,
        decision_context=decision_context,
    ):
        yield event


async def _run_work_brainstorm_graph_round(
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
    mode: str = "brainstorm",
    initial_user_input: str = "",
    decision_context: dict[str, Any] | None = None,
):
    from app.jarvis.work_brainstorm_graph import WorkBrainstormGraphExecutor

    async for event in _run_brainstorm_graph_round(
        executor=WorkBrainstormGraphExecutor(llm_client=llm_client),
        graph_scenario_id="work_brainstorm",
        graph_strategy="langgraph_work_brainstorm_v1",
        llm_client=llm_client,
        session_id=session_id,
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        scenario_icon=scenario_icon,
        participants=participants,
        opening_prompt=opening_prompt,
        profile_prefix=profile_prefix,
        context_prefix=context_prefix,
        phase_label=phase_label,
        mode=mode,
        initial_user_input=initial_user_input,
        decision_context=decision_context,
    ):
        yield event


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
    mode: str = "brainstorm",
    initial_user_input: str = "",
    decision_context: dict[str, Any] | None = None,
):
    """Shared generator for both /start and /continue.

    Emits phase_change, then for each participant: agent_speak + token, then done.
    """
    from app.jarvis.roundtable_sessions import get_session

    timing_started = time.perf_counter()
    timing_spans: list[dict[str, Any]] = []

    def mark_round_span(name: str, started: float, **extra: Any) -> None:
        timing_spans.append({"name": name, "ms": round((time.perf_counter() - started) * 1000, 1), **extra})

    context_prepare_started = time.perf_counter()
    session = get_session(session_id)
    mark_round_span("context_prepare", context_prepare_started, mode=mode, participants=len(participants))

    yield {
        "event": "phase_change",
        "data": json.dumps({
            "phase": phase_label,
            "scenario_id": scenario_id,
            "scenario_name": scenario_name,
            "participants": participants,
            "session_id": session_id,
            "round_count": session.round_count if session else 1,
            "mode": mode,
        }),
    }

    for agent_id in participants:
        agent_started = time.perf_counter()
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
                "progress": {"current": len(timing_spans), "total": len(participants), "status": "speaking"},
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
        if mode == "decision":
            prompt += (
                "\n\n## Decision 规则\n"
                "讨论阶段默认不要调用工具；只给判断依据、取舍和建议。"
                "不要做心理诊断，不要直接承诺修改日程。最终接受后由 Maxwell 生成待确认动作。"
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
            yield {
                "event": "agent_degraded",
                "data": json.dumps({
                    "phase": "degraded",
                    "agent_id": agent_id,
                    "agent_name": agent["name"],
                    "session_id": session_id,
                    "error": error_text[:240],
                    "fallback_content": content,
                    "continue_next_agent": True,
                    "progress": {"current": len(timing_spans) + 1, "total": len(participants), "status": "degraded"},
                }, ensure_ascii=False),
            }


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
                "progress": {"current": len(timing_spans) + 1, "total": len(participants), "status": "completed"},
            }),
        }
        mark_round_span("agent_turn", agent_id=agent_id, started=agent_started, chars=len(content))

    if mode == "decision":
        from app.jarvis.persistence import save_roundtable_result

        result_persist_started = time.perf_counter()
        transcript_text = session.format_for_prompt(max_chars=5000) if session else ""
        result_payload = _build_decision_result(
            session_id=session_id,
            scenario_id=scenario_id,
            user_input=initial_user_input,
            transcript=transcript_text,
            context=decision_context or {},
        )
        saved_result = await save_roundtable_result(
            result_id=result_payload["id"],
            session_id=session_id,
            mode="decision",
            status="draft",
            summary=result_payload["summary"],
            options=result_payload["options"],
            recommended_option=result_payload["recommended_option"],
            tradeoffs=result_payload["tradeoffs"],
            actions=result_payload["actions"],
            handoff_target=result_payload["handoff_target"],
            context=result_payload["context"],
        )
        yield {
            "event": "decision_result",
            "data": json.dumps(jsonable_encoder(saved_result), ensure_ascii=False),
        }
        mark_round_span("result_persist", result_persist_started, result_type="decision")

    yield {
        "event": "roundtable_timing",
        "data": json.dumps({
            "total_ms": round((time.perf_counter() - timing_started) * 1000, 1),
            "spans": timing_spans,
            "mode": mode,
            "strategy": "sequential_agent_turns",
        }, ensure_ascii=False),
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
