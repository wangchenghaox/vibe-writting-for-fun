import json
import logging
from typing import Optional
from ..llm.provider import LLMProvider
from ..agent.session import Session
from ..capability.tool_registry import get_tool_schemas, execute_tool
from ..events.event_bus import EventBus
from ..events.event_types import Event, EventType

logger = logging.getLogger(__name__)

class AgentCore:
    def __init__(self, provider: LLMProvider, session: Session):
        self.provider = provider
        self.session = session
        self.event_bus = EventBus()

    def chat(self, user_message: str) -> str:
        self.session.add_message("user", user_message)
        self.event_bus.publish(Event(EventType.MESSAGE_RECEIVED, {"content": user_message}, self.session.id))

        tools = get_tool_schemas()
        messages = self.session.get_messages()

        while True:
            response = self.provider.chat(messages, tools)

            if response.tool_calls:
                # 显示模型的思考内容
                if response.content:
                    self.event_bus.publish(Event(EventType.THINKING, {"content": response.content}, self.session.id))

                logger.debug(f"Tool calls: {response.tool_calls}")
                self.session.add_message("assistant", response.content or "", tool_calls=response.tool_calls)

                for idx, tc in enumerate(response.tool_calls):
                    tool_name = tc["function"]["name"]
                    tool_args = json.loads(tc["function"]["arguments"])

                    self.event_bus.publish(Event(EventType.TOOL_CALLED, {"name": tool_name, "args": tool_args}, self.session.id))

                    result = execute_tool(tool_name, tool_args)

                    self.event_bus.publish(Event(EventType.TOOL_RESULT, {"name": tool_name, "result": result}, self.session.id))

                    tool_call_id = tc.get("id") or tc.get("tool_call_id")
                    if not tool_call_id or tool_call_id.strip() == "":
                        tool_call_id = f"fallback_{tool_name}_{idx}"

                    self.session.add_message("tool", str(result), tool_call_id=tool_call_id, name=tool_name)

                messages = self.session.get_messages()
                logger.debug(f"Sending {len(messages)} messages to API")
                logger.debug(f"Last 2 messages: {messages[-2:]}")
            else:
                self.session.add_message("assistant", response.content)
                self.event_bus.publish(Event(EventType.MESSAGE_SENT, {"content": response.content}, self.session.id))
                return response.content
