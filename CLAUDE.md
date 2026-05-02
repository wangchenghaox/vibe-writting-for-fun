# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Chinese AI web-novel generation CLI with an Agent Core, tool calling, file-backed novel data, and SQLite-backed agent memory. The previous Web frontend, FastAPI API, WebSocket layer, and JWT authentication have been removed until the CLI workflow is mature enough for a future rebuild.

## Repository Structure

- `backend/` - Python application
- `backend/app/cli/` - CLI runtime, slash commands, Rich display, prompt-toolkit input
- `backend/app/agent/` - Agent orchestration, session, context compression
- `backend/app/llm/` - Kimi, Kimi Coding, OpenAI, and Claude providers
- `backend/app/tools/` - Agent tools
- `backend/app/memory/` - Agent event and long-term memory services
- `backend/data/` - local novel files, sessions, and SQLite memory database
- `docs/superpowers/` - historical specs and implementation plans

## Development Commands

```bash
cd backend
uv sync
cp ../.env.example ../.env
```

Run the CLI:

```bash
cd backend
uv run python -m app.cli_main
```

Or from the repository root:

```bash
./cli.sh
```

Run tests:

```bash
cd backend
uv run pytest
uv run pytest tests/test_*.py
uv run pytest --cov=app
```

## Architecture

1. **CLI** (`app/cli/`)
   - `app.py`: runtime orchestration
   - `commands.py`: slash command handling
   - `display.py`: Rich console output
   - `input.py`: prompt-toolkit history and completion

2. **Agent Core** (`app/agent/`)
   - `AgentCore`: orchestrates messages, tool calls, and LLM responses
   - `Session`: message history and context
   - `ContextCompressor`: compresses history when the token estimate exceeds 70% of max tokens

3. **LLM Providers** (`app/llm/`)
   - OpenAI-compatible provider for Kimi/OpenAI
   - Anthropic provider for Claude and Kimi Coding
   - Provider config lives in `backend/config/llm.yaml`

4. **Tools** (`app/tools/`)
   - Novel, outline, chapter, review, file, memory, and web-search tools
   - Import new tool modules from `app/tools/__init__.py` so decorators register schemas

5. **Memory** (`app/memory/`, `app/models/novel.py`)
   - `AgentEventLog` and `AgentMemory` are SQLAlchemy models
   - Default SQLite URL is `sqlite:///./data/agent_memory.db`

## Notes

- User-facing CLI text should be Chinese.
- Novel data lives in `backend/data/novels/{novel_id}/`.
- CLI sessions live in `backend/data/sessions/`.
- Prefer `app.core.paths` for novel data paths.
- EventBus is a singleton; CLI clears old subscribers when creating an Agent.
- `httpx` is still needed by `web_search`; do not remove it as a Web-only dependency.
