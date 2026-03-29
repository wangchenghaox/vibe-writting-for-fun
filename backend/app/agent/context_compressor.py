"""
Context压缩模块 - 管理对话历史的压缩策略
"""
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class ContextCompressor:
    def __init__(self, max_tokens: int = 100000, compress_threshold: float = 0.7):
        self.max_tokens = max_tokens
        self.compress_threshold = compress_threshold
        self.recent_keep_count = 10  # 保留最近10条消息

    def should_compress(self, messages: List[Dict[str, Any]]) -> bool:
        """判断是否需要压缩"""
        estimated_tokens = self._estimate_tokens(messages)
        should = estimated_tokens > (self.max_tokens * self.compress_threshold)
        if should:
            logger.info(f"触发压缩: {estimated_tokens} tokens > {self.max_tokens * self.compress_threshold}")
        return should

    def compress(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """压缩消息历史"""
        if len(messages) <= self.recent_keep_count:
            return messages

        # 保留system消息
        system_msgs = [m for m in messages if m.get("role") == "system"]

        # 保留最近的消息
        recent_msgs = messages[-self.recent_keep_count:]

        # 中间消息生成摘要
        middle_msgs = messages[len(system_msgs):-self.recent_keep_count]
        summary = self._summarize_messages(middle_msgs)

        compressed = system_msgs + [summary] + recent_msgs
        logger.info(f"压缩消息: {len(messages)} -> {len(compressed)}")
        return compressed

    def _estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """估算token数量（简化实现）"""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += len(content) // 4  # 粗略估算：4字符≈1token
        return total

    def _summarize_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成消息摘要"""
        user_queries = []
        tool_actions = []

        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")[:50]
                user_queries.append(content)
            elif msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    tool_name = tc.get("function", {}).get("name", "")
                    tool_actions.append(tool_name)

        summary_parts = []
        if user_queries:
            summary_parts.append(f"用户请求: {', '.join(user_queries[:3])}")
        if tool_actions:
            summary_parts.append(f"执行工具: {', '.join(set(tool_actions))}")

        summary_text = f"[历史摘要] {' | '.join(summary_parts)}"

        return {
            "role": "system",
            "content": summary_text
        }
