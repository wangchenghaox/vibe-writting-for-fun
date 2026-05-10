import json
import logging
import re
from dataclasses import dataclass
from typing import Iterator, Optional
from ..llm.provider import LLMProvider, Response
from ..agent.session import Session
from ..agent.context_compressor import ContextCompressor
from ..capability.tool_registry import get_tool_schemas, execute_tool
from ..capability.skill_loader import SkillLoader
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
FILE_MUTATION_TOOL_NAMES = {
    "write_file",
    "edit_file",
    "delete_file",
    "rename_file",
}
CONCRETE_DELEGATION_KEYWORDS = (
    "生成",
    "创作",
    "写",
    "续写",
    "改写",
    "润色",
    "细化",
    "整理",
    "大纲",
    "细纲",
    "世界观",
    "势力",
    "人设",
    "角色",
    "章节",
    "正文",
    "审稿",
    "审查",
    "review",
    "保存",
    "写入",
    "文件",
)
BASE_SYSTEM_PROMPT = """你是一个中文长篇小说创作 CLI Agent，运行在本地小说工作区中。你的核心职责是和用户一起完成小说创作、规划、审稿、资料整理和文件落盘工作。

系统整体能力：
- 和用户澄清创作目标、题材、风格、范围和保存意图。
- 生成、细化和整理小说大纲、章节细纲、世界观、剧情线。
- 设计人物设定、角色关系、成长弧和冲突结构。
- 创作、续写、改写章节正文，并保持上下文、人物动机和文风连贯。
- 审查章节质量，指出情节、人物、节奏、逻辑和文风问题，并给出可执行修改建议。
- 将确认后的内容保存为 Markdown 文件，并在保存前确保内容完整、路径明确。

工作原则：
- 默认使用中文回复，除非用户明确要求其他语言。
- 先理解用户真实意图；当方向、范围、风格、目标文件或覆盖意图不明确时，先简短确认，不要直接进入高成本创作或保存。
- 不要假装已经读取文件。需要基于已有大纲、章节、角色或审稿文件工作时，先使用工具读取相关文件。
- 不要凭空覆盖已有文件。涉及保存、覆盖、重写时，必须确认目标路径和内容来源。
- 执行具体创作、整理、改写或审稿任务的 Agent，应优先给出可直接使用的内容，避免空泛解释。
- 文件内容应优先使用 Markdown；写入文件时必须提供完整正文，不要只写摘要、说明或占位内容。
- 如果工具调用失败，清楚说明失败原因，并给出下一步可行方案。

进度总结：
- 正式开始写作、整理、改写、审稿或保存前，先查看当前小说根目录或任务单指定小说目录下的 `progress.md`，用它判断当前进度、最近变更、待确认问题和下一步。
- 如果 `progress.md` 不存在，只做轻量目录检查或读取必要入口文件，不要逐个读取所有文件；随后创建初始进度总结。
- 修改或生成新内容后，必须同步更新 `progress.md`，记录本次变更、影响的文件、待确认问题和建议下一步。
- 进度总结只记录可复用的项目状态和工作推进，不保存无关闲聊或敏感信息。

技能使用：
- 系统会提供可用 skill 的名称、说明、触发时机和说明文件路径。
- 当用户请求符合某个 skill 的触发时机时，你应主动参考该 skill；如果需要完整流程、格式或安全规则，可以读取对应的 skills/*.md 说明文件。
- 不要只因为关键词相似就机械套用 skill；应根据用户的真实任务判断是否需要使用。
- 多个 skill 都相关时，先选择最能降低返工风险的流程。例如高影响创作且需求不清时，先确认需求，再进入章节、大纲、人设或审稿流程。

交互风格：
- 回复要清楚、直接、有创作协作感。
- 用户只是要结果时，少讲过程；用户在探索时，可以给出 1-3 个方向供选择。
- 面对复杂任务，先给简洁计划，再分步执行。
- 面对不确定信息，明确说出不确定点，不要编造。"""
WRITE_FILE_USAGE_PROMPT = (
    "工具调用规则：调用 write_file 必须同时提供 path 和完整 content；content 是要写入文件的完整正文。"
    "没有完整正文时不要调用 write_file，先生成完整正文、询问用户，或说明缺少可保存内容。"
)
MAIN_AGENT_ROLE_PROMPT = (
    "运行时角色：你是主 Agent。你的职责是直接和用户交流、澄清需求、整理约束、制定执行计划，"
    "然后通过 create_sub_agent 把具体执行任务交给子 Agent。"
    "主 Agent 不能直接生成正文、大纲、人设、世界观、细纲、改写稿或审稿意见；"
    "凡是生成、审稿、改写、整理成稿、保存或文件修改，都必须调用 create_sub_agent 交给子 Agent 执行。"
    "主 Agent 只输出必要的澄清问题、简短计划、任务单和子 Agent 执行结果摘要。"
    "委派时，task 参数必须是任务单：写清目标、背景、可读取路径、输出格式、目标文件路径和验收标准；"
    "不要把主 Agent 自己生成的大段正文、大纲或审稿意见塞进 task 让子 Agent 只负责保存。"
)
SUB_AGENT_ROLE_PROMPT = (
    "运行时角色：你是子 Agent。你只负责执行主 Agent 分配的具体任务，不能直接与用户对话，"
    "不能向用户提问或等待用户输入；如果信息不足，把缺口和建议下一步写入执行结果交回主 Agent。"
    "你不能创建新的子 Agent。"
)
MIN_BACKFILL_DRAFT_CHARS = 20
MIN_MAIN_CONCRETE_OUTPUT_CHARS = 40
MAIN_AGENT_DELEGATION_RETRY_PROMPT = (
    "主 Agent 刚才输出了具体成品内容，这违反了职责边界。"
    "请改为调用 create_sub_agent，让子 Agent 执行生成、审稿、改写、整理成稿、保存或文件修改。"
    "create_sub_agent 的 task 必须是任务单，只描述目标、约束、上下文路径、输出格式、目标路径和验收标准；"
    "不要复用或传递主 Agent 刚才生成的大段正文。"
)


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
        memory_enabled: bool = False,
        max_tool_rounds: int = 20,
        blocked_tool_names: Optional[set[str]] = None,
        can_create_sub_agent: bool = True,
    ):
        self.provider = provider
        self.session = session
        self.tool_context = tool_context or {}
        self.memory_recorder = memory_recorder
        self.memory_enabled = memory_enabled
        self.max_tool_rounds = max_tool_rounds
        self.blocked_tool_names = set(blocked_tool_names or [])
        self.can_create_sub_agent = can_create_sub_agent
        self.event_bus = EventBus()
        self.context_compressor = ContextCompressor()
        self.skill_loader = skill_loader or SkillLoader()
        self.skill_catalog_prompt = self.skill_loader.build_catalog_prompt()
        self.subagent_manager = SubAgentManager()
        self.task_manager = TaskManager()

    def _record_memory_event(self, event_type: str, payload: dict):
        if not self.memory_enabled or self.memory_recorder is None:
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

    def _get_tools(self):
        tools = get_tool_schemas()
        if not self.memory_enabled or not self._has_memory_context():
            tools = [
                schema for schema in tools
                if schema["function"]["name"] not in MEMORY_TOOL_NAMES
            ]

        blocked_tool_names = self._blocked_tool_names()
        if blocked_tool_names:
            tools = [
                schema for schema in tools
                if schema["function"]["name"] not in blocked_tool_names
            ]

        return tools

    def _blocked_tool_names(self):
        blocked = set(self.blocked_tool_names)
        if self.tool_context.get("agent_name") == "main":
            blocked.update(FILE_MUTATION_TOOL_NAMES)
        if not self.can_create_sub_agent:
            blocked.add("create_sub_agent")
        return blocked

    def _is_tool_blocked(self, tool_name: str) -> bool:
        return tool_name in self._blocked_tool_names()

    def _tool_execution_context(self):
        context = dict(self.tool_context)
        context.update({
            "provider": self.provider,
            "subagent_manager": self.subagent_manager,
            "parent_session": self.session,
            "tool_context": dict(self.tool_context),
            "memory_enabled": self.memory_enabled,
            "can_create_sub_agent": self.can_create_sub_agent,
            "max_tool_rounds": self.max_tool_rounds,
        })
        return context

    def _agent_name(self) -> str:
        return self.tool_context.get("agent_name") or "agent"

    def _has_memory_context(self):
        return all(
            self.tool_context.get(key) is not None and self.tool_context.get(key) != ""
            for key in MEMORY_CONTEXT_KEYS
        )

    def _inject_base_system_prompt(self, messages: list[dict]):
        if any(
            msg.get("role") == "system"
            and msg.get("content") == BASE_SYSTEM_PROMPT
            for msg in messages
        ):
            return messages

        prepared = list(messages)
        insert_at = 0
        while insert_at < len(prepared) and prepared[insert_at].get("role") == "system":
            insert_at += 1
        prepared.insert(insert_at, {"role": "system", "content": BASE_SYSTEM_PROMPT})
        return prepared

    def _inject_skill_catalog_prompt(self, messages: list[dict]):
        if not self.skill_catalog_prompt:
            return messages
        if any(
            msg.get("role") == "system"
            and msg.get("content") == self.skill_catalog_prompt
            for msg in messages
        ):
            return messages

        prepared = list(messages)
        insert_at = 0
        while insert_at < len(prepared) and prepared[insert_at].get("role") == "system":
            insert_at += 1
        prepared.insert(insert_at, {"role": "system", "content": self.skill_catalog_prompt})
        return prepared

    def _inject_tool_usage_prompt(self, messages: list[dict], tools: list[dict]):
        tool_names = {schema["function"]["name"] for schema in tools}
        if "write_file" not in tool_names:
            return messages
        if any(msg.get("role") == "system" and msg.get("content") == WRITE_FILE_USAGE_PROMPT for msg in messages):
            return messages

        prepared = list(messages)
        insert_at = 0
        while insert_at < len(prepared) and prepared[insert_at].get("role") == "system":
            insert_at += 1
        prepared.insert(insert_at, {"role": "system", "content": WRITE_FILE_USAGE_PROMPT})
        return prepared

    def _role_prompt(self) -> Optional[str]:
        if not self.can_create_sub_agent:
            return SUB_AGENT_ROLE_PROMPT
        if self.tool_context.get("agent_name") == "main":
            return MAIN_AGENT_ROLE_PROMPT
        return None

    def _is_main_agent(self) -> bool:
        return self.tool_context.get("agent_name") == "main" and self.can_create_sub_agent

    def _request_needs_subagent(self, user_message: str) -> bool:
        lowered = (user_message or "").lower()
        return any(keyword in lowered for keyword in CONCRETE_DELEGATION_KEYWORDS)

    def _looks_like_concrete_main_output(self, content: str) -> bool:
        stripped = (content or "").strip()
        if len(stripped) < MIN_MAIN_CONCRETE_OUTPUT_CHARS:
            return False
        if re.search(r"(?m)^#{1,6}\s+\S+", stripped):
            return True
        if re.search(r"(?m)^第[一二三四五六七八九十百千万两0-9]+[章节卷部幕]", stripped):
            return True
        if stripped.count("\n") >= 4 and any(
            marker in stripped
            for marker in ("## ", "### ", "核心设定", "分卷大纲", "审稿意见", "角色卡", "章节细纲")
        ):
            return True
        return len(stripped) >= 500 and stripped.count("\n") >= 2

    def _main_agent_should_retry_as_delegation(self, user_message: str, response: Response) -> bool:
        return (
            self._is_main_agent()
            and self._request_needs_subagent(user_message)
            and not response.tool_calls
            and self._looks_like_concrete_main_output(response.content or "")
        )

    def _append_main_agent_delegation_retry_prompt(self, messages: list[dict]) -> list[dict]:
        prepared = list(messages)
        prepared.append({"role": "system", "content": MAIN_AGENT_DELEGATION_RETRY_PROMPT})
        return prepared

    def _inject_role_prompt(self, messages: list[dict]):
        prompt = self._role_prompt()
        if not prompt:
            return messages
        if any(msg.get("role") == "system" and msg.get("content") == prompt for msg in messages):
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

    def _write_file_missing_content_recovery_message(self, tool_args: dict) -> str:
        path = tool_args.get("path") or "目标文件"
        return (
            f"无法保存到 {path}：缺少要写入的完整内容。"
            "请先让我生成完整正文，或直接提供要保存的内容，然后我再写入文件。"
        )

    def _is_write_file_content_missing(self, tool_args: dict) -> bool:
        return tool_args.get("content") in (None, "")

    def _looks_like_draft_content(self, content: str) -> bool:
        stripped = content.strip()
        if len(stripped) < MIN_BACKFILL_DRAFT_CHARS:
            return False
        return "\n" in stripped

    def _find_recent_assistant_draft_content(self) -> Optional[str]:
        for msg in reversed(self.session.messages):
            if msg.get("role") != "assistant":
                continue
            if msg.get("tool_calls"):
                continue

            content = msg.get("content") or ""
            if self._looks_like_draft_content(content):
                return content

        return None

    def _replace_stored_tool_call_arguments(self, index: int, tool_args: dict):
        if not self.session.messages:
            return

        tool_calls = self.session.messages[-1].get("tool_calls") or []
        if index >= len(tool_calls):
            return

        tool_calls[index]["function"]["arguments"] = json.dumps(tool_args, ensure_ascii=False)

    def _handle_write_file_missing_content(self, tool_args: dict, tool_call_id: str):
        result_text = "Tool write_file missing required argument(s): content"
        self.session.add_message("tool", result_text, tool_call_id=tool_call_id, name="write_file")
        recovery_message = self._write_file_missing_content_recovery_message(tool_args)
        self._finish_assistant_message(recovery_message)
        return ToolHandlingOutcome(self.session.get_messages(), recovery_message=recovery_message)

    def _assistant_message_metadata(self, response: Optional[Response]) -> dict:
        if response is None:
            return {}

        metadata = {}
        reasoning_content = getattr(response, "reasoning_content", None)
        reasoning_blocks = getattr(response, "reasoning_blocks", None)
        if reasoning_content:
            metadata["reasoning_content"] = reasoning_content
        if reasoning_blocks:
            metadata["reasoning_blocks"] = reasoning_blocks
        return metadata

    def _finish_assistant_message(self, content: str, response: Optional[Response] = None):
        self.session.add_message("assistant", content, **self._assistant_message_metadata(response))
        self.event_bus.publish(Event(EventType.MESSAGE_SENT, {"content": content}, self.session.id))
        self._record_memory_event("assistant_message", {"content": content})

    def _stream_interrupted_message(self, exc: Exception) -> str:
        return f"流式输出中断：{type(exc).__name__}: {exc}"

    def _finish_interrupted_stream(self, streamed_parts: list[str], exc: Exception) -> str:
        message = self._stream_interrupted_message(exc)
        self.event_bus.publish(Event(EventType.ERROR, {"message": message}, self.session.id))
        self._record_memory_event("error", {"message": message})
        notice = f"\n\n[{message}]"
        self._finish_assistant_message("".join(streamed_parts) + notice if streamed_parts else notice.strip())
        return notice if streamed_parts else notice.strip()

    def _handle_tool_calls(self, response: Response):
        # 显示模型的思考内容
        if response.content:
            self.event_bus.publish(Event(
                EventType.THINKING,
                {"agent_name": self._agent_name(), "content": response.content},
                self.session.id,
            ))

        logger.debug(f"Tool calls: {response.tool_calls}")
        self.session.add_message(
            "assistant",
            response.content or "",
            tool_calls=response.tool_calls,
            **self._assistant_message_metadata(response),
        )

        for idx, tc in enumerate(response.tool_calls or []):
            tool_name = tc["function"]["name"]
            tool_call_id = tc.get("id") or tc.get("tool_call_id")
            if not tool_call_id or tool_call_id.strip() == "":
                tool_call_id = f"fallback_{tool_name}_{idx}"

            if self._is_tool_blocked(tool_name):
                result = f"当前 Agent 不允许调用工具: {tool_name}"
            else:
                try:
                    tool_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError as exc:
                    tool_args = {}
                    result = f"Tool {tool_name} got invalid JSON arguments: {exc.msg}"
                    logger.warning("Invalid tool arguments for %s: %s", tool_name, exc)
                else:
                    if tool_name == "write_file" and self._is_write_file_content_missing(tool_args):
                        draft_content = self._find_recent_assistant_draft_content()
                        if draft_content is None:
                            return self._handle_write_file_missing_content(tool_args, tool_call_id)
                        tool_args["content"] = draft_content
                        self._replace_stored_tool_call_arguments(idx, tool_args)

                    self.event_bus.publish(Event(
                        EventType.TOOL_CALLED,
                        {"agent_name": self._agent_name(), "name": tool_name, "args": tool_args},
                        self.session.id,
                    ))
                    self._record_memory_event("tool_call", {"name": tool_name, "args": tool_args})

                    try:
                        result = execute_tool(tool_name, tool_args, context=self._tool_execution_context())
                    except Exception as exc:
                        result = f"Tool {tool_name} failed: {type(exc).__name__}: {exc}"
                        logger.warning("Tool execution failed: %s", tool_name, exc_info=True)

            result_text = str(result)
            repeated_missing_arg_error = self._is_repeated_missing_argument_error(tool_name, result_text)

            self.event_bus.publish(Event(
                EventType.TOOL_RESULT,
                {"agent_name": self._agent_name(), "name": tool_name, "result": result},
                self.session.id,
            ))
            self._record_memory_event("tool_result", {"name": tool_name, "result": str(result)})

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
        tools = self._get_tools()
        messages = self._start_turn(user_message)
        messages = self._inject_base_system_prompt(messages)
        messages = self._inject_role_prompt(messages)
        messages = self._inject_skill_catalog_prompt(messages)
        messages = self._inject_tool_usage_prompt(messages, tools)

        for _ in range(self.max_tool_rounds):
            response = self.provider.chat(messages, tools)

            if response.tool_calls:
                outcome = self._handle_tool_calls(response)
                if outcome.recovery_message:
                    return outcome.recovery_message
                messages = outcome.messages
                messages = self._inject_base_system_prompt(messages)
                messages = self._inject_role_prompt(messages)
                messages = self._inject_skill_catalog_prompt(messages)
                messages = self._inject_tool_usage_prompt(messages, tools)
            else:
                if self._main_agent_should_retry_as_delegation(user_message, response):
                    messages = self._append_main_agent_delegation_retry_prompt(messages)
                    continue
                self._finish_assistant_message(response.content, response=response)
                return response.content

        message = f"Exceeded maximum tool rounds: {self.max_tool_rounds}"
        self.event_bus.publish(Event(EventType.ERROR, {"message": message}, self.session.id))
        self._record_memory_event("error", {"message": message})
        raise RuntimeError(message)

    def chat_stream(self, user_message: str) -> Iterator[str]:
        tools = self._get_tools()
        messages = self._start_turn(user_message)
        messages = self._inject_base_system_prompt(messages)
        messages = self._inject_role_prompt(messages)
        messages = self._inject_skill_catalog_prompt(messages)
        messages = self._inject_tool_usage_prompt(messages, tools)

        for _ in range(self.max_tool_rounds):
            response = None
            streamed_parts = []
            buffer_main_response = self._is_main_agent() and self._request_needs_subagent(user_message)

            try:
                for stream_event in self.provider.chat_stream_response(messages, tools):
                    if stream_event.type == "content_delta" and stream_event.content:
                        streamed_parts.append(stream_event.content)
                        if not buffer_main_response:
                            self.event_bus.publish(
                                Event(EventType.MESSAGE_DELTA, {"content": stream_event.content}, self.session.id)
                            )
                            yield stream_event.content
                    elif stream_event.type == "message_end":
                        response = stream_event.response
            except Exception as exc:
                logger.warning("Streaming response interrupted", exc_info=True)
                yield self._finish_interrupted_stream(streamed_parts, exc)
                return

            if response is None:
                response = Response(content="", tool_calls=None, finish_reason="stop")

            if response.tool_calls:
                outcome = self._handle_tool_calls(response)
                if outcome.recovery_message:
                    yield outcome.recovery_message
                    return
                messages = outcome.messages
                messages = self._inject_base_system_prompt(messages)
                messages = self._inject_role_prompt(messages)
                messages = self._inject_skill_catalog_prompt(messages)
                messages = self._inject_tool_usage_prompt(messages, tools)
            else:
                if self._main_agent_should_retry_as_delegation(user_message, response):
                    messages = self._append_main_agent_delegation_retry_prompt(messages)
                    continue
                if buffer_main_response:
                    for part in streamed_parts:
                        self.event_bus.publish(
                            Event(EventType.MESSAGE_DELTA, {"content": part}, self.session.id)
                        )
                        yield part
                self._finish_assistant_message(response.content, response=response)
                return

        message = f"Exceeded maximum tool rounds: {self.max_tool_rounds}"
        self.event_bus.publish(Event(EventType.ERROR, {"message": message}, self.session.id))
        self._record_memory_event("error", {"message": message})
        raise RuntimeError(message)
