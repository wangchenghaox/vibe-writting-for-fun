# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chinese web novel generation tool with AI Agent core system. Python backend with FastAPI for both CLI and Web interfaces. Supports multiple LLM providers (default: Kimi/Moonshot API).

## Repository Structure

- `backend/` - Consolidated Python application (CLI + Web API)
- `frontend/` - Vue.js web interface
- `docs/superpowers/specs/` - Design specifications
- `.claude/` - Claude Code skills and OpenSpec workflow

## Development Commands

### Backend Setup

```bash
cd backend
uv sync  # Install dependencies
cp .env.example .env  # Configure API keys
```

### Running Services

```bash
# CLI interface
cd backend
uv run python -m app.cli_main

# Web API server
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend dev server
cd frontend
npm run dev
```

### Testing

```bash
cd backend
uv run pytest                    # Run all tests
uv run pytest tests/test_*.py    # Run specific test file
uv run pytest --cov=app          # Run with coverage
```

## Architecture Overview

**Consolidated Backend** (`backend/app/`):

1. **Agent Core** (`agent/`) - Conversation engine with context compression
   - `AgentCore`: Main orchestrator, handles tool calls and LLM interaction
   - `Session`: Message history management
   - `ContextCompressor`: Auto-compresses when >70% of token limit (70k tokens)

2. **LLM Providers** (`llm/`) - Multi-provider support via adapter pattern
   - `KimiProvider`: Default, uses OpenAI SDK with 120s timeout
   - `AnthropicProvider`: Direct Anthropic API integration
   - Config: `config/llm.yaml` defines available providers

3. **Capabilities** (`capability/`) - Core agent features
   - `ToolRegistry`: Decorator-based tool registration (`@tool(name, desc)`)
   - `SkillLoader`: Dynamic skill loading from markdown files
   - `SubAgentManager`: Manages child agent instances
   - `TaskManager`: Task tracking and status management

4. **Tools** (`tools/`) - Concrete implementations
   - Novel tools: `save_outline`, `save_chapter`, `load_chapter`
   - Search tools: `web_search` (DuckDuckGo API, no key required)

5. **Events** (`events/`) - Event-driven architecture
   - `EventBus`: Singleton pub/sub for real-time updates
   - Events: `TOOL_CALLED`, `TOOL_RESULT`, `CONTEXT_COMPRESSED`

6. **API** (`api/`) - FastAPI REST + WebSocket endpoints
   - Auth: JWT with bcrypt password hashing
   - WebSocket: Real-time agent communication at `/ws/{novel_id}`
   - Database: SQLAlchemy with SQLite

## Key Design Patterns

- **Tool Registration**: Use `@tool("name", "description")` decorator. Tools auto-register and generate OpenAI function schemas
- **Event-Driven UI**: CLI subscribes to `EventBus` for real-time tool call display
- **Context Compression**: Triggered at 70k tokens, keeps system messages + last 10 messages, summarizes middle
- **Session Persistence**: Auto-saves to `backend/data/sessions/`
- **Database Testing**: Use `StaticPool` for SQLite in-memory tests to share state across connections

## Critical Implementation Details

**Adding New Tools:**
```python
from app.capability.tool_registry import tool

@tool("tool_name", "Description for LLM")
def my_tool(param: str) -> str:
    return result
```
Then import in `app/tools/__init__.py`

**CLI Context Loading:**
When `/load <novel_id>` is called, the command handler adds novel metadata, outline, and chapter list as a system message to the agent's session. This ensures the agent has full context.

**LLM Timeout Handling:**
Kimi provider configured with 120s timeout and 2 retries. If 504/429 errors persist, context compression will trigger automatically on next request.

## Important Notes

- All user-facing content is in Chinese
- Novel data stored in `backend/data/novels/{novel_id}/`
- Test database uses `StaticPool` to prevent "no such table" errors
- EventBus is a singleton - clear subscribers when creating new agent instances
- Tool calls may have missing IDs from Kimi API - fallback IDs are generated automatically
