# Private Chat Collaboration Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Maxwell-only private-chat handoff with unified background specialist consultation while keeping the current private-chat agent as the visible responder.

**Architecture:** Extend `app.jarvis.agent_consultation` with deterministic automatic intent-to-consult routing, preserving explicit "ask this agent" parsing. Update `chat_with_agent()` so `req.agent_id` remains the primary agent, schedule/task intent becomes a Maxwell consultation, and consultation actions are used for persistence/prompting without rendering as a visible main-chat card.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic, pytest, pytest-asyncio, existing Jarvis persistence and private chat pipeline.

---

## File Structure

- Modify `shadowlink-ai/app/jarvis/agent_consultation.py`
  - Add intent metadata to consultation edges.
  - Add automatic rule-based consultation selection.
  - Keep explicit user-directed consultation support.
  - Include intent metadata in saved collaboration memory.
- Modify `shadowlink-ai/app/api/v1/jarvis_router.py`
  - Keep `routed_agent_id = req.agent_id`.
  - Remove private-chat Maxwell strong-route prompt and fallback tool behavior.
  - Return no visible `routing` payload for background consultations.
- Modify `shadowlink-ai/tests/unit/jarvis/test_agent_consultation.py`
  - Add router unit tests.
  - Update pipeline tests for no visible agent switch.
- Optional modify `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
  - Hide `agent.consult` action cards if backend still returns consultation actions.

---

### Task 1: Add Automatic Consultation Routing Tests

**Files:**
- Modify: `shadowlink-ai/tests/unit/jarvis/test_agent_consultation.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_agent_consultation.py`

- [ ] **Step 1: Update imports for the new router helper**

Replace the existing import:

```python
from app.jarvis.agent_consultation import parse_consult_edges, run_agent_consultations
```

with:

```python
from app.jarvis.agent_consultation import parse_consult_edges, plan_consult_edges, run_agent_consultations
```

- [ ] **Step 2: Add failing unit tests for automatic consult routing**

Append these tests after `test_parse_consult_edges_supports_two_hop_chain`:

```python
def test_plan_consult_edges_routes_emotional_message_to_mira():
    edges = plan_consult_edges(
        source_agent="nora",
        message="我最近压力很大，睡不好，也有点焦虑。",
    )

    assert [(edge.from_agent, edge.to_agent, edge.intent_type) for edge in edges] == [
        ("nora", "mira", "care_intent")
    ]
    assert edges[0].metadata["matched_keywords"]


def test_plan_consult_edges_routes_food_energy_message_to_nora():
    edges = plan_consult_edges(
        source_agent="mira",
        message="我今晚很累，吃什么能补充能量又不刺激？",
    )

    assert [(edge.from_agent, edge.to_agent, edge.intent_type) for edge in edges] == [
        ("mira", "nora", "nutrition_intent")
    ]


def test_plan_consult_edges_routes_schedule_message_to_maxwell_without_handoff():
    edges = plan_consult_edges(
        source_agent="leo",
        message="明天下午帮我安排一次散步，别和会议冲突。",
    )

    assert [(edge.from_agent, edge.to_agent, edge.intent_type) for edge in edges] == [
        ("leo", "maxwell", "schedule_intent")
    ]


def test_plan_consult_edges_routes_maxwell_emotional_message_to_mira():
    edges = plan_consult_edges(
        source_agent="maxwell",
        message="我焦虑到有点撑不住，今晚还要继续学吗？",
    )

    assert [(edge.from_agent, edge.to_agent, edge.intent_type) for edge in edges] == [
        ("maxwell", "mira", "care_intent")
    ]


def test_plan_consult_edges_limits_mixed_message_to_two_specialists():
    edges = plan_consult_edges(
        source_agent="alfred",
        message="我今晚很累还要复习，吃什么比较好，明天也要安排会议，周末还想出去放松。",
    )

    assert len(edges) == 2
    assert {edge.to_agent for edge in edges} <= {"maxwell", "mira", "nora", "leo"}
    assert all(edge.to_agent != "alfred" for edge in edges)


def test_plan_consult_edges_explicit_request_takes_priority():
    edges = plan_consult_edges(
        source_agent="nora",
        message="你先去问问心理师我最近心理状态，再决定今天吃什么。",
    )

    assert [(edge.from_agent, edge.to_agent, edge.intent_type) for edge in edges] == [
        ("nora", "mira", "explicit_consult")
    ]


def test_plan_consult_edges_never_consults_self_or_shadow():
    edges = plan_consult_edges(
        source_agent="mira",
        message="我压力很大，也有点焦虑。",
    )

    assert edges == []


def test_plan_consult_edges_ignores_vague_small_talk():
    edges = plan_consult_edges(
        source_agent="alfred",
        message="你好呀，今天感觉还行。",
    )

    assert edges == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3/shadowlink-ai
