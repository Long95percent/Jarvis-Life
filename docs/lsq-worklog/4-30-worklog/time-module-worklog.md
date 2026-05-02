# 时间模块工作日志

## 2026-04-30 初始实现

### 需求
- 自动获取不同使用者所在地/本机时区对应的当前时间。
- 同时服务 Jarvis 对话、日程提醒、主动关怀，以及前端本地时间/世界时钟展示。
- 不依赖服务器所在地；支持用户手动设置城市/时区作为最高优先级。

### 设计决策
- 内部统一使用 IANA timezone，例如 `Asia/Shanghai`、`America/New_York`。
- 前端默认通过浏览器 `Intl.DateTimeFormat().resolvedOptions().timeZone` 获取设备时区。
- 后端提供时间上下文接口，负责校验时区并返回当前本地时间、UTC 偏移、日期等稳定字段。
- 用户 profile 或设置中的手动时区优先于浏览器自动检测值。

### 实施记录
- 开始巡检现有 Jarvis/profile/settings/time 相关代码。

### 2026-04-30 实施结果
- 新增后端 `app.jarvis.time_context`，统一解析 IANA timezone、生成本地时间上下文和 Jarvis prompt 时间行。
- `UserProfile.location` 新增 `timezone` 字段，默认 `Asia/Tokyo`，支持用户手动覆盖。
- 新增 `/api/v1/jarvis/time/context` GET/POST 接口，前端可传浏览器检测到的时区；已保存 profile 时区优先。
- Jarvis 聊天 prompt、日程每日维护、逾期标记、Maxwell workbench、圆桌决策上下文改为使用用户本地日期/时间，不再依赖服务器所在地。
- 前端 Dashboard 新增 Local Time 卡片，按后端返回时区每秒刷新显示。
- 设置页 Location 区域新增 Timezone(IANA) 输入框和“Use browser timezone”按钮。
- Python 依赖新增 `tzdata>=2024.1`，用于 Windows 环境解析 `America/New_York` 等 IANA 时区。

### 验证记录
- `python -m pytest shadowlink-ai\tests\unit\jarvis\test_time_context.py -q`：4 passed，1 个既有 pytest 配置 warning。
- `cd shadowlink-web; npm.cmd run type-check`：通过，exit 0。
- 尝试运行 `test_user_settings.py` 时遇到本机 pytest 临时目录权限问题：`C:\Users\22641\AppData\Local\Temp\pytest-of-22641` 与 `shadowlink-ai\.pytest_time_tmp` 拒绝访问；该问题与本次业务代码无关，需要清理/修复本机 pytest 临时目录权限后再跑更大范围测试。
- 初次验证发现 Windows 缺少 IANA tz 数据，已添加 `tzdata` 依赖并在当前环境安装验证。

## 2026-04-30 Review 修复：默认 profile 时区误判

### Review 问题
- 外部 review 指出：`Location.timezone` 默认 `Asia/Tokyo` 会被 `choose_timezone()` 当作用户显式保存的时区，导致新用户/未配置用户传入浏览器时区时仍显示东京时间。

### 根因判断
- 反馈成立。当前模型无法区分“系统默认 timezone”和“用户手动配置 timezone”。
- 正确行为应为：用户手动保存的时区优先；否则优先使用浏览器 `Intl` 检测时区；最后才 fallback 到系统默认时区。

### 修复方案
- 新增 `location.timezone_source` 字段，用来区分默认/自动值与用户手动保存值。
- `choose_timezone()` 优先级调整为：`timezone_source == manual` 的 profile timezone > 浏览器 timezone > profile 默认 timezone > 系统默认 timezone。
- `PATCH /profile` 保存 location.timezone 时自动标记 `timezone_source=manual`，确保用户手动设置后优先级最高。
- 前端默认 profile 使用 `timezone_source: auto`，设置页点击/输入时区时标记为 `manual`。

### 验证记录
- 新增回归测试：默认 `UserProfile()` + `browser_timezone=America/Los_Angeles` 必须返回 `America/Los_Angeles`。
- RED：修复前 `test_build_time_context_prefers_browser_timezone_for_default_profile` 失败，实际返回 `Asia/Tokyo`。
- GREEN：`python -m pytest shadowlink-ai\tests\unit\jarvis\test_time_context.py -q`：6 passed，1 个既有 pytest 配置 warning。
- `cd shadowlink-web; npm.cmd run type-check`：通过，exit 0。

