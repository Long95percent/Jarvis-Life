# Demo：Step 2 schedule_intent / task_intent 路由 Maxwell

创建时间：2026-04-26（Asia/Shanghai）

## 1. Demo 目标

展示私人管家团队的分工：用户可以找任何 Agent 说日程或长期计划，但真正写日程、拆任务、生成确认卡的秘书中枢是 Maxwell。

## 2. Demo A：Mira 收到短期日程

### demo_step_id

```text
step2-A-mira-schedule-intent
```

### 用户输入

在 Mira 私聊输入：

```text
明天下午提醒我散步恢复一下
```

### 预期演示效果

- 页面提示：`mira 已把日程安排交给 maxwell`。
- Maxwell 接管后，生成待确认日程卡，或先追问更合适的时间。
- 用户看到这不是 Mira 直接写日程，而是秘书 Maxwell 统一安排。

### 讲解词

```text
这里体现团队分工：Mira 可以识别用户是在提出日程需求，但她不直接写日程。
系统会把这个需求结构化成 schedule_intent，再交给 Maxwell 处理。
这样可以保证日程、冲突检查和确认写入都收束到秘书中枢。
```

## 3. Demo B：Nora 收到长期任务

### demo_step_id

```text
step2-B-nora-task-intent
```

### 用户输入

在 Nora 私聊输入：

```text
我下个月想开始准备雅思，你帮我先做个长期计划
```

### 预期演示效果

- 页面提示：`nora 已把长期任务规划交给 maxwell`。
- Maxwell 接管后，生成 `task.plan` 待确认卡，或追问目标分数/考试时间/每周投入。
- 不应出现 `tool not allowed for nora`。

### 讲解词

```text
长期计划不是单条日程，系统会识别为 task_intent。
Nora 不直接创建任务计划，而是把它交给 Maxwell，由 Maxwell 判断是否进入后台任务清单。
这就是 Step 2 和 Step 3.5 的衔接。
```

## 4. Demo C：普通聊天不接管

### demo_step_id

```text
step2-C-normal-chat-no-route
```

### 用户输入

在 Leo 私聊输入：

```text
你觉得今天适合喝咖啡吗
```

### 预期演示效果

- 不出现 Maxwell 接管提示。
- Leo 正常回答。
- 说明系统不是所有消息都硬转给 Maxwell，只路由日程/任务类需求。

## 5. 追溯检查

打开浏览器 Network 或后端日志，检查 `/api/v1/jarvis/chat` 响应：

```json
{
  "agent_id": "maxwell",
  "routing": {
    "type": "schedule_intent",
    "source_agent": "mira",
    "target_agent": "maxwell",
    "status": "routed_to_maxwell",
    "matched_keywords": ["提醒", "明天", "下午"],
    "reason": "..."
  },
  "actions": [
    { "type": "schedule_intent", "ok": true }
  ]
}
```

字段内容不要求逐字一致，但必须能看出 source、target、intent 类型和路由原因。

## 6. 通过标准

- Demo A 出现 `schedule_intent` 接管提示。
- Demo B 出现 `task_intent` 接管提示。
- Demo C 不出现接管提示。
- 日程/长期任务后续由 Maxwell 生成卡片或追问。
- 没有 `tool not allowed for mira/nora`。
