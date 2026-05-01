import json
from datetime import datetime

from sqlalchemy import and_, or_

from app.models.novel import AgentEventLog, AgentMemory


class MemoryRepository:
    def __init__(self, db):
        self.db = db

    def log_event(
        self,
        user_id,
        novel_id,
        agent_name,
        agent_instance_id,
        session_id,
        event_type,
        payload,
    ):
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
        user_id,
        novel_id,
        agent_name,
        scope,
        layer,
        memory_type,
        content,
        tags,
        importance,
        source_event_id=None,
        source_event_ids=None,
        confidence=1.0,
        extractor_version=None,
        embedding_model=None,
        embedding=None,
    ):
        memory = AgentMemory(
            user_id=user_id,
            novel_id=novel_id,
            agent_name=agent_name,
            scope=scope,
            layer=layer,
            memory_type=memory_type,
            content=content,
            tags_json=json.dumps(tags or [], ensure_ascii=False),
            importance=importance,
            source_event_id=source_event_id,
            source_event_ids_json=json.dumps(source_event_ids or [], ensure_ascii=False),
            confidence=confidence,
            extractor_version=extractor_version,
            embedding_model=embedding_model,
            embedding_json=(
                json.dumps(embedding, ensure_ascii=False)
                if embedding is not None
                else None
            ),
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def query_memories(
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
        db_query = self.db.query(AgentMemory).filter(
            AgentMemory.user_id == user_id,
            AgentMemory.novel_id == novel_id,
            AgentMemory.status == "active",
        )

        if scope == "agent":
            db_query = db_query.filter(
                AgentMemory.scope == "agent",
                AgentMemory.agent_name == agent_name,
            )
        elif scope == "novel":
            db_query = db_query.filter(AgentMemory.scope == "novel")
        elif scope is None:
            db_query = db_query.filter(self._visible_to_agent_filter(agent_name))
        else:
            return []

        if memory_type:
            db_query = db_query.filter(AgentMemory.memory_type == memory_type)
        if query:
            db_query = db_query.filter(AgentMemory.content.like(f"%{query}%"))

        db_query = db_query.order_by(
            AgentMemory.importance.desc(),
            AgentMemory.updated_at.desc(),
        )

        results = db_query.all()
        if tags:
            required_tags = set(tags)
            results = [
                memory
                for memory in results
                if required_tags.issubset(set(memory.tags))
            ]

        return results[:limit]

    def archive_memory(self, memory_id, user_id, novel_id, agent_name):
        memory = (
            self.db.query(AgentMemory)
            .filter(
                AgentMemory.id == memory_id,
                AgentMemory.user_id == user_id,
                AgentMemory.novel_id == novel_id,
                AgentMemory.status == "active",
                self._visible_to_agent_filter(agent_name),
            )
            .one_or_none()
        )
        if memory is None:
            return False

        memory.status = "archived"
        memory.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    @staticmethod
    def _visible_to_agent_filter(agent_name):
        return or_(
            AgentMemory.scope == "novel",
            and_(
                AgentMemory.scope == "agent",
                AgentMemory.agent_name == agent_name,
            ),
        )
