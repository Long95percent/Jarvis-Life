# StepB1 工作留痕：心理机制情绪采集层 MVP

日期：2026-04-28  
阶段：Phase 1 / B1  
模块：心理机制 - 情绪采集层 MVP  
对应主计划：`docs/lsq-worklog/4-28-worklog/4-28plan.md` Phase 1  
对照 checklist：`docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md` -> `五、05 心理关怀模块 Checklist` -> `A. 情绪采集层`  
对应原始设计：`docs/lsq-worklog/待完成/05-心理关怀模块架构.md`

## 一、重要声明

本次只完成 **B1 情绪采集层 MVP**，不是心理机制全量完成。

不能误判为完成的内容：

- 不是完整心理关怀模块。
- 不是每日心理快照层。
- 不是长期趋势层。
- 不是完整关怀触发层。
- 不是 LLM 结构化心理分析系统。
- 不是医疗诊断或心理诊断能力。

本次只把此前聊天触发型 `MoodSnapshot` MVP 往原始设计中的 `emotion observation` 持久化推进了一层。

## 二、本次完成范围

### 1. 新增情绪 observation 持久化表

表名：

```text
jarvis_emotion_observations
```

字段：

```text
id
session_id
turn_id
agent_id
primary_emotion
secondary_emotions
valence
arousal
stress_score
fatigue_score
risk_level
confidence
evidence_summary
signals_json
source
created_at
```

索引：

```text
idx_emotion_observations_created
idx_emotion_observations_session
idx_emotion_observations_risk
```

说明：

- `session_id` 用于追踪来自哪次私聊。
- `turn_id` 预留给后续和 `agent_chat_turns.id` 关联，本次 MVP 先允许为空。
- `evidence_summary` 只保存摘要，不保存用户心理原文全文。
- `signals_json` 保存规则识别到的信号，例如 `low_energy`、`stress_signal`、`sleep_signal`。
- `source=chat_rule_mvp`，明确当前来源是规则 MVP，不是全量 LLM 心理分析。

### 2. 新增 persistence DAO

文件：`shadowlink-ai/app/jarvis/persistence.py`

新增函数：

```text
save_emotion_observation()
list_emotion_observations()
```

内部函数：

```text
_save_emotion_observation_sync()
_list_emotion_observations_sync()
_row_to_emotion_observation()
```

能力：

- 保存单条 emotion observation。
- 按 `session_id` 查询。
- 按 `risk_level` 查询。
- 自动把 `secondary_emotions` 和 `signals_json` 从 JSON 字符串转回数组。

### 3. 将 MoodSnapshot 转成 observation payload

文件：`shadowlink-ai/app/jarvis/mood_care.py`

新增：

```text
MoodSnapshot.to_observation_payload()
build_evidence_summary()
```

映射内容：

- `mood_label` -> `primary_emotion`
- `signals` -> `secondary_emotions` / `signals_json`
- `stress_level` -> `stress_score`
- `10 - energy_level` -> `fatigue_score`
- `risk_level` -> `risk_level`
- 规则估算 `valence`、`arousal`、`confidence`
- `signals` 汇总成 `evidence_summary`

### 4. 在心理关怀闭环中写入 observation

文件：`shadowlink-ai/app/jarvis/mood_care.py`

改动函数：

```text
persist_mood_care()
```

新增行为：

- 当 `detect_mood_snapshot()` 识别出状态后，先调用 `save_emotion_observation()`。
- 保存成功后，把 `emotion_observation_id` 写回所有 care actions 的 `arguments`。
- 保持原有 `mood.snapshot` / `care.intervention` / `care.followup` 前端卡片不破坏。

## 三、代码文件

本次改动代码文件：

```text
shadowlink-ai/app/jarvis/persistence.py
shadowlink-ai/app/jarvis/mood_care.py
shadowlink-ai/tests/unit/jarvis/test_mood_care_observations.py
```

本次未改动前端 UI。

说明：前端现有 Step3 卡片仍消费 `actions`；本次只是给 action arguments 增加 `emotion_observation_id`，不会破坏卡片渲染。

## 四、表变更

新增表：

```text
jarvis_emotion_observations
```

新增索引：

```text
idx_emotion_observations_created
idx_emotion_observations_session
idx_emotion_observations_risk
```

迁移策略：

- 当前项目使用 demo-scale SQLite schema 初始化模式。
- 在 `SCHEMA` 中新增表。
- 在 `_ensure_initialized()` 中补充基础列兼容和索引创建，避免旧库缺少新增列时无法使用。

## 五、接口变化

本次没有新增 HTTP API。

原因：Phase 1 / B1 只要求情绪采集层 MVP，重点是 observation 持久化。

间接影响：

- `POST /v1/jarvis/chat` 在 Mira 心理触发场景下，返回的 `actions[].arguments` 可能新增：

