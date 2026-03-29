from typing import List, Dict, Any, Optional, Iterator
import logging
from openai import OpenAI
from .provider import LLMProvider, Response

logger = logging.getLogger(__name__)

class KimiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, base_url: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Response:
        kwargs = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools

        logger.debug(f"Sending {len(messages)} messages to Kimi API")
        if len(messages) > 0:
            logger.debug(f"Last message: {messages[-1]}")

        completion = self.client.chat.completions.create(**kwargs)
        msg = completion.choices[0].message

        # 处理 tool_calls，确保每个都有有效的 id
        tool_calls = None
        if msg.tool_calls:
            tool_calls = []
            for idx, tc in enumerate(msg.tool_calls):
                tc_dict = tc.model_dump()
                logger.debug(f"Original tool_call: {tc_dict}")
                # 确保 id 非空
                if not tc_dict.get("id") or tc_dict["id"].strip() == "":
                    tc_dict["id"] = f"call_{idx}_{tc_dict['function']['name']}"
                    logger.warning(f"Generated fallback id: {tc_dict['id']}")
                tool_calls.append(tc_dict)

        return Response(
            content=msg.content or "",
            tool_calls=tool_calls,
            finish_reason=completion.choices[0].finish_reason
        )

    def chat_stream(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Iterator[str]:
        kwargs = {"model": self.model, "messages": messages, "stream": True}
        if tools:
            kwargs["tools"] = tools

        for chunk in self.client.chat.completions.create(**kwargs):
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
