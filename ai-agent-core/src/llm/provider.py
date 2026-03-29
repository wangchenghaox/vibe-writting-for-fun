from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Iterator
from pydantic import BaseModel

class Message(BaseModel):
    role: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

class Response(BaseModel):
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: str

class LLMProvider(ABC):
    @abstractmethod
    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Response:
        pass

    @abstractmethod
    def chat_stream(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Iterator[str]:
        pass
