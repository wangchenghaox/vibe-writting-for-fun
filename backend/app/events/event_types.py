from enum import Enum
from dataclasses import dataclass
from typing import Any, Optional

class EventType(Enum):
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_DELTA = "message_delta"
    MESSAGE_SENT = "message_sent"
    THINKING = "thinking"
    TOOL_CALLED = "tool_called"
    TOOL_RESULT = "tool_result"
    CONTEXT_COMPRESSED = "context_compressed"
    ERROR = "error"

@dataclass
class Event:
    type: EventType
    data: Any
    session_id: Optional[str] = None
