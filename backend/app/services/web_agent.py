"""
完整的Agent服务，支持工具调用和事件推送
"""
import os
from typing import Callable
from app.agent.core import AgentCore
from app.agent.session import Session
from app.llm.config import create_provider
from app.events.event_types import EventType

class WebAgentService:
    def __init__(self, novel_id: str, on_event: Callable = None):
        self.novel_id = novel_id
        self.on_event = on_event

        # 设置环境变量
        os.environ['CURRENT_NOVEL_ID'] = novel_id

        # 初始化Agent
        self.provider = create_provider()
        self.session = Session(f"web_{novel_id}")
        self.agent = AgentCore(self.provider, self.session)

        # 订阅事件
        if on_event:
            self.agent.event_bus.subscribe(EventType.THINKING, self._handle_event)
            self.agent.event_bus.subscribe(EventType.TOOL_CALLED, self._handle_event)
            self.agent.event_bus.subscribe(EventType.TOOL_RESULT, self._handle_event)
            self.agent.event_bus.subscribe(EventType.MESSAGE_SENT, self._handle_event)

    def _handle_event(self, event):
        if self.on_event:
            self.on_event(event)

    def chat(self, message: str) -> str:
        """发送消息给Agent"""
        return self.agent.chat(message)
