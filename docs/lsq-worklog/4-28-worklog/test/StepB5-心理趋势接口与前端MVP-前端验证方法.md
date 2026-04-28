# StepB5 心理趋势接口与前端 MVP 前端验证方法

## 验证目标

验证 Jarvis 前端能从后端 `GET /api/v1/jarvis/care/trends` 读取心理趋势，并在“心理趋势中心 MVP”中展示周/月/年趋势与某一天的压力解释。

本验证只证明 B5 长期趋势层 MVP 可用，不代表心理关怀模块全量完成。

## 前端怎么操作

1. 启动后端和前端。
2. 打开 Jarvis 首页。
3. 查看右侧栏顶部的“心理趋势中心 MVP”。
4. 切换 `周 / 月 / 年` 下拉框。
5. 切换指标：心情、压力、能量、睡眠风险、日程压力。
6. 点击柱状/热度图里的某一天。
7. 查看下方“来源解释”：应展示 snapshot summary、stress signal reason、晚间行为信号等。
8. 点击“追踪已开启/追踪已关闭”验证开关真实生效。
9. 点击“清除心理数据”验证趋势数据被真实清空。

## 最佳 Demo 数据路径

为了让图表有明显变化，建议先完成以下 Demo 链路：

1. 在 Mira 私聊里输入低能量/压力文本，触发 B1 emotion observation。
2. 在超过 bedtime 后继续发消息或停留页面，触发 B2 behavior observation。
3. 添加多个当天日程、多个 Maxwell 任务 day，触发 B3 stress signals。
4. 让后端生成当天 mood snapshot。
5. 刷新 Jarvis 首页，查看心理趋势中心。

## 预期现象

- 周视图显示最近 7 天。
- 月视图显示最近 30 天。
- 年视图显示全年热力网格。
- 当前指标决定柱状/热力颜色和数值。
- 点击某一天后，能看到日程压力解释、晚间活跃解释和 snapshot summary。
- 前端文案会标明数据来自后端 snapshots，不是前端临时猜测。
- 关闭追踪后，B1/B2/B3 不再继续写入心理相关 observation/signal，趋势接口返回空序列。
- 清除心理数据后，emotion observations、behavior observations、stress signals、mood snapshots 都被删除。

## 开发者辅助验证

后端测试：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
Remove-Item Env:SSLKEYLOGFILE -ErrorAction SilentlyContinue
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests\unit\jarvis\test_care_trends.py -q
```

前端类型检查：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-web
npm.cmd run type-check
```

## 产品化缺口

- 仍未引入第三方折线图库。
- 仍未提供数据导出。
- 仍需要与任务、日程详情页做深度联动。
