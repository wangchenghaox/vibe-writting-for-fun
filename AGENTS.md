# AGENTS.md

本文件是给 Codex 在本仓库工作的工程速览。目标不是替代 README，而是让下一次进入代码时能快速判断入口、边界、运行方式和容易踩坑的地方。

## Project Snapshot

这是一个中文 AI 小说生成器，核心形态是“Agent 对话 + 工具调用 + 小说文件落盘”，同时提供 CLI 和 Web 两种入口。

- `backend/` 是统一 Python 后端，包含 FastAPI API、WebSocket、CLI、Agent Core、LLM Provider、工具注册、事件总线和 SQLite 数据模型。
- `frontend/` 是 Vue 3 + Vite + Element Plus 前端，包含登录注册、小说列表、小说详情和聊天页。
- `docs/superpowers/` 保存历史设计稿和实现计划，偏规格参考，不一定完全等同当前代码。
- `.agents/skills/` 保存本仓库的 OpenSpec 工作流技能。
- 小说正文、大纲、章节等文件数据默认在 `backend/data/novels/`；Web 元数据默认在 SQLite `backend/data/web.db`。

## Development Commands

后端依赖和环境：

```bash
cd backend
uv sync
cp ../.env.example ../.env
```

运行 CLI：

```bash
cd backend
uv run python -m app.cli_main
```

运行 Web API：

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

运行前端：

```bash
cd frontend
npm run dev
```

一键启动前后端：

```bash
./start.sh
```

测试：

```bash
cd backend
uv run pytest
uv run pytest tests/test_*.py
uv run pytest --cov=app
```

## Environment

根目录 `.env.example` 是主要配置模板。当前 LLM 配置读取 `backend/config/llm.yaml`，默认 provider 是：

```yaml
llm.default: ${LLM_PROVIDER:-kimi}
```

支持的 provider：

- `kimi`: OpenAI-compatible Moonshot API，默认 `kimi-k2.6`。
- `kimi_coding`: 通过 Anthropic SDK 调用 `https://api.kimi.com/coding/`，默认 `kimi-k2.6`。
- `openai`: OpenAI-compatible provider。
- `claude`: Anthropic provider。

常用变量：`LLM_PROVIDER`、`KIMI_API_KEY`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`JWT_SECRET_KEY`、`DATABASE_URL`、`SERVER_HOST`、`SERVER_PORT`。

## Backend Architecture

主要入口：

- `backend/app/main.py`: FastAPI app，初始化数据库表、CORS、异常处理，并挂载 `auth`、`novels`、`websocket`、`reviews` 路由。
- `backend/app/cli_main.py`: CLI 入口，实例化 `app.ui.cli.CLI`。
- `backend/app/services/web_agent.py`: WebSocket 聊天使用的 Agent 服务封装。

Agent 主链路：

1. `AgentCore.chat()` 将用户消息写入 `Session` 并发布 `MESSAGE_RECEIVED`。
2. 读取 `get_tool_schemas()`，把消息和工具 schema 交给当前 LLM Provider。
3. 如果 provider 返回 tool calls，写入 assistant 消息，执行 `execute_tool()`，发布 `TOOL_CALLED` / `TOOL_RESULT`，再把 tool 结果写回 session。
4. 没有 tool calls 时写入最终 assistant 消息并返回。
5. `ContextCompressor` 在估算 token 超过 `max_tokens * 0.7` 时保留 system 消息和最近 10 条消息，中间消息压缩为 system 摘要。

Provider 层：

- `LLMProvider` 在 `backend/app/llm/provider.py` 定义统一接口。
- `OpenAICompatibleProvider` 负责 OpenAI/Kimi 兼容接口，设置 120s timeout 和 2 次重试，并为缺失 tool call id 生成 fallback。
- `AnthropicProvider` 负责 Anthropic 消息格式转换，也用于 `kimi_coding`。
- `create_provider()` 从 `backend/config/llm.yaml` 加载配置，并解析 `${ENV}` / `${ENV:-default}`。

能力模块：

- `ToolRegistry`: 用 `@tool(name, description)` 注册工具，自动生成函数调用 schema。
- `SkillLoader`: 从本地 `skills/` 读取 Markdown 技能，目前是基础能力。
- `SubAgentManager`: 可创建和执行子 Agent，目前未直接暴露到 API。
- `TaskManager`: 内存任务状态管理，目前是基础能力。

