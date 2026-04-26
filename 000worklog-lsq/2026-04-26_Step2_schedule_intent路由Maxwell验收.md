# 验收说明：Step 2 schedule_intent / task_intent 路由 Maxwell

创建时间：2026-04-26（Asia/Shanghai）

## 1. 本次变更范围

本次落地 Step 2 的 MVP：其它 Agent 遇到日程、提醒、安排、长期任务规划需求时，不再直接承担秘书职责，而是生成结构化 intent 并交给 Maxwell 接管。

已实现内容：

1. 后端新增正式 `_build_schedule_intent`，输出 `schedule_intent` 或 `task_intent`。
2. 私聊 pipeline 根据 intent 路由到 Maxwell。
3. Maxwell prompt 中会收到“路由接管说明”和结构化 intent。
4. 后端响应新增 `routing` 字段，并在 `actions` 中插入 intent action。
5. 前端私聊展示“已把日程安排/长期任务规划交给 maxwell”的提示卡。
6. pending action 保存时使用实际执行的 `routed_agent_id`，避免仍归属原 Agent。

## 2. 涉及文件

- `shadowlink-ai/app/api/v1/jarvis_router.py`：新增 intent 构造、路由接管 prompt、routing/action 返回。
- `shadowlink-web/src/services/jarvisApi.ts`：`ChatResponse` 新增 `routing`。
- `shadowlink-web/src/stores/jarvisStore.ts`：聊天历史保存 `routing`。
- `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`：展示 Maxwell 接管提示和 intent action 卡。
- `4-26plan.md`：更新 Step 2 完成状态。

## 3. 如何验收

### 验收项 A：短期日程从 Mira 路由 Maxwell

在 Mira 私聊输入：

```text
明天下午提醒我散步恢复一下
```

预期结果：

- 前端出现“mira 已把日程安排交给 maxwell”提示。
- 后端返回 `routing.type = schedule_intent`。
- `actions` 中包含 `type = schedule_intent`。
- Maxwell 应继续生成待确认日程卡，或在信息不足时追问。
- 不应出现 `tool not allowed for mira`。

### 验收项 B：长期任务从 Nora 路由 Maxwell

在 Nora 私聊输入：

```text
我下个月想开始准备雅思，你帮我先做个长期计划
```

预期结果：

- 前端出现“Nora 已把长期任务规划交给 maxwell”提示。
- 后端返回 `routing.type = task_intent`。
- Maxwell 应生成 `task.plan` 待确认卡，或先追问目标分数/考试时间等关键信息。

### 验收项 C：普通闲聊不路由

在 Leo 私聊输入：

```text
你觉得今天适合喝咖啡吗
```

预期结果：

- 不出现 Maxwell 接管提示。
- 后端 `routing` 为空。
- Leo 正常回答。

## 4. 通过标准

- 非 Maxwell Agent 不直接调用日程/长期任务工具。
- 明显日程/任务需求会生成结构化 intent。
- Maxwell 是实际规划和确认卡生成方。
- 前端能让用户明确看到“秘书已接管”。
- 返回结构中能追溯 source_agent、target_agent、matched_keywords、user_message 和 reason。

## 5. 已知边界

- 当前 intent 分类仍是规则/关键词 MVP，不是完整意图分类模型。
- 当前用户不能手动取消或改派接管对象。
- 历史消息重新加载时主要依靠 actions 恢复 intent 卡，`routing` 元数据暂未单独持久化。
