# 待完成工作与验收清单整理

## 2026-04-30 整理来源
- `docs/lsq-worklog/4-28-worklog`
- `docs/ohmori-worklog/2026-04-30-daily-summary.txt`

## 结论摘要
- 4-28 早期缺口清单与后续完成简记存在时间顺序差异：早期文件曾标注圆桌 return/schema/错误降级未完成，但 `4-28_work.md` 和 4-30 Ohmori 日报显示这些已被后续补齐或迁移到 LangGraph 方案。因此本整理以较新的完成简记、4-30 日报和最终验证记录为准。
- 当前真正的工程待办集中在：私聊 token 级流式、Alfred 本地意图、真实 benchmark、sidecar provider probe、后台任务 runner、LifeContextBus 异步生命周期、本地生活生产质量评估。
- 当前大量工作已经有自动化验证，但还需要用户从页面/路演视角验收，尤其是心理关怀、圆桌、统一计划、本地生活、Athena 角色和性能可感知体验。

## A. 工程待完成工作

### P0：稳定性与可观测性
1. LifeContextBus `snapshot_context` 异步任务生命周期治理
   - 来源：4-30 Ohmori 日报最终剩余风险。
   - 现状：测试通过，但仍有 `Task was destroyed but it is pending!` 既有 warning。
   - 建议验收：关闭服务/跑测试时不再留下 pending task warning。
2. 后台任务 runner 化
   - 来源：4-30 Ohmori 当前风险与后续建议。
   - 范围：统一错误捕捉、并发上限、可观测指标、graceful shutdown。
   - 价值：避免后台记忆、偏好学习、心理快照等 create_task 越来越多后不可控。
3. 真实延迟 benchmark 脚本
   - 来源：4-28 Phase12 缺口、4-30 Ohmori 下一步建议。
   - 建议脚本：`scripts/bench_jarvis_private_chat.py`。
   - 指标：cold/warm、timing.spans、LLM call count、tool count、p50/p95、历史 JSON/CSV 对比。

### P1：私聊体验与低延迟
1. 私聊 token 级流式输出
   - 来源：4-30 Ohmori 未完成项。
   - 现状：已有 `/chat/stream` SSE 生命周期入口，但不是 token 级流式。
   - 建议路线：拆 `run_agent_turn` 阶段；本地意图命中且工具已预执行时直接 token stream；动态工具块保留两阶段状态流。
2. Alfred 本地 intent router
   - 来源：4-30 Ohmori 未完成项。
   - 现状：本地 router 覆盖 Maxwell / Nora / Mira / Leo，Alfred 仍更多依赖 LLM 工具块。
   - 建议覆盖：daily_briefing、specialist_orchestrate、calendar_create、context_update。
   - 注意：Alfred 是总管家，只覆盖统筹型任务，避免抢所有角色意图。
3. sidecar provider probe
   - 来源：4-30 Ohmori 当前风险。
   - 范围：设置页增加“测试后台模型”按钮；返回 sidecar model/base_url/max_tokens/latency；显示最近后台任务状态。

### P2：本地生活与生产化质量
1. 本地生活实时 web search 质量评估
   - 来源：4-30 Ohmori 最终剩余风险。
   - 现状：缓存过滤、半径/窗口约束已做过 review 二次修复并有测试；生产仍依赖外部搜索质量。
   - 后续：真实地理编码、页面抓取质量、不同城市/半径/时间窗口数据准确性评估。
2. 本地生活推荐体验验收后再调策略
   - 风险：主动提醒不应像广告插入。
   - 关注：只在压力、过载、低能量、周末充电、mood recovery 等相关场景附带机会。

### P3：统一计划与兼容性
1. 统一计划领域模型页面验收
   - 来源：4-28 Phase11 缺口。
   - 关注：plan day 是否显示在日历、任务列表、Maxwell 工作台。
2. 旧 `background_task` 迁移/兼容确认
   - 来源：4-28 Phase11 缺口。
   - 决策点：旧数据是否迁移到 `jarvis_plan_days`，还是双轨并存。
3. 心理压力联动验收
   - 来源：4-28 Phase11 缺口。
   - 关注：stress signals 是否优先读取 `jarvis_plan_days`，并在心理趋势/圆桌 decision 中体现。
4. missed -> 重排 -> proactive message 页面验收
   - 来源：4-28 Phase11 缺口。
   - 关注：自动 missed 后，LLM/Maxwell 重排和主动提醒是否能被用户看到。

### P4：长期产品化/策略项
1. 管家团队架构升级
   - 来源：4-28 明确排除 Phase10。
   - 状态：不是当前已要求工作，但属于后续产品化方向。
2. 圆桌更强冲突仲裁和证据引用
   - 来源：4-30 Ohmori 未完成方向。
   - 现状：六个预设场景已迁移 LangGraph 多轮会议协议。
   - 后续：继续增强冲突仲裁、证据引用和更高质量总结。

