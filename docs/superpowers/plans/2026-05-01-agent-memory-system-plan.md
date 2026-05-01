# Agent Memory System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first-phase Agent memory system: SQLite-backed raw event logs, explicit memory tools, namespace isolation, stable agent roles, and conditional novel-wide sharing.

**Architecture:** Extend the existing lightweight AgentCore and ToolRegistry rather than adding a new framework. Memory is stored in SQLite through SQLAlchemy models, accessed through a small repository/service pair, exposed to the model through tools, and recorded from AgentCore through a safe event recorder that never breaks chat on raw-log failures.

**Tech Stack:** Python, FastAPI, SQLAlchemy, SQLite, pytest, existing `AgentCore`, `ToolRegistry`, `SessionLocal`, and WebSocket service.

---

## File Structure

- Modify `backend/app/capability/tool_registry.py`: add `context_params` support so hidden context fields can be injected without appearing in LLM tool schemas.
- Modify `backend/app/models/novel.py`: add `AgentEventLog` and `AgentMemory` SQLAlchemy models.
- Create `backend/app/memory/__init__.py`: package marker and exports.
- Create `backend/app/memory/repository.py`: database access for logs and memories.
- Create `backend/app/memory/service.py`: validation, tag parsing, query visibility, and JSON-friendly service methods.
- Create `backend/app/memory/event_recorder.py`: safe AgentCore event recorder backed by `SessionLocal`.
- Create `backend/app/tools/memory_tools.py`: `remember_memory`, `search_memory`, `list_memories`, `archive_memory`.
- Modify `backend/app/tools/__init__.py`: import memory tools for registration side effects.
- Modify `backend/app/agent/core.py`: accept a memory recorder and record user messages, assistant messages, tool calls, tool results, errors, and context compression.
- Modify `backend/app/services/web_agent.py`: accept `user_id`, `novel_id`, stable `agent_name`, and runtime `agent_instance_id`; wire tool context and recorder.
- Modify `backend/app/api/websocket.py`: pass authenticated user id and business `novel.novel_id` into `WebAgentService`.
- Modify `backend/app/capability/subagent_manager.py`: separate stable `agent_name` from runtime `agent_instance_id`.
- Modify `backend/app/ui/cli.py` and `backend/app/ui/commands.py`: provide CLI memory context with `user_id = 0` and update `novel_id` on `/load`.
- Add tests:
  - `backend/tests/test_memory_repository.py`
  - `backend/tests/test_memory_service.py`
  - `backend/tests/test_memory_tools.py`
  - Update `backend/tests/test_tools.py`
  - Update `backend/tests/test_agent_core.py`
  - Update `backend/tests/test_p1_regressions.py`
  - Update `backend/tests/test_subagent_manager.py`
  - Update `backend/tests/test_cli.py`

---

### Task 1: ToolRegistry Context-Only Parameters

**Files:**
- Modify: `backend/app/capability/tool_registry.py`
- Modify: `backend/tests/test_tools.py`

- [ ] **Step 1: Add failing tests for hidden context params**

Append these tests to `backend/tests/test_tools.py`:

```python
def test_tool_context_params_are_hidden_from_schema_and_injected():
    @tool(
        name="context_hidden_tool",
        description="Context hidden",
        context_params=["user_id", "novel_id"],
    )
    def context_hidden_tool(public: str, user_id: int = None, novel_id: str = None) -> str:
        return f"{public}:{user_id}:{novel_id}"

    schema = next(
        item for item in get_tool_schemas(allowed_names=["context_hidden_tool"])
        if item["function"]["name"] == "context_hidden_tool"
    )

    assert set(schema["function"]["parameters"]["properties"]) == {"public"}
    assert schema["function"]["parameters"]["required"] == ["public"]

    result = execute_tool(
        "context_hidden_tool",
        {"public": "hello", "user_id": 999, "novel_id": "spoof"},
        context={"user_id": 7, "novel_id": "novel_ctx"},
    )

    assert result == "hello:7:novel_ctx"


def test_non_context_params_keep_existing_injection_behavior():
    @tool(name="context_optional_tool", description="Optional context")
    def context_optional_tool(novel_id: str = None) -> str:
        return novel_id or "missing"

    assert execute_tool(
        "context_optional_tool",
        {},
        context={"novel_id": "novel_ctx"},
    ) == "novel_ctx"
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/test_tools.py::test_tool_context_params_are_hidden_from_schema_and_injected tests/test_tools.py::test_non_context_params_keep_existing_injection_behavior -v
```

Expected: first test fails because `tool()` does not accept `context_params`.

- [ ] **Step 3: Implement context-only params**

Replace `backend/app/capability/tool_registry.py` with:

```python
import inspect
from typing import Callable, Dict, Any, List, Optional, Sequence

_tool_registry: Dict[str, Dict[str, Any]] = {}


def tool(name: str, description: str, context_params: Optional[Sequence[str]] = None):
    hidden_context_params = set(context_params or [])

    def decorator(func: Callable):
        sig = inspect.signature(func)
        params = {}
        required = []

        for param_name, param in sig.parameters.items():
            if param_name in hidden_context_params:
                continue

            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == bool:
                    param_type = "boolean"

            params[param_name] = {
                "type": param_type,
                "description": f"Parameter {param_name}",
            }
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": params,
                    "required": required,
                },
            },
        }

        _tool_registry[name] = {
            "schema": schema,
            "func": func,
            "signature": sig,
            "context_params": hidden_context_params,
        }

        return func

    return decorator


def get_tool_schemas(allowed_names: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    if allowed_names is None:
        return [t["schema"] for t in _tool_registry.values()]

    allowed = set(allowed_names)
    return [
        entry["schema"]
        for name, entry in _tool_registry.items()
        if name in allowed
    ]


def execute_tool(name: str, arguments: Dict[str, Any], context: Dict[str, Any] = None) -> Any:
    if name not in _tool_registry:
        raise ValueError(f"Tool {name} not found")

    entry = _tool_registry[name]
    call_args = dict(arguments)
    context_params = entry.get("context_params", set())

    if context:
        for key, value in context.items():
            if key not in entry["signature"].parameters:
                continue
            if key in context_params:
                call_args[key] = value
            elif key not in call_args or call_args[key] in (None, ""):
                call_args[key] = value

    return entry["func"](**call_args)
```

