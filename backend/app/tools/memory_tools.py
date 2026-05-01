import json

from app.capability.tool_registry import tool
from app.db.base import SessionLocal
from app.memory.service import MemoryService


CONTEXT_PARAMS = ["user_id", "novel_id", "agent_name", "agent_instance_id"]


def _json(payload):
    return json.dumps(payload, ensure_ascii=False)


def _run_service(operation):
    db = SessionLocal()
    try:
        return operation(MemoryService(db))
    finally:
        db.close()


@tool(
    name="remember_memory",
    description="Remember a durable agent memory for the current novel context",
    context_params=CONTEXT_PARAMS,
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
        memory = _run_service(
            lambda service: service.remember(
                user_id=user_id,
                novel_id=novel_id,
                agent_name=agent_name,
                content=content,
                memory_type=memory_type,
                tags=tags,
                importance=importance,
                scope=scope,
            )
        )
        return _json({"ok": True, "memory": memory})
    except Exception as exc:
        return _json({"ok": False, "error": str(exc)})


@tool(
    name="search_memory",
    description="Search visible agent memories in the current novel context",
    context_params=CONTEXT_PARAMS,
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
        result = _run_service(
            lambda service: service.search(
                user_id=user_id,
                novel_id=novel_id,
                agent_name=agent_name,
                query=query,
                memory_type=memory_type,
                tags=tags,
                scope=scope,
                limit=limit,
            )
        )
        return _json({"ok": True, "result": result})
    except Exception as exc:
        return _json({"ok": False, "error": str(exc)})


@tool(
    name="list_memories",
    description="List visible agent memories in the current novel context",
    context_params=CONTEXT_PARAMS,
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
    description="Archive a visible agent memory in the current novel context",
    context_params=CONTEXT_PARAMS,
)
def archive_memory(
    memory_id: int,
    user_id: int = None,
    novel_id: str = None,
    agent_name: str = "main",
    agent_instance_id: str = None,
) -> str:
    try:
        result = _run_service(
            lambda service: service.archive(
                user_id=user_id,
                novel_id=novel_id,
                agent_name=agent_name,
                memory_id=memory_id,
            )
        )
        return _json({"ok": True, "result": result})
    except Exception as exc:
        return _json({"ok": False, "error": str(exc)})
