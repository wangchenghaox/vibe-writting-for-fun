from unittest.mock import Mock

from app.agent.session import Session
from app.capability.subagent_manager import SubAgentManager


def test_create_subagent_sets_stable_agent_name_and_runtime_instance_id():
    mock_provider = Mock()
    session = Session("test")
    manager = SubAgentManager()

    agent_id = manager.create_subagent(
        "writer",
        mock_provider,
        session,
        tool_context={"user_id": 1, "novel_id": "novel_1"},
    )

    subagent = manager.subagents[agent_id]
    assert agent_id.startswith("subagent_writer_")
    assert subagent.tool_context["user_id"] == 1
    assert subagent.tool_context["novel_id"] == "novel_1"
    assert subagent.tool_context["agent_name"] == "writer"
    assert subagent.tool_context["agent_instance_id"] == agent_id
    assert subagent.session.context["agent_name"] == "writer"
    assert subagent.session.context["agent_instance_id"] == agent_id


def test_remove_subagent():
    mock_provider = Mock()
    session = Session("test")
    manager = SubAgentManager()
    agent_id = manager.create_subagent("test", mock_provider, session)
    manager.remove_subagent(agent_id)
    assert agent_id not in manager.subagents
