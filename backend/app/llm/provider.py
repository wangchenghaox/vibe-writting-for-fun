from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Iterator
from pydantic import BaseModel


@dataclass(frozen=True)
class ThinkingConfig:
    enabled: bool = True
    effort: str = "medium"
    budget_tokens: int = 1024
    keep: Optional[str] = "all"
    display: Optional[str] = "omitted"

class Message(BaseModel):
    role: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

class Response(BaseModel):
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: str
    reasoning_content: Optional[str] = None
    reasoning_blocks: Optional[List[Dict[str, Any]]] = None

class StreamEvent(BaseModel):
    type: str
    content: str = ""
    response: Optional[Response] = None

class LLMProvider(ABC):
    @abstractmethod
    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Response:
        pass

    @abstractmethod
    def chat_stream(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Iterator[str]:
        pass

    def chat_stream_response(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[StreamEvent]:
        content_parts = []
        for content in self.chat_stream(messages, tools):
            content_parts.append(content)
            yield StreamEvent(type="content_delta", content=content)

        yield StreamEvent(
            type="message_end",
            response=Response(
                content="".join(content_parts),
                tool_calls=None,
                finish_reason="stop",
            ),
        )
