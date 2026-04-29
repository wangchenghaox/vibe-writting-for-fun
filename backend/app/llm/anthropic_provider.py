from typing import List, Dict, Any, Optional, Iterator
import json
import anthropic
from .provider import LLMProvider, Response, StreamEvent

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, base_url: str):
        self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
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
            elif msg["role"] == "assistant" and msg.get("tool_calls"):
                # 转换 assistant 的 tool_calls
                content = []
                if msg.get("content"):
                    content.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
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

        return Response(
            content=content,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason
        )

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Response:
        system_msg, chat_messages = self._prepare_messages(messages)

        kwargs = {"model": self.model, "messages": chat_messages, "max_tokens": 4096}
        if system_msg:
            kwargs["system"] = system_msg
        if tools:
            kwargs["tools"] = [self._convert_tool(t) for t in tools]

        response = self.client.messages.create(**kwargs)
        return self._response_from_message(response)

    def chat_stream(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Iterator[str]:
        for event in self.chat_stream_response(messages, tools):
            if event.type == "content_delta":
                yield event.content

    def chat_stream_response(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Iterator[StreamEvent]:
        system_msg, chat_messages = self._prepare_messages(messages)

        kwargs = {"model": self.model, "messages": chat_messages, "max_tokens": 4096}
        if system_msg:
            kwargs["system"] = system_msg
        if tools:
            kwargs["tools"] = [self._convert_tool(t) for t in tools]

        with self.client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield StreamEvent(type="content_delta", content=text)
            response = stream.get_final_message()

        yield StreamEvent(type="message_end", response=self._response_from_message(response))

    def _convert_tool(self, tool: Dict[str, Any]) -> Dict[str, Any]:
        func = tool["function"]
        return {
            "name": func["name"],
            "description": func["description"],
            "input_schema": func["parameters"]
        }
