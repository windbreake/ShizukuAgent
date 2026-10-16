# ShizukuClaw Remake Alpha 1.0

当前仓库以 ShizukuAgent 名称维护。新版功能、网关设置、任务计划及已知边界参见 [初步项目说明](PROJECT_OVERVIEW.md)。本文件与 ABOUT.md 保留重构历史说明，部分早期描述以初步项目说明和当前源码为准。

前后端分离的本地智能体：LangGraph 状态图 + Skill 人格 + MCP 插件 + SQLite 默认存储。

Agent 核心使用 `model -> tools -> model` 条件状态图。模型直接回复时结束运行；模型产生 tool calls 时进入工具节点，并在工具执行后回到模型节点，最多执行 6 轮。

许可证：GPL-3.0

## 启动

### NekoAgent CLI

安装为命令后，可以直接在终端使用：

```powershell
pip install -e .
nekoagent
```

CLI 命令：`/help`、`/clear`、`/persona [name]`、`/model [group]`、`/exit`。

启动可视化界面：

```powershell
nekoagent web
```

在未安装为命令时，项目目录也可以使用 `nekoagent.bat`。

Windows 一键启动（推荐）：

```bat
start-all.bat
```

或分别启动：

```bat
start-backend.bat
start-frontend.bat
```

手动启动：

```powershell
pip install -r requirements.txt
uvicorn app.main:app --reload
```

另开终端：

```powershell
cd frontend
npm run dev
```

- 前端: http://127.0.0.1:5173
- 后端端口自动选择：优先 8888，8000 被占用则换端口
- 实际端口写在 `data/dev_port.txt`，前端代理会读这个文件

`npm run dev` 会先跑 `scripts/auto-install.js`，自动补齐缺失的前端依赖。

## 存储

默认 SQLite：`data/storage/agent.db`

切换 MySQL / PostgreSQL：改 `config/storage.yaml` 的 `storage.driver`，并安装对应驱动。

```yaml
storage:
  driver: mysql   # sqlite | mysql | postgresql
```

### RAG（检索增强生成）

项目采用 **RAG + Agentic 混合架构**：

```text
START → query_router ── rag（增强检索）──┐
                    └─────────────────── model ── tools / response
```

- **嵌入**：优先使用 LLM 语义嵌入（`text-embedding-3-small`），无 API Key 或调用失败时自动回退到本地哈希词袋嵌入
- **写入**：对话中用户长消息自动沉淀为记忆；模型也可通过 `add_memory` 工具写入
- **被动 RAG**：每次对话将提问向量化，按余弦相似度检索 top_k=5 记忆注入 system prompt；支持 `min_score` 相关性阈值过滤
- **主动 RAG（Agentic）**：`QueryRouter` 判断记忆/知识相关问题，先走 `RagNode` 深度检索（top_k=10）并把结果注入模型上下文；模型在工具循环中还可主动调用 `search_memory` 继续检索
- **重建索引**：切换嵌入模型后可调用 `storage.reindex_memories()` 批量重建已有记忆的向量

## Skill 与 MCP

Skill 和 MCP 已接入 Agent 工具调用循环：

- **Skill**：`plugins/skills/` 下每个含 `SKILL.md`（+ 可选 `handler.py`）的技能会被注册为可调用工具。模型可通过 `list_skills` 查看、`run_skill` 调用。
- **MCP**：`plugins/mcp/servers.json` 中启用的服务器会被动态发现。模型可通过 `list_mcp_tools` 查看、`call_mcp` 调用。内置 `local-files` 服务器（internal 类型）直接映射到内置文件工具。

不需要额外安装依赖，MCP stdio/HTTP 客户端基于标准库实现。

## 插件框架

项目采用统一的插件元数据协议（`app/plugin_protocol.py`）：

```text
plugins/
├── core/            # 通用插件（plugin.json + 可选 handler.py）
├── skills/          # 技能插件（SKILL.md + 可选 handler.py）
├── mcp/             # MCP 服务器（servers.json / *.json）
└── observability/   # 可观测性插件（plugin.json + handler.py）
```

- **通用插件**：`PluginManager` 管理，支持 `set_plugin_enabled` 持久化开关
- **技能插件**：`SkillManager` 管理，执行时校验 `enabled` / `allow_model_invocation` 策略
- **MCP 服务器**：`MCPManager` 管理，执行时校验服务器 `enabled`
- **可观测性插件**：`ObservabilityManager` 管理，聚合 `configure/status/invoke_config`

各专用插件族由各自的 Manager 负责，`PluginManager` 不会重复加载 `skills/`、`mcp/`、`observability/` 目录下的插件。

## 可观测性插件（LangSmith）

LangSmith 以插件形式存在于 `plugins/observability/langsmith/`，项目只包含可观测性插件框架（`app/observability.py`）。

启用方式 A——项目配置 `config/settings.yaml`：

```yaml
langsmith:
  enabled: true
  api_key: lsv2_...
  project: shizukuclaw
  endpoint: https://api.smith.langchain.com
```

启用方式 B——官方环境变量：

```powershell
$env:LANGSMITH_TRACING="true"
$env:LANGSMITH_API_KEY=""
nekoagent
```

状态查询：`GET /api/observability`。

## 人格

人格在 `plugins/personas/`，不是 companion/engineer 这类模板。
