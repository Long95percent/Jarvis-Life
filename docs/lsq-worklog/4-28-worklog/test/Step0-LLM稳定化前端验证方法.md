# Step 0 LLM API 轻量稳定化前端验证方法

日期：2026-04-28  
验证对象：`/api/v1/jarvis/llm-status`、Jarvis 私聊错误提示、Java Gateway 透传行为  
前提：需要同时启动 `shadowlink-ai`、`shadowlink-server/shadowlink-gateway` 和 `shadowlink-web`。

## 一、验证目标

确认 Step 0 的用户可见效果：

1. 前端可以通过状态接口看到当前 LLM 配置摘要。
2. API key 不会在前端明文出现，只显示是否存在和脱敏值。
3. 默认状态检查不真实调用 LLM，因此打开很快。
4. 加 `probe=true` 时才真实请求 Provider，并能区分鉴权失败、模型不存在、连接失败等错误。
5. Jarvis 私聊失败时，前端/Network 能看到明确 `error_code` 和 `suggestion`，不再只有泛化 500。
6. Java Gateway 对 Python AI 返回的错误保持透传；只有 Python AI 服务不可达时才返回 503。

## 二、推荐启动方式

### 1. 启动 Python AI 服务

在项目根目录执行：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

观察日志：

- 配置有效时，应看到类似 `llm_client_ready`。
- 配置无效时，服务仍应启动，但会看到 `llm_client_config_invalid` 和 `llm_client_not_ready`。
- 日志里只能出现脱敏 key，例如 `sk-1...abcd`，不能出现完整 API key。

### 2. 启动 Java Gateway

按项目当前方式启动 `shadowlink-server` / `shadowlink-gateway`。如果你平时用 IDE 启动，就保持原方式。

验证网关地址通常是：

```text
http://localhost:8080
```

### 3. 启动前端

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-web
npm run dev
```

打开前端页面，一般是：

```text
http://localhost:5173
```

## 三、从前端浏览器验证

### Case 1：默认 LLM 状态检查，不触发真实 LLM 调用

在浏览器直接打开：

```text
http://localhost:8080/api/v1/jarvis/llm-status
```

预期返回结构：

```json
{
  "ok": true,
  "config": {
    "base_url": "...",
    "model": "...",
    "api_key_present": true,
    "api_key_masked": "sk-1...abcd",
    "timeout_seconds": 120
  },
  "probe": {
    "enabled": false,
    "ok": null,
    "reply_preview": null
  },
  "error_code": null,
  "error": null,
  "suggestion": null
}
```

验收点：

- `probe.enabled` 必须是 `false`。
- `reply_preview` 必须是 `null`，说明没有真实调用 LLM。
- 不应出现完整 API key。
- 如果配置有效，`ok=true`。

### Case 2：真实探测 Provider

在浏览器直接打开：

```text
http://localhost:8080/api/v1/jarvis/llm-status?probe=true
```

配置正确时，预期：

```json
{
  "ok": true,
  "probe": {
    "enabled": true,
    "ok": true,
    "reply_preview": "OK"
  }
}
```

如果 Provider 不通或配置错误，预期：

```json
{
  "ok": false,
  "error_code": "LLM_PROVIDER_AUTH_FAILED",
  "error": "...",
  "suggestion": "请检查 API Key 是否有效...",
  "probe": {
    "enabled": true,
    "ok": false,
    "reply_preview": null
  }
}
```

常见错误码含义：

- `LLM_CONFIG_MISSING_API_KEY`：非本地 Provider 缺少 API key。
- `LLM_CONFIG_MISSING_MODEL`：模型名为空。
- `LLM_CONFIG_INVALID_BASE_URL`：Base URL 不是合法 `http://` 或 `https://` 地址。
- `LLM_PROVIDER_AUTH_FAILED`：Provider 返回 401/403。
- `LLM_PROVIDER_MODEL_NOT_FOUND`：模型不存在或无权限。
- `LLM_PROVIDER_ENDPOINT_NOT_FOUND`：Base URL endpoint 不对，常见于少了 `/v1`。
- `LLM_PROVIDER_RATE_LIMITED`：Provider 限流。
- `LLM_PROVIDER_TIMEOUT`：请求超时。
- `LLM_PROVIDER_UNREACHABLE`：网络或服务不可达。
- `LLM_PROVIDER_BAD_RESPONSE`：Provider 返回格式不兼容。

