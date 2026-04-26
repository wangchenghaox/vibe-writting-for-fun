from typing import Any, Dict, Iterator, List, Optional
import logging

from openai import OpenAI

from .provider import LLMProvider, Response

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
        kwargs = {"model": self.model, "messages": messages, "stream": True}
        if tools:
            kwargs["tools"] = tools

        for chunk in self.client.chat.completions.create(**kwargs):
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
