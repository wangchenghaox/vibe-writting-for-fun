import threading
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


def test_create_subagent_uses_configured_max_tool_rounds():
    mock_provider = Mock()
    session = Session("test")
    manager = SubAgentManager()

    agent_id = manager.create_subagent(
        "writer",
        mock_provider,
        session,
        max_tool_rounds=33,
    )

    assert manager.subagents[agent_id].max_tool_rounds == 33


def test_create_subagent_uses_configured_sub_agent_timeout_without_mutating_parent_provider():
    class FakeProvider:
        def __init__(self, timeout):
            self.timeout = timeout
            self.clone_requests = []

        def with_timeout(self, timeout):
            self.clone_requests.append(timeout)
            return FakeProvider(timeout)

    provider = FakeProvider(timeout=120.0)
    session = Session("test")
    manager = SubAgentManager()

    agent_id = manager.create_subagent(
        "writer",
        provider,
        session,
        sub_agent_timeout=300.0,
    )

    assert provider.timeout == 120.0
    assert provider.clone_requests == [300.0]
    assert manager.subagents[agent_id].provider.timeout == 300.0


def test_get_or_create_subagent_reuses_same_role_with_same_context(tmp_path):
    mock_provider = Mock()
    session = Session("parent_session")
    session.context.update({
        "user_id": 1,
        "novel_id": "novel_1",
        "workdir": str(tmp_path / "novel_1"),
    })
    manager = SubAgentManager()

    first_id, first_created = manager.get_or_create_subagent("writer", mock_provider, session)
    manager.subagents[first_id].session.add_message("assistant", "已读取总纲")
    second_id, second_created = manager.get_or_create_subagent("writer", mock_provider, session)

    assert first_created is True
    assert second_created is False
    assert second_id == first_id
    assert manager.subagents[second_id].session.messages[-1]["content"] == "已读取总纲"


def test_get_or_create_subagent_keeps_roles_and_novels_isolated(tmp_path):
    mock_provider = Mock()
    session = Session("parent_session")
    manager = SubAgentManager()

    writer_id, _ = manager.get_or_create_subagent(
        "writer",
        mock_provider,
        session,
        tool_context={
            "user_id": 1,
            "novel_id": "novel_1",
            "workdir": str(tmp_path / "novel_1"),
        },
    )
    reviewer_id, _ = manager.get_or_create_subagent(
        "reviewer",
        mock_provider,
        session,
        tool_context={
            "user_id": 1,
            "novel_id": "novel_1",
            "workdir": str(tmp_path / "novel_1"),
        },
    )
    other_novel_writer_id, _ = manager.get_or_create_subagent(
        "writer",
        mock_provider,
        session,
        tool_context={
            "user_id": 1,
            "novel_id": "novel_2",
            "workdir": str(tmp_path / "novel_2"),
        },
    )

    assert writer_id != reviewer_id
    assert writer_id != other_novel_writer_id
    assert reviewer_id != other_novel_writer_id
    assert writer_id in manager.subagents
    assert reviewer_id in manager.subagents
    assert other_novel_writer_id in manager.subagents
    assert len(manager.subagents) == 3


def test_get_or_create_subagent_replaces_same_role_when_context_nearly_full(tmp_path):
    mock_provider = Mock()
    session = Session("parent_session")
    session.context.update({
        "user_id": 1,
        "novel_id": "novel_1",
        "workdir": str(tmp_path / "novel_1"),
    })
    manager = SubAgentManager()

    first_id, first_created = manager.get_or_create_subagent("writer", mock_provider, session)
    first_subagent = manager.subagents[first_id]
    first_subagent.context_compressor.max_tokens = 10
    first_subagent.session.add_message("user", "x" * 40)
    second_id, second_created = manager.get_or_create_subagent("writer", mock_provider, session)

    assert first_created is True
    assert second_created is True
    assert second_id != first_id
    assert first_id not in manager.subagents
    assert second_id in manager.subagents
    assert len(manager.subagents) == 1


def test_create_subagent_does_not_attach_recorder_by_default():
    mock_provider = Mock()
    session = Session("parent_session")
    manager = SubAgentManager()
    created_recorders = []

    class FakeRecorder:
        def __init__(self, **kwargs):
            created_recorders.append(self)

    agent_id = manager.create_subagent(
        "writer",
        mock_provider,
        session,
        tool_context={"user_id": 1, "novel_id": "novel_1"},
        memory_recorder_factory=FakeRecorder,
    )

    subagent = manager.subagents[agent_id]
    assert subagent.memory_recorder is None
    assert created_recorders == []


def test_create_subagent_attaches_recorder_with_runtime_identity_when_memory_enabled():
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
        memory_enabled=True,
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


def test_execute_subagent_records_raw_log_events_when_memory_enabled():
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
        memory_enabled=True,
    )

    assert manager.execute_subagent(agent_id, "hello") == "ok"
    assert created_recorders[0].records == [
        ("user_message", {"content": "hello"}),
        ("assistant_message", {"content": "ok"}),
    ]


def test_execute_subagent_rejects_parallel_execution():
    manager = SubAgentManager()
    entered = threading.Event()
    release = threading.Event()
    second_called = False

    class BlockingAgent:
        def chat(self, message):
            entered.set()
            assert release.wait(timeout=2)
            return "first done"

    class SecondAgent:
        def chat(self, message):
            nonlocal second_called
            second_called = True
            return "second done"

    manager.subagents["subagent_writer_0"] = BlockingAgent()
    manager.subagents["subagent_reviewer_1"] = SecondAgent()

    first_result = {}
    worker = threading.Thread(
        target=lambda: first_result.setdefault(
            "value",
            manager.execute_subagent("subagent_writer_0", "first"),
        )
    )
    worker.start()
    assert entered.wait(timeout=2)

    second_result = manager.execute_subagent("subagent_reviewer_1", "second")

    release.set()
    worker.join(timeout=2)
    assert first_result["value"] == "first done"
    assert "已有子 Agent 正在执行任务" in second_result
    assert second_called is False


def test_remove_subagent():
    mock_provider = Mock()
    session = Session("test")
    manager = SubAgentManager()
    agent_id = manager.create_subagent("test", mock_provider, session)
    manager.remove_subagent(agent_id)
    assert agent_id not in manager.subagents
