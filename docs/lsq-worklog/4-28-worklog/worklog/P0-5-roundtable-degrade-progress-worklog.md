# P0-5 圆桌轮流发言错误降级与进度反馈 Worklog

## 对应原始设计
- 对应 `心理与圆桌全量完成指令.md` P0-5：补轮流发言错误降级和进度反馈。
- 对应用户明确要求：圆桌保留旧的角色轮流发言模式，不要一次请求返回整轮。
- 本次增强轮流模式稳定性，不声明圆桌模块全量完成。

## 完成范围
- 保留 sequential agent turns：每个角色依次请求、依次产出。
- 单个 Agent LLM 调用失败时不终止整轮：生成降级内容，持久化该角色回合，并继续下一个 Agent。
- SSE 新增 `agent_degraded` 事件，前端可提示“某角色暂时不可用，已继续下一位”。
- `agent_speak` 与 `token` 事件增加 `progress` 字段，包含 current、total、status。

## 代码文件
- `shadowlink-ai/app/api/v1/jarvis_router.py`
  - `_run_roundtable_round()` 中增加进度 payload。
  - 捕获单 Agent 错误后发送 `agent_degraded` 事件，并继续轮流流程。
- `shadowlink-ai/tests/unit/jarvis/test_roundtable_decision.py`
  - 新增失败 Agent 降级后继续下一个 Agent 的测试。

## 表 / 接口
- 表：无新增表；降级发言仍通过原有 `roundtable_turns` 持久化。
- 接口：`POST /api/v1/jarvis/roundtable/start` 与 `POST /api/v1/jarvis/roundtable/continue` 的 SSE 流新增：
  - `agent_degraded`
  - `progress` 字段
- 接口仍保持轮流发言，不改成一次性返回整轮。

## 前端影响
- 前端圆桌页可根据 `progress.current/total` 展示“第 N / M 位角色正在发言”。
- 如果收到 `agent_degraded`，前端可在该角色卡片上显示“暂时失败，已使用降级回复并继续”。
- 用户在路演中能看到圆桌不会因为某个角色失败而整轮卡死。

## 测试
- `python -m py_compile app\jarvis\persistence.py app\api\v1\jarvis_router.py tests\unit\jarvis\test_roundtable_decision.py`
- `pytest tests\unit\jarvis\test_roundtable_decision.py tests\unit\jarvis\test_roundtable_brainstorm.py -q`：7 passed。

## 完成度变化
- 圆桌从“单个角色异常可能影响体验”提升为“逐角色可降级、可继续、可反馈进度”。
- 圆桌轮流发言链路完成度提升，但仍不标记为全量完成。

## 剩余缺口
- 前端需要把 `agent_degraded` 和 `progress` 正式接入 UI 状态。
- 降级文案目前是服务端错误摘要，后续可按角色语气做更自然的用户提示。
