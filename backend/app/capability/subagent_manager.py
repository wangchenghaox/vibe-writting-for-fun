"""
SubAgent管理器 - 管理子代理的创建和执行
"""
from pathlib import Path
from typing import Any, Dict, Optional
import logging
import threading

logger = logging.getLogger(__name__)


def _provider_with_timeout(provider, timeout: float | None):
    if timeout is None:
        return provider

    with_timeout = getattr(type(provider), "with_timeout", None)
    if callable(with_timeout):
        return provider.with_timeout(float(timeout))

    return provider


class SubAgentManager:
    def __init__(self):
        self.subagents: Dict[str, Any] = {}
        self._reusable_subagent_ids: Dict[tuple, str] = {}
        self._next_subagent_index = 0
        self._execution_lock = threading.Lock()

    def _context_key(self, name: str, session, tool_context: dict | None = None) -> tuple:
        context = dict(session.context)
        context.update(tool_context or {})
        workdir = context.get("workdir") or ""
        if workdir:
            workdir = str(Path(workdir).expanduser().resolve(strict=False))
        return (
            session.id,
            context.get("user_id"),
            context.get("novel_id"),
            workdir,
            name,
        )

    def _subagent_context(self, name: str, subagent_id: str, session, tool_context: dict | None = None) -> dict:
        context = dict(session.context)
        context.update(tool_context or {})
        context["agent_name"] = name
        context["agent_instance_id"] = subagent_id
        return context

    def _subagent_context_nearly_full(self, subagent) -> bool:
        compressor = getattr(subagent, "context_compressor", None)
        subagent_session = getattr(subagent, "session", None)
        if compressor is None or subagent_session is None:
            return False

        return compressor.should_compress(subagent_session.get_messages())

    def create_subagent(
        self,
        name: str,
        provider,
        session,
        tool_context: dict | None = None,
        memory_recorder_factory=None,
        memory_enabled: bool = False,
        blocked_tool_names: set[str] | None = None,
        max_tool_rounds: int = 100,
        sub_agent_timeout: float | None = None,
    ) -> str:
        """创建子代理"""
        from ..agent.core import AgentCore
        from ..agent.session import Session
        from ..memory.event_recorder import MemoryEventRecorder

        index = self._next_subagent_index
        self._next_subagent_index += 1
        subagent_id = f"subagent_{name}_{index}"
        context = self._subagent_context(name, subagent_id, session, tool_context)
        subagent_session = Session(subagent_id)
        subagent_session.context.update(context)

        memory_recorder = None
        if memory_enabled:
            recorder_factory = memory_recorder_factory or MemoryEventRecorder
            memory_recorder = recorder_factory(
                user_id=context.get("user_id"),
                novel_id=context.get("novel_id"),
                agent_name=name,
                agent_instance_id=subagent_id,
                session_id=session.id,
            )
        subagent = AgentCore(
            _provider_with_timeout(provider, sub_agent_timeout),
            subagent_session,
            tool_context=context,
            memory_recorder=memory_recorder,
            memory_enabled=memory_enabled,
            max_tool_rounds=max_tool_rounds,
            blocked_tool_names=set(blocked_tool_names or set()) | {"create_sub_agent"},
            can_create_sub_agent=False,
        )
        self.subagents[subagent_id] = subagent

        logger.info(f"创建子代理: {subagent_id}")
        return subagent_id

    def get_or_create_subagent(
        self,
        name: str,
        provider,
        session,
        tool_context: dict | None = None,
        memory_recorder_factory=None,
        memory_enabled: bool = False,
        blocked_tool_names: set[str] | None = None,
        max_tool_rounds: int = 100,
        sub_agent_timeout: float | None = None,
    ) -> tuple[str, bool]:
        """按父会话、小说工作区和业务角色复用子代理。"""
        key = self._context_key(name, session, tool_context)
        existing_id = self._reusable_subagent_ids.get(key)
        if existing_id in self.subagents:
            subagent = self.subagents[existing_id]
            if self._subagent_context_nearly_full(subagent):
                logger.info(f"子代理上下文接近满载，创建新实例替换: {existing_id}")
                self.remove_subagent(existing_id)
            else:
                context = self._subagent_context(name, existing_id, session, tool_context)
                subagent.tool_context.update(context)
                subagent.session.context.update(context)
                logger.info(f"复用子代理: {existing_id}")
                return existing_id, False
        elif existing_id is not None:
            self._reusable_subagent_ids.pop(key, None)

        subagent_id = self.create_subagent(
            name,
            provider,
            session,
            tool_context=tool_context,
            memory_recorder_factory=memory_recorder_factory,
            memory_enabled=memory_enabled,
            blocked_tool_names=blocked_tool_names,
            max_tool_rounds=max_tool_rounds,
            sub_agent_timeout=sub_agent_timeout,
        )
        self._reusable_subagent_ids[key] = subagent_id
        return subagent_id, True

    def execute_subagent(self, subagent_id: str, message: str) -> Optional[str]:
        """执行子代理任务"""
        if subagent_id not in self.subagents:
            logger.error(f"子代理不存在: {subagent_id}")
            return None

        if not self._execution_lock.acquire(blocking=False):
            return "已有子 Agent 正在执行任务，请等待当前任务完成后再重试。"

        try:
            subagent = self.subagents[subagent_id]
            return subagent.chat(message)
        finally:
            self._execution_lock.release()

    def remove_subagent(self, subagent_id: str):
        """移除子代理"""
        if subagent_id in self.subagents:
            del self.subagents[subagent_id]
            self._reusable_subagent_ids = {
                key: value
                for key, value in self._reusable_subagent_ids.items()
                if value != subagent_id
            }
            logger.info(f"移除子代理: {subagent_id}")