.venv311/bin/pytest tests/unit/jarvis/test_agent_consultation.py -q
```

Expected: FAIL because `plan_consult_edges` does not exist and `ConsultEdge` does not expose `intent_type` or `metadata`.

- [ ] **Step 4: Commit failing tests**

```bash
git add shadowlink-ai/tests/unit/jarvis/test_agent_consultation.py
git commit -m "test: specify private chat collaboration routing"
```

---

### Task 2: Implement Unified Consultation Planner

**Files:**
- Modify: `shadowlink-ai/app/jarvis/agent_consultation.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_agent_consultation.py`

- [ ] **Step 1: Extend `ConsultEdge`**

Replace the existing dataclass:

```python
@dataclass(frozen=True)
class ConsultEdge:
    from_agent: str
    to_agent: str
```

with:

```python
@dataclass(frozen=True)
class ConsultEdge:
    from_agent: str
    to_agent: str
    intent_type: str = "explicit_consult"
    metadata: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 2: Add automatic intent keyword definitions**

Place this after `_ALIASES`:

```python
_AUTO_INTENTS: tuple[dict[str, Any], ...] = (
    {
        "intent_type": "task_intent",
        "target_agent": "maxwell",
        "keywords": (
            "备考", "雅思", "ielts", "考研", "考试", "长期", "一个月后", "下个月",
            "暑假", "寒假", "旅游", "旅行", "搬家", "作品集", "健身习惯", "长期计划",
            "每周", "每天", "周期", "以后", "未来", "准备", "目标",
        ),
        "reason": "用户表达了长期任务或背景计划需求，应咨询 Maxwell。",
    },
    {
        "intent_type": "schedule_intent",
        "target_agent": "maxwell",
        "keywords": (
            "日程", "安排", "提醒", "预约", "开会", "会议", "deadline", "schedule", "待办",
            "帮我", "记得", "加入", "写进", "放到", "规划", "定个", "约",
            "明天", "后天", "今天", "今晚", "下午", "上午", "晚上", "几点", "周一", "周二",
            "周三", "周四", "周五", "周六", "周日", "星期", "下周", "本周",
        ),
        "reason": "用户表达了日程、提醒或短期安排需求，应咨询 Maxwell。",
    },
    {
        "intent_type": "care_intent",
        "target_agent": "mira",
        "keywords": (
            "压力", "焦虑", "累", "疲惫", "睡不好", "失眠", "崩溃", "撑不住",
            "扛不住", "难受", "烦", "自责", "不想学", "不想动", "stressed",
            "anxious", "overwhelmed", "tired", "burnout",
        ),
        "reason": "用户表达了情绪、压力、睡眠或恢复边界需求，应咨询 Mira。",
    },
    {
        "intent_type": "nutrition_intent",
        "target_agent": "nora",
        "keywords": (
            "吃什么", "吃啥", "晚饭", "午饭", "早饭", "饭", "营养", "咖啡", "水",
            "补充能量", "能量", "胃", "低糖", "蛋白", "碳水", "喝什么", "meal",
            "nutrition", "coffee", "hydration",
        ),
        "reason": "用户表达了饮食、补水、咖啡或能量恢复需求，应咨询 Nora。",
    },
    {
        "intent_type": "lifestyle_intent",
        "target_agent": "leo",
        "keywords": (
            "周末", "出门", "散步", "活动", "放松", "去哪", "去哪玩", "推荐",
            "运动", "恢复", "休息", "社交", "weekend", "relax", "activity",
        ),
        "reason": "用户表达了活动、生活方式或低负担恢复需求，应咨询 Leo。",
    },
)
```

- [ ] **Step 3: Add helper functions and `plan_consult_edges`**

Place this after `parse_consult_edges`:

```python
def _match_keywords(text: str, keywords: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [keyword for keyword in keywords if keyword.lower() in lowered]


def _explicit_edges_with_metadata(source_agent: str, message: str) -> list[ConsultEdge]:
    return [
        ConsultEdge(
            from_agent=edge.from_agent,
            to_agent=edge.to_agent,
            intent_type="explicit_consult",
            metadata={
                "mode": "private_consult",
                "reason": "用户显式要求当前角色咨询该专家。",
                "matched_keywords": [],
                "confidence": 0.95,
            },
        )
        for edge in parse_consult_edges(source_agent=source_agent, message=message)
    ]


def plan_consult_edges(source_agent: str, message: str) -> list[ConsultEdge]:
    explicit_edges = _explicit_edges_with_metadata(source_agent, message)
    if explicit_edges:
        return explicit_edges[:_MAX_CONSULT_EDGES]

    text = message.strip()
    if not text:
        return []

    edges: list[ConsultEdge] = []
    seen_targets: set[str] = set()
    for definition in _AUTO_INTENTS:
        target_agent = str(definition["target_agent"])
        if not _can_consult(source_agent, target_agent) or target_agent in seen_targets:
            continue
        matched = _match_keywords(text, definition["keywords"])
        if not matched:
            continue
        seen_targets.add(target_agent)
        edges.append(
            ConsultEdge(
                from_agent=source_agent,
                to_agent=target_agent,
                intent_type=str(definition["intent_type"]),
                metadata={
                    "mode": "private_consult",
                    "reason": str(definition["reason"]),
                    "matched_keywords": matched[:4],
                    "confidence": 0.82 if len(matched) >= 2 else 0.68,
                },
            )
        )
        if len(edges) >= _MAX_CONSULT_EDGES:
            break
    return edges
```

