import json
import logging
from dataclasses import dataclass
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


@dataclass
class ToolHandlingOutcome:
    messages: list[dict]
    recovery_message: Optional[str] = None


class AgentCore:
    def __init__(
        self,
        provider: LLMProvider,
        session: Session,
        tool_context: Optional[dict] = None,
        skill_loader: Optional[SkillLoader] = None,
        memory_recorder=None,
        max_tool_rounds: int = 8,
    ):
        self.provider = provider
        self.session = session
        self.tool_context = tool_context or {}
        self.memory_recorder = memory_recorder
        self.max_tool_rounds = max_tool_rounds
        self.event_bus = EventBus()
        self.context_compressor = ContextCompressor()
        self.skill_loader = skill_loader or SkillLoader()
        self.subagent_manager = SubAgentManager()
        self.task_manager = TaskManager()

    def _record_memory_event(self, event_type: str, payload: dict):
        if self.memory_recorder is None:
            return

        try:
            self.memory_recorder.record(event_type, payload)
        except Exception:
            logger.warning("Failed to record memory event: %s", event_type, exc_info=True)

    def _start_turn(self, user_message: str):
        self.session.add_message("user", user_message)
        self.event_bus.publish(Event(EventType.MESSAGE_RECEIVED, {"content": user_message}, self.session.id))
        self._record_memory_event("user_message", {"content": user_message})

        messages = self.session.get_messages()

        # 检查是否需要压缩context
        if self.context_compressor.should_compress(messages):
            messages = self.context_compressor.compress(messages)
            self.session.messages = messages
            self.event_bus.publish(Event(EventType.CONTEXT_COMPRESSED, {"count": len(messages)}, self.session.id))
            self._record_memory_event("context_compressed", {"count": len(messages)})

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
        return all(
            self.tool_context.get(key) is not None and self.tool_context.get(key) != ""
            for key in MEMORY_CONTEXT_KEYS
        )

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

    def _is_repeated_missing_argument_error(self, tool_name: str, result: str) -> bool:
        if not result.startswith(f"Tool {tool_name} missing required argument(s): "):
            return False

        return any(
            msg.get("role") == "tool"
            and msg.get("name") == tool_name
            and msg.get("content") == result
            for msg in self.session.messages
        )

    def _missing_argument_recovery_message(self, tool_name: str, result: str) -> str:
        missing_args = result.split("missing required argument(s): ", 1)[-1]
        return (
            f"工具调用连续失败：{tool_name} 缺少必填参数 {missing_args}。"
            "请先提供完整内容，或让我先生成完整正文后再保存。"
        )

    def _finish_assistant_message(self, content: str):
        self.session.add_message("assistant", content)
        self.event_bus.publish(Event(EventType.MESSAGE_SENT, {"content": content}, self.session.id))
        self._record_memory_event("assistant_message", {"content": content})

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
            self._record_memory_event("tool_call", {"name": tool_name, "args": tool_args})

            result = execute_tool(tool_name, tool_args, context=self.tool_context)
            result_text = str(result)
            repeated_missing_arg_error = self._is_repeated_missing_argument_error(tool_name, result_text)

            self.event_bus.publish(Event(EventType.TOOL_RESULT, {"name": tool_name, "result": result}, self.session.id))
            self._record_memory_event("tool_result", {"name": tool_name, "result": str(result)})

            tool_call_id = tc.get("id") or tc.get("tool_call_id")
            if not tool_call_id or tool_call_id.strip() == "":
                tool_call_id = f"fallback_{tool_name}_{idx}"

            self.session.add_message("tool", result_text, tool_call_id=tool_call_id, name=tool_name)

            if repeated_missing_arg_error:
                recovery_message = self._missing_argument_recovery_message(tool_name, result_text)
                self._finish_assistant_message(recovery_message)
                return ToolHandlingOutcome(self.session.get_messages(), recovery_message=recovery_message)

        messages = self.session.get_messages()
        logger.debug(f"Sending {len(messages)} messages to API")
        logger.debug(f"Last 2 messages: {messages[-2:]}")
        return ToolHandlingOutcome(messages)

    def chat(self, user_message: str) -> str:
        skills = self._select_skills(user_message)
        tools = self._get_tools_for_skills(skills)
        messages = self._start_turn(user_message)
        messages = self._inject_skill_prompt(messages, skills)

        for _ in range(self.max_tool_rounds):
            response = self.provider.chat(messages, tools)

            if response.tool_calls:
                outcome = self._handle_tool_calls(response)
                if outcome.recovery_message:
                    return outcome.recovery_message
                messages = outcome.messages
                messages = self._inject_skill_prompt(messages, skills)
            else:
                self._finish_assistant_message(response.content)
                return response.content

        message = f"Exceeded maximum tool rounds: {self.max_tool_rounds}"
        self.event_bus.publish(Event(EventType.ERROR, {"message": message}, self.session.id))
        self._record_memory_event("error", {"message": message})
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
                outcome = self._handle_tool_calls(response)
                if outcome.recovery_message:
                    yield outcome.recovery_message
                    return
                messages = outcome.messages
                messages = self._inject_skill_prompt(messages, skills)
            else:
                self._finish_assistant_message(response.content)
                return

        message = f"Exceeded maximum tool rounds: {self.max_tool_rounds}"
        self.event_bus.publish(Event(EventType.ERROR, {"message": message}, self.session.id))
        self._record_memory_event("error", {"message": message})
        raise RuntimeError(message)
