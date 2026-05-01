import json
import logging
from typing import Iterator, Optional
from ..llm.provider import LLMProvider, Response
from ..agent.session import Session
from ..agent.context_compressor import ContextCompressor
from ..capability.tool_registry import get_tool_schemas, execute_tool
from ..capability.skill_loader import SkillDefinition, SkillLoader
from ..capability.subagent_manager import SubAgentManager
from ..capability.task_manager import TaskManager
from ..events.event_bus import EventBus
from ..events.event_types import Event, EventType

logger = logging.getLogger(__name__)

MEMORY_TOOL_NAMES = {
    "remember_memory",
    "search_memory",
    "list_memories",
    "archive_memory",
}
MEMORY_CONTEXT_KEYS = ("user_id", "novel_id", "agent_name")


class AgentCore:
    def __init__(
        self,
        provider: LLMProvider,
        session: Session,
        tool_context: Optional[dict] = None,
        skill_loader: Optional[SkillLoader] = None,
        max_tool_rounds: int = 8,
    ):
        self.provider = provider
        self.session = session
        self.tool_context = tool_context or {}
        self.max_tool_rounds = max_tool_rounds
        self.event_bus = EventBus()
        self.context_compressor = ContextCompressor()
        self.skill_loader = skill_loader or SkillLoader()
        self.subagent_manager = SubAgentManager()
        self.task_manager = TaskManager()

    def _start_turn(self, user_message: str):
        self.session.add_message("user", user_message)
        self.event_bus.publish(Event(EventType.MESSAGE_RECEIVED, {"content": user_message}, self.session.id))

        messages = self.session.get_messages()

        # 检查是否需要压缩context
        if self.context_compressor.should_compress(messages):
            messages = self.context_compressor.compress(messages)
            self.session.messages = messages
            self.event_bus.publish(Event(EventType.CONTEXT_COMPRESSED, {"count": len(messages)}, self.session.id))

        return messages

    def _select_skills(self, user_message: str):
        requested = (
            self.session.context.get("active_skills")
            or self.session.context.get("active_skill")
        )
        return self.skill_loader.select_skills(user_message, requested=requested)

    def _get_tools_for_skills(self, skills: list[SkillDefinition]):
        allowed_tools = []
        for skill in skills:
            allowed_tools.extend(skill.allowed_tools)

        tools = get_tool_schemas(allowed_names=allowed_tools or None)
        if self._has_memory_context():
            return tools

        return [
            schema for schema in tools
            if schema["function"]["name"] not in MEMORY_TOOL_NAMES
        ]

    def _has_memory_context(self):
        return all(self.tool_context.get(key) for key in MEMORY_CONTEXT_KEYS)

    def _inject_skill_prompt(self, messages: list[dict], skills: list[SkillDefinition]):
        prompt = self.skill_loader.build_prompt(skills)
        if not prompt:
            return messages

        prepared = list(messages)
        insert_at = 0
        while insert_at < len(prepared) and prepared[insert_at].get("role") == "system":
            insert_at += 1
        prepared.insert(insert_at, {"role": "system", "content": prompt})
        return prepared

    def _handle_tool_calls(self, response: Response):
        # 显示模型的思考内容
        if response.content:
            self.event_bus.publish(Event(EventType.THINKING, {"content": response.content}, self.session.id))

        logger.debug(f"Tool calls: {response.tool_calls}")
        self.session.add_message("assistant", response.content or "", tool_calls=response.tool_calls)

        for idx, tc in enumerate(response.tool_calls or []):
            tool_name = tc["function"]["name"]
            tool_args = json.loads(tc["function"]["arguments"])

            self.event_bus.publish(Event(EventType.TOOL_CALLED, {"name": tool_name, "args": tool_args}, self.session.id))

            result = execute_tool(tool_name, tool_args, context=self.tool_context)

            self.event_bus.publish(Event(EventType.TOOL_RESULT, {"name": tool_name, "result": result}, self.session.id))

            tool_call_id = tc.get("id") or tc.get("tool_call_id")
            if not tool_call_id or tool_call_id.strip() == "":
                tool_call_id = f"fallback_{tool_name}_{idx}"

            self.session.add_message("tool", str(result), tool_call_id=tool_call_id, name=tool_name)

        messages = self.session.get_messages()
        logger.debug(f"Sending {len(messages)} messages to API")
        logger.debug(f"Last 2 messages: {messages[-2:]}")
        return messages

    def chat(self, user_message: str) -> str:
        skills = self._select_skills(user_message)
        tools = self._get_tools_for_skills(skills)
        messages = self._start_turn(user_message)
        messages = self._inject_skill_prompt(messages, skills)

        for _ in range(self.max_tool_rounds):
            response = self.provider.chat(messages, tools)

            if response.tool_calls:
                messages = self._handle_tool_calls(response)
                messages = self._inject_skill_prompt(messages, skills)
            else:
                self.session.add_message("assistant", response.content)
                self.event_bus.publish(Event(EventType.MESSAGE_SENT, {"content": response.content}, self.session.id))
                return response.content

        message = f"Exceeded maximum tool rounds: {self.max_tool_rounds}"
        self.event_bus.publish(Event(EventType.ERROR, {"message": message}, self.session.id))
        raise RuntimeError(message)

    def chat_stream(self, user_message: str) -> Iterator[str]:
        skills = self._select_skills(user_message)
        tools = self._get_tools_for_skills(skills)
        messages = self._start_turn(user_message)
        messages = self._inject_skill_prompt(messages, skills)

        for _ in range(self.max_tool_rounds):
            response = None

            for stream_event in self.provider.chat_stream_response(messages, tools):
                if stream_event.type == "content_delta" and stream_event.content:
                    self.event_bus.publish(
                        Event(EventType.MESSAGE_DELTA, {"content": stream_event.content}, self.session.id)
                    )
                    yield stream_event.content
                elif stream_event.type == "message_end":
                    response = stream_event.response

            if response is None:
                response = Response(content="", tool_calls=None, finish_reason="stop")

            if response.tool_calls:
                messages = self._handle_tool_calls(response)
                messages = self._inject_skill_prompt(messages, skills)
            else:
                self.session.add_message("assistant", response.content)
                self.event_bus.publish(Event(EventType.MESSAGE_SENT, {"content": response.content}, self.session.id))
                return

        message = f"Exceeded maximum tool rounds: {self.max_tool_rounds}"
        self.event_bus.publish(Event(EventType.ERROR, {"message": message}, self.session.id))
        raise RuntimeError(message)