## Tools And Data

已注册工具集中在 `backend/app/tools/`，新增工具后必须从 `backend/app/tools/__init__.py` import，确保注册副作用生效。

当前工具：

- `create_novel`、`list_novels`、`get_novel_info`
- `save_outline`、`load_outline`
- `save_chapter`、`load_chapter`、`list_chapters`
- `review_chapter`
- `web_search`

小说内容采用文件存储：

```text
backend/data/novels/{novel_id}/
  meta.json
  outlines/{outline_id}.json
  chapters/{chapter_id}.json
```

Web 侧元数据采用 SQLAlchemy + SQLite：

- `users`: 登录用户。
- `novels`: 用户所属小说元数据。
- `sessions`: 预留的 Web 会话表。
- `review_history`: 审查历史。

路径相关代码应优先使用 `app.core.paths`，避免在不同 cwd 下写错 `data/`。

## API And WebSocket

REST API：

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/novels`
- `POST /api/novels`
- `GET /api/novels/{novel_id}`，这里的 `novel_id` 参数实际是数据库自增 `Novel.id`。
- `GET /api/chapters/{chapter_id}/reviews`

WebSocket：

- `ws://localhost:8000/ws/chat/{novel_id}?token=...`
- token 使用 JWT 校验。
- `websocket_chat()` 将同步 Agent 调用放入 `ThreadPoolExecutor`。
- tool/thinking 事件通过线程安全队列发回前端，最终回复以 `message_sent` 发送。

注意：WebSocket 路由里的 `{novel_id}` 当前也是数据库自增 id，而工具落盘通常按字符串 `novel_id` 组织目录。处理 Web 生成章节展示问题时，要先核对 DB id 与 `Novel.novel_id` 的映射。

## Frontend Architecture

前端入口：

- `frontend/src/main.js`: Vue app，注册 Pinia、Router、Element Plus。
- `frontend/src/router/index.js`: 路由和登录守卫。
- `frontend/src/api/client.js`: axios 实例，自动注入 `Authorization: Bearer <token>`，401 时登出并跳转登录。
- `frontend/src/stores/user.js`: token 和 user 的 Pinia store，token 持久化到 localStorage。

页面：

- `Login.vue` / `Register.vue`: 登录注册。
- `NovelList.vue`: 小说列表、创建新小说、退出。
- `NovelDetail.vue`: 小说详情和章节折叠展示。
- `Chat.vue`: WebSocket 聊天页，目前只展示用户消息和 `message_sent`，尚未展示 `thinking`、`tool_called`、`tool_result`。

## Testing Notes

测试集中在 `backend/tests/`：

- Agent、Session、ContextCompressor、ToolRegistry、EventBus。
- LLM 配置解析和 provider 创建。
- API auth、小说 API、WebSocket 线程安全事件回传。
- 搜索工具、TaskManager、SubAgentManager、SkillLoader。

测试数据库使用 SQLite in-memory + `StaticPool`，并通过 `app.dependency_overrides[get_db]` 替换 FastAPI 依赖，避免多连接下 no such table。

涉及文件落盘的测试要小心清理 `backend/data/novels/` 下临时目录。

## Local Conventions

- 面向用户的产品文案、CLI 输出、错误提示优先使用中文。
- 新工具使用 `@tool("name", "description")`，参数类型尽量用基础类型，工具函数返回字符串或可 JSON 序列化内容。
- Web Agent 不应依赖或修改全局 `CURRENT_NOVEL_ID`；通过 `tool_context={"novel_id": ...}` 注入业务小说 ID。
- EventBus 是单例。CLI 会清空旧订阅；WebAgentService 使用连接级 session id，并在 `close()` 中 unsubscribe。
- 不要把 `docs/superpowers/` 中的设计稿当成当前实现真相；以 `backend/app/` 和 `frontend/src/` 为准。
- 修改 API 或数据路径时，同时检查 CLI、WebSocket、前端详情页和测试。

## Known Sharp Edges

- `POST /api/novels` 只创建数据库记录，不创建 `backend/data/novels/{novel_id}` 目录或 `meta.json`。
- `GET /api/chapters/{chapter_id}/reviews` 只按 chapter_id 查 ReviewHistory，没有按当前用户或小说进一步限定。
