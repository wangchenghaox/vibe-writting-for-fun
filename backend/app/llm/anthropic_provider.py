from typing import List, Dict, Any, Optional, Iterator
import json
import anthropic
from .provider import LLMProvider, Response

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, base_url: str):
        self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
        self.model = model

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Response:
        system_msg = None
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
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

        kwargs = {"model": self.model, "messages": chat_messages, "max_tokens": 4096}
        if system_msg:
            kwargs["system"] = system_msg
        if tools:
            kwargs["tools"] = [self._convert_tool(t) for t in tools]

        response = self.client.messages.create(**kwargs)

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

    def chat_stream(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Iterator[str]:
        system_msg = None
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)

        kwargs = {"model": self.model, "messages": chat_messages, "max_tokens": 4096, "stream": True}
        if system_msg:
            kwargs["system"] = system_msg
        if tools:
            kwargs["tools"] = [self._convert_tool(t) for t in tools]

        with self.client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text

    def _convert_tool(self, tool: Dict[str, Any]) -> Dict[str, Any]:
        func = tool["function"]
        return {
            "name": func["name"],
            "description": func["description"],
            "input_schema": func["parameters"]
        }