### 后续留痕规则
- 时间模块后续修复/review 继续追加到本文件，不新建文件。
- 之后所有任务都必须在对应模块/任务日志中留痕；同一模块的后续修复和 review 追加到原文件。

## 2026-04-30 Bug 修复：浏览器定位后城市/时区仍显示旧值

### 问题现象
- 用户在南京，点击“使用浏览器定位”后页面仍显示苏州，时区甚至显示东京。

### 初步根因假设
- 浏览器 `navigator.geolocation` 只返回经纬度，不返回城市名；当前前端只更新 lat/lng，没有反查城市，也没有强制覆盖旧 label。
- 时区字段如果保留旧值或默认 `Asia/Tokyo`，会继续显示东京。
- 需要让“使用浏览器定位”至少根据浏览器 `Intl` 覆盖时区，并对中国经纬度提供本地可用的城市近似识别/明确标注，避免继续显示旧城市。

### 修复方案
- 后端新增 `suggest_location_from_browser_coordinates()`，根据浏览器经纬度给出位置建议；南京经纬度会识别为 `Nanjing`，时区为 `Asia/Shanghai`。
- 新增 `/api/v1/jarvis/time/browser-location`，供设置页在浏览器定位成功后获取城市/时区建议。
- 前端“使用浏览器定位”现在会覆盖旧 `label` 和旧 `timezone`，不再保留苏州/东京等旧值。
- 如果后端建议接口失败，前端也会 fallback 到 `Current Location` + 浏览器 `Intl` 时区，避免显示旧城市和错误时区。

### 验证记录
- RED：新增 `test_suggest_location_from_browser_coordinates_identifies_nanjing` 和 `test_suggest_location_from_browser_coordinates_clears_stale_label_when_unknown` 后，测试因缺少 helper 失败。
- GREEN：`python -m pytest shadowlink-ai\tests\unit\jarvis\test_time_context.py -q`：8 passed，1 个既有 pytest 配置 warning。
- `cd shadowlink-web; npm.cmd run type-check`：通过，exit 0。

### 用户复验建议
- 在南京点击“使用浏览器定位”。
- 期望：Latitude/Longitude 更新；Location label 显示 `Nanjing`；Timezone 显示 `Asia/Shanghai`；不再显示苏州或东京。
- 点击保存后，Dashboard Local Time 应显示中国本地时间。

## 2026-04-30 Review 修复：定位逻辑不能只对南京/苏州硬编码

### 问题反馈
- 当前修复用内置城市坐标表识别南京，只是局部兜底，不适用于其它地区用户。

### 修正方向
- 时区必须全局优先使用浏览器 `Intl.DateTimeFormat().resolvedOptions().timeZone`，不依赖城市表。
- 城市名应走通用反向地理编码；如果不可用，显示坐标型通用标签，不能继续显示旧城市。
- 后端不再维护南京/苏州等城市硬编码表作为定位主逻辑。

### 通用化修复方案
- 移除后端南京/苏州/东京等内置城市坐标表，不再用地区硬编码识别所在地。
- 后端 `/time/browser-location` 尝试调用 Nominatim/OpenStreetMap 反向地理编码获取通用城市/地区名称。
- 无论用户在哪个地区，时区都优先使用浏览器 `Intl` 返回的 IANA timezone。
- 反向地理编码失败时，label 使用 `Current Location (lat, lng)`，明确这是当前坐标，且不沿用旧城市。
- 该方案适用于所有地区：有网络/反向地理编码时显示真实地名；无网络时显示坐标标签 + 正确浏览器时区。

### 验证记录
- 新增/更新测试：反向地理编码 label 优先、未知地区清除旧 label、巴黎坐标使用 `Europe/Paris` 且不依赖中国城市表。
- `python -m pytest shadowlink-ai\tests\unit\jarvis\test_time_context.py -q`：9 passed，1 个既有 pytest 配置 warning。
- `cd shadowlink-web; npm.cmd run type-check`：通过，exit 0。

