"""
完整的Agent服务，支持工具调用和事件推送
"""
from typing import Callable
from app import tools as _tools
from app.agent.core import AgentCore
from app.agent.session import Session
from app.llm.config import create_provider
from app.events.event_types import EventType

class WebAgentService:
    def __init__(self, novel_id: str, on_event: Callable = None):
        self.novel_id = novel_id
        self.on_event = on_event

        # 初始化Agent
        self.provider = create_provider()
        self.session = Session(f"web_{novel_id}")
        self.session.context["novel_id"] = novel_id
        self.agent = AgentCore(self.provider, self.session, tool_context={"novel_id": novel_id})
        self._subscriptions = []

        # 订阅事件
        if on_event:
            for event_type in (EventType.THINKING, EventType.TOOL_CALLED, EventType.TOOL_RESULT):
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
        return self.agent.chat(message)
