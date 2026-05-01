import logging

from app.db.base import SessionLocal
from app.memory.repository import MemoryRepository

logger = logging.getLogger(__name__)


class MemoryEventRecorder:
    def __init__(
        self,
        user_id,
        novel_id,
        agent_name="main",
        agent_instance_id=None,
        session_id=None,
        session_factory=SessionLocal,
    ):
        self.user_id = user_id
        self.novel_id = novel_id
        self.agent_name = agent_name
        self.agent_instance_id = agent_instance_id
        self.session_id = session_id
        self.session_factory = session_factory

    @property
    def enabled(self):
        return self.user_id is not None and bool(self.novel_id)

    def record(self, event_type, payload):
        if not self.enabled:
            return

        db = self.session_factory()
        try:
            MemoryRepository(db).log_event(
                user_id=self.user_id,
                novel_id=self.novel_id,
                agent_name=self.agent_name,
                agent_instance_id=self.agent_instance_id,
                session_id=self.session_id,
                event_type=event_type,
                payload=payload,
            )
        except Exception:
            logger.warning("Failed to record memory event: %s", event_type, exc_info=True)
            try:
                db.rollback()
            except Exception:
                logger.warning("Failed to rollback memory event session", exc_info=True)
        finally:
            db.close()