### 用户复验建议
- 在南京点击“使用浏览器定位”：有网络时应显示反向地理编码返回的南京/相关行政区；无网络时显示 `Current Location (纬度, 经度)`。
- 时区应始终显示浏览器时区，比如中国地区为 `Asia/Shanghai`，不会显示 `Asia/Tokyo`，除非用户手动输入并保存东京时区。


## 2026-04-30 ?????????

### ????
- ???`app/jarvis/time_context.py`?`app/api/v1/jarvis_router.py`?profile timezone ???????????/?????
- ???`jarvisApi.ts`?`jarvisStore.ts`?Dashboard Local Time ? Settings Profile ???/???????

### ?????
1. Jarvis ?? `/chat` ? `/chat/stream` ????????? `browser_timezone`?????????????/auto profile ??? prompt ?????????? auto ????? `Asia/Tokyo`???????????????
2. ?? prompt ???????????????????????? mojibake ???

### ??
- `/time/context` ??? browser timezone??????????? chat ????????????? prompt ??? `build_time_context(profile=profile)`?
- ?????????/??/?????????? prompt ?????? `??????` / `??????`?

### ??
- `AgentChatRequest` ?? `browser_timezone` ?????
- `chat_with_agent()` ?? prompt ??? life context ??? `req.browser_timezone`?
- ?? `jarvisApi.chat/chatStream` ????? `browser_timezone`?`jarvisStore.sendMessage()` ?? `Intl.DateTimeFormat().resolvedOptions().timeZone` ????????
- ???????prompt ????????????auto profile + invalid saved timezone ??? browser timezone ???manual invalid timezone ??????
- ?????????/auto profile ??? prompt ???????? `America/Los_Angeles`????? `Asia/Tokyo`?

### ????
- `python -m pytest tests/unit/jarvis/test_time_context.py -q`????`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` ??? `SSLKEYLOGFILE`??11 passed?1 ??? pytest ?? warning?
- `python -m pytest tests/integration/test_jarvis_api.py::test_chat_with_agent_uses_browser_timezone_for_default_profile -q`??? `SSLKEYLOGFILE`??1 passed?23 ??? warning??????????? pytest-asyncio ???? `pytest.mark.asyncio` ??????? datetime.utcnow deprecation??
- `cd shadowlink-web; npm.cmd run type-check`?exit 0?

### ????
- ???? pytest ???????? `SSLKEYLOGFILE=D:\sslkey.log` ??? `PermissionError: [Errno 13] Permission denied: 'D:\sslkey.log'`???????????????????
- ?? `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` ???????????? pytest ??????????????? anyio ????????????????????

## 2026-05-01 Bug 修复：个人资料位置获取/手动城市/天气联动失效

### 问题现象
- 个人资料点击“使用浏览器定位”后，位置字段没有按当前所在地更新，仍显示固定旧值。
- Dashboard 天气卡显示“位置未设置”。
- 个人资料手动填写城市后，没有解析成实际位置，也没有更新对应经纬度。
- 手动城市一般只有城市名，页面不应继续显示默认旧经纬度，应显示该城市解析后的默认经纬度。

### 调试方向
- 检查 SettingsProfile 保存逻辑、定位按钮逻辑、后端 profile patch 合并、local-life/weather 读取 profile 位置逻辑。
- 增加城市名解析/定位建议的回归测试后再改实现。

### 修复方案
- 个人资料“使用浏览器定位”现在不只是更新表单，而是：获取浏览器坐标 -> 调用后端位置建议 -> 自动 PATCH 保存 profile -> 广播 `jarvis:profile-updated`。
- Dashboard 天气卡监听 `jarvis:profile-updated`，profile 保存后会重新拉取 `/local-life` 和 `/profile`，避免继续显示“位置未设置”或旧天气。
- 新增 `POST /api/v1/jarvis/time/city-location`，支持用户输入城市名后解析默认经纬度。
- 个人资料城市输入框失焦或点击“解析并保存”会调用城市解析接口，并保存解析后的 `lat/lng/timezone/label`。
- 手动城市名不再保留 Tokyo 默认经纬度；解析成功后页面显示该城市的默认经纬度，天气和本地生活也按该坐标读取。

### 验证记录
- 新增 `suggest_location_from_city_name` 单测，覆盖城市名解析成功与未解析失败。
- RED：新增测试后因缺少 `suggest_location_from_city_name` 失败。
- GREEN：`python -m pytest shadowlink-ai\tests\unit\jarvis\test_time_context.py -q`：13 passed，1 个既有 pytest 配置 warning。
- `cd shadowlink-web; npm.cmd run type-check`：通过，exit 0。