- [ ] **Step 4: Run the focused tests and verify pass**

Run:

```bash
cd backend
uv run pytest tests/test_tools.py::test_tool_context_params_are_hidden_from_schema_and_injected tests/test_tools.py::test_non_context_params_keep_existing_injection_behavior -v
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/capability/tool_registry.py backend/tests/test_tools.py
git commit -m "Add context-only tool parameters"
```

---

### Task 2: Memory Models and Repository

**Files:**
- Modify: `backend/app/models/novel.py`
- Create: `backend/app/memory/__init__.py`
- Create: `backend/app/memory/repository.py`
- Create: `backend/tests/test_memory_repository.py`

- [ ] **Step 1: Add repository tests**

Create `backend/tests/test_memory_repository.py`:

```python
from uuid import uuid4

from app.memory.repository import MemoryRepository
from app.models.novel import AgentEventLog, AgentMemory


def test_log_event_persists_payload_json(test_db):
    repo = MemoryRepository(test_db)
    novel_id = f"novel_{uuid4().hex}"

    event = repo.log_event(
        user_id=1,
        novel_id=novel_id,
        agent_name="writer",
        agent_instance_id="subagent_writer_1",
        session_id="session_1",
        event_type="user_message",
        payload={"content": "你好"},
    )

    row = test_db.query(AgentEventLog).filter(AgentEventLog.id == event.id).one()
    assert row.user_id == 1
    assert row.novel_id == novel_id
    assert row.agent_name == "writer"
    assert row.agent_instance_id == "subagent_writer_1"
    assert row.payload == {"content": "你好"}


def test_query_memories_respects_agent_private_and_novel_shared_scope(test_db):
    repo = MemoryRepository(test_db)
    novel_id = f"novel_{uuid4().hex}"

    writer_private = repo.create_memory(
        user_id=1,
        novel_id=novel_id,
        agent_name="writer",
        scope="agent",
        layer="explicit",
        memory_type="style",
        content="写作偏好短句",
        tags=["style"],
        importance=4,
    )
    reviewer_private = repo.create_memory(
        user_id=1,
        novel_id=novel_id,
        agent_name="reviewer",
        scope="agent",
        layer="explicit",
        memory_type="constraint",
        content="审稿优先看冲突密度",
        tags=["review"],
        importance=3,
    )
    shared = repo.create_memory(
        user_id=1,
        novel_id=novel_id,
        agent_name="writer",
        scope="novel",
        layer="explicit",
        memory_type="canon",
        content="女主不能使用火系能力",
        tags=["canon", "女主"],
        importance=5,
    )

    writer_results = repo.query_memories(user_id=1, novel_id=novel_id, agent_name="writer")
    reviewer_results = repo.query_memories(user_id=1, novel_id=novel_id, agent_name="reviewer")

    assert {item.id for item in writer_results} == {writer_private.id, shared.id}
    assert {item.id for item in reviewer_results} == {reviewer_private.id, shared.id}


def test_query_memories_filters_by_user_novel_keyword_type_tags_and_limit(test_db):
    repo = MemoryRepository(test_db)
    novel_id = f"novel_{uuid4().hex}"

    match = repo.create_memory(
        user_id=2,
        novel_id=novel_id,
        agent_name="writer",
        scope="agent",
        layer="explicit",
        memory_type="character",
        content="男主害怕深水",
        tags=["男主", "弱点"],
        importance=5,
    )
    repo.create_memory(
        user_id=2,
        novel_id=novel_id,
        agent_name="writer",
        scope="agent",
        layer="explicit",
        memory_type="character",
        content="男主喜欢甜食",
        tags=["男主"],
        importance=4,
    )
    repo.create_memory(
        user_id=3,
        novel_id=novel_id,
        agent_name="writer",
        scope="agent",
        layer="explicit",
        memory_type="character",
        content="男主害怕深水",
        tags=["男主", "弱点"],
        importance=5,
    )

    results = repo.query_memories(
        user_id=2,
        novel_id=novel_id,
        agent_name="writer",
        query="深水",
        memory_type="character",
        tags=["弱点"],
        limit=1,
    )

    assert [item.id for item in results] == [match.id]


def test_archive_memory_only_archives_visible_memory(test_db):
    repo = MemoryRepository(test_db)
    novel_id = f"novel_{uuid4().hex}"
    other_novel_id = f"novel_{uuid4().hex}"

    visible = repo.create_memory(
        user_id=1,
        novel_id=novel_id,
        agent_name="writer",
        scope="agent",
        layer="explicit",
        memory_type="note",
        content="可归档",
        tags=[],
        importance=3,
    )
    hidden = repo.create_memory(
        user_id=1,
        novel_id=other_novel_id,
        agent_name="writer",
        scope="agent",
        layer="explicit",
        memory_type="note",
        content="不可归档",
        tags=[],
        importance=3,
    )

    assert repo.archive_memory(
        memory_id=visible.id,
        user_id=1,
        novel_id=novel_id,
        agent_name="writer",
    ) is True
    assert repo.archive_memory(
        memory_id=hidden.id,
        user_id=1,
        novel_id=novel_id,
        agent_name="writer",
    ) is False

    assert test_db.get(AgentMemory, visible.id).status == "archived"
    assert test_db.get(AgentMemory, hidden.id).status == "active"
```

- [ ] **Step 2: Run repository tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/test_memory_repository.py -v
```

Expected: import failure because `app.memory.repository` and memory models do not exist.

- [ ] **Step 3: Add SQLAlchemy models**

Update the import in `backend/app/models/novel.py`:

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
```

Append these model classes to `backend/app/models/novel.py` after `ReviewHistory`:

