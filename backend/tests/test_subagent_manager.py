from types import SimpleNamespace
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


def test_create_subagent_attaches_recorder_with_runtime_identity():
    mock_provider = Mock()
    session = Session("parent_session")
    manager = SubAgentManager()
    created_recorders = []

    class FakeRecorder:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.records = []
            created_recorders.append(self)

        def record(self, event_type, payload):
            self.records.append((event_type, payload))

    agent_id = manager.create_subagent(
        "writer",
        mock_provider,
        session,
        tool_context={"user_id": 1, "novel_id": "novel_1"},
        memory_recorder_factory=FakeRecorder,
    )

    subagent = manager.subagents[agent_id]
    recorder = created_recorders[0]
    assert subagent.memory_recorder is recorder
    assert recorder.kwargs == {
        "user_id": 1,
        "novel_id": "novel_1",
        "agent_name": "writer",
        "agent_instance_id": agent_id,
        "session_id": "parent_session",
    }


def test_execute_subagent_records_raw_log_events():
    provider = Mock()
    provider.chat.return_value = SimpleNamespace(content="ok", tool_calls=None)
    session = Session("parent_session")
    manager = SubAgentManager()
    created_recorders = []

    class FakeRecorder:
        def __init__(self, **kwargs):
            self.records = []
            created_recorders.append(self)

        def record(self, event_type, payload):
            self.records.append((event_type, payload))

    agent_id = manager.create_subagent(
        "writer",
        provider,
        session,
        tool_context={"user_id": 1, "novel_id": "novel_1"},
        memory_recorder_factory=FakeRecorder,
    )

    assert manager.execute_subagent(agent_id, "hello") == "ok"
    assert created_recorders[0].records == [
        ("user_message", {"content": "hello"}),
        ("assistant_message", {"content": "ok"}),
    ]


def test_remove_subagent():
    mock_provider = Mock()
    session = Session("test")
    manager = SubAgentManager()
    agent_id = manager.create_subagent("test", mock_provider, session)
    manager.remove_subagent(agent_id)
    assert agent_id not in manager.subagents