### 用户复验建议
- 个人资料点击“使用浏览器定位”：应自动保存，城市/经纬度/时区更新；回到 Jarvis 仪表盘后天气卡刷新，不再显示位置未设置。
- 在城市输入框填 `Nanjing` / `南京` 后点击“解析并保存”或输入框失焦：经纬度应变为南京附近默认坐标，天气按南京获取。
- 若外部地理编码网络不可用，页面会提示城市解析失败；浏览器定位 fallback 仍会保存坐标标签。

## 2026-05-01 Bug 修复：定位结果必须回填城市、时区和当地天气

### 需求澄清
- 点击个人资料里的浏览器定位后，不仅要更新经纬度，还要解析所在地城市名和 IANA 时区。
- 定位成功后要基于该城市/坐标查询当地天气，并在前端显示。
- 该信息应同步保存到 profile，使 Jarvis 首页天气卡、本地生活和时间上下文都使用新位置。

### 初步问题判断
- 当前 `/time/browser-location` 主要返回 lat/lng/label/timezone，不返回 weather。
- 设置页保存后只通过事件刷新 Dashboard，但设置页自身没有天气预览，用户感知像“没查天气”。
- 需要让定位接口返回完整 location + weather，并让设置页立即展示。

### 修复方案
- `/time/browser-location` 现在返回完整定位结果：城市/地区 label、经纬度、浏览器 IANA 时区、当地天气 `weather`。
- 后端新增模块级 `_fetch_browser_location_metadata()`，统一做反向地理编码和 Open-Meteo 天气查询，便于测试与复用。
- `/time/city-location` 也会在城市名解析出经纬度后查询该城市天气并返回。
- 设置页新增“当前位置预览”，定位或城市解析后立即展示城市、时区、天气。
- 设置页定位/城市解析成功后仍会自动保存 profile，并广播 `jarvis:profile-updated`，使 Dashboard 天气卡按新城市刷新。

### 验证记录
- 新增接口测试：`test_browser_location_returns_city_timezone_and_weather`，断言定位接口返回城市、时区和 weather。
- `python -m pytest shadowlink-ai\tests\unit\jarvis\test_time_context.py -q`：13 passed，1 个既有 pytest 配置 warning。
- `python -m pytest shadowlink-ai\tests\integration\test_jarvis_api.py::test_browser_location_returns_city_timezone_and_weather -q`：1 passed，21 个既有 async marker warning。
- `cd shadowlink-web; npm.cmd run type-check`：通过，exit 0。

### 用户复验建议
- 点击个人资料“使用浏览器定位”：应回填城市/地区名、经纬度、浏览器时区，并在当前位置预览看到天气。
- 回到 Jarvis 首页：天气卡应刷新为该位置天气。
- 输入城市名并解析：同样应回填城市默认经纬度、时区和天气预览。

## 2026-05-01 Bug 排查：定位后仍显示 Current Location

### 问题现象
- 经纬度已能更新，但位置名仍显示 `Current Location`，说明城市名反查链路没有成功或前端没有使用反查结果。

### 排查计划
- 检查 `/time/browser-location` 是否实际做了反向地理编码。
- 检查 Nominatim 返回字段是否被正确读取，尤其中国地址可能返回 `city`、`town`、`county`、`state_district`、`province/state`，或只有 `display_name`。
- 检查前端是否把返回的 label 保存进 profile，并刷新展示。

### 本轮排查结论
- 链路里已经有城市名反查功能：`/time/browser-location` 调用 Nominatim/OpenStreetMap reverse geocode。
- 当前显示 `Current Location` 的直接原因是反向地理编码请求失败或返回字段未命中，之前失败被静默吞掉，前端无法知道城市名没解析成功。
- 本机实际请求 `https://nominatim.openstreetmap.org/reverse?...` 时出现“无法连接到远程服务器”，因此会进入 fallback。

