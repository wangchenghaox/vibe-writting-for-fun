import json
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float

from app.db.base import Base

class AgentEventLog(Base):
    __tablename__ = "agent_event_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    novel_id = Column(String(100), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False, index=True)
    agent_instance_id = Column(String(100), index=True)
    session_id = Column(String(100), index=True)
    event_type = Column(String(100), nullable=False, index=True)
    payload_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    @property
    def payload(self):
        if not self.payload_json:
            return {}
        return json.loads(self.payload_json)

class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    novel_id = Column(String(100), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False, index=True)
    scope = Column(String(20), nullable=False, index=True)
    layer = Column(String(50), nullable=False, index=True)
    memory_type = Column(String(100), nullable=False, index=True)
    content = Column(Text, nullable=False)
    tags_json = Column(Text, nullable=False, default="[]")
    importance = Column(Integer, nullable=False, default=3)
    status = Column(String(20), nullable=False, default="active", index=True)
    source_event_id = Column(Integer, ForeignKey("agent_event_logs.id"))
    source_event_ids_json = Column(Text, nullable=False, default="[]")
    confidence = Column(Float, nullable=False, default=1.0)
    extractor_version = Column(String(100))
    embedding_model = Column(String(100))
    embedding_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    @property
    def tags(self):
        if not self.tags_json:
            return []
        return json.loads(self.tags_json)
