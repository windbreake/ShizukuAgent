# ShizukuAgent 初步项目说明

本文参考仓库保留的 `README.md`、`ABOUT.md`，记录当前 Alpha 版本的结构与实现范围。

## 项目定位

ShizukuAgent 是一个支持人格、工具调用、记忆检索和本地文件工作台的智能体应用。前端使用 Vue 3、TypeScript、Pinia 和 Vite，后端使用 FastAPI、LangGraph，默认以 SQLite 保存聊天记录、检查点和记忆。

## 快速启动

环境要求：Python 3.11+、Node.js 18+。

```powershell
python -m pip install -r requirements.txt
python -m app.cli web
```

Windows 也可运行 `start-all.bat`。前端通常为 `http://127.0.0.1:5173`。实际后端端口记录在 `data/dev_port.txt`。首次启动前端会检查并安装 npm 依赖。

在提供商设置中填写兼容 OpenAI 的服务地址、API Key 和模型名称。仓库不包含个人密钥与运行数据。

## 当前功能

| 模块 | 当前实现 |
| --- | --- |
| 工作台 | 会话、模型选择、文件浏览、工具记录、权限审批与变更查看 |
| 智能体 | LangGraph 模型／工具循环、模型回退、记忆检索 |
| 任务计划 | Agent 使用 todowrite／todoread 更新步骤，前端显示折叠计划与完成状态 |
| 模型管理 | 提供商、模型发现、模型组、能力标签、辅助模型选择 |
| 设置 | 折叠卡片、MCP 连接编辑、技能 Markdown 与人格 JSON／Markdown 编辑 |
| 存储 | 按人格显示聊天记录，支持搜索、分页、单条删除 |
| 日志 | 固定终端区域、自动换行、跟随开关、日志级别筛选与配色 |
| 网关 | OpenAI 兼容 API 与 WebSocket 开关、监听地址和端口保存 |
| TTS | ZIP／文件夹资源导入、资源选择与语音设置保存 |

## 目录结构

```text
app/                 FastAPI 路由、配置及运行服务
  agent/             AgentHarness、LangGraph 节点、模型客户端、工具注册
  storage/           存储适配器
frontend/src/        页面、共享组件和状态管理
plugins/             人格、技能、MCP、可观测性插件
config/              无密钥的默认配置
scripts/             启动与依赖检查脚本
tests/               后端回归和浏览器 smoke 测试
data/                首次运行生成的本地数据，不上传
```

## 网关和任务计划

API 接口包括 `GET /v1/models`、`POST /v1/chat/completions`。WebSocket 地址为 `/ws/chat`，请求包含 `message`、`thread_id` 及可选 `persona`，返回 started、plan、result、error 消息。

API 和 WebSocket 共用监听端口。网关开关保存后立即生效，监听地址／端口在通过启动脚本重新启动后端时应用。

计划按会话和人格保存；Agent 明确更新任务状态，系统不会将请求结束自动视为全部任务完成。简单问答不要求创建计划。

## 当前边界

- 聊天正文仍为整段返回；WebSocket 的计划更新不等于逐 token 流式输出。
- TTS 完成资源管理，实际语音合成需要接入匹配引擎。
- 工具能力依赖模型支持、工作模式、审批结果和外部服务可用性。
- 数据库驱动和真实服务商的组合需按部署环境验证。
- 当前以本地开发与单机使用为主；公开部署前需审查现有身份认证及访问控制。

## 验证

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

前端目录运行 `npm run build`。安装 Playwright 与 Chromium 后可运行 `python tests/ui_modern_smoke.py`。浏览器 smoke 使用隔离 API fixtures；真实模型、外部 MCP 和 TTS 引擎需要另行联调。

## 参考与许可证

- 历史文档：`README.md`、`ABOUT.md`。
- 任务计划交互参考：[OpenCode](https://github.com/anomalyco/opencode/)。
- 许可证沿用项目现有 `LICENSE`：GPL-3.0。
