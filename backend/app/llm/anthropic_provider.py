from typing import List, Dict, Any, Optional, Iterator
import json
import anthropic
from .provider import LLMProvider, Response, StreamEvent, ThinkingConfig

class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float = 120.0,
        max_retries: int = 2,
        thinking_config: Optional[ThinkingConfig] = None,
    ):
        self.timeout = float(timeout)
        self.max_retries = int(max_retries)
        self.thinking_config = thinking_config or ThinkingConfig()
        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        self.model = model

    def _prepare_messages(self, messages: List[Dict[str, Any]]):
        system_parts = []
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            elif msg["role"] == "tool":
                # 转换为 Anthropic 格式
                chat_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg["tool_call_id"],
                        "content": msg["content"]
                    }]
                })
            elif msg["role"] == "assistant" and (msg.get("tool_calls") or msg.get("reasoning_blocks")):
                # 转换 assistant 的 tool_calls
                content = []
                content.extend(msg.get("reasoning_blocks") or [])
                if msg.get("content"):
                    content.append({"type": "text", "text": msg["content"]})
                for tc in msg.get("tool_calls") or []:
                    content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": json.loads(tc["function"]["arguments"])
                    })
                chat_messages.append({"role": "assistant", "content": content})
            else:
                chat_messages.append(msg)

        system_msg = "\n\n".join(system_parts) if system_parts else None
        return system_msg, chat_messages

    def _response_from_message(self, response) -> Response:
        content = ""
        tool_calls = None
        reasoning_blocks = None

        if response.content:
            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.append({
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input)
                        }
                    })
                elif block.type in ("thinking", "redacted_thinking"):
                    if reasoning_blocks is None:
                        reasoning_blocks = []
                    dump = getattr(block, "model_dump", None)
                    if dump is not None:
                        reasoning_blocks.append(dump(exclude_none=True))
                    else:
                        reasoning_blocks.append(dict(block))

        return Response(
            content=content,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason,
            reasoning_blocks=reasoning_blocks,
        )

    def _thinking_payload(self) -> dict:
        if not self.thinking_config.enabled:
            return {"type": "disabled"}

        payload = {
            "type": "enabled",
            "budget_tokens": self.thinking_config.budget_tokens,
        }
        if self.thinking_config.display:
            payload["display"] = self.thinking_config.display
        return payload

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Response:
        system_msg, chat_messages = self._prepare_messages(messages)

        kwargs = {
            "model": self.model,
            "messages": chat_messages,
            "max_tokens": 4096,
            "thinking": self._thinking_payload(),
        }
        if system_msg:
            kwargs["system"] = system_msg
        if tools:
            kwargs["tools"] = self._convert_tools(tools, strict=True)

        try:
            response = self.client.messages.create(**kwargs)
        except anthropic.BadRequestError as exc:
            if not tools or not self._is_strict_tool_schema_error(exc):
                raise
            kwargs["tools"] = self._convert_tools(tools, strict=False)
            response = self.client.messages.create(**kwargs)
        return self._response_from_message(response)

    def chat_stream(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Iterator[str]:
        for event in self.chat_stream_response(messages, tools):
            if event.type == "content_delta":
                yield event.content

    def chat_stream_response(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Iterator[StreamEvent]:
        system_msg, chat_messages = self._prepare_messages(messages)

        kwargs = {
            "model": self.model,
            "messages": chat_messages,
            "max_tokens": 4096,
            "thinking": self._thinking_payload(),
        }
        if system_msg:
            kwargs["system"] = system_msg
        if tools:
            kwargs["tools"] = self._convert_tools(tools, strict=True)

        try:
            with self.client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield StreamEvent(type="content_delta", content=text)
                response = stream.get_final_message()
        except anthropic.BadRequestError as exc:
            if not tools or not self._is_strict_tool_schema_error(exc):
                raise
            kwargs["tools"] = self._convert_tools(tools, strict=False)
            with self.client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield StreamEvent(type="content_delta", content=text)
                response = stream.get_final_message()

        yield StreamEvent(type="message_end", response=self._response_from_message(response))

    def _convert_tools(self, tools: List[Dict[str, Any]], strict: bool = True) -> List[Dict[str, Any]]:
        return [self._convert_tool(tool, strict=strict) for tool in tools]

    def _convert_tool(self, tool: Dict[str, Any], strict: bool = True) -> Dict[str, Any]:
        func = tool["function"]
        converted = {
            "name": func["name"],
            "description": func["description"],
            "input_schema": func["parameters"]
        }
        if strict:
            converted["strict"] = True
        return converted

    def _is_strict_tool_schema_error(self, exc: anthropic.BadRequestError) -> bool:
        body = getattr(exc, "body", None)
        haystack = f"{exc} {body}".lower()
        return "strict" in haystack
