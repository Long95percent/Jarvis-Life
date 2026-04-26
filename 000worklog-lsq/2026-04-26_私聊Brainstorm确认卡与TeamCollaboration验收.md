# 验收说明：私聊 Brainstorm 确认卡与 Team Collaboration Layer

创建时间：2026-04-26（Asia/Shanghai）

## 1. 本次功能范围

本次需要验收两部分：

1. 普通私聊中触发 Brainstorm / Roundtable 时，不再自动跳转，而是在输入框上方弹出确认卡。
2. Team Collaboration Layer 第一版真实闭环已落地：后端支持多个 Jarvis 专家 Agent 协作、Alfred 汇总、保存协作记忆。

## 2. 启动前准备

请重启三个服务，避免浏览器或后端仍使用旧代码：

1. AI 服务：`shadowlink-ai`
2. Java Gateway：`shadowlink-server`
3. 前端：`shadowlink-web`

如果使用浏览器开发模式，建议强刷页面或清缓存。

## 3. 验收项 A：私聊触发协作前必须弹确认卡

### 操作步骤

1. 打开 Jarvis 页面。
2. 进入任意普通私聊，例如 Maxwell / Alfred / Mira。
3. 发送一个容易触发协作的话，例如：
   - “我今天日程有点乱，帮我整体协调一下。”
   - “我压力有点大，不知道怎么安排恢复。”
   - “我想做一个复杂方案，能不能头脑风暴一下？”
4. 等 Agent 回复完成。

### 预期结果

- 页面不应该自动跳到 Brainstorm / Roundtable。
- 私聊输入框上方应该出现一个小确认卡。
- 卡片文案包含类似：`建议进入 Brainstorm / 团队协作模式`。
- 卡片上有两个按钮：
  - `进入协作模式`
  - `暂不进入`

### 通过标准

- 未点击按钮前，页面仍停留在普通私聊。
- 点击 `暂不进入` 后，确认卡消失，仍留在私聊。
- 点击 `进入协作模式` 后，才进入 Roundtable / Brainstorm 页面。

## 4. 验收项 B：Team Collaboration Layer 后端真实可用

### 操作方式 1：用前端间接验收

当前前端已接入 `jarvisStore.startTeamCollaboration()`，但还没有专门的可视化协作面板。可以先通过后端接口或开发者工具调用验证。

### 操作方式 2：直接调用后端接口

向以下接口发送 POST 请求：

```http
POST /api/v1/jarvis/team/collaborate
Content-Type: application/json
```

请求体示例：

```json
{
  "goal": "帮用户安排一个低压力的下午恢复计划",
  "user_message": "我下午有点累，想出去散心，但又怕耽误事情",
  "agents": ["maxwell", "mira", "nora"],
  "source_agent": "maxwell",
  "session_id": "manual-acceptance-test"
}
```

### 预期返回

接口应返回 200，且结构包含：

```json
{
  "type": "team.collaboration",
  "ok": true,
  "goal": "...",
  "participants": ["maxwell", "mira", "nora"],
  "specialists": [ ... ],
  "summary": "...",
  "aligned_actions": [ ... ],
  "conflicts": [ ... ],
  "followups": [ ... ],
  "handoffs": [ ... ],
  "memory_saved": true
}
```

### 通过标准

- `ok` 为 `true`。
- `participants` 包含请求中的有效 Agent。
- `specialists` 不为空，每个专家有自己的建议。
- `summary` 有 Alfred 汇总内容。
- `memory_saved` 为 `true`。

## 5. 验收项 C：协作记忆被保存

### 操作步骤

1. 先调用一次 `/api/v1/jarvis/team/collaborate`。
2. 再回到任意相关 Agent 私聊，例如 Alfred 或 Maxwell。
3. 发送：“刚刚团队协作的结论是什么？” 或 “继续刚才那个恢复计划。”

### 预期结果

- Agent 的上下文中应该能参考刚才协作结果。
- 这依赖 `collaboration_memories` 注入，不要求逐字复述，但应能延续协作结论。

## 6. 验收项 D：回归日程卡片不受影响

### 操作步骤

1. 私聊 Maxwell。
2. 发送：“帮我今天下午安排 30 分钟散步。”
3. 等待日程卡片出现。
4. 点击 `确认写入日程`。

### 预期结果

- 仍显示待确认日程卡。
- 点击确认后显示已写入。
- 日历面板能看到新增日程。

## 7. 开发验证命令

在代码侧已执行过以下验证，后续如果复测可再次运行：

```powershell
cd D:\github_desktop\Jarvis-Life
python -m py_compile shadowlink-ai\app\api\v1\jarvis_router.py

cd D:\github_desktop\Jarvis-Life\shadowlink-web
npm run type-check
npm run build

cd D:\github_desktop\Jarvis-Life\shadowlink-server
.\mvnw.cmd -pl shadowlink-starter -am test -DskipTests
```

## 8. 已知边界

- Team Collaboration Layer 的后端闭环已经真实可用，但前端还没有专门的“协作云图”展示页。
- 当前私聊确认卡点击后进入的是已有 Roundtable / Brainstorm 页面。
- `/team/collaborate` 已为后续云图准备了 `specialists` 和 `handoffs` 数据。

## 9. 后续验收规范

从本次开始，以后每次新增功能或较大行为改动，都需要在 `D:\github_desktop\Jarvis-Life\worklog-lsq` 下新增一个验收说明文件，说明：

1. 本次功能范围。
2. 用户如何操作。
3. 预期看到什么。
4. 什么算通过。
5. 可选的开发验证命令。
6. 已知边界或下一步。
