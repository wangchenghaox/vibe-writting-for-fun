# CLI-Only Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the Web surface and reorganize the CLI into a dedicated package.

**Architecture:** The project becomes a backend-only CLI application. Agent, LLM, tools, events, storage, memory, and DB infrastructure remain shared backend modules; UI-specific CLI code lives under `app.cli`.

**Tech Stack:** Python 3, prompt-toolkit, Rich, SQLAlchemy, SQLite, pytest, uv.

---

### Task 1: Create CLI Package

**Files:**
- Create: `backend/app/cli/__init__.py`
- Create: `backend/app/cli/app.py`
- Create: `backend/app/cli/commands.py`
- Create: `backend/app/cli/display.py`
- Create: `backend/app/cli/input.py`
- Modify: `backend/app/cli_main.py`
- Modify: `backend/tests/test_cli.py`
- Modify: `backend/tests/test_prompt_input.py`

- [x] **Step 1: Write failing imports**

Update tests to import `app.cli.app` and `app.cli.input`.

- [x] **Step 2: Verify failure**

Run: `cd backend && uv run pytest tests/test_cli.py tests/test_prompt_input.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.cli'`.

- [x] **Step 3: Move implementation**

Create the new package files with the current CLI behavior and update `cli_main.py`.

- [x] **Step 4: Verify focused tests pass**

Run: `cd backend && uv run pytest tests/test_cli.py tests/test_prompt_input.py -q`

Expected: PASS.

### Task 2: Remove Web Surface

**Files:**
- Delete: `frontend/`
- Delete: `backend/app/api/`
- Delete: `backend/app/services/web_agent.py`
- Delete: `backend/app/main.py`
- Delete: `backend/app/core/deps.py`
- Delete: `backend/app/core/security.py`
- Delete: `backend/app/models/user.py`
- Modify: `backend/app/models/novel.py`
- Modify: `backend/app/db/init.py`
- Modify: `backend/tests/conftest.py`
- Delete: `backend/tests/integration/test_api_auth.py`
- Delete: `backend/tests/e2e/test_web_e2e.py`
- Modify: `backend/tests/test_p1_regressions.py`

- [x] **Step 1: Remove Web-only tests and support imports**

Delete API/E2E tests and remove `app.main` dependency from `conftest.py`.

- [x] **Step 2: Remove Web implementation**

Delete FastAPI, WebSocket, auth, frontend, and Web-only model files.

- [x] **Step 3: Keep memory database models**

Leave only `AgentEventLog` and `AgentMemory` in `app.models.novel`.

- [x] **Step 4: Verify no Web imports remain in backend code**

Run: `rg -n "FastAPI|WebSocket|JWT|app\\.api|app\\.main|app\\.services|app\\.models\\.user" backend/app backend/tests`

Expected: no matches.

### Task 3: Clean Dependencies And Docs

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `cli.sh`
- Delete: `start.sh`
- Delete: `cli/main.py`

- [x] **Step 1: Remove Web-only dependencies**

Remove FastAPI, uvicorn, python-jose, bcrypt, python-multipart, and websockets. Keep `httpx` because `web_search` uses it.

- [x] **Step 2: Refresh lockfile**

Run: `cd backend && uv sync`

Expected: lockfile matches `pyproject.toml`.

- [x] **Step 3: Update docs and scripts**

Document CLI-only setup and remove Web startup instructions.

- [x] **Step 4: Run final test suite**

Run: `cd backend && uv run pytest -q`

Expected: PASS.