```python
class AgentEventLog(Base):
    __tablename__ = "agent_event_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    novel_id = Column(String(100), nullable=False, index=True)
    agent_name = Column(String(80), nullable=False, index=True)
    agent_instance_id = Column(String(160), nullable=True, index=True)
    session_id = Column(String(160), nullable=False, index=True)
    event_type = Column(String(40), nullable=False, index=True)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def payload(self):
        import json

        return json.loads(self.payload_json)


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    novel_id = Column(String(100), nullable=False, index=True)
    agent_name = Column(String(80), nullable=False, index=True)
    scope = Column(String(20), nullable=False, default="agent", index=True)
    layer = Column(String(20), nullable=False, default="explicit", index=True)
    memory_type = Column(String(40), nullable=False, index=True)
    content = Column(Text, nullable=False)
    tags_json = Column(Text, nullable=False, default="[]")
    importance = Column(Integer, nullable=False, default=3)
    status = Column(String(20), nullable=False, default="active", index=True)
    source_event_id = Column(Integer, nullable=True, index=True)
    source_event_ids_json = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    extractor_version = Column(String(80), nullable=True)
    embedding_model = Column(String(120), nullable=True)
    embedding_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def tags(self):
        import json

        return json.loads(self.tags_json or "[]")
```

- [ ] **Step 4: Add repository package**

Create `backend/app/memory/__init__.py`:

```python
"""Agent memory storage and service helpers."""
```

Create `backend/app/memory/repository.py`:

```python
import json
from typing import Any, Iterable

from app.models.novel import AgentEventLog, AgentMemory


class MemoryRepository:
    def __init__(self, db):
        self.db = db

    def log_event(
        self,
        user_id: int,
        novel_id: str,
        agent_name: str,
        agent_instance_id: str | None,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> AgentEventLog:
        event = AgentEventLog(
            user_id=user_id,
            novel_id=novel_id,
            agent_name=agent_name,
            agent_instance_id=agent_instance_id,
            session_id=session_id,
            event_type=event_type,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def create_memory(
        self,
        user_id: int,
        novel_id: str,
        agent_name: str,
        scope: str,
        layer: str,
        memory_type: str,
        content: str,
        tags: Iterable[str],
        importance: int,
        source_event_id: int | None = None,
        source_event_ids: Iterable[int] | None = None,
        confidence: float | None = None,
        extractor_version: str | None = None,
    ) -> AgentMemory:
        memory = AgentMemory(
            user_id=user_id,
            novel_id=novel_id,
            agent_name=agent_name,
            scope=scope,
            layer=layer,
            memory_type=memory_type,
            content=content,
            tags_json=json.dumps(list(tags), ensure_ascii=False),
            importance=importance,
            status="active",
            source_event_id=source_event_id,
            source_event_ids_json=(
                json.dumps(list(source_event_ids), ensure_ascii=False)
                if source_event_ids is not None
                else None
            ),
            confidence=confidence,
            extractor_version=extractor_version,
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def query_memories(
        self,
        user_id: int,
        novel_id: str,
        agent_name: str,
        query: str = "",
        memory_type: str | None = None,
        tags: Iterable[str] | None = None,
        scope: str | None = None,
        limit: int = 5,
    ) -> list[AgentMemory]:
        q = self.db.query(AgentMemory).filter(
            AgentMemory.user_id == user_id,
            AgentMemory.novel_id == novel_id,
            AgentMemory.status == "active",
        )

        if scope == "agent":
            q = q.filter(AgentMemory.scope == "agent", AgentMemory.agent_name == agent_name)
        elif scope == "novel":
            q = q.filter(AgentMemory.scope == "novel")
        else:
            q = q.filter(
                (AgentMemory.scope == "novel")
                | ((AgentMemory.scope == "agent") & (AgentMemory.agent_name == agent_name))
            )

        if memory_type:
            q = q.filter(AgentMemory.memory_type == memory_type)
        if query:
            q = q.filter(AgentMemory.content.like(f"%{query}%"))

        rows = q.order_by(AgentMemory.importance.desc(), AgentMemory.updated_at.desc()).all()
        tag_set = set(tags or [])
        if tag_set:
            rows = [row for row in rows if tag_set.issubset(set(row.tags))]

        return rows[:limit]

    def archive_memory(
        self,
        memory_id: int,
        user_id: int,
        novel_id: str,
        agent_name: str,
    ) -> bool:
        memory = self.db.query(AgentMemory).filter(
            AgentMemory.id == memory_id,
            AgentMemory.user_id == user_id,
            AgentMemory.novel_id == novel_id,
            AgentMemory.status == "active",
            (
                (AgentMemory.scope == "novel")
                | ((AgentMemory.scope == "agent") & (AgentMemory.agent_name == agent_name))
            ),
        ).first()

        if memory is None:
            return False

        memory.status = "archived"
        self.db.commit()
        return True
```

- [ ] **Step 5: Run repository tests and verify pass**

Run:

```bash
cd backend
uv run pytest tests/test_memory_repository.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/novel.py backend/app/memory/__init__.py backend/app/memory/repository.py backend/tests/test_memory_repository.py
git commit -m "Add memory models and repository"
```

---

### Task 3: Memory Service Validation and Formatting

**Files:**
- Create: `backend/app/memory/service.py`
- Create: `backend/tests/test_memory_service.py`

- [ ] **Step 1: Add service tests**

Create `backend/tests/test_memory_service.py`:

```python
import pytest
from uuid import uuid4

from app.memory.service import MemoryService


def test_create_memory_validates_required_context(test_db):
    service = MemoryService(test_db)

    with pytest.raises(ValueError, match="缺少记忆上下文"):
        service.remember(
            user_id=None,
            novel_id="novel",
            agent_name="writer",
            content="记住这个",
        )


def test_create_memory_validates_type_scope_and_importance(test_db):
    service = MemoryService(test_db)
    novel_id = f"novel_{uuid4().hex}"

    with pytest.raises(ValueError, match="不支持的 memory_type"):
        service.remember(1, novel_id, "writer", "内容", memory_type="bad")

    with pytest.raises(ValueError, match="不支持的 scope"):
        service.remember(1, novel_id, "writer", "内容", scope="global")

    memory = service.remember(
        1,
        novel_id,
        "writer",
        "内容",
        memory_type="note",
        tags="a, b，c",
        importance=99,
        scope="agent",
    )

    assert memory["importance"] == 5
    assert memory["tags"] == ["a", "b", "c"]


def test_search_formats_visible_memories(test_db):
    service = MemoryService(test_db)
    novel_id = f"novel_{uuid4().hex}"

    service.remember(
        1,
        novel_id,
        "writer",
        "女主不能使用火系能力",
        memory_type="canon",
        tags="女主, canon",
        importance=5,
        scope="novel",
    )

    result = service.search(
        1,
        novel_id,
        "reviewer",
        query="火系",
        memory_type="canon",
        tags="女主",
        limit=10,
    )

    assert result["count"] == 1
    assert result["items"][0]["content"] == "女主不能使用火系能力"
    assert result["items"][0]["scope"] == "novel"
```

