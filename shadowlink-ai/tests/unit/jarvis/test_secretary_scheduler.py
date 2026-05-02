import pytest

from app.jarvis.secretary_scheduler import (
    parse_secretary_long_plan_response,
    parse_secretary_reschedule_response,
    parse_secretary_schedule_response,
)


def test_parse_secretary_schedule_response_accepts_valid_short_schedule():
    raw = """
    {
      "schema_version": "secretary_schedule.v1",
      "intent": "short_schedule",
      "summary": "明晚安排一次雅思听力复习。",
      "items": [
        {
          "client_item_id": "item-1",
          "date": "2026-05-02",
          "start_time": "19:30",
          "end_time": "21:00",
          "title": "雅思听力复习",
          "description": "完成 Section 1-2 并整理错题。",
          "estimated_minutes": 90,
          "priority": "high",
          "reason": "用户指定明晚。"
        }
      ]
    }
    """

    parsed = parse_secretary_schedule_response(raw)

    assert parsed["schema_version"] == "secretary_schedule.v1"
    assert parsed["items"][0]["date"] == "2026-05-02"
    assert parsed["items"][0]["title"] == "雅思听力复习"


def test_parse_secretary_long_plan_response_accepts_valid_long_plan():
    raw = """
    {
      "schema_version": "secretary_long_plan.v1",
      "intent": "long_plan",
      "plan": {
        "title": "雅思 30 天备考计划",
        "goal": "30 天内完成基础训练",
        "plan_type": "long_term",
        "start_date": "2026-05-01",
        "target_date": "2026-05-30"
      },
      "days": [
        {
          "day_index": 1,
          "date": "2026-05-01",
          "start_time": "19:30",
          "end_time": "21:00",
          "title": "雅思听力诊断",
          "description": "完成一套诊断。",
          "estimated_minutes": 90,
          "reason": "第一天建立基线。"
        }
      ]
    }
    """

    parsed = parse_secretary_long_plan_response(raw)

    assert parsed["schema_version"] == "secretary_long_plan.v1"
    assert parsed["plan"]["title"] == "雅思 30 天备考计划"
    assert parsed["days"][0]["day_index"] == 1


def test_parse_secretary_reschedule_response_accepts_valid_reschedule():
    raw = """
    {
      "schema_version": "secretary_reschedule.v1",
      "intent": "reschedule_plan",
      "summary": "已从明天开始重新安排。",
      "plan_id": "plan-ielts-30d",
      "days": [
        {
          "id": "day-001",
          "date": "2026-05-02",
          "start_time": "19:30",
          "end_time": "21:00",
          "title": "雅思听力训练",
          "description": "继续完成听力训练。",
          "estimated_minutes": 90,
          "reason": "用户今日未完成。"
        }
      ]
    }
    """

    parsed = parse_secretary_reschedule_response(raw)

    assert parsed["schema_version"] == "secretary_reschedule.v1"
    assert parsed["plan_id"] == "plan-ielts-30d"
    assert parsed["days"][0]["id"] == "day-001"


@pytest.mark.parametrize(
    "parser,raw",
    [
        (parse_secretary_schedule_response, "not json"),
        (parse_secretary_schedule_response, '{"schema_version":"secretary_long_plan.v1","items":[]}'),
        (parse_secretary_long_plan_response, '{"schema_version":"secretary_long_plan.v1","plan":{},"days":[]}'),
        (parse_secretary_reschedule_response, '{"schema_version":"secretary_reschedule.v1","plan_id":"p","days":[{"id":"d","date":"2026-05-02"}]}'),
    ],
)
def test_secretary_parser_rejects_invalid_payloads(parser, raw):
    with pytest.raises(ValueError):
        parser(raw)


def test_secretary_parser_rejects_markdown_wrapped_json():
    raw = """```json
    {"schema_version":"secretary_schedule.v1","intent":"short_schedule","summary":"ok","items":[]}
    ```"""

    with pytest.raises(ValueError, match="strict JSON"):
        parse_secretary_schedule_response(raw)
