from datetime import datetime

from app.jarvis.intent_router import plan_agent_intent


NOW = datetime(2026, 4, 30, 10, 0, 0)


def test_maxwell_complete_calendar_create_extracts_slots():
    decision = plan_agent_intent("maxwell", "明天下午 3 点提醒我复习英语 1 小时", local_now=NOW)

    assert decision.intent == "calendar_create"
    assert decision.tool_name == "jarvis_calendar_add"
    assert decision.next_action == "pending_confirmation"
    assert decision.slots["title"] == "复习英语"
    assert decision.slots["start"].startswith("2026-05-01T15:00:00")
    assert decision.slots["end"].startswith("2026-05-01T16:00:00")
    assert decision.missing_slots == []


def test_maxwell_calendar_create_missing_time_asks_slots():
    decision = plan_agent_intent("maxwell", "帮我安排复习英语", local_now=NOW)

    assert decision.intent == "calendar_create"
    assert decision.tool_name == "jarvis_calendar_add"
    assert decision.next_action == "ask_missing_slots"
    assert "start" in decision.missing_slots
    assert "end" in decision.missing_slots


def test_maxwell_long_term_study_plan_decomposes_task():
    decision = plan_agent_intent("maxwell", "我想一个月内准备完雅思第一轮", local_now=NOW)

    assert decision.intent == "task_decompose"
    assert decision.tool_name == "jarvis_task_plan_decompose"
    assert decision.next_action == "call_tool"
    assert decision.slots["user_request"] == "我想一个月内准备完雅思第一轮"


def test_athena_learning_strategy_decomposes_study_goal():
    decision = plan_agent_intent("athena", "我想一个月内准备完雅思第一轮，应该怎么复习？", local_now=NOW)

    assert decision.intent == "learning_plan"
    assert decision.tool_name == "jarvis_task_plan_decompose"
    assert decision.next_action == "call_tool"
    assert decision.slots["source_agent"] == "athena"
    assert "雅思" in decision.slots["user_request"]


def test_athena_deadline_pressure_checks_learning_goal():
    decision = plan_agent_intent("athena", "下周考试，现在复习还来得及吗？", local_now=NOW)

    assert decision.intent == "learning_deadline_check"
    assert decision.tool_name == "jarvis_deadline_check"
    assert decision.next_action == "call_tool"
    assert decision.slots["source_agent"] == "athena"


def test_nora_meal_plan_extracts_dinner_and_recovery_goal():
    decision = plan_agent_intent("nora", "今晚很累，吃什么比较撑得住？", local_now=NOW)

    assert decision.intent == "meal_plan"
    assert decision.tool_name == "jarvis_meal_plan"
    assert decision.next_action == "call_tool"
    assert decision.slots["meals"] == ["dinner"]
    assert decision.slots["goal"] == "stress_recovery"


def test_nora_caffeine_guard_defaults_to_coffee():
    decision = plan_agent_intent("nora", "咖啡现在还能喝吗？", local_now=NOW)

    assert decision.intent == "caffeine_guard"
    assert decision.tool_name == "jarvis_caffeine_cutoff_guard"
    assert decision.next_action == "call_tool"
    assert decision.slots["beverage_name"] == "coffee"


def test_nora_nutrition_lookup_missing_food_name_asks():
    decision = plan_agent_intent("nora", "帮我查一下这个营养怎么样", local_now=NOW)

    assert decision.intent == "nutrition_lookup"
    assert decision.next_action == "ask_missing_slots"
    assert decision.missing_slots == ["food_name"]


def test_mira_anxiety_maps_to_breathing_protocol():
    decision = plan_agent_intent("mira", "我焦虑得有点喘不过气", local_now=NOW)

    assert decision.intent == "breathing_protocol"
    assert decision.tool_name == "jarvis_breathing_protocol"
    assert decision.next_action == "call_tool"
    assert decision.slots["goal"] == "calm_down"


def test_mira_checkin_schedule_extracts_tomorrow_delay():
    decision = plan_agent_intent("mira", "明天回访一下我的状态", local_now=NOW)

    assert decision.intent == "checkin_schedule"
    assert decision.tool_name == "jarvis_checkin_schedule"
    assert decision.next_action == "pending_confirmation"
    assert decision.slots["delay_hours"] == 24


def test_leo_weekend_activity_maps_to_local_activities():
    decision = plan_agent_intent("leo", "周末有什么低负担活动推荐？", local_now=NOW)

    assert decision.intent == "local_activities"
    assert decision.tool_name == "jarvis_local_activities"
    assert decision.next_action == "call_tool"


def test_leo_plan_activity_slot_missing_time_asks():
    decision = plan_agent_intent("leo", "把散步安排进日程", local_now=NOW)

    assert decision.intent == "plan_activity_slot"
    assert decision.tool_name == "jarvis_plan_activity_slot"
    assert decision.next_action == "ask_missing_slots"
    assert "start" in decision.missing_slots


def test_tool_outside_agent_whitelist_is_not_planned():
    decision = plan_agent_intent("mira", "今晚吃什么比较好？", local_now=NOW)

    assert decision.intent == "chat_only"
    assert decision.tool_name is None


def test_small_talk_is_chat_only():
    decision = plan_agent_intent("nora", "你好呀，今天还不错", local_now=NOW)

    assert decision.intent == "chat_only"
    assert decision.next_action == "chat_only"
