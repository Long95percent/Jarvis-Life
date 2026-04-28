# P0-4 roundtable_results Schema 规范化 Worklog

## 对应原始设计
- 对应 `心理与圆桌全量完成指令.md` P0-4：规范 `roundtable_results` schema：`result_json`、`user_choice`、`handoff_status`。
- 对应原始圆桌设计的“圆桌产物可追踪、用户选择可记录、交接状态可恢复”。
- 本次是 schema 兼容升级，不声明圆桌模块全量完成。

## 完成范围
- `roundtable_results` 新增兼容字段：
  - `result_json`：保存结构化圆桌产物快照。
  - `user_choice`：保存用户后续选择，例如 accepted、save_as_memory、convert_to_plan、return_to_private_chat。
  - `handoff_status`：保存 none、pending、returned、saved_memory 等交接状态。
- 保存圆桌结果时会自动生成 `result_json`，保留旧字段 `summary/options_json/tradeoffs_json/actions_json/context_json` 兼容现有接口。
- 接受决策、保存 brainstorm、转计划、返回私聊时，会写入对应用户选择和交接状态。

## 代码文件
- `shadowlink-ai/app/jarvis/persistence.py`
  - `SCHEMA` 新增字段。
  - `_init_db()` 新增旧库迁移列。
  - `_row_to_roundtable_result()` 解析并回填 `result_json`。
  - `_save_roundtable_result_sync()` 支持 `result_json/user_choice/handoff_status`。
- `shadowlink-ai/app/api/v1/jarvis_router.py`
  - 接受、保存、转计划、返回接口写入规范状态字段。
- `shadowlink-ai/tests/unit/jarvis/test_roundtable_decision.py`
  - 新增 schema 字段暴露测试。

## 表 / 接口
- 表：`roundtable_results` 新增 `result_json TEXT NOT NULL DEFAULT '{}'`。
- 表：`roundtable_results` 新增 `user_choice TEXT`。
- 表：`roundtable_results` 新增 `handoff_status TEXT NOT NULL DEFAULT 'none'`。
- 接口：现有 decision/brainstorm/result/accept/save/plan/return 返回体会包含新字段。

## 前端影响
- 前端可直接读取 `result_json` 渲染完整圆桌产物，也可以继续用旧的 `summary/options/tradeoffs/actions/context` 字段。
- 前端可用 `user_choice` 和 `handoff_status` 判断按钮状态：已接受、已保存为记忆、已转计划、已返回私聊等。
- 旧页面不会因新字段破坏。

## 测试
- `python -m py_compile app\jarvis\persistence.py app\api\v1\jarvis_router.py tests\unit\jarvis\test_roundtable_decision.py`
- `pytest tests\unit\jarvis\test_roundtable_decision.py tests\unit\jarvis\test_roundtable_brainstorm.py -q`：7 passed。

## 完成度变化
- 圆桌结果从“分散旧字段 + 状态不统一”提升为“结构化产物 + 用户选择 + 交接状态”。
- 圆桌结果持久化完成度提升，但仍不标记为圆桌全量完成。

## 剩余缺口
- 前端需要进一步利用 `handoff_status` 禁用重复按钮、展示已交接状态。
- 历史旧数据的 `result_json` 会在读取时动态回填到返回体，但不会批量回写数据库。