- [ ] **Step 4: Make `run_agent_consultations` use `plan_consult_edges`**

Replace:

```python
edges = parse_consult_edges(source_agent=source_agent, message=user_message)
```

with:

```python
edges = plan_consult_edges(source_agent=source_agent, message=user_message)
```

- [ ] **Step 5: Include intent metadata in consultation result items**

Inside the `item = { ... }` block in `run_agent_consultations`, add:

```python
"intent_type": edge.intent_type,
"metadata": edge.metadata,
```

- [ ] **Step 6: Run router tests**

Run:

```bash
cd /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3/shadowlink-ai
.venv311/bin/pytest tests/unit/jarvis/test_agent_consultation.py -q
```

Expected: Existing explicit tests and new router tests pass except pipeline tests that still depend on Maxwell strong-route behavior.

- [ ] **Step 7: Commit router implementation**

```bash
git add shadowlink-ai/app/jarvis/agent_consultation.py shadowlink-ai/tests/unit/jarvis/test_agent_consultation.py
git commit -m "feat: add private chat collaboration router"
```

---

### Task 3: Update Private Chat Pipeline To Keep The Primary Agent

**Files:**
- Modify: `shadowlink-ai/app/api/v1/jarvis_router.py`
- Modify: `shadowlink-ai/tests/unit/jarvis/test_agent_consultation.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_agent_consultation.py`

- [ ] **Step 1: Add a fake LLM response for Nora and Leo**

Update `FakeConsultLLM.chat()` in `test_agent_consultation.py` so it can distinguish consulted agents and final primary-agent calls:

```python
    async def chat(self, *, message: str, system_prompt: str, temperature: float = 0.7, **kwargs):
        self.calls.append({"message": message, "system_prompt": system_prompt})
        if "严格只输出 JSON" in message:
            return '{"memories":[]}'
        if "## Jarvis private agent consultation" in message and "Mira" in system_prompt:
            return '{"summary":"心理状态偏紧绷，建议先降低强度并保留恢复边界。","confidence":0.82,"needs_followup":false}'
        if "## Jarvis private agent consultation" in message and "Maxwell" in system_prompt:
            return '{"summary":"今晚时间紧，只适合一个 45 分钟学习块，不建议强塞 2 小时。","confidence":0.78,"needs_followup":false}'
        if "## Jarvis private agent consultation" in message and "Nora" in system_prompt:
            return '{"summary":"建议温热、低油，搭配一点碳水和蛋白，避免空腹咖啡。","confidence":0.8,"needs_followup":false}'
        if "## Jarvis private agent consultation" in message and "Leo" in system_prompt:
            return '{"summary":"建议低负担散步或短时户外，不要安排高消耗活动。","confidence":0.76,"needs_followup":false}'
        if "Mira" in system_prompt:
            return "我问了 Maxwell 和 Nora。今晚先别硬顶，保留一个 45 分钟学习块，再吃一点温热、低油、有碳水和蛋白的晚饭。"
        if "Nora" in system_prompt:
            return "我问了 Mira。你现在更需要先降强度，再吃温热、简单、低刺激的食物。"
        if "Leo" in system_prompt:
            return "我问了 Maxwell。明天下午可以安排散步，但要避开会议并留出缓冲。"
        return "结合内部咨询，我建议先做一个轻量版本。"
```

- [ ] **Step 2: Add failing pipeline test for Maxwell no-handoff**

Append this test after `test_chat_pipeline_injects_consult_context_into_final_agent`:

