# StepC4C5 圆桌舞台体验与性能 Worklog

## 完成范围

本步按用户调整后的 Phase 9 执行：保留圆桌角色轮流发言，不改成一次请求返回整轮内容；暂不做减少上下文。

已完成：

- 清理正常使用页里的 Demo / MVP 展示入口。
- 圆桌舞台区分 Decision / Brainstorm 视觉模式。
- 席位、头像、当前发言高亮继续保留并强化 `Speaking` 标识。
- 中心圆桌增加主持总结卡：Decision 展示推荐结论，Brainstorm 展示沉淀想法数和下一步。
- 当前发言气泡做长度控制，完整内容保留在“完整记录”中，避免舞台文本墙。
- 后端为轮流发言圆桌增加 timing：`context_prepare`、`agent_turn`、`result_persist`、`total_ms`。
- 前端顶部显示本轮 timing 总耗时，便于解释轮流发言耗时。
- C2 / C3 前端验证文档改为路演/用户使用手册，而不是后台逻辑验证说明。

## 代码文件

后端：

- `shadowlink-ai/app/api/v1/jarvis_router.py`

前端：

- `shadowlink-web/src/components/jarvis/RoundtableStage.tsx`
- `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
- `shadowlink-web/src/components/jarvis/JarvisTopBar.tsx`

文档：

- `docs/lsq-worklog/4-28-worklog/4-28plan.md`
- `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`
- `docs/lsq-worklog/4-28-worklog/test/StepC2-圆桌Decision结构化与Handoff-路演使用手册.md`
- `docs/lsq-worklog/4-28-worklog/test/StepC3-圆桌Brainstorm模式-路演使用手册.md`

## 清理内容

已移除正常用户页中的不必要展示入口：

- 私聊里的“行为采集层 MVP”明细面板。
- 顶部栏 Demo proactive trigger 下拉入口。

保留：

- 后台行为采集事件写入逻辑。
- 正常 proactive message feed。
- 正常心理趋势中心。
- 正常圆桌 / 私聊 / 日历 / 记忆入口。

## 接口 / 事件

新增 SSE 事件：

- `roundtable_timing`

事件内容：

- `total_ms`
- `spans`
  - `context_prepare`
  - `agent_turn`
  - `result_persist`
- `mode`
- `strategy=sequential_agent_turns`

## 计划调整记录

用户明确调整：

- 圆桌保留角色轮流发言形式。
- 不做一次请求返回所有内容。
- 暂不做减少上下文。

因此 checklist 中相关性能条目已标为 `[DEFER]`，并说明原因。后续性能优化只围绕轮流发言体验、耗时解释、错误降级和必要的 UI 反馈进行。

## 测试

待验证命令：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-web
npm.cmd run type-check
```

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
Remove-Item Env:SSLKEYLOGFILE -ErrorAction SilentlyContinue
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests\unit\jarvis\test_roundtable_decision.py tests\unit\jarvis\test_roundtable_brainstorm.py -q
```

## 完成度变化

Checklist 变化：

- 圆桌 E 舞台体验：`[TODO] -> [MVP]`
- 角色发言长度控制：`[TODO] -> [MVP]`
- roundtable timing：`[TODO] -> [MVP]`
- 一次生成整轮 / 禁止串行 / 减少上下文：按新产品决策 `[TODO] -> [DEFER]`

## 剩余缺口

- `return` 接口仍未产品化。
- 舞台动效和主持总结卡还可进一步精修。
- consult、planner、proactive 的完整 timing 仍待后续阶段。
- 如果后续轮流发言性能不足，应优先做并发预取、错误降级、缓存或用户可见进度，不默认牺牲圆桌感。
