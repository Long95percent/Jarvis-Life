# P0 剩余缺口：圆桌前端返回、进度与降级产品化 Worklog

## 对应原始设计
- 对应 `心理与圆桌全量完成指令.md` 的 P0 剩余缺口：`/roundtable/{session_id}/return` 需要产品化，轮流发言错误降级与进度反馈需要用户可见。
- 对应用户要求：验证方法必须是前端真实操作链路/路演手册，不是后台跑通。
- 本次只补心理/圆桌必要链路，不做速度调优，不做管家团队架构升级。

## 完成范围
- 前端 API 新增 `returnRoundtableToPrivateChat()`，接入后端 `/roundtable/{session_id}/return`。
- Zustand store 新增 `openExistingPrivateChat(agentId, sessionId)`，支持圆桌回到来源私聊并加载该 session 历史。
- `RoundtableStage` 接入：
  - 顶部展示轮流发言进度 `current/total/status`。
  - 接收 `agent_degraded`，显示“某角色已降级继续”。
  - Decision / Brainstorm 结果卡展示 `handoff_status` 与 `user_choice`。
  - 结果卡新增 `带总结回私聊`，成功后跳回来源私聊。
- 新增前端路演验证手册，说明用户如何从页面验证功能。

## 代码文件
- `shadowlink-web/src/services/jarvisApi.ts`
  - 扩展圆桌结果类型字段。
  - 新增 `RoundtableReturnResponse` 与 `returnRoundtableToPrivateChat()`。
- `shadowlink-web/src/stores/jarvisStore.ts`
  - 新增 `openExistingPrivateChat()`。
- `shadowlink-web/src/components/jarvis/JarvisHome.tsx`
  - 将返回私聊能力传给 `RoundtableStage`。
- `shadowlink-web/src/components/jarvis/RoundtableStage.tsx`
  - 接入 progress、agent_degraded、return 操作、交接状态展示。
- `docs/lsq-worklog/4-28-worklog/test/roundtable-return-and-progress-frontend-validation.md`
  - 新增面向用户/路演的验证方法。

## 表 / 接口
- 表：本次无新增表，复用上一批已补的 `roundtable_results.result_json/user_choice/handoff_status` 与 `agent_chat_turns`。
- 接口：前端新增调用 `POST /api/v1/jarvis/roundtable/{session_id}/return`。
- SSE：前端消费 `agent_degraded`，并读取 `agent_speak/token` 里的 `progress`。

## 前端影响
- 用户在圆桌结果卡点击 `带总结回私聊` 后，会回到来源私聊，不再只是关闭圆桌。
- 用户可看到发言进度，不会误以为圆桌卡住。
- 单角色失败时，用户看到降级提示，理解系统正在继续下一位角色。
- Decision/Brainstorm 卡片会展示交接状态，减少重复点击误操作。

## 测试
- `npm.cmd run type-check`：通过。
- `pytest tests\unit\jarvis\test_care_triggers.py tests\unit\jarvis\test_mood_care_observations.py tests\unit\jarvis\test_roundtable_decision.py tests\unit\jarvis\test_roundtable_brainstorm.py -q`：21 passed。

## 完成度变化
- 圆桌返回链路从“后端可用”提升为“前端真实用户可操作”。
- 圆桌错误降级与进度反馈从“SSE 字段存在”提升为“页面可见”。
- 仍不声明圆桌模块全量完成；剩余缺口继续按 plan/原始设计推进。

## 剩余缺口
- 若要进一步完整化，需要让所有圆桌发起入口都稳定携带 `source_session_id/source_agent_id`，避免非私聊入口无法返回私聊。
- 降级文案仍可继续按角色人格润色。
- 需要继续执行指令文档中 P1/P2 的心理模块完整化项目。

