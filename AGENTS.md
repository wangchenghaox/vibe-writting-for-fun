# AGENTS.md

本文件是给 Codex 在本仓库工作的工程速览。目标不是替代 README，而是让下一次进入代码时能快速判断入口、边界、运行方式和容易踩坑的地方。

## Project Snapshot

这是一个中文 AI 小说生成器，当前只保留 CLI 入口。核心形态是“Agent 对话 + 工具调用 + 小说文件落盘”，Web 前端、FastAPI API、WebSocket、JWT 登录注册等逻辑已删除，等 CLI 完善之后再重构。

- `backend/` 是 Python 后端，包含 CLI、Agent Core、LLM Provider、工具注册、事件总线、文件存储和 SQLite 记忆模型。
- `backend/app/cli/` 是 CLI 输入、输出、命令和运行编排。
- `backend/app/tools/` 是 Agent 工具；新增工具后必须从 `backend/app/tools/__init__.py` import，确保注册副作用生效。
- `backend/data/novels/` 保存小说正文、大纲、章节等文件数据。
- `backend/data/sessions/` 保存 CLI 会话快照。
- SQLite 默认 `backend/data/agent_memory.db`，用于 Agent 事件和长期记忆。
- `docs/superpowers/` 保存历史设计稿和实现计划，偏规格参考，不一定完全等同当前代码。
- `.agents/skills/` 保存本仓库的 OpenSpec 工作流技能。

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

或从仓库根目录：

```bash
./cli.sh
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

常用变量：`LLM_PROVIDER`、`KIMI_API_KEY`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`DATABASE_URL`。

## Backend Architecture

主要入口：

- `backend/app/cli_main.py`: CLI module entrypoint，实例化 `app.cli.app.CLI`。
- `backend/app/cli/app.py`: CLI 主循环，初始化日志、数据库、Provider、Session、Agent 和命令处理。
- `backend/app/cli/commands.py`: `/list`、`/load`、`/current`、`/chapters`、`/help`。
- `backend/app/cli/input.py`: prompt-toolkit 输入历史和补全。
- `backend/app/cli/display.py`: Rich 控制台显示。

Agent 主链路：

1. `AgentCore.chat()` / `chat_stream()` 将用户消息写入 `Session` 并发布事件。
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
- `SubAgentManager`: 可创建和执行子 Agent，目前未直接暴露到 CLI 命令。
- `TaskManager`: 内存任务状态管理，目前是基础能力。

## Tools And Data

当前工具：

- `create_novel`、`list_novels`、`get_novel_info`
- `save_outline`、`load_outline`
- `save_chapter`、`load_chapter`、`list_chapters`
- `review_chapter`
- `read_file`、`write_file`、`edit_file`、`list_files`、`search_files`、`grep_files`
- `remember_memory`、`search_memory`、`list_memories`、`archive_memory`
- `web_search`

小说内容采用文件存储：

```text
backend/data/novels/{novel_id}/
  meta.json
  outlines/{outline_id}.json
  chapters/{chapter_id}.json
```

路径相关代码应优先使用 `app.core.paths`，避免在不同 cwd 下写错 `data/`。

## Testing Notes

测试集中在 `backend/tests/`：

- Agent、Session、ContextCompressor、ToolRegistry、EventBus。
- CLI 主循环、命令输入补全。
- LLM 配置解析和 provider 创建。
- 搜索工具、文件工具、记忆工具。
- TaskManager、SubAgentManager、SkillLoader。

测试数据库使用 SQLite in-memory + `StaticPool`。涉及文件落盘的测试要小心清理 `backend/data/novels/` 下临时目录。

## Local Conventions

- 面向用户的产品文案、CLI 输出、错误提示优先使用中文。
- 新工具使用 `@tool("name", "description")`，参数类型尽量用基础类型，工具函数返回字符串或可 JSON 序列化内容。
- CLI 不应依赖或修改 Web 全局概念；当前小说通过 `CURRENT_NOVEL_ID` 或 `tool_context={"novel_id": ...}` 注入。
- EventBus 是单例。CLI 创建 Agent 时会清空旧订阅。
- 不要把 `docs/superpowers/` 中的历史设计稿当成当前实现真相；以 `backend/app/` 为准。
- 修改数据路径时，同时检查 CLI、工具和测试。
