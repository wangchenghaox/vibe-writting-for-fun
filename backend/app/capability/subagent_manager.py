"""
SubAgent管理器 - 管理子代理的创建和执行
"""
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SubAgentManager:
    def __init__(self):
        self.subagents: Dict[str, Any] = {}
        self._next_subagent_index = 0

    def create_subagent(
        self,
        name: str,
        provider,
        session,
        tool_context: dict | None = None,
    ) -> str:
        """创建子代理"""
        from ..agent.core import AgentCore

        index = self._next_subagent_index
        self._next_subagent_index += 1
        subagent_id = f"subagent_{name}_{index}"
        context = dict(tool_context or {})
        context["agent_name"] = name
        context["agent_instance_id"] = subagent_id
        session.context.update(context)

        subagent = AgentCore(provider, session, tool_context=context)
        self.subagents[subagent_id] = subagent

        logger.info(f"创建子代理: {subagent_id}")
        return subagent_id

    def execute_subagent(self, subagent_id: str, message: str) -> Optional[str]:
        """执行子代理任务"""
        if subagent_id not in self.subagents:
            logger.error(f"子代理不存在: {subagent_id}")
            return None

        subagent = self.subagents[subagent_id]
        return subagent.chat(message)

    def remove_subagent(self, subagent_id: str):
        """移除子代理"""
        if subagent_id in self.subagents:
            del self.subagents[subagent_id]
            logger.info(f"移除子代理: {subagent_id}")
