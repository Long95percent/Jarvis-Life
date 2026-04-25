# ShadowLink

ShadowLink 是一个基于 PyQt 的桌面 AI 应用，集成了 LLM 对话、本地 RAG 检索、历史记录管理与 Agent 工具调用能力，适用于个人知识库与任务协作场景。

## 功能概览

- 支持 OpenAI 兼容接口、DeepSeek 和本地模型接入
- 支持本地文档索引与 RAG 问答
- 支持基于 LangChain/LangGraph 的 Agent 工具调用
- 支持本地 SQLite 历史记录与任务配置持久化
- 支持 PyInstaller 打包为桌面应用

## 启动方式

### 源码运行

请使用你的 conda 环境 `D:\software\study\Ana\envs\shadowlink\python.exe` 运行项目。

```bash
D:\software\study\Ana\envs\shadowlink\python.exe -m pip install -r requirements.txt
D:\software\study\Ana\envs\shadowlink\python.exe launcher.py
```

### 打包运行

- PyInstaller 打包入口统一使用 `launcher.py`
- 规格文件为 `ShadowLink.spec`

## 资源初始化

推荐使用本地资源初始化脚本，不把大模型、索引和 Ollama 安装目录提交到 Git：

```bash
D:\software\study\Ana\envs\shadowlink\python.exe scripts/bootstrap_resources.py --embedding-repo intfloat/multilingual-e5-small --skip-index
D:\software\study\Ana\envs\shadowlink\python.exe scripts/bootstrap_resources.py --mode-id project_docs --source docs --source README.md --skip-model
D:\software\study\Ana\envs\shadowlink\python.exe scripts/bootstrap_resources.py --ollama-model qwen2.5:7b --skip-index
```

初始化后会在本地生成：

- `models/`
- `rag_indexes/`
- 可选的 Ollama 本地模型资源

这些目录均已纳入 `.gitignore`。

## 当前入口设计

- `launcher.py`：唯一运行入口，用于源码启动和打包启动
- `main.py`：业务入口模块，只暴露启动函数，不允许直接运行

## 核心模块

- `main.py`：GUI 主流程与窗口逻辑
- `llm/llm_client.py`：模型配置与流式调用
- `rag/rag_engine.py`：文档采集、向量化、FAISS 索引与检索
- `storage/history_manager.py`：聊天历史的 SQLite 持久化
- `core/skill_interface.py`：技能加载与工具装配
- `tools/my_skills.py`：内置技能定义
- 根目录同名文件：兼容层转发模块，保证旧导入不失效

## 协作规范

详细工程化重构方案、Git 上传策略、大文件处理方案和多人协作规范见：

- `docs/工程化重构与协作规范.md`
- `docs/项目交接书.md`（组员接手与 Bug 修复流程）

## Git 规则

### 必须上传

- 源代码
- `requirements.txt`
- `README.md`
- `docs/`
- `scripts/`
- `ShadowLink.spec`
- `.gitignore`

### 严禁上传

- `__pycache__/`
- `.venv/`
- `.idea/`
- `.vscode/`
- `build/`
- `dist/`
- `*.db`
- `models/`
- `rag_indexes/`
- `Ollama/`
- `llm_config.json`
- `tasks_config.json`

## 技术栈

- Python
- PyQt6
- LangChain
- LangGraph
- SentenceTransformers
- FAISS
- SQLite
- PyInstaller
