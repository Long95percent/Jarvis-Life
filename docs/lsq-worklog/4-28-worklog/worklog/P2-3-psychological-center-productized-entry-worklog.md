# P2-3 心理中心产品化入口 worklog

## 对应原始设计

- 对应 `docs/lsq-worklog/待完成/05-心理关怀模块架构.md` 中“趋势分析层、关怀交互层、隐私边界”的产品入口要求：用户要在正常页面看到今日状态、趋势、解释、关怀和隐私控制。
- 对照 `docs/lsq-worklog/4-28-worklog/心理与圆桌全量完成指令.md`：本步完成 P2-3 产品化入口，不做速度调优和管家团队架构升级。

## 完成范围

- Jarvis 主页右侧栏保留并产品化“心理中心”入口。
- 心理中心展示今日状态：心情、压力、能量。
- 心理中心支持趋势图：本周/本月/全年，指标包括心情、压力、能量、睡眠、计划压力。
- 点击某天展示可解释详情：压力信号、行为信号、情绪证据、关怀触发、正向事件、负向事件、风险标签。
- 显示最近关怀摘要，并保留主动提醒区完整 CareCard 交互。
- 支持隐私开关：开启/关闭心理追踪。
- 支持清除心理数据。
- 增加“找 Mira 聊聊”入口，用户可从心理中心进入 Mira 私聊。
- 移除组件中的 Demo/MVP/后台调试式文案，改为面向用户的正常产品文案。

## 代码文件

- `shadowlink-web/src/components/jarvis/CareTrendsPanel.tsx`：重写为心理中心产品卡片，整合今日状态、趋势、详情、最近关怀、隐私操作。
- `shadowlink-web/src/components/jarvis/JarvisHome.tsx`：向心理中心传入最近关怀消息，并接入打开 Mira 的入口。

## 表与接口

- 读取 `GET /api/v1/jarvis/care/trends`：趋势与基础详情。
- 读取 `GET /api/v1/jarvis/care/days/{date}`：点击某日后的真实详情。
- 读取 `GET /api/v1/jarvis/care/settings`：心理追踪开关状态。
- 写入 `PATCH /api/v1/jarvis/care/settings/tracking`：开启/关闭心理追踪。
- 写入 `DELETE /api/v1/jarvis/care/data`：清除心理数据。
- 复用前端 store 中的 proactive messages：展示最近关怀摘要。

## 前端影响

- 用户在 Jarvis 主页右侧即可看到心理中心，不需要进入调试页。
- 心理中心是正常使用页面，不展示 Demo/MVP 字样。
- Mira 私聊、任务/计划、关怀卡片、心理趋势详情之间形成可路演闭环。

## 测试

- 已通过：`npm.cmd run type-check`（shadowlink-web）。
- 已通过：`pytest tests\unit\jarvis\test_care_trends.py tests\unit\jarvis\test_mood_snapshots.py tests\unit\jarvis\test_care_triggers.py -q`，结果 `21 passed`。
- 仍有既存 warning：pytest 配置中的 `asyncio_mode` 未识别、部分 `datetime.utcnow()` deprecation，不影响本步功能结论。

## 完成度变化

- P2-3 从“未完成”推进为“已完成”。
- 当前 `心理与圆桌全量完成指令.md` 中要求的心理模块、圆桌模块及必要计划联动步骤已逐项完成；速度调优和管家团队架构升级仍按用户要求不处理。

## 剩余缺口

- 本指令范围内无 P0/P1/P2-1/P2-2/P2-3 剩余缺口。
- 后续如果要继续，应另行确认是否进入速度调优、轻量管家团队架构升级、或更高阶心理分析能力。
