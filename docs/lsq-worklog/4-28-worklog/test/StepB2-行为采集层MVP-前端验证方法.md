# StepB2 行为采集层 MVP 前端验证方法

## 验证目标

验证用户在前端 Agent 私聊页发送消息时，后端能自动记录行为采集层 MVP observation。

本验证只证明 B2 行为采集层 MVP 可用，不代表心理关怀模块全量完成。

## 前端 Demo 怎么操作

1. 启动后端和前端。
2. 打开 Jarvis 前端 Agent 私聊页。
3. 进入 Mira 私聊，或任意非 Shadow Agent 私聊。
4. 在白天发送第一条消息，例如：`我现在打开 Jarvis 准备学习。`
5. 等待回复完成后，再发送第二条消息，例如：`我又回来继续聊一下今天的计划。`
6. 停留在私聊面板 30 秒以上，观察底部“行为采集层 MVP”面板出现 `心跳在线`。
7. 切换到其他浏览器标签页再切回来，观察出现 `切到后台` / `回到前台`。
8. 关闭私聊面板再重新打开同一 session，观察出现 `关闭私聊`。
9. 如果要最大化展示潜力，把用户资料里的作息设置为 `23:00` 睡觉、`07:00` 起床，并在 23:30 以后发送消息。

## 预期现象

- 第一次发送消息后，后端应记录：
  - `first_active`
  - `last_active`
- 同一天同 session 第二次发送消息后，后端应继续记录：
  - `last_active`
  - `duration_minutes`
- 超过 bedtime 后发送消息，后端应额外记录：
  - `late_night_usage`
  - `beyond_bedtime`
  - `deviation_minutes`
- 停留、切后台、关闭私聊后，前端面板应展示：
  - `心跳在线`
  - `切到后台`
  - `回到前台`
  - `关闭私聊`

## 当前前端看不到什么

当前 B2 MVP 已在 Agent 私聊面板底部新增“行为采集层 MVP”小面板，可直接查看最近 behavior observations。

它仍不是完整心理趋势页，只用于 MVP 验证和 Demo 调试。

## 建议做的最佳 Demo

建议做一个“晚睡陪伴 Demo”：

1. 用户资料设置：
   - bedtime：`23:00`
   - wake：`07:00`
2. 用户在 23:45 打开 Mira 私聊并发送：
   - `我还没睡，感觉今天有点累但还想继续刷一会。`
3. 后端会同时产生：
   - 情绪采集层：低能量/睡眠相关 emotion observation。
   - 行为采集层：`late_night_usage`、`beyond_bedtime` behavior observation。
   - 每日快照层：behavior observation 已汇入 `sleep_risk_score` 和 `risk_flags`。

这个 Demo 最能展示 B1、B2、B4 之间的长期状态追踪潜力：不是单次弹窗，而是已经能把“主观表达 + 客观使用行为”合成每日心理快照；日程压力仍是后续缺口。

## 开发者辅助验证

后端测试命令：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
Remove-Item Env:SSLKEYLOGFILE -ErrorAction SilentlyContinue
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests\unit\jarvis\test_behavior_observations.py tests\unit\jarvis\test_mood_snapshots.py -q
```

通过标准：

- `3 passed`
- 允许出现已有 pytest 配置 warning。

## 产品化缺口

- 仍需要独立“心理趋势/行为信号”详情页。
- 仍需要把 behavior 信号长期趋势化，而不只是显示最近几条 observation。
- 仍需要更高精度的在线会话合并算法。
- 仍需要把日程压力、任务完成情况纳入每日心理快照。
