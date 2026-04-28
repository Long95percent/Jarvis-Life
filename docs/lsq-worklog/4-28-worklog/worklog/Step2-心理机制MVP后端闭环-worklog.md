# Step 2 工作留痕：心理机制 MVP 后端闭环

日期：2026-04-28  
对应计划：`docs/lsq-worklog/4-28-worklog/4-28plan.md` 中 `Step 2：心理机制 MVP 后端闭环`  
验证文档：`docs/lsq-worklog/4-28-worklog/test/Step2-心理机制MVP后端闭环验证方法.md`

## 一、本 Step 目标

目标是让 Mira 不只是温柔回复，而是形成后端闭环：

1. 识别用户当前心理/精力状态信号。
2. 生成最小 `mood snapshot`。
3. 更新 `LifeContext`。
4. 返回结构化 care actions。
5. 必要时生成 proactive 回访消息。
6. 坚持非医疗定位：只做陪伴、状态记录、轻量建议和必要时求助提醒。

## 二、完成内容

### 1. 新增心理关怀模块

文件：`shadowlink-ai/app/jarvis/mood_care.py`

新增结构：

- `MoodSnapshot`
- `detect_mood_snapshot()`
- `build_care_actions()`
- `persist_mood_care()`

识别字段：

- `mood_label`
- `stress_level`
- `energy_level`
- `risk_level`
- `support_need`
- `next_checkin_at`
- `signals`

当前为规则 MVP，不依赖额外 LLM 调用，避免拖慢 Step1 中建立的速度基线。

### 2. Mira 私聊链路接入状态识别

文件：`shadowlink-ai/app/api/v1/jarvis_router.py`

改动：

- 在构造 prompt 前，对 Mira 相关私聊调用 `detect_mood_snapshot()`。
- 如果识别到状态信号，在 prompt 中加入 `Mira 心理陪伴上下文`。
- 明确提示：只做陪伴、状态记录、轻量建议和必要时求助提醒，不做医疗诊断。

### 3. 返回结构化 care actions

文件：`shadowlink-ai/app/api/v1/jarvis_router.py`

当识别到心理状态时，`actions` 会追加：

- `mood.snapshot`
- `care.intervention`
- `care.followup`

说明：

- `mood.snapshot`：状态记录。
- `care.intervention`：轻量关怀建议或安全提示。
- `care.followup`：后续回访动作，包含 `next_checkin_at` 和 `proactive_message_id`。

### 4. LifeContext 更新

文件：`shadowlink-ai/app/jarvis/mood_care.py`

`persist_mood_care()` 会通过 `get_life_context_bus().update_fields()` 更新：

- `stress_level`
- `sleep_quality`
- `mood_trend`

`LifeContextBus` 现有逻辑会异步写入 `life_context_snapshots`，因此刷新/后续上下文可以恢复趋势。

### 5. Proactive 回访消息

文件：`shadowlink-ai/app/jarvis/mood_care.py`

当出现以下情况时，保存 proactive message：

- 用户要求提醒/回访。
- `risk_level=medium`。
- `risk_level=high`。

保存方式：

- 复用 `ProactiveMessage` 模型。
- 复用 `save_proactive_message()`。
- `trigger=mood_care_followup`。
- 高风险时 `priority=high`。

### 6. 安全边界

高风险关键词触发后：

- `risk_level=high`。
- `care.intervention.description` 会提示优先保证安全。
- 建议联系身边可信任的人或当地紧急求助渠道。
- 不输出医疗诊断。

## 三、当前识别规则

### 低能量信号

关键词示例：

- 累
- 疲惫
- 没力气
- 不想动
- 不想学
- tired

### 压力信号

关键词示例：

- 压力
- 焦虑
- 烦
- 崩
- 撑不住
- 扛不住
- 透不过气
- 自责
- 难受

### 睡眠信号

关键词示例：

- 睡不好
- 失眠
- 睡眠
- 熬夜

### 回访信号

关键词示例：

- 提醒我
- 回访
- 晚点问我
- 稍后
- 今晚
- 明天

### 高风险安全信号

关键词示例：

- 不想活
- 自杀
- 伤害自己
- 结束生命
- 活不下去

## 四、已执行验证

### 1. Python 编译检查

验证文件：

```text
shadowlink-ai/app/jarvis/mood_care.py
shadowlink-ai/app/api/v1/jarvis_router.py
```

结果：通过。

### 2. 规则识别小测试

验证项：

- “我今天特别累，不想学了，也有点自责。” 能识别出低能量/压力信号。
- “今晚 9 点提醒我休息一下，别一直硬撑。” 能识别出 followup_requested。
- “我有点活不下去了。” 能识别出 high risk。

结果：通过。

说明：本轮没有强制真实调用 LLM。前端/接口验证方法见 Step2 验证文档。

## 五、影响范围

代码文件：

```text
shadowlink-ai/app/jarvis/mood_care.py
shadowlink-ai/app/api/v1/jarvis_router.py
```

文档文件：

```text
docs/lsq-worklog/4-28-worklog/test/Step2-心理机制MVP后端闭环验证方法.md
docs/lsq-worklog/4-28-worklog/Step2-心理机制MVP后端闭环-worklog.md
```

## 六、后续建议

Step3 前端最小展示可以直接消费 `actions`：

- `mood.snapshot` 渲染状态摘要。
- `care.intervention` 渲染 Mira 关怀卡片。
- `care.followup` 渲染“稍后提醒 / 不用了 / 我已处理”动作入口。

注意：当前 Step2 后端已经有 `proactive_message_id`，Step3 可以把它作为回写状态的关联 ID。