- [ ] **Step 2: Run service tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/test_memory_service.py -v
```

Expected: import failure because `MemoryService` does not exist.

- [ ] **Step 3: Implement service**

Create `backend/app/memory/service.py`:

```python
import re

from app.memory.repository import MemoryRepository

ALLOWED_SCOPES = {"agent", "novel"}
ALLOWED_LAYERS = {"explicit", "extracted"}
ALLOWED_MEMORY_TYPES = {
    "preference",
    "canon",
    "character",
    "plot",
    "style",
    "constraint",
    "note",
}


def _require_context(user_id: int | None, novel_id: str | None, agent_name: str | None) -> tuple[int, str, str]:
    if user_id is None or not novel_id or not agent_name:
        raise ValueError("缺少记忆上下文: user_id、novel_id、agent_name 必须存在")
    return int(user_id), str(novel_id), str(agent_name)


def _parse_tags(tags) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, list):
        return [str(tag).strip() for tag in tags if str(tag).strip()]
    if isinstance(tags, str):
        return [part.strip() for part in re.split(r"[,，]", tags) if part.strip()]
    return [str(tags).strip()] if str(tags).strip() else []


def _clamp_importance(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 3
    return max(1, min(5, parsed))


def _serialize_memory(memory) -> dict:
    return {
        "id": memory.id,
        "user_id": memory.user_id,
        "novel_id": memory.novel_id,
        "agent_name": memory.agent_name,
        "scope": memory.scope,
        "layer": memory.layer,
        "memory_type": memory.memory_type,
        "content": memory.content,
        "tags": memory.tags,
        "importance": memory.importance,
        "status": memory.status,
        "created_at": memory.created_at.isoformat() if memory.created_at else None,
        "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
    }


class MemoryService:
    def __init__(self, db):
        self.repo = MemoryRepository(db)

    def remember(
        self,
        user_id: int | None,
        novel_id: str | None,
        agent_name: str | None,
        content: str,
        memory_type: str = "note",
        tags=None,
        importance: int = 3,
        scope: str = "agent",
        layer: str = "explicit",
    ) -> dict:
        user_id, novel_id, agent_name = _require_context(user_id, novel_id, agent_name)
        if memory_type not in ALLOWED_MEMORY_TYPES:
            raise ValueError(f"不支持的 memory_type: {memory_type}")
        if scope not in ALLOWED_SCOPES:
            raise ValueError(f"不支持的 scope: {scope}")
        if layer not in ALLOWED_LAYERS:
            raise ValueError(f"不支持的 layer: {layer}")
        if not content or not str(content).strip():
            raise ValueError("记忆内容不能为空")

        memory = self.repo.create_memory(
            user_id=user_id,
            novel_id=novel_id,
            agent_name=agent_name,
            scope=scope,
            layer=layer,
            memory_type=memory_type,
            content=str(content).strip(),
            tags=_parse_tags(tags),
            importance=_clamp_importance(importance),
        )
        return _serialize_memory(memory)

    def search(
        self,
        user_id: int | None,
        novel_id: str | None,
        agent_name: str | None,
        query: str = "",
        memory_type: str | None = None,
        tags=None,
        scope: str | None = None,
        limit: int = 5,
    ) -> dict:
        user_id, novel_id, agent_name = _require_context(user_id, novel_id, agent_name)
        if memory_type and memory_type not in ALLOWED_MEMORY_TYPES:
            raise ValueError(f"不支持的 memory_type: {memory_type}")
        if scope and scope not in ALLOWED_SCOPES:
            raise ValueError(f"不支持的 scope: {scope}")

        safe_limit = max(1, min(20, int(limit or 5)))
        memories = self.repo.query_memories(
            user_id=user_id,
            novel_id=novel_id,
            agent_name=agent_name,
            query=str(query or ""),
            memory_type=memory_type,
            tags=_parse_tags(tags),
            scope=scope,
            limit=safe_limit,
        )
        return {
            "count": len(memories),
            "items": [_serialize_memory(memory) for memory in memories],
        }

    def archive(self, user_id: int | None, novel_id: str | None, agent_name: str | None, memory_id: int) -> dict:
        user_id, novel_id, agent_name = _require_context(user_id, novel_id, agent_name)
        archived = self.repo.archive_memory(
            memory_id=int(memory_id),
            user_id=user_id,
            novel_id=novel_id,
            agent_name=agent_name,
        )
        return {"archived": archived, "memory_id": int(memory_id)}
```

- [ ] **Step 4: Run service tests and verify pass**

Run:

```bash
cd backend
uv run pytest tests/test_memory_service.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/memory/service.py backend/tests/test_memory_service.py
git commit -m "Add memory service validation"
```

---

### Task 4: Memory Tools

**Files:**
- Create: `backend/app/tools/memory_tools.py`
- Modify: `backend/app/tools/__init__.py`
- Create: `backend/tests/test_memory_tools.py`
- Update: `backend/tests/test_p1_regressions.py`

- [ ] **Step 1: Add memory tool tests**

Create `backend/tests/test_memory_tools.py`:

```python
import json
from uuid import uuid4

from app.capability.tool_registry import execute_tool, get_tool_schemas
from app.db.base import Base
from app.models.novel import AgentMemory


def test_memory_tools_are_registered_with_hidden_context_params():
    import app.tools.memory_tools  # noqa: F401

    tool_names = {schema["function"]["name"]: schema for schema in get_tool_schemas()}

    assert {"remember_memory", "search_memory", "list_memories", "archive_memory"}.issubset(tool_names)
    remember_props = tool_names["remember_memory"]["function"]["parameters"]["properties"]
    assert "content" in remember_props
    assert "user_id" not in remember_props
    assert "novel_id" not in remember_props
    assert "agent_name" not in remember_props
    assert "agent_instance_id" not in remember_props


def test_remember_and_search_memory_tools_use_injected_namespace(monkeypatch, test_db):
    import app.tools.memory_tools as memory_tools
    from sqlalchemy.orm import sessionmaker

    TestSessionLocal = sessionmaker(bind=test_db.get_bind())
    Base.metadata.create_all(test_db.get_bind())
    monkeypatch.setattr(memory_tools, "SessionLocal", TestSessionLocal)
    novel_id = f"novel_{uuid4().hex}"

    remember_payload = json.loads(execute_tool(
        "remember_memory",
        {
            "content": "女主不能使用火系能力",
            "memory_type": "canon",
            "tags": "女主, canon",
            "importance": 5,
            "scope": "novel",
            "user_id": 999,
        },
        context={
            "user_id": 1,
            "novel_id": novel_id,
            "agent_name": "writer",
            "agent_instance_id": "instance_1",
        },
    ))

    assert remember_payload["ok"] is True
    assert remember_payload["memory"]["user_id"] == 1
    assert remember_payload["memory"]["novel_id"] == novel_id

    search_payload = json.loads(execute_tool(
        "search_memory",
        {"query": "火系", "memory_type": "canon", "tags": "女主"},
        context={
            "user_id": 1,
            "novel_id": novel_id,
            "agent_name": "reviewer",
            "agent_instance_id": "instance_2",
        },
    ))

    assert search_payload["ok"] is True
    assert search_payload["result"]["count"] == 1
    assert search_payload["result"]["items"][0]["content"] == "女主不能使用火系能力"


def test_archive_memory_tool_respects_visibility(monkeypatch, test_db):
    import app.tools.memory_tools as memory_tools
    from sqlalchemy.orm import sessionmaker

    TestSessionLocal = sessionmaker(bind=test_db.get_bind())
    Base.metadata.create_all(test_db.get_bind())
    monkeypatch.setattr(memory_tools, "SessionLocal", TestSessionLocal)
    novel_id = f"novel_{uuid4().hex}"

    memory = AgentMemory(
        user_id=2,
        novel_id=novel_id,
        agent_name="writer",
        scope="agent",
        layer="explicit",
        memory_type="note",
        content="只能 writer 归档",
        tags_json="[]",
        importance=3,
        status="active",
    )
    test_db.add(memory)
    test_db.commit()
    test_db.refresh(memory)

    reviewer_payload = json.loads(execute_tool(
        "archive_memory",
        {"memory_id": memory.id},
        context={"user_id": 2, "novel_id": novel_id, "agent_name": "reviewer"},
    ))
    writer_payload = json.loads(execute_tool(
        "archive_memory",
        {"memory_id": memory.id},
        context={"user_id": 2, "novel_id": novel_id, "agent_name": "writer"},
    ))

    assert reviewer_payload["result"]["archived"] is False
    assert writer_payload["result"]["archived"] is True
```

Update `backend/tests/test_p1_regressions.py::test_web_agent_import_registers_all_novel_tools` so the asserted set also includes memory tools:

```python
    assert {
        "create_novel",
        "save_chapter",
        "load_chapter",
        "save_outline",
        "load_outline",
        "review_chapter",
        "web_search",
        "remember_memory",
        "search_memory",
        "list_memories",
        "archive_memory",
    }.issubset(tool_names)
```

- [ ] **Step 2: Run memory tool tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/test_memory_tools.py tests/test_p1_regressions.py::test_web_agent_import_registers_all_novel_tools -v
```

Expected: memory tools are not registered.

- [ ] **Step 3: Implement memory tools**

Create `backend/app/tools/memory_tools.py`:

```python
import json

from app.capability.tool_registry import tool
from app.db.base import SessionLocal
from app.memory.service import MemoryService


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _run_service(operation):
    db = SessionLocal()
    try:
        return operation(MemoryService(db))
    finally:
        db.close()


@tool(
    name="remember_memory",
    description="记录一条当前小说和当前 agent 的长期记忆",
    context_params=["user_id", "novel_id", "agent_name", "agent_instance_id"],
)
def remember_memory(
    content: str,
    memory_type: str = "note",
    tags: str = "",
    importance: int = 3,
    scope: str = "agent",
    user_id: int = None,
    novel_id: str = None,
    agent_name: str = "main",
    agent_instance_id: str = None,
) -> str:
    try:
        memory = _run_service(lambda service: service.remember(
            user_id=user_id,
            novel_id=novel_id,
            agent_name=agent_name,
            content=content,
            memory_type=memory_type,
            tags=tags,
            importance=importance,
            scope=scope,
        ))
        return _json({"ok": True, "memory": memory})
    except Exception as exc:
        return _json({"ok": False, "error": str(exc)})


@tool(
    name="search_memory",
    description="查询当前小说和当前 agent 可见的长期记忆",
    context_params=["user_id", "novel_id", "agent_name", "agent_instance_id"],
)
def search_memory(
    query: str = "",
    memory_type: str = None,
    tags: str = "",
    scope: str = None,
    limit: int = 5,
    user_id: int = None,
    novel_id: str = None,
    agent_name: str = "main",
    agent_instance_id: str = None,
) -> str:
    try:
        result = _run_service(lambda service: service.search(
            user_id=user_id,
            novel_id=novel_id,
            agent_name=agent_name,
            query=query,
            memory_type=memory_type,
            tags=tags,
            scope=scope,
            limit=limit,
        ))
        return _json({"ok": True, "result": result})
    except Exception as exc:
        return _json({"ok": False, "error": str(exc)})


@tool(
    name="list_memories",
    description="列出当前小说和当前 agent 可见的长期记忆",
    context_params=["user_id", "novel_id", "agent_name", "agent_instance_id"],
)
def list_memories(
    memory_type: str = None,
    tags: str = "",
    scope: str = None,
    limit: int = 10,
    user_id: int = None,
    novel_id: str = None,
    agent_name: str = "main",
    agent_instance_id: str = None,
) -> str:
    return search_memory(
        query="",
        memory_type=memory_type,
        tags=tags,
        scope=scope,
        limit=limit,
        user_id=user_id,
        novel_id=novel_id,
        agent_name=agent_name,
        agent_instance_id=agent_instance_id,
    )


@tool(
    name="archive_memory",
    description="归档当前可见范围内的一条长期记忆",
    context_params=["user_id", "novel_id", "agent_name", "agent_instance_id"],
)
def archive_memory(
    memory_id: int,
    user_id: int = None,
    novel_id: str = None,
    agent_name: str = "main",
    agent_instance_id: str = None,
) -> str:
    try:
        result = _run_service(lambda service: service.archive(
            user_id=user_id,
            novel_id=novel_id,
            agent_name=agent_name,
            memory_id=memory_id,
        ))
        return _json({"ok": True, "result": result})
    except Exception as exc:
        return _json({"ok": False, "error": str(exc)})
```

Modify `backend/app/tools/__init__.py`:

```python
from . import chapter_tools, file_tools, memory_tools, novel_tools, outline_tools, review_tools, search_tools
```

- [ ] **Step 4: Run memory tool tests and verify pass**

Run:

```bash
cd backend
uv run pytest tests/test_memory_tools.py tests/test_p1_regressions.py::test_web_agent_import_registers_all_novel_tools -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tools/memory_tools.py backend/app/tools/__init__.py backend/tests/test_memory_tools.py backend/tests/test_p1_regressions.py
git commit -m "Add agent memory tools"
```

---

### Task 5: AgentCore Raw Log Recording

**Files:**
- Create: `backend/app/memory/event_recorder.py`
- Modify: `backend/app/agent/core.py`
- Modify: `backend/tests/test_agent_core.py`

- [ ] **Step 1: Add AgentCore recording tests**

Append these tests to `backend/tests/test_agent_core.py`:

```python
def test_agent_core_records_user_and_assistant_messages(session):
    provider = Mock()
    provider.chat.return_value = SimpleNamespace(content="回复", tool_calls=None)

    class FakeRecorder:
        def __init__(self):
            self.records = []

        def record(self, event_type, payload):
            self.records.append((event_type, payload))

    recorder = FakeRecorder()
    agent = AgentCore(provider, session, memory_recorder=recorder)

    assert agent.chat("你好") == "回复"
    assert [event_type for event_type, payload in recorder.records] == [
        "user_message",
        "assistant_message",
    ]
    assert recorder.records[0][1]["content"] == "你好"
    assert recorder.records[1][1]["content"] == "回复"


def test_agent_core_records_tool_calls_and_results(session):
    tool_name = f"memory_record_probe_{uuid4().hex}"

    @tool(name=tool_name, description="Probe")
    def memory_record_probe() -> str:
        return "tool result"

    provider = Mock()
    provider.chat.side_effect = [
        SimpleNamespace(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": tool_name, "arguments": "{}"},
                }
            ],
        ),
        SimpleNamespace(content="done", tool_calls=None),
    ]

    class FakeRecorder:
        def __init__(self):
            self.records = []

        def record(self, event_type, payload):
            self.records.append((event_type, payload))

    recorder = FakeRecorder()
    agent = AgentCore(provider, session, memory_recorder=recorder)

    assert agent.chat("run") == "done"
    assert [event_type for event_type, payload in recorder.records] == [
        "user_message",
        "tool_call",
        "tool_result",
        "assistant_message",
    ]
    assert recorder.records[1][1]["name"] == tool_name
    assert recorder.records[2][1]["result"] == "tool result"
```

- [ ] **Step 2: Run AgentCore recording tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/test_agent_core.py::test_agent_core_records_user_and_assistant_messages tests/test_agent_core.py::test_agent_core_records_tool_calls_and_results -v
```

Expected: `AgentCore.__init__` does not accept `memory_recorder`.

- [ ] **Step 3: Add MemoryEventRecorder**

Create `backend/app/memory/event_recorder.py`:

```python
import logging
from typing import Any, Callable

from app.db.base import SessionLocal
from app.memory.repository import MemoryRepository

logger = logging.getLogger(__name__)


class MemoryEventRecorder:
    def __init__(
        self,
        user_id: int | None,
        novel_id: str | None,
        agent_name: str = "main",
        agent_instance_id: str | None = None,
        session_id: str | None = None,
        session_factory: Callable = SessionLocal,
    ):
        self.user_id = user_id
        self.novel_id = novel_id
        self.agent_name = agent_name or "main"
        self.agent_instance_id = agent_instance_id
        self.session_id = session_id or agent_instance_id or "unknown"
        self.session_factory = session_factory

    @property
    def enabled(self) -> bool:
        return self.user_id is not None and bool(self.novel_id)

    def record(self, event_type: str, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return

        db = self.session_factory()
        try:
            MemoryRepository(db).log_event(
                user_id=int(self.user_id),
                novel_id=str(self.novel_id),
                agent_name=self.agent_name,
                agent_instance_id=self.agent_instance_id,
                session_id=self.session_id,
                event_type=event_type,
                payload=payload,
            )
        except Exception:
            logger.warning("写入 Agent Raw Log 失败", exc_info=True)
            try:
                db.rollback()
            except Exception:
                logger.debug("回滚 Raw Log 写入失败", exc_info=True)
        finally:
            db.close()
```

- [ ] **Step 4: Wire AgentCore recording**

Modify `backend/app/agent/core.py`:

1. Change the `AgentCore.__init__` signature:

```python
    def __init__(
        self,
        provider: LLMProvider,
        session: Session,
        tool_context: Optional[dict] = None,
        skill_loader: Optional[SkillLoader] = None,
        max_tool_rounds: int = 8,
        memory_recorder=None,
    ):
```

2. Store the recorder:

```python
        self.memory_recorder = memory_recorder
```

3. Add a helper method inside `AgentCore`:

```python
    def _record_memory_event(self, event_type: str, payload: dict):
        if not self.memory_recorder:
            return
        try:
            self.memory_recorder.record(event_type, payload)
        except Exception:
            logger.warning("记录 Agent 记忆事件失败", exc_info=True)
```

4. In `_start_turn`, after publishing `MESSAGE_RECEIVED`, add:

```python
        self._record_memory_event("user_message", {"content": user_message})
```

5. In `_start_turn`, after publishing `CONTEXT_COMPRESSED`, add:

```python
            self._record_memory_event("context_compressed", {"count": len(messages)})
```

6. In `_handle_tool_calls`, before `execute_tool`, add:

```python
            self._record_memory_event("tool_call", {"name": tool_name, "args": tool_args})
```

7. In `_handle_tool_calls`, after publishing `TOOL_RESULT`, add:

```python
            self._record_memory_event("tool_result", {"name": tool_name, "result": str(result)})
```

8. In `chat`, before returning final content, add:

```python
                self._record_memory_event("assistant_message", {"content": response.content})
```

9. In `chat_stream`, before returning after final assistant message, add:

```python
                self._record_memory_event("assistant_message", {"content": response.content})
```

10. In both maximum tool round error paths, before raising, add:

```python
        self._record_memory_event("error", {"message": message})
```

- [ ] **Step 5: Run AgentCore recording tests and verify pass**

Run:

```bash
cd backend
uv run pytest tests/test_agent_core.py::test_agent_core_records_user_and_assistant_messages tests/test_agent_core.py::test_agent_core_records_tool_calls_and_results -v
```

Expected: selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/memory/event_recorder.py backend/app/agent/core.py backend/tests/test_agent_core.py
git commit -m "Record agent raw memory events"
```

---

### Task 6: Web and CLI Memory Context Wiring

**Files:**
- Modify: `backend/app/services/web_agent.py`
- Modify: `backend/app/api/websocket.py`
- Modify: `backend/app/ui/cli.py`
- Modify: `backend/app/ui/commands.py`
- Modify: `backend/tests/test_p1_regressions.py`
- Modify: `backend/tests/test_cli.py`

- [ ] **Step 1: Update Web and CLI tests**

In `backend/tests/test_p1_regressions.py`, update WebAgentService calls to include user id where constructing real services:

```python
    web_agent.WebAgentService(user_id=1, novel_id="web-novel")
```

```python
    first = web_agent.WebAgentService(user_id=1, novel_id="shared-novel")
    second = web_agent.WebAgentService(user_id=1, novel_id="shared-novel")
```

```python
    service = web_agent.WebAgentService(user_id=1, novel_id="stream-novel", on_event=events.append)
```

Extend `test_web_agent_uses_unique_session_per_connection` assertions:

```python
        assert first.session.context["user_id"] == 1
        assert first.session.context["agent_name"] == "main"
        assert first.agent.tool_context["user_id"] == 1
        assert first.agent.tool_context["agent_name"] == "main"
        assert first.agent.tool_context["agent_instance_id"] == first.session.id
```

Update the fake service in `test_websocket_event_callback_is_thread_safe`:

```python
    class FakeAgentService:
        initialized_with = []

        def __init__(self, user_id, novel_id, agent_name="main", agent_instance_id=None, on_event=None):
            self.initialized_with.append((user_id, novel_id, agent_name))
            self.on_event = on_event
```

Update its assertion:

```python
    assert FakeAgentService.initialized_with == [(user.id, novel.novel_id, "main")]
```

In `backend/tests/test_cli.py`, update `FakeAgent.__init__` to accept `tool_context` and `memory_recorder`:

```python
        def __init__(self, provider, session, tool_context=None, memory_recorder=None):
            self.event_bus = type(
                "FakeEventBus",
                (),
                {"_subscribers": {}, "subscribe": lambda *args, **kwargs: None},
            )()
            self.tool_context = tool_context or {}
            self.memory_recorder = memory_recorder
            self.chat_calls = []
            self.chat_stream_calls = []
            created_agents.append(self)
```

Add this assertion at the end of `test_cli_streams_assistant_response`:

```python
    assert agent.tool_context["user_id"] == 0
    assert agent.tool_context["agent_name"] == "main"
    assert agent.tool_context["agent_instance_id"] == saved_sessions[0].id
```

- [ ] **Step 2: Run selected tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/test_p1_regressions.py::test_web_agent_does_not_mutate_current_novel_env tests/test_p1_regressions.py::test_web_agent_uses_unique_session_per_connection tests/test_p1_regressions.py::test_web_agent_chat_forwards_streaming_deltas tests/test_p1_regressions.py::test_websocket_event_callback_is_thread_safe tests/test_cli.py::test_cli_streams_assistant_response -v
```

Expected: failures because constructors and context are not wired yet.

- [ ] **Step 3: Wire WebAgentService**

Modify `backend/app/services/web_agent.py`:

```python
class WebAgentService:
    def __init__(
        self,
        user_id: int,
        novel_id: str,
        agent_name: str = "main",
        agent_instance_id: str = None,
        on_event: Callable = None,
    ):
        self.user_id = user_id
        self.novel_id = novel_id
        self.agent_name = agent_name or "main"
        self.on_event = on_event

        self.provider = create_provider()
        session_id = agent_instance_id or f"web_{novel_id}_{uuid4().hex}"
        self.session = Session(session_id)
        self.session.context["user_id"] = user_id
        self.session.context["novel_id"] = novel_id
        self.session.context["agent_name"] = self.agent_name
        self.session.context["agent_instance_id"] = session_id

        tool_context = {
            "user_id": user_id,
            "novel_id": novel_id,
            "agent_name": self.agent_name,
            "agent_instance_id": session_id,
        }
        self.agent = AgentCore(
            self.provider,
            self.session,
            tool_context=tool_context,
            memory_recorder=MemoryEventRecorder(
                user_id=user_id,
                novel_id=novel_id,
                agent_name=self.agent_name,
                agent_instance_id=session_id,
                session_id=session_id,
            ),
        )
        self._subscriptions = []
```

Also add the import:

```python
from app.memory.event_recorder import MemoryEventRecorder
```

- [ ] **Step 4: Wire WebSocket route**

Modify `backend/app/api/websocket.py` service construction:

```python
    agent_service = WebAgentService(
        user_id=user.id,
        novel_id=novel.novel_id,
        agent_name="main",
        on_event=enqueue_event,
    )
```

- [ ] **Step 5: Wire CLI context**

Modify `backend/app/ui/cli.py` where the agent is created:

```python
        session_id = str(uuid.uuid4())
        session = Session(session_id)
        session.context["user_id"] = 0
        session.context["novel_id"] = os.getenv("CURRENT_NOVEL_ID", "default")
        session.context["agent_name"] = "main"
        session.context["agent_instance_id"] = session_id
        agent = AgentCore(
            self.provider,
            session,
            tool_context=dict(session.context),
            memory_recorder=MemoryEventRecorder(
                user_id=0,
                novel_id=session.context["novel_id"],
                agent_name="main",
                agent_instance_id=session_id,
                session_id=session_id,
            ),
        )
```

Add the import:

```python
from ..memory.event_recorder import MemoryEventRecorder
```

Modify `backend/app/ui/commands.py` inside `_load_novel` after `os.environ['CURRENT_NOVEL_ID'] = novel_id`:

```python
        if self.agent:
            self.agent.session.context["novel_id"] = novel_id
            self.agent.tool_context["novel_id"] = novel_id
            if getattr(self.agent, "memory_recorder", None):
                self.agent.memory_recorder.novel_id = novel_id
```

- [ ] **Step 6: Run selected tests and verify pass**

Run:

```bash
cd backend
uv run pytest tests/test_p1_regressions.py::test_web_agent_does_not_mutate_current_novel_env tests/test_p1_regressions.py::test_web_agent_uses_unique_session_per_connection tests/test_p1_regressions.py::test_web_agent_chat_forwards_streaming_deltas tests/test_p1_regressions.py::test_websocket_event_callback_is_thread_safe tests/test_cli.py::test_cli_streams_assistant_response -v
```

Expected: selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/web_agent.py backend/app/api/websocket.py backend/app/ui/cli.py backend/app/ui/commands.py backend/tests/test_p1_regressions.py backend/tests/test_cli.py
git commit -m "Wire memory context through web and CLI"
```

---

### Task 7: SubAgent Stable Role Identity

**Files:**
- Modify: `backend/app/capability/subagent_manager.py`
- Modify: `backend/tests/test_subagent_manager.py`

- [ ] **Step 1: Add subagent identity tests**

Replace `backend/tests/test_subagent_manager.py` with:

```python
from unittest.mock import Mock

from app.agent.session import Session
from app.capability.subagent_manager import SubAgentManager


def test_create_subagent_sets_stable_agent_name_and_runtime_instance_id():
    mock_provider = Mock()
    session = Session("test")
    manager = SubAgentManager()

    agent_id = manager.create_subagent(
        "writer",
        mock_provider,
        session,
        tool_context={"user_id": 1, "novel_id": "novel_1"},
    )

    subagent = manager.subagents[agent_id]
    assert agent_id.startswith("subagent_writer_")
    assert subagent.tool_context["user_id"] == 1
    assert subagent.tool_context["novel_id"] == "novel_1"
    assert subagent.tool_context["agent_name"] == "writer"
    assert subagent.tool_context["agent_instance_id"] == agent_id
    assert subagent.session.context["agent_name"] == "writer"
    assert subagent.session.context["agent_instance_id"] == agent_id


def test_remove_subagent():
    mock_provider = Mock()
    session = Session("test")
    manager = SubAgentManager()
    agent_id = manager.create_subagent("test", mock_provider, session)
    manager.remove_subagent(agent_id)
    assert agent_id not in manager.subagents
```

- [ ] **Step 2: Run subagent tests and verify failure**

Run:

```bash
cd backend
uv run pytest tests/test_subagent_manager.py -v
```

Expected: first test fails because `create_subagent` does not accept `tool_context` and does not set identity fields.

- [ ] **Step 3: Implement stable role identity**

Replace `backend/app/capability/subagent_manager.py` with:

```python
"""
SubAgent管理器 - 管理子代理的创建和执行
"""
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class SubAgentManager:
    def __init__(self):
        self.subagents: Dict[str, Any] = {}

    def create_subagent(self, name: str, provider, session, tool_context: dict | None = None) -> str:
        """创建子代理"""
        from ..agent.core import AgentCore

        subagent_id = f"subagent_{name}_{len(self.subagents)}"
        context = dict(tool_context or {})
        context.setdefault("agent_name", name)
        context.setdefault("agent_instance_id", subagent_id)

        session.context.update(context)
        subagent = AgentCore(provider, session, tool_context=context)
        self.subagents[subagent_id] = subagent

        logger.info(f"创建子代理: {subagent_id}")
        return subagent_id

    def execute_subagent(self, subagent_id: str, message: str) -> Optional[str]:
        if subagent_id not in self.subagents:
            logger.error(f"子代理不存在: {subagent_id}")
            return None

        subagent = self.subagents[subagent_id]
        return subagent.chat(message)

    def remove_subagent(self, subagent_id: str):
        if subagent_id in self.subagents:
            del self.subagents[subagent_id]
            logger.info(f"移除子代理: {subagent_id}")
```

- [ ] **Step 4: Run subagent tests and verify pass**

Run:

```bash
cd backend
uv run pytest tests/test_subagent_manager.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/capability/subagent_manager.py backend/tests/test_subagent_manager.py
git commit -m "Clarify subagent memory identity"
```

---

### Task 8: Full Regression and Final Verification

**Files:**
- Verify all files changed by Tasks 1-7.

- [ ] **Step 1: Run focused memory and integration tests**

Run:

```bash
cd backend
uv run pytest tests/test_tools.py tests/test_memory_repository.py tests/test_memory_service.py tests/test_memory_tools.py tests/test_agent_core.py tests/test_subagent_manager.py tests/test_p1_regressions.py tests/test_cli.py -v
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full backend test suite**

Run:

```bash
cd backend
uv run pytest
```

Expected: full backend test suite passes.

- [ ] **Step 3: Inspect generated tool schemas**

Run:

```bash
cd backend
uv run python - <<'PY'
from app import tools  # noqa: F401
from app.capability.tool_registry import get_tool_schemas

for schema in get_tool_schemas(allowed_names=["remember_memory", "search_memory"]):
    name = schema["function"]["name"]
    props = schema["function"]["parameters"]["properties"]
    print(name, sorted(props))
    assert "user_id" not in props
    assert "novel_id" not in props
    assert "agent_name" not in props
    assert "agent_instance_id" not in props
PY
```

Expected output includes memory tools with only model-fillable parameters:

```text
remember_memory ['content', 'importance', 'memory_type', 'scope', 'tags']
search_memory ['limit', 'memory_type', 'query', 'scope', 'tags']
```

- [ ] **Step 4: Check working tree**

Run:

```bash
git status --short
```

Expected: clean working tree after all task commits, or only intentional files staged for the final commit.

- [ ] **Step 5: Final commit if Task 8 required fixes**

If Step 1, 2, or 3 required small fixes, commit only those fixes:

```bash
git add backend/app backend/tests
git commit -m "Stabilize agent memory system"
```
