# StepB4 工作留痕：每日心理快照层 MVP

日期：2026-04-28  
阶段：Phase 2 / B4  
模块：心理机制 - 每日心理快照层 MVP  
对应主计划：`docs/lsq-worklog/4-28-worklog/4-28plan.md` Phase 2  
对照 checklist：`docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md` -> `五、05 心理关怀模块 Checklist` -> `D. 每日心理快照层`  
对应原始设计：`docs/lsq-worklog/待完成/05-心理关怀模块架构.md`

## 一、重要声明

本次只完成 **B4 每日心理快照层 MVP**，不是心理机制全量完成。

不能误判为完成的内容：

- 不是完整心理趋势系统。
- 不是周/月/年趋势接口。
- 不是图表面板。
- 不是完整行为 + 日程压力 + 任务完成情况综合聚合。
- 不是完整 care trigger / intervention 系统。

本次目标只是把 B1 的 emotion observations 聚合成日级 `jarvis_mood_snapshots`。

## 二、本次完成范围

### 1. 新增每日心理快照表

表名：

```text
jarvis_mood_snapshots
```

字段：

```text
date
mood_score
stress_score
energy_score
sleep_risk_score
schedule_pressure_score
dominant_emotions
positive_events
negative_events
risk_flags
summary
confidence
created_at
updated_at
```

索引：

```text
idx_mood_snapshots_updated
```

说明：

- `date` 为主键，表示日级快照。
- `dominant_emotions`、`positive_events`、`negative_events`、`risk_flags` 使用 JSON 数组保存。
- 当前 `schedule_pressure_score=0.0`，因为 B3 日程压力层尚未实现。
- 当前 positive events 暂为空，后续需要从正向情绪 observation 或用户反馈中补齐。

### 2. 新增 mood snapshot DAO

文件：`shadowlink-ai/app/jarvis/persistence.py`

新增函数：

```text
upsert_mood_snapshot()
list_mood_snapshots()
```

内部函数：

```text
_upsert_mood_snapshot_sync()
_list_mood_snapshots_sync()
_row_to_mood_snapshot()
```

能力：

- 按日期 upsert 一条日级快照。
- 按 `start/end` 查询快照列表。
- 自动反序列化 JSON 数组字段。

### 3. 扩展 emotion observation 查询

文件：`shadowlink-ai/app/jarvis/persistence.py`

`list_emotion_observations()` 新增：

```text
created_from
created_to
```

用途：

- 聚合某一天 00:00 到次日 00:00 的 emotion observations。

### 4. 新增聚合模块

文件：`shadowlink-ai/app/jarvis/mood_snapshot.py`

新增函数：

```text
build_snapshot_payload()
aggregate_mood_snapshot()
```

聚合逻辑：

- 从当天 emotion observations 读取：
  - `primary_emotion`
  - `valence`
  - `stress_score`
  - `fatigue_score`
  - `risk_level`
  - `confidence`
  - `signals_json`
- 计算：
  - `mood_score`
  - `stress_score`
  - `energy_score`
  - `sleep_risk_score`
  - `dominant_emotions`
  - `negative_events`
  - `risk_flags`
  - `summary`
  - `confidence`

风险标记：

```text
high_risk_observation
repeated_medium_risk
fatigue_high
stress_high
```

### 5. Mira 心理触发后自动聚合当天快照

文件：`shadowlink-ai/app/jarvis/mood_care.py`

改动：

- `persist_mood_care()` 在保存 emotion observation 后，会调用 `aggregate_mood_snapshot()`。
- 如果生成成功，会把 `daily_mood_snapshot_date` 写回 care actions 的 `arguments`。

### 6. 新增查询接口

文件：`shadowlink-ai/app/api/v1/jarvis_router.py`

新增接口：

```text
GET /v1/jarvis/care/snapshots?start=YYYY-MM-DD&end=YYYY-MM-DD&limit=60
```

经 Gateway 可访问：

```text
GET /api/v1/jarvis/care/snapshots?start=YYYY-MM-DD&end=YYYY-MM-DD&limit=60
```

返回：

```json
[
  {
    "date": "2026-04-28",
    "mood_score": 2.75,
    "stress_score": 7.5,
    "energy_score": 3.5,
    "sleep_risk_score": 2.0,
    "schedule_pressure_score": 0.0,
    "dominant_emotions": ["tired", "stressed"],
    "risk_flags": ["repeated_medium_risk", "stress_high", "fatigue_high"],
    "summary": "...",
    "confidence": 0.76
  }
]
```

## 三、代码文件

本次改动代码文件：