### 修复方案
- 增强 `_pick_geocode_label()`：支持 `city_district`、`district`、`state_district`、`display_name` 等更多字段，避免有城市信息却没取到。
- 反向地理编码失败时，后端返回 `label_error`，不再静默失败。
- 前端设置页展示 `label_error`，用户能看到“城市名解析失败：网络或地理编码服务不可用/错误详情”。
- `Current Location (lat,lng)` 仍作为兜底标签，但它现在代表“城市名反查失败”，不是假装城市已解析成功。

### 验证记录
- `python -m pytest shadowlink-ai\tests\unit\jarvis\test_time_context.py::test_suggest_location_from_browser_coordinates_reports_label_error -q`：1 passed。
- `python -m pytest shadowlink-ai\tests\integration\test_jarvis_api.py::test_pick_geocode_label_supports_display_name_and_district_fields -q`：1 passed。
- `cd shadowlink-web; npm.cmd run type-check`：通过，exit 0。

### 后续产品建议
- 如果希望离线/内网环境也稳定解析城市名，需要接入可用的地理编码服务，或引入本地城市库/国内地图 API。当前 OpenStreetMap 反查在网络不可达时只能回退到坐标标签。

## 2026-05-01 方案：接入国内地图 API 解析城市名

### 设计目标
- 国内用户点击浏览器定位后，必须能稳定解析城市/区县名，不再依赖国外 OpenStreetMap 单点。
- 地图能力独立成 `app.jarvis.geocoding` 服务，Jarvis router 只依赖统一函数，不直接耦合高德 API。
- 默认优先国内地图 provider；没有 key 或请求失败时，再 fallback 到 OpenStreetMap；最后才显示坐标标签并返回错误原因。
- 天气仍通过已有 Open-Meteo weather adapter，使用最终解析/保存的经纬度。

### 配置建议
- 使用环境变量 `SHADOWLINK_GEOCODING_PROVIDER=amap`。
- 使用环境变量 `SHADOWLINK_AMAP_KEY=<高德Web服务Key>`。

## 2026-05-01 实现：国内地图 API 解耦接入

### 背景
- 用户确认需要使用国内地图 API，目标是点击“用浏览器定位”后能正确显示地区名，不再长期显示 `Current Location`。
- 根因是浏览器只能给经纬度，城市名必须后端反向地理编码；原实现直接在 Jarvis router 内调用 OpenStreetMap/Nominatim，国内网络环境不稳定且模块耦合偏重。

### 本次实现
- 新增 `app.jarvis.geocoding` 独立服务，封装地理编码能力，Jarvis router 不再直接耦合具体地图 API。
- 国内优先支持高德/AMap Web Service：
  - 反向地理编码：坐标 -> 城市/区县标签。
  - 正向地理编码：城市名 -> 默认经纬度和城市标签。
- 保留 OpenStreetMap 作为 fallback：高德未配置 key 或 auto 模式下高德失败时，可继续尝试 OSM。
- `/time/browser-location` 返回 `geocoding` 元信息，包含 provider、formatted_address、adcode 等可观测字段；天气继续按最终经纬度获取。
- `/time/city-location` 使用统一 `geocode_city()`，手动填写城市时返回该城市默认经纬度，不再沿用旧坐标。

### 配置说明
- 实际环境变量为：
  - `SHADOWLINK_GEOCODING_PROVIDER=auto` 或 `amap`。
  - `SHADOWLINK_GEOCODING_AMAP_KEY=<高德 Web 服务 Key>`。
- 示例已同步到根目录 `.env.example` 和 `shadowlink-ai/.env.example`。
- 不提交真实 API Key；生产/本机运行时写入 `.env`。

### 修改文件
- `shadowlink-ai/app/jarvis/geocoding.py`：新增统一地理编码服务与高德/OSM parser。
- `shadowlink-ai/app/api/v1/jarvis_router.py`：浏览器定位和城市定位改为调用 geocoding 服务。
- `shadowlink-ai/app/config.py`：新增 `geocoding` 配置分组。
- `shadowlink-ai/tests/unit/jarvis/test_geocoding.py`：新增高德解析与 OSM fallback parser 单测。
- `shadowlink-ai/tests/integration/test_jarvis_api.py`：旧 OSM label parser 测试迁移到 geocoding 服务。
- `.env.example`、`shadowlink-ai/.env.example`：新增地理编码配置示例。

