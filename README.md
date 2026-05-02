# AI 小说生成器

一个中文 AI 小说创作 CLI。核心形态是 Agent 对话、工具调用和小说文件落盘；Web 入口已移除，等 CLI 工作流成熟后再重构。

## 功能

- AI 对话式创作，支持工具调用
- 小说、大纲、章节文件管理
- 章节审查辅助
- CLI 会话持久化
- 多 LLM Provider：Kimi、Kimi Coding、OpenAI、Claude
- SQLite 记录 Agent 事件和长期记忆

## 项目结构

```text
vibe-writting-for-fun/
├── backend/
│   ├── app/
│   │   ├── agent/      # Agent 核心
│   │   ├── capability/ # 工具注册、技能、子 Agent、任务管理
│   │   ├── cli/        # CLI 输入、输出、命令和运行编排
│   │   ├── db/         # SQLite 初始化
│   │   ├── events/     # 事件总线
│   │   ├── llm/        # LLM Provider
│   │   ├── memory/     # Agent 事件和记忆
│   │   ├── models/     # 记忆相关 SQLAlchemy 模型
│   │   ├── storage/    # 会话文件存储
│   │   └── tools/      # Agent 工具
│   ├── config/         # LLM 配置
│   ├── data/           # 小说、会话、记忆数据库
│   └── tests/
├── docs/superpowers/   # 历史设计和实现计划
├── cli.sh              # CLI 启动脚本
└── .env.example
```

## 快速开始

```bash
cd backend
uv sync
cp ../.env.example ../.env
```

配置 `.env` 中的 API key 后运行：

```bash
cd backend
uv run python -m app.cli_main
```

也可以从仓库根目录运行：

```bash
./cli.sh
```

## 测试

```bash
cd backend
uv run pytest
uv run pytest tests/test_*.py
uv run pytest --cov=app
```

## 数据

小说内容默认写入：

```text
backend/data/novels/{novel_id}/
  meta.json
  outlines/{outline_id}.json
  chapters/{chapter_id}.json
```

CLI 会话默认写入 `backend/data/sessions/`。Agent 事件和长期记忆默认使用 SQLite `backend/data/agent_memory.db`。

## License

MIT
