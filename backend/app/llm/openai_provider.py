from typing import Any, Dict, Iterator, List, Optional
import logging

from openai import OpenAI

from .provider import LLMProvider, Response, StreamEvent

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, base_url: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=120.0,
            max_retries=2,
        )
        self.model = model

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Response:
        kwargs = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools

        logger.debug("Sending %s messages to OpenAI-compatible API", len(messages))
        completion = self.client.chat.completions.create(**kwargs)
        msg = completion.choices[0].message

        tool_calls = None
        if msg.tool_calls:
            tool_calls = []
            for idx, tool_call in enumerate(msg.tool_calls):
                tool_call_dict = tool_call.model_dump()
                if not tool_call_dict.get("id") or tool_call_dict["id"].strip() == "":
                    tool_call_dict["id"] = f"call_{idx}_{tool_call_dict['function']['name']}"
                    logger.warning("Generated fallback tool call id: %s", tool_call_dict["id"])
                tool_calls.append(tool_call_dict)

        return Response(
            content=msg.content or "",
            tool_calls=tool_calls,
            finish_reason=completion.choices[0].finish_reason,
        )

    def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[str]:
        for event in self.chat_stream_response(messages, tools):
            if event.type == "content_delta":
                yield event.content

    def chat_stream_response(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[StreamEvent]:
        kwargs = {"model": self.model, "messages": messages, "stream": True}
        if tools:
            kwargs["tools"] = tools

        content_parts = []
        tool_calls: Dict[int, Dict[str, Any]] = {}
        finish_reason = "stop"

        for chunk in self.client.chat.completions.create(**kwargs):
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta
            content = getattr(delta, "content", None)
            if content:
                content_parts.append(content)
                yield StreamEvent(type="content_delta", content=content)

            for tool_delta in getattr(delta, "tool_calls", None) or []:
                index = getattr(tool_delta, "index", None)
                if index is None:
                    index = len(tool_calls)

                current = tool_calls.setdefault(index, {
                    "id": "",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                })

                tool_call_id = getattr(tool_delta, "id", None)
                if tool_call_id:
                    current["id"] = tool_call_id

                tool_call_type = getattr(tool_delta, "type", None)
                if tool_call_type:
                    current["type"] = tool_call_type

                function_delta = getattr(tool_delta, "function", None)
                if function_delta:
                    name = getattr(function_delta, "name", None)
                    arguments = getattr(function_delta, "arguments", None)
                    if name:
                        current["function"]["name"] += name
                    if arguments:
                        current["function"]["arguments"] += arguments

            if choice.finish_reason:
                finish_reason = choice.finish_reason

        normalized_tool_calls = []
        for idx in sorted(tool_calls):
            tool_call = tool_calls[idx]
            if not tool_call["id"] or tool_call["id"].strip() == "":
                tool_call["id"] = f"call_{idx}_{tool_call['function']['name']}"
                logger.warning("Generated fallback tool call id: %s", tool_call["id"])
            normalized_tool_calls.append(tool_call)

        yield StreamEvent(
            type="message_end",
            response=Response(
                content="".join(content_parts),
                tool_calls=normalized_tool_calls or None,
                finish_reason=finish_reason,
            ),
        )