```text
shadowlink-ai/app/jarvis/persistence.py
shadowlink-ai/app/jarvis/mood_snapshot.py
shadowlink-ai/app/jarvis/mood_care.py
shadowlink-ai/app/api/v1/jarvis_router.py
shadowlink-ai/tests/unit/jarvis/test_mood_snapshots.py
```

## 四、表变更

新增表：

```text
jarvis_mood_snapshots
```

新增索引：

```text
idx_mood_snapshots_updated
```

## 五、接口变化

新增接口：

```text
GET /v1/jarvis/care/snapshots
```

参数：

```text
start: 可选，YYYY-MM-DD
end: 可选，YYYY-MM-DD
limit: 默认 60
```

说明：

- 这是日级 snapshot 查询接口。
- 不是长期趋势接口。
- 周/月/年趋势图仍属于后续 Phase。

## 六、测试

新增测试文件：

```text
shadowlink-ai/tests/unit/jarvis/test_mood_snapshots.py
```

覆盖主计划测试任务：

1. 当天多条 emotion observations 能聚合成一条 snapshot。
2. 无数据当天不生成误导性高风险结论。
3. 高风险 observation 能进入 `risk_flags`。

已执行命令：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
python -m py_compile app\jarvis\persistence.py app\jarvis\mood_snapshot.py app\jarvis\mood_care.py app\api\v1\jarvis_router.py tests\unit\jarvis\test_mood_snapshots.py
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests\unit\jarvis\test_mood_snapshots.py -q
```

测试结果：

```text
3 passed
```

备注：

- 本机全局 pytest 插件会读取 `D:\sslkey.log` 并触发权限错误，因此本次测试使用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` 禁用外部 pytest 插件。

## 七、Checklist 完成度变化

对照 `原始设计完成度-checklist.md`：

### D. 每日心理快照层

本次从：

```text
[MVP] 当前有单轮 MoodSnapshot action，但不是日级快照。
[TODO] 新增 jarvis_mood_snapshots 表。
[TODO] 字段包括 date、mood_score、stress_score、energy_score、sleep_risk_score、schedule_pressure_score、dominant_emotions、positive_events、negative_events、risk_flags、summary、confidence。
[TODO] 每天定时或用户启动时聚合情绪、行为、压力、任务完成情况。
[REWORK] 当前 mood.snapshot action 命名容易和日级 snapshot 混淆，后续需区分 observation card 与 daily snapshot。
```

更新为：

```text
[MVP] 新增 jarvis_mood_snapshots 表，可保存日级综合状态。
[MVP] 字段包括 date、mood_score、stress_score、energy_score、sleep_risk_score、schedule_pressure_score、dominant_emotions、positive_events、negative_events、risk_flags、summary、confidence、created_at、updated_at。
[MVP] Mira 心理触发后可聚合当天 emotion observations 生成日级 snapshot；行为、压力、任务完成情况尚未纳入。
[MVP] 已在 worklog 中明确区分单轮 mood.snapshot action 与日级 jarvis_mood_snapshots；前端命名仍需后续统一调整。
```

心理机制整体完成度建议变化：

```text
32% -> 42%
```

注意：主计划原先按 Phase 1 完成度估算为 35% -> Phase 2 45%。由于当前 B1 实际落地后我保守估算为 32%，本次 B4 后建议为 42%。仍未达到全量完成。

## 八、剩余缺口

B4 内部剩余缺口：

- 当前快照只聚合 emotion observations。
- 尚未纳入 `jarvis_behavior_observations`。
- 尚未纳入 `jarvis_stress_signals`。
- 尚未纳入任务完成情况、逾期、重排、休息窗口。
- `positive_events` 暂为空。
- `schedule_pressure_score` 暂为 0。
- 没有定时任务每天自动生成，仅在 Mira 心理触发后生成。
- 前端还没有今日状态摘要面板。

心理模块全量剩余缺口：

- B2 行为采集层。
- B3 日程压力观测层。
- B5 长期趋势层。
- B6 关怀触发层 cooldown / budget。
- B7 关怀交互层 ack/snooze/accept/feedback。
- B8 安全边界更细危机分级和自动化文案测试。

## 九、下一步建议

严格按主计划，下一步应进入：

```text
Phase 3：心理机制 B2 行为采集层 MVP
```

建议目标：

- 新增 `jarvis_behavior_observations` 表。
- 记录首次活跃、最后活跃、深夜使用、超过 bedtime。
- 复用用户资料中的 bedtime / wake。
- 当前可先从聊天行为推断，不阻塞后端表设计。
