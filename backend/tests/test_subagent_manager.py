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


def test_create_subagent_overrides_inherited_identity():
    mock_provider = Mock()
    session = Session("test")
    manager = SubAgentManager()

    agent_id = manager.create_subagent(
        "writer",
        mock_provider,
        session,
        tool_context={"agent_name": "main", "agent_instance_id": "parent"},
    )

    subagent = manager.subagents[agent_id]
    assert subagent.tool_context["agent_name"] == "writer"
    assert subagent.tool_context["agent_instance_id"] == agent_id
    assert subagent.session.context["agent_name"] == "writer"
    assert subagent.session.context["agent_instance_id"] == agent_id


def test_create_subagent_ids_do_not_collide_after_removal():
    mock_provider = Mock()
    session = Session("test")
    manager = SubAgentManager()

    writer_id = manager.create_subagent("writer", mock_provider, session)
    first_editor_id = manager.create_subagent("editor", mock_provider, session)
    manager.remove_subagent(writer_id)
    second_editor_id = manager.create_subagent("editor", mock_provider, session)

    assert writer_id == "subagent_writer_0"
    assert first_editor_id == "subagent_editor_1"
    assert second_editor_id == "subagent_editor_2"
    assert first_editor_id in manager.subagents
    assert second_editor_id in manager.subagents
    assert first_editor_id != second_editor_id


def test_remove_subagent():
    mock_provider = Mock()
    session = Session("test")
    manager = SubAgentManager()
    agent_id = manager.create_subagent("test", mock_provider, session)
    manager.remove_subagent(agent_id)
    assert agent_id not in manager.subagents
