# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Chinese web novel generation tool built around an AI Agent core system. The project uses Python with FastAPI and supports multiple LLM providers (default: Kimi/Moonshot API).

## Repository Structure

- `ai-agent-core/` - Main Python application implementing the AI agent system
- `openspec/` - OpenSpec workflow configuration and change management
- `docs/superpowers/specs/` - Design specifications and architecture documents
- `.claude/` - Claude Code skills and commands (OpenSpec workflow)

## Development Commands

### Setup and Dependencies

```bash
# Install uv package manager (if not installed)
pip install uv

# Install dependencies
cd ai-agent-core
uv sync
```

### Configuration

```bash
# Create environment file
cp ai-agent-core/.env.example ai-agent-core/.env
# Edit .env and add your API keys (KIMI_API_KEY, etc.)
```

### Running the Application

```bash
# Run the CLI interface
cd ai-agent-core
uv run python -m src.main
```

### Testing

```bash
# Run tests (when implemented)
cd ai-agent-core
uv run pytest
```

## Architecture Overview

The system uses a layered architecture:

1. **Agent Core Layer** (`src/agent/`) - Conversation engine and session management
2. **LLM Provider Layer** (`src/llm/`) - Multi-provider adapter (Kimi, Claude, OpenAI)
3. **Capability Layer** (`src/capability/`) - Tool registry, skill loader, subagent manager
4. **Tools Layer** (`src/tools/`) - Concrete tool implementations (chapter, outline management)
5. **Storage Layer** (`src/storage/`) - Session persistence and checkpoint management
6. **Events Layer** (`src/events/`) - Event bus for real-time feedback
7. **UI Layer** (`src/ui/`) - CLI interface using rich library

## Key Design Patterns

- **Decorator-based Tool Registration**: Tools are registered using `@tool` decorator with automatic schema generation
- **Event-Driven Architecture**: All operations emit events for real-time UI updates
- **Provider Adapter Pattern**: Unified interface for multiple LLM providers
- **Session Persistence**: Automatic saving of conversation state and execution logs

## LLM Configuration

LLM providers are configured in `ai-agent-core/config/llm.yaml`. The default provider is `kimi_coding` which uses the Claude Sonnet 4.6 model through Kimi's coding API.

## OpenSpec Workflow

This project uses OpenSpec for structured feature development:
- Use `/opsx:propose` to create new changes
- Use `/opsx:explore` for thinking through ideas
- Use `/opsx:apply` to implement tasks
- Use `/opsx:archive` to finalize completed changes

## Important Notes

- All user-facing content and documentation is in Chinese
- The system is designed for web novel generation with specific tools for chapters, outlines, and character management
- Session state is automatically persisted to `ai-agent-core/data/sessions/`
- The CLI uses rich library for real-time progress display