### Case 3：从前端 Jarvis 私聊验证错误提示

打开前端 Jarvis 私聊页面，向任意 Agent 发送一条简单消息，例如：

```text
你好，测试一下现在能不能回复。
```

在浏览器 DevTools 中查看：

```text
Network -> /api/v1/jarvis/chat
```

配置正确时：

- HTTP status 应为 200。
- 页面应正常出现 Agent 回复。

配置错误时：

- HTTP status 可能是 502 或 503，取决于错误类型。
- Response body 里应包含：
  - `error_code`
  - `error_type`
  - `error`
  - `suggestion`
  - `llm.base_url`
  - `llm.model`
  - `llm.api_key_present`
  - `llm.api_key_masked`
- Response body 不应包含完整 API key。

如果前端已经做了错误 toast/卡片展示，应能看到 `suggestion`，而不是只有 `Internal server error`。

## 四、故障注入验证

下面几项可以任选 2 到 3 项验证，不需要每次都全跑。

### 1. 缺少 API key

临时将 `shadowlink-ai/.env` 或运行环境中的：

```text
SHADOWLINK_LLM_API_KEY=
```

然后重启 Python AI。

打开：

```text
http://localhost:8080/api/v1/jarvis/llm-status
```

预期：

```json
{
  "ok": false,
  "error_code": "LLM_CONFIG_MISSING_API_KEY"
}
```

注意：如果 `base_url` 是 `localhost` / `127.0.0.1` 本地模型地址，允许没有 API key。

### 2. Base URL 非法

临时设置：

```text
SHADOWLINK_LLM_BASE_URL=dashscope
```

重启 Python AI 后打开：

```text
http://localhost:8080/api/v1/jarvis/llm-status
```

预期：

```json
{
  "ok": false,
  "error_code": "LLM_CONFIG_INVALID_BASE_URL"
}
```

### 3. 模型名错误

临时设置一个不存在的模型，例如：

```text
SHADOWLINK_LLM_MODEL=not-a-real-model
```

打开：

```text
http://localhost:8080/api/v1/jarvis/llm-status?probe=true
```

预期可能是：

```json
{
  "ok": false,
  "error_code": "LLM_PROVIDER_MODEL_NOT_FOUND"
}
```

不同 Provider 可能返回不同状态码；如果不是 404，也可能落到 `LLM_PROVIDER_HTTP_ERROR`，但必须有 `suggestion` 和脱敏配置。

### 4. Python AI 服务不可达

停止 `shadowlink-ai`，保持 Java Gateway 和前端运行。

打开：

```text
http://localhost:8080/api/v1/jarvis/llm-status
```

预期 Java Gateway 返回：

```json
{
  "success": false,
  "code": 503,
  "message": "Python AI service is unavailable",
  "data": {
    "error_type": "...",
    "error": "...",
    "suggestion": "请确认 shadowlink-ai 服务已启动..."
  }
}
```

验收点：这是网关层错误，说明 Python AI 不可达；不是 LLM Provider 错误。

## 五、通过标准

Step 0 可以认为验证通过，当满足：

- `/api/v1/jarvis/llm-status` 默认不调用 LLM，返回速度快。
- `/api/v1/jarvis/llm-status?probe=true` 能真实探测 Provider。
- 所有响应都不泄漏完整 API key。
- 配置错误能返回明确 `error_code` 和 `suggestion`。
- Python AI 不可达时，Java Gateway 返回 503 和明确提示。
- Jarvis 私聊失败时，前端 Network 能看到可定位错误，而不是只有泛化 500。

## 六、验证记录模板

```text
验证时间：
验证人：
前端地址：
Gateway 地址：
Python AI 地址：

Case 1 默认 llm-status：通过 / 不通过
截图或响应摘要：

Case 2 probe=true：通过 / 不通过
截图或响应摘要：

Case 3 Jarvis 私聊：通过 / 不通过
截图或响应摘要：

故障注入项：
结果：

是否发现完整 API key 泄漏：否 / 是
备注：
```
