# AI Agent Core - Phase 1 MVP

基于设计文档实现的AI Agent核心系统。

## 功能特性

- 多LLM Provider支持（默认Kimi）
- Tool注册和调用机制
- 会话持久化
- 实时事件反馈
- CLI交互界面

## 安装

本项目使用 [uv](https://docs.astral.sh/uv/) 管理依赖。

```bash
# 安装 uv（如果尚未安装）
pip install uv

# 同步依赖
cd ai-agent-core
uv sync
```

## 配置

创建 `.env` 文件：

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 API key
```

## 运行

```bash
uv run python -m src.main
```

## 项目结构

```
ai-agent-core/
├── src/
│   ├── agent/          # 对话引擎和会话管理
│   ├── llm/            # LLM Provider适配层
│   ├── capability/     # Tool注册系统
│   ├── tools/          # 具体Tool实现
│   ├── storage/        # 持久化存储
│   ├── events/         # 事件系统
│   └── ui/             # CLI界面
├── config/             # 配置文件
├── data/               # 数据存储
└── skills/             # Skill目录（预留）
```

## 可用工具

- `save_chapter`: 保存章节
- `load_chapter`: 加载章节
- `list_chapters`: 列出所有章节
- `save_outline`: 保存大纲
- `load_outline`: 加载大纲
