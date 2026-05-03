# 个人画像页面接口说明

更新时间：2026-05-02

## 1. 当前结论

`/knowledge` 路由暂时不再展示知识库上传面板，改为展示「个人画像」。前端页面仍然复用 `KnowledgePage` 组件名，避免大范围改路由。

本次不新增后端接口，不删除 RAG 相关服务文件，只把页面展示切到已有接口组合。

## 2. 前端可以改什么

前端开发人员可以改这些文件里的展示、布局、文案、样式：

- `shadowlink-web/src/pages/KnowledgePage.tsx`
- `shadowlink-web/src/components/layout/Sidebar.tsx`
- `shadowlink-web/src/components/jarvis/JarvisTopBar.tsx`

注意：如果只是重新排版个人画像页面，优先只改 `shadowlink-web/src/pages/KnowledgePage.tsx`。

## 3. 前端不能直接改什么

- 不要在页面或组件里直接写 `fetch('/api/...')`。
- 不要在页面或组件里直接拼后端 URL。
- 不要为了这个页面改后端接口路径。
- 不要删除 `shadowlink-web/src/services/ragApi.ts`，RAG 后续可能恢复。
- 不要删除 ambient mode 相关 store/theme 文件，本次只是隐藏模式切换入口。

## 4. 页面读取的数据

个人画像页只通过前端服务层读数据：

```ts
jarvisSettingsApi.getProfile(): Promise<UserProfile>
jarvisSettingsApi.getShadowProfile(): Promise<ShadowProfile | null>
jarvisMemoryApi.listMemories({ limit: 12 }): Promise<JarvisMemory[]>
```

调用位置：`shadowlink-web/src/pages/KnowledgePage.tsx`

## 5. 接口边界

### 5.1 用户基础资料

服务文件：`shadowlink-web/src/services/jarvisSettingsApi.ts`

页面调用：

```ts
jarvisSettingsApi.getProfile()
```

页面使用字段：

```ts
profile.name
profile.occupation
profile.location.label
profile.location.timezone
profile.sleep_schedule.bedtime
profile.sleep_schedule.wake
profile.interests
profile.diet_restrictions
```

### 5.2 Shadow Learner 学到的偏好

服务文件：`shadowlink-web/src/services/jarvisSettingsApi.ts`

页面调用：

```ts
jarvisSettingsApi.getShadowProfile()
```

页面使用字段：

```ts
shadowProfile.preferences
shadowProfile.interaction_count
shadowProfile.last_updated
```

### 5.3 长期记忆摘要

服务文件：`shadowlink-web/src/services/jarvisMemoryApi.ts`

页面调用：

```ts
jarvisMemoryApi.listMemories({ limit: 12 })
```

页面使用字段：

```ts
memory.id
memory.memory_kind
memory.content
memory.importance
```

## 6. 模式切换处理

全局暂时默认生活总管，不再让用户在侧边栏切换「生活总管、全速工作、深度学习」等模式。

本次做法：

- `shadowlink-web/src/components/layout/Sidebar.tsx` 不再渲染 `ModeSwitcher`。
- 不删除 `shadowlink-web/src/components/ambient/ModeSwitcher.tsx`。
- 不删除 ambient store/theme 基础设施。

这样以后如果要恢复模式切换，只需要重新接回入口，不需要重做底层逻辑。

## 7. 协作规则

前端开发人员要改个人画像时，按这个顺序做：

1. 先确认页面需要什么数据。
2. 如果已有服务层方法能提供，就只改 `KnowledgePage.tsx` 的展示。
3. 如果缺数据，先在接口说明文档里写清楚需要新增什么字段。
4. 再由接口负责人决定是扩展现有服务，还是新增服务方法。
5. 页面和组件仍然只调用 `shadowlink-web/src/services/*.ts`。

## 8. 防乱码要求

- 所有中文文件统一保存为 UTF-8。
- 不要用 PowerShell `Set-Content` / `Add-Content` 直接写中文。
- 修改中文文档或中文 TSX 文案时，优先用 `apply_patch`。
- 如果必须用脚本写文件，使用 `Path.write_text(text, encoding='utf-8')`。
- 提交前检查是否出现 `�`、`馃`、`鈥`、`鐭`、`璁` 等乱码特征。

## 9. 初步验收方法

前端改完后至少检查：

```powershell
Push-Location shadowlink-web
npm.cmd run type-check
Pop-Location
rg "fetch\(" shadowlink-web/src/pages/KnowledgePage.tsx
```

预期结果：

- `type-check` 通过。
- `KnowledgePage.tsx` 中没有 `fetch(`。

