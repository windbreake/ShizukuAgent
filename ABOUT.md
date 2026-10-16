# ABOUT

ShizukuClaw Remake Alpha 1.0 是对原项目的前后端分离重构，不是把 `old/` 整包复制过来。

许可证：GPL-3.0

## 相对原项目改了什么

### 架构

- 后端从 Flask 巨石入口改成 FastAPI：`app/main.py`
- 智能体编排改成 LangGraph 监督者 + 人格路由；没装 LangGraph 时自动走本地回退引擎
- 人格来自 `plugins/personas/`，不是写死的 companion/engineer 模板
- MCP 改为可扫描插件：`plugins/mcp/`
- 默认单文件存储 SQLite：`data/storage/agent.db`（含对话、检查点、向量记忆）
- MySQL / PostgreSQL 作为可选驱动，改 `config/storage.yaml` 的 `storage.driver` 即可
- API Key 改为环境变量 / 配置文件：`OPENAI_API_KEY`、`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`

### 前端

- 保留原 Vue3 + Vite + Pinia 页面和样式
- `store/app.ts` 对接后端聊天、人格、记忆接口
- 沙箱页可切换人格并真实发消息
- Vite 代理读取 `data/dev_port.txt`，后端换端口时前端不用手改

### 启动与易用性

- `start-all.bat` / `start-backend.bat` / `start-frontend.bat` 一键启动
- bat 用 ASCII 保存，避免双击闪退
- 自动查找本机 Python / Node
- 8000 被占用或权限拒绝时自动换端口（8888 / 18000 / 8001 / 8765）
- `scripts/auto-install.js` 在前端启动前补齐缺失 npm 依赖

### 没有整包搬过来的部分

这些仍在 `old/`，本仓库是重写后的可运行骨架：

- 旧 Flask `web_server.py` 全量路由
- 沙箱执行器、OneBot、TTS
- 旧的 `ai_chat_system.py` / `agent_sandbox.py` 大文件

前端现有页面会打到的接口已经接上：聊天、记忆、配置、记录、监控、日志、诊断、安全初始化、`/v1/models`。

## 启动方法

环境：Python 3.11+、Node.js 18+。

### NekoAgent 命令

```powershell
pip install -e .
nekoagent
nekoagent web
```

未安装命令时：

```powershell
python -m app
python -m app web
```

### Windows（推荐）

双击项目根目录的 `start-all.bat`。

会打开两个窗口：

- 后端：自动选空闲端口，地址看后端窗口或 `data/dev_port.txt`
- 前端：http://127.0.0.1:5173

也可以分别双击：

- `start-backend.bat`
- `start-frontend.bat`

### 手动启动

```powershell
pip install -r requirements.txt
python scripts/run_backend.py
```

另开终端：

```powershell
cd frontend
npm run dev
```

不要再直接 `uvicorn app.main:app --port 8000`。8000 常被占用，Windows 会报 `WinError 10013`。请用 `scripts/run_backend.py`。

## 常用地址

- 前端控制台：http://127.0.0.1:5173
- 沙箱聊天：http://127.0.0.1:5173/chat-sandbox
- 后端健康检查：`/health`
- API 文档：`/docs`
- OpenAI 兼容：`/v1/models`、`/v1/chat/completions`

## 配置

- 总配置：`config/settings.yaml`
- 存储：`config/storage.yaml`
- 运行时覆盖：`data/config.json`（控制台保存配置后生成）

切换数据库示例：

```yaml
storage:
  driver: sqlite   # sqlite | mysql | postgresql
```

## 加人格 / 插件

1. 在 `plugins/skills/<id>/` 新建 `SKILL.md`
2. frontmatter 里设 `persona: true`
3. 重启后端，或调用 `POST /api/skills/reload`

MCP 服务放到 `plugins/mcp/*.json`。