## B. 需要用户验收的工作

### B1：心理关怀与心理中心
最小必验：
1. P1 低能量关怀卡片
   - 操作：和 Mira 聊“最近有点累/压力大”。
   - 期望：出现关怀内容或卡片，语气自然，不机械。
2. P2 后续回访按钮
   - 操作：点击关怀卡片里的后续回访/反馈按钮。
   - 期望：按钮可点击，状态可保存，后续消息不会无限刷屏。
3. P4 心理趋势与详情
   - 操作：进入心理趋势/心理中心页面。
   - 期望：看到趋势、日期详情、触发原因或观测来源。

建议补验：
4. P3 高风险安全边界
   - 期望：高风险表达时给出安全边界与求助建议，不乱承诺治疗。
5. P5 追踪开关与清除
   - 期望：关闭心理追踪后停止采集；清除后相关数据消失或不可见。

### B2：圆桌 Decision / Brainstorm
最小必验：
1. R1 Decision 圆桌轮流发言并给出建议
   - 期望：角色轮流发言，有主持总结/结构化建议，页面不长时间无反馈。
2. R2 Decision 接受建议 -> Maxwell 待确认卡
   - 期望：生成待确认动作，不直接改日程。
3. R4 Brainstorm 发散
   - 期望：显示 themes / ideas / tensions / followup questions，不默认生成日程或计划。
4. R5 Brainstorm 保存灵感
   - 期望：写入记忆，不改计划/日程。

建议补验：
5. R3 返回私聊
   - 期望：圆桌总结写回来源私聊，继续对话能接上上下文。
6. R6 Brainstorm 转成计划
   - 期望：生成 Maxwell pending action，不直接执行。
7. 错误降级与进度
   - 期望：某个 agent 失败时页面显示跳过/失败原因，不整场卡死；显示第几位/共几位或正在总结。

### B3：统一计划 / Maxwell / 日程联动
1. 计划 day 页面显示
   - 验收点：日历、任务列表、Maxwell 工作台都能看到一致的计划信息。
2. pending action 确认链路
   - 验收点：用户确认前不落日程；确认后状态变化清楚。
3. missed 和自动重排
   - 验收点：过期任务被标记 missed，重排建议能显示给用户。
4. 心理压力联动
   - 验收点：高压力/低能量状态会影响计划建议和圆桌 decision。

### B4：私聊主链路
1. 当前角色稳定持有对话
   - 验收点：不要每次都跳到 Maxwell；当前角色能连续上下文回复。
2. 私下咨询其它角色
   - 验收点：当前角色能引用其它角色意见，但最终回复仍保持当前角色身份。
3. 工具调用和待确认动作
   - 验收点：创建日程/计划类操作先进入待确认，不误执行。
4. 速度体感
   - 验收点：普通聊天、工具聊天、咨询聊天都有可接受首响；失败时错误可读。

### B5：Athena 角色
1. Athena 不是硬编码临时 participant
   - 验收点：私聊、咨询、圆桌都能作为一等角色出现。
2. Athena 可被其它角色咨询，也可主动咨询其它角色。
3. 角色禁用/interrupt_budget=0 不被加载逻辑悄悄恢复默认。

### B6：本地生活机会雷达
1. 不同城市/半径/时间窗口结果合理
   - 验收点：不会出现明显超远、过期、无关的活动。
2. 私聊/圆桌只读取缓存，不明显拖慢响应。
3. 主动提醒只在相关场景附带本地生活机会，不像广告。

### B7：时间模块（今日新增）
1. 新用户默认使用浏览器时区
   - 验收点：不手动设置时，Dashboard Local Time 与本机浏览器时区一致。
2. 手动设置时区优先
   - 验收点：设置页改为 `America/New_York` 后，Dashboard/Jarvis prompt 使用纽约时间。
3. 日程/今天/明天语义
   - 验收点：跨时区用户问“今天/明天/今晚”时，不按服务器所在地理解。

## C. 推荐执行顺序
1. 先做用户验收：B1/B2/B3/B4 的最小必验，确认可演示主链路。
2. 同步补 P0 稳定性：LifeContextBus pending task、后台 task runner、benchmark。
3. 再补 P1 体验：token 级流式、Alfred intent、sidecar probe。
4. 最后做 P2/P4 产品化：本地生活真实质量、圆桌冲突仲裁、管家团队架构。

## D. 建议验收记录模板
```text
验收时间：
验收人：
环境：本地 / Docker / 路演机

心理关怀 B1：通过 / 不通过，问题：
圆桌 B2：通过 / 不通过，问题：
统一计划 B3：通过 / 不通过，问题：
私聊主链路 B4：通过 / 不通过，问题：
Athena B5：通过 / 不通过，问题：
本地生活 B6：通过 / 不通过，问题：
时间模块 B7：通过 / 不通过，问题：

最严重问题 Top 3：
1.
2.
3.
```