### 验证记录
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_geocoding.py shadowlink-ai\tests\unit\jarvis\test_time_context.py -q`：17 passed，1 个既有 pytest config warning。
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\integration\test_jarvis_api.py::test_browser_location_returns_city_timezone_and_weather shadowlink-ai\tests\integration\test_jarvis_api.py::test_pick_geocode_label_supports_display_name_and_district_fields -q`：2 passed，存在既有 async marker warnings。
- `cd shadowlink-web; npm.cmd run type-check`：通过，exit 0。

### 后续验收点
- 本机 `.env` 配置高德 Web 服务 Key 后重启 AI 服务。
- 在个人资料点击“用浏览器定位”，南京坐标应显示南京市/对应区县，不应显示 `Current Location`。
- 手动输入城市名保存后，经纬度应变成该城市默认经纬度，天气卡片应刷新为该城市天气。

## 2026-05-01 Bug 修复：城市名解析失败仍出现

### 现象
- 用户反馈点击浏览器定位后仍显示“城市名解析失败”。

### 排查结论
- 本机实际配置检查结果：`SHADOWLINK_GEOCODING_AMAP_KEY` 未配置，运行时 `settings.geocoding.amap_key=False`。
- 因为没有高德 Key，后端进入 OSM fallback；而国内网络下 OSM/Nominatim 之前已确认不稳定或不可达，所以前端显示城市名解析失败。
- 同时发现前一版留痕里曾写过 `SHADOWLINK_AMAP_KEY`，但代码只读取 `SHADOWLINK_GEOCODING_AMAP_KEY`，存在配置名不一致风险。

### 本次修复
- `_GeocodingSettings` 增加向后兼容：优先读取 `SHADOWLINK_GEOCODING_AMAP_KEY`，如果为空则兼容读取旧变量 `SHADOWLINK_AMAP_KEY`。
- 当高德 Key 缺失时，错误信息明确包含 `SHADOWLINK_GEOCODING_AMAP_KEY`，方便前端和日志定位真实原因。
- `.env.example` 和 `shadowlink-ai/.env.example` 补充旧变量兼容说明，避免再次误配。

### 修改文件
- `shadowlink-ai/app/config.py`：兼容读取 `SHADOWLINK_AMAP_KEY`。
- `shadowlink-ai/app/jarvis/geocoding.py`：缺少高德 Key 时返回明确错误。
- `shadowlink-ai/tests/unit/jarvis/test_geocoding.py`：新增旧变量兼容和缺 key 错误测试。
- `.env.example`、`shadowlink-ai/.env.example`：补充配置说明。

### 验证记录
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_geocoding.py shadowlink-ai\tests\unit\jarvis\test_time_context.py -q`：19 passed，1 个既有 pytest config warning。
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\integration\test_jarvis_api.py::test_browser_location_returns_city_timezone_and_weather -q`：1 passed，存在既有 async marker warnings。
- `cd shadowlink-web; npm.cmd run type-check`：通过，exit 0。

### 当前验收前置
- 必须在实际运行的 AI 服务环境配置高德 Web 服务 Key：`SHADOWLINK_GEOCODING_AMAP_KEY=<key>`，或兼容写法 `SHADOWLINK_AMAP_KEY=<key>`。
- 配置后需要重启 AI 服务，否则进程仍会使用旧配置。

## 2026-05-01 功能：前端管理高德地图 API Key

### 需求
- 在前端 `设置 -> AI模型` 增加高德地图 API Key 输入、保存、删除能力。
- 保存后写入后端本地持久化，下次打开仍可使用。
- 删除时同步删除后端本地保存的 Key。
- 该能力仍归属于本地时间/定位模块，留痕继续写入本文件，不新建日志文件。

### 设计与实现
- 后端在 `settings_router` 新增通用外部服务 API Key 管理接口：
  - `GET /v1/settings/api-keys`：返回支持的外部服务 Key 状态，仅返回 `has_key` 和 masked key。
  - `PUT /v1/settings/api-keys/{key_id}`：保存或覆盖 Key。
  - `DELETE /v1/settings/api-keys/{key_id}`：删除后端本地保存的 Key。
- 本地持久化文件为 AI 服务数据目录下的 `api_keys.json`，沿用当前 LLM provider 的本地 JSON 持久化模式。
- 地理编码模块新增 `get_amap_api_key()`：优先读取前端保存的 `amap` Key；没有时再 fallback 到 `.env` 中的 `SHADOWLINK_GEOCODING_AMAP_KEY` / `SHADOWLINK_AMAP_KEY`。
- 前端 `SettingsLLM` 增加“外部服务 API Key”区块，显示高德地图 Key 是否已配置，支持保存覆盖和删除。

