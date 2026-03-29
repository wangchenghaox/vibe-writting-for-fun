import os
from typing import Optional
from .repository import ensure_dir, write_json, read_json, append_jsonl, read_jsonl
from ..agent.session import Session

class SessionStore:
    def __init__(self, base_path: str = "data/sessions"):
        self.base_path = base_path
        ensure_dir(base_path)

    def save_session(self, session: Session):
        session_dir = os.path.join(self.base_path, session.id)
        ensure_dir(session_dir)

        metadata = {
            "id": session.id,
            "created_at": session.created_at,
            "updated_at": session.updated_at
        }
        write_json(os.path.join(session_dir, "metadata.json"), metadata)
        write_json(os.path.join(session_dir, "context.json"), session.context)

        messages_path = os.path.join(session_dir, "messages.jsonl")
        with open(messages_path, 'w') as f:
            pass
        for msg in session.messages:
            append_jsonl(messages_path, msg)

    def load_session(self, session_id: str) -> Optional[Session]:
        session_dir = os.path.join(self.base_path, session_id)
        if not os.path.exists(session_dir):
            return None

        metadata = read_json(os.path.join(session_dir, "metadata.json"))
        context = read_json(os.path.join(session_dir, "context.json"))
        messages = read_jsonl(os.path.join(session_dir, "messages.jsonl"))

        session = Session(session_id)
        session.created_at = metadata["created_at"]
        session.updated_at = metadata["updated_at"]
        session.context = context
        session.messages = messages
        return session
