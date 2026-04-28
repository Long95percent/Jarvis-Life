# Step 0 工作留痕：LLM API 轻量稳定化

日期：2026-04-28  
对应计划：`docs/lsq-worklog/4-28-worklog/4-28plan.md` 中 `Step 0：LLM API 轻量稳定化`  
验证文档：`docs/lsq-worklog/4-28-worklog/test/Step0-LLM稳定化前端验证方法.md`

## 一、本 Step 目标

本 Step 的目标不是做完整 LLM 配置中心，而是把当前 LLM 调用链路变得可诊断、可验收、不会泄漏 key：

1. 配置读取后先做本地快速校验。
2. API key 只允许脱敏展示。
3. `/jarvis/llm-status` 默认不真实调用 Provider。
4. `?probe=true` 时才真实探测 Provider。
5. Provider 错误映射为稳定 `error_code`。
6. Jarvis 对话失败时返回可定位 `suggestion`。
7. Java Gateway 继续只做 Python AI 可达性判断和错误透传。

## 二、完成内容

### 1. 新增运行时配置模块

文件：`shadowlink-ai/app/llm/runtime_config.py`

新增内容：

- `LLMErrorCode`
- `LLMRuntimeConfig`
- `LLMRuntimeError`
- `mask_api_key`
- `current_llm_config`
- `validate_current_llm_config`

作用：

- 从 `settings.llm` 读取当前配置。
- 生成安全的配置摘要。
- 校验 `base_url`、`model`、`api_key`。
- 把配置问题转为统一错误码和建议。

### 2. 增强 LLMClient 初始化

文件：`shadowlink-ai/app/llm/client.py`

改动：

- `initialize()` 调用 `validate_current_llm_config()`。
- 初始化日志打印 `base_url`、`model`、`api_key_masked`。
- 配置错误时记录 `_initialization_error`，不阻塞 Python AI 服务启动。
- 后续真实聊天调用时，如果 Provider 未初始化，则抛出标准 `LLMRuntimeError`。

原因：

- 避免服务启动时直接崩掉。
- 让 `/jarvis/llm-status` 可以明确告诉用户配置哪里错。
- 避免用户聊天时只看到不可定位的 500。

### 3. Provider 错误统一映射

文件：`shadowlink-ai/app/llm/providers/openai.py`

改动：

- 新增 `_map_http_error()`。
- 新增 `_map_request_error()`。
- 将 `httpx.HTTPStatusError` / timeout / connect error / bad JSON / bad response format 映射成稳定错误码。

当前映射：

- `401/403` -> `LLM_PROVIDER_AUTH_FAILED`
- `404` 且像模型问题 -> `LLM_PROVIDER_MODEL_NOT_FOUND`
- `404` 其他 -> `LLM_PROVIDER_ENDPOINT_NOT_FOUND`
- `429` -> `LLM_PROVIDER_RATE_LIMITED`
- timeout -> `LLM_PROVIDER_TIMEOUT`
- connect error -> `LLM_PROVIDER_UNREACHABLE`
- 非 JSON 或响应结构异常 -> `LLM_PROVIDER_BAD_RESPONSE`
- 其他 HTTP 错误 -> `LLM_PROVIDER_HTTP_ERROR`

顺手修复：

- `temperature=0` 不再被 `settings.llm.temperature` 覆盖。
- `max_tokens=0` 虽然正常不会传，但也改为只在 `None` 时走默认值。

### 4. 增强 Jarvis LLM 状态接口

文件：`shadowlink-ai/app/api/v1/jarvis_router.py`

接口：

```text
GET /v1/jarvis/llm-status
GET /v1/jarvis/llm-status?probe=true
```

改动：

- 默认只做本地配置校验，不真实调用 LLM。
- `probe=true` 时才调用一次最小 LLM 探测。
- 返回结构统一为：
  - `ok`
  - `config`
  - `probe`
  - `error_code`
  - `error`
  - `suggestion`
- `config` 中只包含 `api_key_present` 和 `api_key_masked`，不返回明文 key。

### 5. 增强 Jarvis 聊天错误详情

文件：`shadowlink-ai/app/api/v1/jarvis_router.py`

