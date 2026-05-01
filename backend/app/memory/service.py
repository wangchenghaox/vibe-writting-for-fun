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


def _require_context(user_id, novel_id, agent_name):
    if not user_id or not novel_id or not agent_name:
        raise ValueError("缺少记忆上下文: user_id、novel_id、agent_name 必须存在")


def _parse_tags(tags):
    if tags is None:
        return []
    if isinstance(tags, list):
        return [str(tag).strip() for tag in tags if str(tag).strip()]
    if isinstance(tags, str):
        normalized = tags.replace("，", ",")
        return [tag.strip() for tag in normalized.split(",") if tag.strip()]
    return []


def _clamp_importance(value):
    try:
        importance = int(value)
    except (TypeError, ValueError):
        return 3
    return max(1, min(5, importance))


def _serialize_memory(memory):
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
        user_id,
        novel_id,
        agent_name,
        content,
        memory_type="note",
        tags=None,
        importance=3,
        scope="agent",
        layer="explicit",
    ):
        _require_context(user_id, novel_id, agent_name)
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
        user_id,
        novel_id,
        agent_name,
        scope=None,
        query=None,
        memory_type=None,
        tags=None,
        limit=20,
    ):
        _require_context(user_id, novel_id, agent_name)
        if memory_type is not None and memory_type not in ALLOWED_MEMORY_TYPES:
            raise ValueError(f"不支持的 memory_type: {memory_type}")
        if scope is not None and scope not in ALLOWED_SCOPES:
            raise ValueError(f"不支持的 scope: {scope}")

        try:
            normalized_limit = int(limit)
        except (TypeError, ValueError):
            normalized_limit = 20
        normalized_limit = max(1, min(20, normalized_limit))

        memories = self.repo.query_memories(
            user_id=user_id,
            novel_id=novel_id,
            agent_name=agent_name,
            scope=scope,
            query=query,
            memory_type=memory_type,
            tags=_parse_tags(tags),
            limit=normalized_limit,
        )
        items = [_serialize_memory(memory) for memory in memories]
        return {"count": len(items), "items": items}

    def archive(self, user_id, novel_id, agent_name, memory_id):
        _require_context(user_id, novel_id, agent_name)
        archived = self.repo.archive_memory(
            memory_id=memory_id,
            user_id=user_id,
            novel_id=novel_id,
            agent_name=agent_name,
        )
        return {"archived": archived, "memory_id": memory_id}
