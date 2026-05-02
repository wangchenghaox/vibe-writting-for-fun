# CLI-Only Refactor Design

## Goal

Remove the Web application surface completely and make the repository a CLI-first Chinese AI novel generator until the CLI workflow is mature enough for a future Web rebuild.

## Scope

This change deletes the Vue frontend, FastAPI routes, WebSocket service, JWT/password authentication, Web-only tests, and Web startup documentation. It preserves the Agent Core, LLM providers, tool registry, file tools, event bus, SQLite-backed agent memory, and CLI session persistence.

## CLI Structure

CLI code moves from `backend/app/ui/` into a dedicated `backend/app/cli/` package:

- `app.py`: CLI runtime orchestration.
- `commands.py`: slash command handling.
- `display.py`: Rich console rendering.
- `input.py`: prompt-toolkit input, history, and completion.

`backend/app/cli_main.py` remains the module entrypoint and imports `app.cli.app.CLI`.

## Data And Persistence

The CLI keeps using `backend/data/novels/` for novel files and `backend/data/sessions/` for session snapshots. SQLAlchemy remains because agent memory uses `AgentEventLog` and `AgentMemory`; Web-only `User`, `Novel`, `Session`, and `ReviewHistory` database models are removed.

## Verification

Focused tests must pass for the new CLI package imports, prompt completion, and existing Agent/tool/memory behavior. Web/API/E2E tests are removed with their implementation.