改动：

- `_chat_error_detail()` 支持读取 `LLMRuntimeError.code` 和 `suggestion`。
- 兼容旧异常文本推断错误码。
- 返回的 `llm` 信息改为脱敏摘要。

目的：

- 前端可以直接展示 `suggestion`。
- 开发者可以根据 `error_code` 快速定位问题。
- 不再把所有 Provider 问题都表现为模糊 500。

### 6. Settings 接口 key 脱敏统一

文件：`shadowlink-ai/app/api/v1/settings_router.py`

改动：

- `/settings/llm` 使用 `mask_api_key()`。
- 避免空 key 或短 key 显示异常。

### 7. 启动日志状态区分

文件：`shadowlink-ai/app/core/lifespan.py`

改动：

- LLM 配置有效时记录 `llm_client_ready`。
- LLM 配置无效时记录 `llm_client_not_ready`。
- 服务仍继续启动，方便用户访问状态接口查看原因。

### 8. Java Gateway 核对

文件：`shadowlink-server/shadowlink-gateway/src/main/java/com/shadowlink/gateway/controller/JarvisProxyController.java`

结论：无需新增改动。

已确认现有行为满足 Step 0：

- Python AI 返回 4xx/5xx：Gateway 透传 status、body、content-type。
- Python AI 服务不可达：Gateway 返回 503 `Python AI service is unavailable`。
- Gateway 不解析 LLM Provider 细节。

## 三、已执行验证

### 1. Python 编译检查

执行范围：

```text
shadowlink-ai/app/llm/runtime_config.py
shadowlink-ai/app/llm/client.py
shadowlink-ai/app/llm/providers/openai.py
shadowlink-ai/app/api/v1/jarvis_router.py
shadowlink-ai/app/api/v1/settings_router.py
shadowlink-ai/app/core/lifespan.py
```

结果：通过。

### 2. 运行时配置小测试

验证项：

- 空 API key 脱敏为 `(empty)`。
- 普通 key 脱敏为前 4 位 + 后 4 位。
- 非法 Base URL 返回 `LLM_CONFIG_INVALID_BASE_URL`。
- 非本地 Provider 缺 key 返回 `LLM_CONFIG_MISSING_API_KEY`。
- 本地 `localhost` Provider 允许没有 API key。

结果：通过，输出：

```text
runtime_config_checks_ok
```

### 3. Gateway 行为核对

通过阅读 `JarvisProxyController` 核对：

- `WebClientResponseException` 分支透传 Python AI response。
- `WebClientRequestException` 分支返回 503 和 AI 服务不可达提示。

结果：符合 Step 0 要求。

## 四、前端验收入口

推荐从浏览器验证：

```text
http://localhost:8080/api/v1/jarvis/llm-status
http://localhost:8080/api/v1/jarvis/llm-status?probe=true
```

详细步骤见：

```text
docs/lsq-worklog/4-28-worklog/test/Step0-LLM稳定化前端验证方法.md
```

## 五、影响范围

涉及文件：

```text
shadowlink-ai/app/llm/runtime_config.py
shadowlink-ai/app/llm/client.py
shadowlink-ai/app/llm/providers/openai.py
shadowlink-ai/app/api/v1/jarvis_router.py
shadowlink-ai/app/api/v1/settings_router.py
shadowlink-ai/app/core/lifespan.py
```

文档文件：

```text
docs/lsq-worklog/4-28-worklog/4-28plan.md
docs/lsq-worklog/4-28-worklog/test/Step0-LLM稳定化前端验证方法.md
docs/lsq-worklog/4-28-worklog/Step0-LLM_API轻量稳定化-worklog.md
```

## 六、后续注意

- 后续每个 Step 都需要单独写一个工作留痕文件，放在 `docs/lsq-worklog/4-28-worklog` 下。
- 测试/验证说明放在 `docs/lsq-worklog/4-28-worklog/test` 下。
- 不要在日志、前端响应、文档示例中写真实 API key。
- 如果前端要做 UI 面板，可以直接消费 `/api/v1/jarvis/llm-status` 的 `ok/error_code/suggestion/config`。