### 修改文件
- `shadowlink-ai/app/api/v1/settings_router.py`：新增外部 API Key CRUD 与本地持久化。
- `shadowlink-ai/app/jarvis/geocoding.py`：高德 Key 来源改为“前端保存优先，环境变量兜底”。
- `shadowlink-ai/tests/unit/jarvis/test_external_api_keys.py`：新增保存、列表遮罩、删除测试。
- `shadowlink-web/src/stores/settings-store.ts`：新增外部 API Key 状态与 save/delete actions。
- `shadowlink-web/src/components/settings/SettingsLLM.tsx`：新增高德地图 API Key 管理 UI。

### 验证记录
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_external_api_keys.py shadowlink-ai\tests\unit\jarvis\test_geocoding.py shadowlink-ai\tests\unit\jarvis\test_time_context.py -q --basetemp=shadowlink-ai\.pytest_time_tmp`：20 passed，1 个既有 pytest config warning。
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\integration\test_jarvis_api.py::test_browser_location_returns_city_timezone_and_weather -q --basetemp=shadowlink-ai\.pytest_time_tmp`：1 passed，存在既有 async marker warnings。
- `cd shadowlink-web; npm.cmd run type-check`：通过，exit 0。

### 验收方式
- 打开 `设置 -> AI模型 -> 外部服务 API Key`，输入高德 Web 服务 Key 并保存。
- 刷新页面后应显示高德地图 Key 已配置和 masked key。
- 回到个人资料点击浏览器定位，后端应优先使用前端保存的高德 Key 解析城市名。
- 点击删除后刷新页面，应显示未配置；后端 `api_keys.json` 中不再保留 `amap` Key。

## 2026-05-01 Bug 排查：高德 Key 保存后仍不生效

### 现象
- 用户在 `设置 -> AI模型 -> 外部服务 API Key` 输入并保存高德 Key 后，浏览器定位仍无法解析城市名。

### 排查结论
- 后端本地文件 `shadowlink-ai/data/api_keys.json` 已保存 `amap` Key，长度 32；说明前端保存链路成功。
- 原实现中 `geocoding.get_amap_api_key()` 为读取保存 Key 导入了 `app.api.v1.settings_router`，该导入会触发 `app.api.v1.__init__` 继续加载 Jarvis router、LangChain、requests 等重依赖；在本机 `SSLKEYLOGFILE=D:\sslkey.log` 权限问题下导入异常被 `except` 吞掉，导致 geocoding 实际没有读到已保存 Key。
- 解耦修复后，geocoding 已能读到保存的 Key：诊断显示 `geocoding_amap_len=32`。
- 联网诊断高德接口返回：`status=0`、`infocode=10009`、`info=USERKEY_PLAT_NOMATCH`。这说明当前保存的 Key 类型/平台与调用的高德 Web 服务接口不匹配，不是保存失败。

### 本次修复
- 新增 `app.jarvis.api_key_store`，把外部 API Key 本地持久化从 `settings_router` 中拆出来，避免 geocoding 依赖 API router 造成循环/重依赖。
- `settings_router` 改为复用 `api_key_store` 提供 CRUD 接口。
- `geocoding.get_amap_api_key()` 改为直接读取 `api_key_store`，保存的 Key 现在可稳定被定位模块读取。
- 高德返回业务错误时不再被 OSM fallback 覆盖；对 `10009 USERKEY_PLAT_NOMATCH` 等配置错误直接透传给前端。

### 修改文件
- `shadowlink-ai/app/jarvis/api_key_store.py`：新增外部 API Key 独立存储模块。
- `shadowlink-ai/app/api/v1/settings_router.py`：外部 API Key CRUD 改用独立 store。
- `shadowlink-ai/app/jarvis/geocoding.py`：读取保存 Key 解耦，并透传高德业务错误。
- `shadowlink-ai/tests/unit/jarvis/test_external_api_keys.py`：新增 geocoding 不导入 router 也能读取保存 Key 的测试。
- `shadowlink-ai/tests/unit/jarvis/test_geocoding.py`：新增高德配置错误不被 fallback 掩盖的测试。