```text
emotion_observation_id
```

示例：

```json
{
  "type": "mood.snapshot",
  "arguments": {
    "mood_label": "tired",
    "risk_level": "medium",
    "emotion_observation_id": "emo-..."
  }
}
```

## 六、测试

新增测试文件：

```text
shadowlink-ai/tests/unit/jarvis/test_mood_care_observations.py
```

覆盖 checklist 要求的五类输入：

1. 低能量：`我今天特别累，不想学了，也有点自责。`
2. 焦虑/压力：`我压力很大，焦虑到透不过气。`
3. 睡眠：`我最近睡不好，还经常熬夜。`
4. 高风险：`我有点活不下去了，不知道该怎么办。`
5. 无信号：`今天早餐吃了面包。`

额外验证：

- `persist_mood_care()` 会保存 emotion observation。
- observation 能按 `session_id` 查出。
- `evidence_summary` 不包含用户心理原文全文。
- care actions 中会带回 `emotion_observation_id`。

已执行命令：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
python -m py_compile app\jarvis\persistence.py app\jarvis\mood_care.py tests\unit\jarvis\test_mood_care_observations.py
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests\unit\jarvis\test_mood_care_observations.py -q
```

测试结果：

```text
6 passed
```

备注：

- 本机全局 pytest 插件会读取 `D:\sslkey.log` 并触发权限错误，因此本次测试使用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` 禁用外部 pytest 插件。
- 测试中出现 Python 3.12 `datetime.utcnow()` deprecation warning，属于既有代码风格问题，本次未扩展修复。

## 七、Checklist 完成度变化

对照 `原始设计完成度-checklist.md`：

### A. 情绪采集层

本次从：

```text
[MVP] Mira 私聊中规则识别低能量、压力、睡眠、回访、高风险关键词。
[TODO] 新增 jarvis_emotion_observations 表。
[TODO] 保存 primary_emotion、secondary_emotions、valence、arousal、stress_score、fatigue_score、risk_level、confidence、evidence_summary。
[TODO] 规则快速判断 + 必要时 LLM 结构化 JSON。
[TODO] 只保存摘要和指标，不重复保存心理原文。
[TODO] 单元测试覆盖低能量、焦虑、睡眠、高风险、无信号五类输入。
```

更新为：

```text
[MVP] 新增 jarvis_emotion_observations 表，已可保存聊天触发型情绪 observation。
[MVP] 保存 primary_emotion、secondary_emotions、valence、arousal、stress_score、fatigue_score、risk_level、confidence、evidence_summary，当前来源为规则 MVP。
[MVP] 已有规则快速判断并写入 observation；必要时 LLM 结构化 JSON 仍未实现。
[MVP] observation 只保存 evidence_summary、signals 和结构化指标，不保存用户心理原文全文。
[MVP] 单元测试覆盖低能量、焦虑/压力、睡眠、高风险、无信号五类输入，并验证 observation 不保存原文。
```

心理机制整体完成度建议变化：

```text
25% -> 32%
```

原因：

- 情绪采集层从“只在 action 中返回单轮状态”推进到“有正式 observation 表和持久化”。
- 但行为采集、日程压力、每日快照、长期趋势、触发预算、反馈学习、安全分级都未完成，因此仍是 MVP。

## 八、剩余缺口

### B1 内部剩余缺口

- `turn_id` 还未关联真实 `agent_chat_turns.id`。
- 目前 observation 来源是规则 MVP，没有必要时 LLM 结构化 JSON。
- `valence` / `arousal` / `confidence` 是规则估算，不是模型校准结果。
- 没有对 observation 暴露查询 API。
- 没有前端心理趋势面板消费 observation。

### 心理模块全量剩余缺口

仍未完成：

- `jarvis_behavior_observations` 行为采集层。
- `jarvis_stress_signals` 日程压力观测层。
- `jarvis_mood_snapshots` 日级快照层。
- `GET /care/trends?range=week|month|year` 长期趋势接口。
- `jarvis_care_triggers` 关怀触发层，包括 cooldown 和 daily care budget。
- `jarvis_care_interventions` 关怀交互层，包括 ack/snooze/accept/feedback。
- 高风险危机分级更细化和安全边界自动化文案测试。
- 用户可退出/关闭心理追踪的 settings。

## 九、下一步建议

严格按主计划，下一步应进入：

```text
Phase 2：心理机制 B2 行为采集层 MVP
```

建议目标：

- 新增 `jarvis_behavior_observations` 表。
- 记录用户最后活跃、深夜使用、超过 bedtime、连续在线等行为信号。
- 只作为疲劳/风险信号，不做诊断。
- worklog 继续写清完成范围、表、接口、测试、完成度变化和剩余缺口。
