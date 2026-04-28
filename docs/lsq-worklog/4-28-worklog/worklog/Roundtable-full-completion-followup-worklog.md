# 圆桌模块完整化补齐 Worklog

## 对应原始设计
- 对应 `docs/lsq-worklog/待完成/07-圆桌模式架构.md`：圆桌必须是可见讨论舞台、保留轮流发言、结果可返回来源私聊、Decision 能解释心理状态/日程压力/今日计划如何影响建议。
- 对应 `心理与圆桌全量完成指令.md` 中圆桌剩余缺口：来源字段稳定保存、结果写回来源私聊、上下文解释、错误降级、进度反馈、验收链路。
- 明确未做：速度调优、一次请求返回整轮、管家团队架构升级、减少上下文策略。

## 完成范围
- `roundtable_sessions` 新增并迁移稳定元数据：`title`、`user_prompt`。
- 圆桌从私聊 escalation 启动时，前端会携带 `source_session_id/source_agent_id`，后端写入 session 与 conversation route_payload。
- 从历史会话恢复圆桌时，也会恢复来源字段，保证 `带总结回私聊` 可用。
- Decision 结果新增 `context_explanation`，解释心理状态、日程压力、今日计划如何影响最终建议。
- 前端 Decision 卡展示“为什么这样建议”，不再只展示结果。
- 保持角色轮流发言模式，不改为一次请求返回整轮。

## 代码文件
- `shadowlink-ai/app/jarvis/persistence.py`
  - `roundtable_sessions` schema 增加 `title/user_prompt`。
  - `_init_db()` 增加旧库列迁移。
  - `save_session()`、`list_sessions()`、`get_roundtable_session()` 支持新字段。
- `shadowlink-ai/app/jarvis/roundtable_sessions.py`
  - `create_session_async()` 支持 `title/user_prompt`。
- `shadowlink-ai/app/api/v1/jarvis_router.py`
  - `/roundtable/start` 写入来源字段到 conversation route_payload。
  - Decision result context 增加 `context_explanation`。
  - `/roundtable/{session_id}/return` 保留 title/user_prompt 并标记 returned。
- `shadowlink-web/src/stores/jarvisStore.ts`
  - 记录 `activeRoundtableSourceSessionId/activeRoundtableSourceAgentId`。
  - `startRoundtable()` 从私聊启动时自动带来源。
- `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
  - escalation 进入圆桌时传入当前私聊来源。
- `shadowlink-web/src/components/jarvis/JarvisHome.tsx`
  - 将来源字段传给圆桌舞台。
- `shadowlink-web/src/components/jarvis/RoundtableStage.tsx`
  - `/roundtable/start` 请求带 `source_session_id/source_agent_id`。
  - Decision 卡展示上下文解释。
- `shadowlink-web/src/services/jarvisApi.ts`
  - 圆桌结果类型补 `context` 字段。
- `shadowlink-ai/tests/unit/jarvis/test_roundtable_decision.py`
  - 新增 session title/user_prompt/source 字段持久化测试。

## 表 / 接口
- 表：`roundtable_sessions` 新增 `title TEXT NOT NULL DEFAULT ''`。
- 表：`roundtable_sessions` 新增 `user_prompt TEXT NOT NULL DEFAULT ''`。
- 表：继续复用 `roundtable_results.result_json/user_choice/handoff_status`。
- 接口：`POST /api/v1/jarvis/roundtable/start` 继续轮流发言，但请求体现在稳定携带来源字段。
- 接口：`POST /api/v1/jarvis/roundtable/{session_id}/return` 继续负责写回来源私聊。

## 前端影响
- 用户从私聊点击“进入协作模式”进入圆桌后，返回按钮能稳定回到原私聊。
- Decision 结果卡会显示“为什么这样建议”，包括心理状态、日程压力、今日计划三类解释。
- 历史圆桌恢复后仍能保留来源信息。
- 圆桌仍是轮流发言，用户可以看到每个角色依次表达。

## 测试
- `python -m py_compile app\jarvis\persistence.py app\jarvis\roundtable_sessions.py app\api\v1\jarvis_router.py tests\unit\jarvis\test_roundtable_decision.py`：通过。
- `pytest tests\unit\jarvis\test_roundtable_decision.py tests\unit\jarvis\test_roundtable_brainstorm.py -q`：8 passed。
- `npm.cmd run type-check`：通过。

## 完成度变化
- 圆桌来源、返回、schema、错误降级、进度反馈、上下文解释、前端验收链路均已补齐。
- 在当前指令限定范围内，圆桌模块可以视为“本轮完整完成”。
- 不包含被明确排除的速度调优、管家团队升级、一次性整轮生成。

## 剩余缺口
- 后续若继续增强，可做角色人格化降级文案和更丰富的圆桌场景配置。
- 性能优化仍按用户要求暂不处理。