### 验证记录
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_external_api_keys.py shadowlink-ai\tests\unit\jarvis\test_geocoding.py -q --basetemp=shadowlink-ai\.pytest_time_tmp`：8 passed，1 个既有 pytest config warning。
- 联网诊断：保存 Key 可被读取，`amap_key_len=32`；高德返回 `AMap error 10009: USERKEY_PLAT_NOMATCH`。
- `cd shadowlink-web; npm.cmd run type-check`：通过，exit 0。

### 用户侧处理
- 需要在高德开放平台创建或切换为“Web服务”类型 Key，不能使用 JS API、Android、iOS 等其它平台 Key。
- 如果 Key 设置了服务平台/白名单，需要允许当前服务端出口 IP 或取消不匹配限制。
- 重新在前端保存正确的 Web 服务 Key 后，再点击个人资料中的浏览器定位验收。

## 2026-05-01 Review 修复：API Key 文件与城市天气解耦

### Review 问题
- P1：`shadowlink-ai/data/api_keys.json` 是运行时生成的本地密钥文件，包含真实高德 Key，不能进入代码变更。
- P2：`/time/city-location` 中城市解析成功后直接 await 天气接口；天气服务失败会导致整个接口 500，阻断城市/经纬度保存。

### 修复内容
- 删除本地未跟踪的 `shadowlink-ai/data/api_keys.json`，避免真实 Key 泄露。
- `.gitignore` 增加 `data/api_keys.json` 和 `shadowlink-ai/data/api_keys.json`，确保后续前端保存的运行时 Key 不会被误提交。
- `suggest_city_location()` 中天气获取改为可选预览：天气失败时返回 `weather.error` 和 `is_good_weather=false`，但仍返回已解析的城市名、经纬度、时区和 geocoding 信息。
- 新增回归测试 `test_city_location_saves_when_weather_fails`，覆盖“天气失败不阻断城市保存”。

### 验证记录
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\integration\test_jarvis_api.py::test_city_location_saves_when_weather_fails shadowlink-ai\tests\integration\test_jarvis_api.py::test_browser_location_returns_city_timezone_and_weather -q --basetemp=shadowlink-ai\.pytest_time_tmp`：2 passed，存在既有 async marker warnings。
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_external_api_keys.py shadowlink-ai\tests\unit\jarvis\test_geocoding.py shadowlink-ai\tests\unit\jarvis\test_time_context.py -q --basetemp=shadowlink-ai\.pytest_time_tmp`：22 passed，1 个既有 pytest config warning。
- `cd shadowlink-web; npm.cmd run type-check`：通过，exit 0。
- `Test-Path shadowlink-ai\data\api_keys.json`：False。

## 2026-05-01 Review 修复：手动城市时区不应被后续浏览器时区覆盖

### Review 问题
- `suggest_location_from_city_name()` 在城市 geocode 结果没有 timezone 字段时，会使用浏览器 timezone。
- 但返回的 `timezone_source` 是 `browser`。
- `choose_timezone()` 只把 `timezone_source == "manual"` 视为权威保存时区。
- 结果：用户手动选择城市后，如果下一次从不同时区浏览器打开，时间上下文会被浏览器时区覆盖。

### 修复内容
- 城市名解析属于用户手动选择位置，因此即使 timezone 来自当前浏览器，也应随该城市选择一起保存为手动 profile 时区。
- 将 `suggest_location_from_city_name()` 返回的 `timezone_source` 从 `browser` 改为 `manual`。
- 浏览器经纬度定位链路保持 `timezone_source = browser`，不受影响。

### 修改文件
- `shadowlink-ai/app/jarvis/time_context.py`
- `shadowlink-ai/tests/unit/jarvis/test_time_context.py`

### 回归测试
- 新增 `test_suggest_location_from_city_name_marks_browser_timezone_as_manual_city_choice`。
- 覆盖场景：用户手动选择南京，保存 `Asia/Shanghai`；后续 `/time/context` 传入 `Europe/Paris` 浏览器时区时，仍应使用保存的 `Asia/Shanghai`。

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_time_context.py -q --basetemp=shadowlink-ai\.pytest_time_tmp2`
  - 结果：`15 passed, 1 warning`。