```python
@pytest.mark.asyncio
async def test_chat_pipeline_schedule_intent_consults_maxwell_without_switching_agent(monkeypatch):
    llm = FakeConsultLLM()

    async def no_memory_extract(**kwargs):
        return []

    monkeypatch.setattr(jarvis_router, "extract_and_save_chat_memories", no_memory_extract)

    response = await jarvis_router.chat_with_agent(
        AgentChatRequest(
            agent_id="mira",
            session_id="session-mira-schedule",
            message="今晚很累但还要学 2 小时，帮我重新安排一下。",
        ),
        llm_client=llm,
    )

    final_call = llm.calls[-1]
    assert response.agent_id == "mira"
    assert response.routing is None
    assert response.actions is None or all(action["type"] != "schedule_intent" for action in response.actions)
    assert "## 私下咨询结果" in final_call["message"]
    assert "Maxwell" in final_call["message"]
    assert "我问了 Maxwell" in response.content
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
cd /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3/shadowlink-ai
.venv311/bin/pytest tests/unit/jarvis/test_agent_consultation.py::test_chat_pipeline_schedule_intent_consults_maxwell_without_switching_agent -q
```

Expected: FAIL because `response.agent_id` is still `maxwell` or `routing` is still populated.

- [ ] **Step 4: Remove Maxwell strong-route from `chat_with_agent()`**

In `jarvis_router.py`, replace:

```python
schedule_intent = _build_schedule_intent(req.message, req.agent_id)
routed_agent_id = "maxwell" if schedule_intent else req.agent_id
```

with:

```python
schedule_intent = None
routed_agent_id = req.agent_id
```

Then remove the `intent_context` block from the `full_message` inputs by replacing:

```python
intent_context = ""
if schedule_intent:
    intent_label = "长期/后台任务规划" if schedule_intent.get("type") == "task_intent" else "短期日程安排"
    intent_context = (
        "## 路由接管说明\n"
        f"用户原本正在和 {req.agent_id} 对话，但系统识别到这是{intent_label}需求。\n"
        "你是秘书 Maxwell，请正式接管：判断是生成待确认日程卡、长期任务计划卡，还是先追问必要信息。\n"
        f"结构化意图: {json.dumps(schedule_intent, ensure_ascii=False)}\n\n"
    )
```

with:

```python
intent_context = ""
```

Remove the fallback tool execution block:

```python
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
```

Remove the schedule intent action insertion block:

```python
if schedule_intent:
    action_results.insert(0, {
        "type": schedule_intent["type"],
        "ok": True,
        "pending_confirmation": False,
        "description": schedule_intent["reason"],
        "arguments": schedule_intent,
    })
```

Keep the `routing=schedule_intent` response line; with `schedule_intent = None`, the response remains explicitly no-routing.

- [ ] **Step 5: Run pipeline tests**

Run:

```bash
cd /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3/shadowlink-ai
.venv311/bin/pytest tests/unit/jarvis/test_agent_consultation.py -q
```

Expected: All tests in `test_agent_consultation.py` pass.

- [ ] **Step 6: Commit pipeline change**

```bash
git add shadowlink-ai/app/api/v1/jarvis_router.py shadowlink-ai/tests/unit/jarvis/test_agent_consultation.py
git commit -m "feat: keep private chat agent during specialist consultation"
```

---

### Task 4: Hide Consultation Cards In The Main Chat UI

**Files:**
- Modify: `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`

- [ ] **Step 1: Remove visible rendering for `agent.consult`**

In `renderAction`, find:

```tsx
    if (action.type === "agent.consult") {
      const consultations = asList(action.arguments?.consultations);
      return (
        <div key={key} className="w-full rounded-2xl border border-violet-200 bg-violet-50 p-3 text-xs text-violet-900">
          <div className="text-sm font-semibold">已完成私下咨询</div>
```

Replace the whole `if (action.type === "agent.consult") { ... }` block with:

```tsx
    if (action.type === "agent.consult") {
      return null;
    }
```

- [ ] **Step 2: Verify TypeScript accepts nullable rendered actions**

Run:

```bash
cd /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3/shadowlink-web
npm run build
```

Expected: PASS. If the build fails because `renderAction` is typed to disallow `null`, change the function return type to allow `React.ReactNode`.

- [ ] **Step 3: Commit UI change**

```bash
git add shadowlink-web/src/components/jarvis/AgentChatPanel.tsx
git commit -m "fix: hide private consultation actions in chat"
```

---

### Task 5: Full Verification

**Files:**
- Verify only unless fixes are required.

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
cd /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3/shadowlink-ai
.venv311/bin/pytest tests/unit/jarvis/test_agent_consultation.py -q
```

Expected: PASS.

- [ ] **Step 2: Run nearby Jarvis unit tests**

Run:

```bash
cd /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3/shadowlink-ai
.venv311/bin/pytest tests/unit/jarvis/test_agent_consultation.py tests/unit/jarvis/test_persistence.py tests/unit/jarvis/test_escalation.py -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3/shadowlink-web
npm run build
```

Expected: PASS.

- [ ] **Step 4: Inspect final git state**

Run:

```bash
git -C /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3 status --short --branch
```

Expected: On `main`, ahead of origin by the spec and implementation commits, with no uncommitted changes.

