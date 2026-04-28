# StepB6B7 关怀触发与反馈闭环 前端验证方法

## 验证目标

验证关怀提醒不是静态展示，而是从后端 care trigger 生成 proactive message，前端 CareCard 操作会真实回写反馈、snooze 和降频。

本验证只证明 B6/B7 MVP 可用，不代表心理关怀模块全量完成。

## 前端怎么操作

1. 启动后端和前端。
2. 打开 Jarvis 首页右侧“主动提醒”。
3. 通过 Demo 数据制造高压力/任务过载/连续晚睡信号，或先跑后端测试种子逻辑。
4. 等待/刷新 proactive messages。
5. 在主动提醒里看到 `Mira 关怀卡片`。
6. 分别点击：
   - `有帮助`
   - `太频繁`
   - `稍后提醒`
   - `不需要这类`
   - `我已处理`
7. 再刷新主动提醒列表，观察状态变化。

## 预期现象

- `稍后提醒` 后，该 message 在 snooze 到期前不会再出现在主动提醒列表。
- `太频繁` 或 `不需要这类` 后，后续触发 daily budget 降低，减少当天/近期提醒。
- `我已处理` / `有帮助` 会标记干预已处理，并更新 proactive message 状态。
- 高风险文案不会说“你得了某种病”，只提示联系可信任的人和当地紧急求助渠道。

## 最佳 Demo 路径

1. 连续三天生成高 stress snapshot，触发 `stress_streak`。
2. 连续三天生成 `late_night_usage` 或 `beyond_bedtime`，触发 `late_night_streak`。
3. 当天生成 `task_load_high` 或 `schedule_density_high` stress signal，触发 `task_overload`。
4. 生成包含 `high_risk_observation` 的 snapshot，触发高风险安全边界文案。

## 开发者辅助验证

后端测试：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
Remove-Item Env:SSLKEYLOGFILE -ErrorAction SilentlyContinue
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests\unit\jarvis\test_care_triggers.py -q
```

前端类型检查：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-web
npm.cmd run type-check
```

## 产品化缺口

- 用户主动求助触发还未完全统一进 care trigger rule。
- 危机分级仍需更细。
- feedback 尚未沉淀为长期个性化频率画像。
- suggested action 尚未直接生成 Maxwell 待确认日程调整卡。
