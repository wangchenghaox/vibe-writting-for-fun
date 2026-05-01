"""
完整的Agent服务，支持工具调用和事件推送
"""
from typing import Callable
from uuid import uuid4
from app import tools as _tools
from app.agent.core import AgentCore
from app.agent.session import Session
from app.llm.config import create_provider
from app.events.event_types import EventType
from app.memory.event_recorder import MemoryEventRecorder

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
        self.agent_name = agent_name
        self.on_event = on_event

        # 初始化Agent
        self.provider = create_provider()
        session_id = agent_instance_id or f"web_{novel_id}_{uuid4().hex}"
        self.session = Session(session_id)
        self.session.context["user_id"] = user_id
        self.session.context["novel_id"] = novel_id
        self.session.context["agent_name"] = self.agent_name
        self.session.context["agent_instance_id"] = session_id
        tool_context = dict(self.session.context)
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

        # 订阅事件
        if on_event:
            for event_type in (
                EventType.MESSAGE_DELTA,
                EventType.THINKING,
                EventType.TOOL_CALLED,
                EventType.TOOL_RESULT,
            ):
                self.agent.event_bus.subscribe(event_type, self._handle_event)
                self._subscriptions.append(event_type)

    def _handle_event(self, event):
        if event.session_id and event.session_id != self.session.id:
            return
        if self.on_event:
            self.on_event(event)

    def close(self):
        for event_type in self._subscriptions:
            try:
                self.agent.event_bus.unsubscribe(event_type, self._handle_event)
            except ValueError:
                pass
        self._subscriptions.clear()

    def chat(self, message: str) -> str:
        """发送消息给Agent"""
        chunks = []
        for chunk in self.agent.chat_stream(message):
            chunks.append(chunk)

        for msg in reversed(self.session.messages):
            if msg.get("role") == "assistant" and not msg.get("tool_calls"):
                return msg["content"]
        return "".join(chunks)
