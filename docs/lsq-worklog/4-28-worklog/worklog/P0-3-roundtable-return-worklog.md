# P0-3 圆桌返回原私聊接口 Worklog

## 对应原始设计
- 对应 `心理与圆桌全量完成指令.md` P0-3：补 `/roundtable/{session_id}/return`，返回原私聊并写入圆桌总结。
- 对应原始圆桌设计的“圆桌不是孤立页面，必须能回到用户原本的 Agent 私聊继续处理”。
- 本次完成返回链路，不声明圆桌模块全量完成。

## 完成范围
- 新增 `POST /api/v1/jarvis/roundtable/{session_id}/return`。
- 接口读取圆桌 session 的 `source_session_id` / `source_agent_id`，把圆桌总结写回原私聊 `agent_chat_turns`。
- 写回内容包含：圆桌总结、用户选择、用户补充说明，并附带 `roundtable.return_summary` action，前端正常私聊页可看到该总结。
- 返回后将圆桌 session 标记为 `returned`，并同步更新圆桌 result 的 `status=user returned` 语义字段。

## 代码文件
- `shadowlink-ai/app/api/v1/jarvis_router.py`
  - 新增 `RoundtableReturnRequest`。
  - 新增 `/roundtable/{session_id}/return` 接口。
- `shadowlink-ai/app/jarvis/persistence.py`
  - 新增 `get_roundtable_session()`，用于读取圆桌来源私聊信息。
- `shadowlink-ai/tests/unit/jarvis/test_roundtable_decision.py`
  - 新增返回原私聊测试。

## 表 / 接口
- 表：复用 `roundtable_sessions` 的 `source_session_id`、`source_agent_id`。
- 表：向 `agent_chat_turns` 写入一条 agent 消息，作为原私聊里的圆桌总结。
- 表：更新 `roundtable_results` 的状态、用户选择与交接状态。
- 接口：新增 `POST /api/v1/jarvis/roundtable/{session_id}/return`。

## 前端影响
- 前端在圆桌页提供“带着总结回到私聊 / 返回原私聊继续”的按钮即可调用该接口。
- 成功后跳转到接口返回的 `source_session_id` 对应私聊页面，用户会看到一条由原 Agent 写入的“圆桌讨论总结”。
- 这不是后台展示面板，而是用户真实操作链路：私聊发起圆桌 → 角色轮流讨论 → 用户带总结回私聊继续。

## 测试
- `python -m py_compile app\jarvis\persistence.py app\api\v1\jarvis_router.py tests\unit\jarvis\test_roundtable_decision.py`
- `pytest tests\unit\jarvis\test_roundtable_decision.py tests\unit\jarvis\test_roundtable_brainstorm.py -q`：7 passed。

## 完成度变化
- 圆桌“返回私聊”从缺失提升为可持久化闭环：原私聊能收到圆桌总结。
- 圆桌模块完成度提升，但仍不标记为全量完成。

## 剩余缺口
- 前端还需要接一个用户按钮和跳转逻辑，后端接口已经可用。
- 返回总结目前基于已持久化 result 或最近发言，不额外调用 LLM 重新润色。
