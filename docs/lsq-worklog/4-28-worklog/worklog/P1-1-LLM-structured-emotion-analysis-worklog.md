# P1-1 LLM 结构化情绪分析 fallback Worklog

## 对应原始设计
- 对应 `心理与圆桌全量完成指令.md` P1-1：心理分析不能只靠关键词规则，需要保留规则快速层，并在低置信度、多情绪混合、长文本倾诉、含糊表达时调用 LLM 输出结构化 JSON。
- 高风险场景仍必须走安全边界，不允许 LLM 把高风险降成低风险。
- 不保存用户心理原文全文。

## 完成范围
- 新增 `detect_mood_snapshot_enhanced()`：先跑规则层，再按条件决定是否调用 LLM。
- LLM 触发条件包括：规则无结果但文本较长、压力信号、多个情绪信号、长文本、含糊/复杂表达。
- LLM 输出 JSON 字段：`primary_emotion`、`secondary_emotions`、`valence`、`arousal`、`stress_score`、`fatigue_score`、`risk_level`、`confidence`、`evidence_summary`。
- LLM 失败时回退规则结果，不阻塞聊天。
- 高风险规则命中 `safety_risk_signal` 时不调用 LLM，保证安全边界不被覆盖。
- 聊天入口改为 Mira 相关对话使用增强检测。
- 持久化 emotion observation 时只保存结构化字段和概括，不保存用户原文全文。

## 代码文件
- `shadowlink-ai/app/jarvis/mood_care.py`
  - 新增 LLM 触发判断、JSON 提取、payload 归一化、增强检测函数。
  - `MoodSnapshot` 增加 `analysis_source` 与 `llm_payload` 用于前端 action/调试结构化来源。
  - emotion observation 持久化过滤非表字段，source 区分 `chat_llm_structured` 与 `chat_rule_mvp`。
- `shadowlink-ai/app/api/v1/jarvis_router.py`
  - Mira 私聊 mood snapshot 检测改为 `detect_mood_snapshot_enhanced(req.message, llm_client=llm_client)`。
- `shadowlink-ai/tests/unit/jarvis/test_mood_care_observations.py`
  - 新增混合表达 LLM 结构化测试。
  - 新增 LLM 失败回退规则测试。
  - 新增高风险表达不调用 LLM、保持 high risk 测试。

## 表 / 接口
- 表：未新增表，继续写 `jarvis_emotion_observations`。
- 表字段：继续使用 `primary_emotion`、`secondary_emotions`、`valence`、`arousal`、`stress_score`、`fatigue_score`、`risk_level`、`confidence`、`evidence_summary`、`signals_json`、`source`。
- 接口：未新增 HTTP 接口；Mira 私聊链路自动使用增强分析。

## 前端影响
- Mira 私聊中复杂表达更容易生成结构化状态记录/关怀卡。
- 前端 action arguments 里可看到 `analysis_source` 与 `llm_payload`，但不新增 MVP 展示面板。
- 用户正常体验是“更懂复杂表达”，而不是展示后台逻辑。

## 测试
- `python -m py_compile app\jarvis\mood_care.py app\api\v1\jarvis_router.py tests\unit\jarvis\test_mood_care_observations.py`：通过。
- `pytest tests\unit\jarvis\test_mood_care_observations.py -q`：10 passed。

## 完成度变化
- P1-1 从未完成变为已完成。
- 心理模块仍未全量完成；P1-2、P1-3、P2-1、P2-2、P2-3 仍需继续。

## 剩余缺口
- 需要继续 P1-2：mood snapshot 自动调度与 backfill。
- 后续可进一步把 LLM 结构化输出纳入 day detail 解释链路。
