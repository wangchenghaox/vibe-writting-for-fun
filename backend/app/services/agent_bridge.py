"""
AI Agent包装器，用于在Web后端中使用ai-agent-core
"""
import sys
import os
from pathlib import Path

# 添加ai-agent-core/src到Python路径
agent_core_path = Path(__file__).parent.parent.parent.parent / "ai-agent-core" / "src"
sys.path.insert(0, str(agent_core_path))

# 导入必要的模块
from agent.core import AgentCore
from agent.session import Session
from llm.config import create_provider
from events.event_types import EventType

__all__ = ['AgentCore', 'Session', 'create_provider', 'EventType']
