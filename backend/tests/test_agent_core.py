import pytest
from types import SimpleNamespace
from unittest.mock import Mock
from app.agent.core import AgentCore
from app.agent.session import Session
from app.capability.tool_registry import tool
from app.events.event_types import EventType
from uuid import uuid4


class TestAgentCore:
    @pytest.fixture
    def mock_provider(self):
        provider = Mock()
        provider.chat.return_value = Mock(
            content="Test response",
            tool_calls=None
        )
        return provider

    @pytest.fixture
    def session(self):
        return Session("test_agent")

    def test_agent_initialization(self, mock_provider, session):
        agent = AgentCore(mock_provider, session)
        assert agent.provider == mock_provider
        assert agent.session == session

    def test_chat_simple_response(self, mock_provider, session):
        agent = AgentCore(mock_provider, session)
        response = agent.chat("Hello")

        assert response == "Test response"
        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["role"] == "assistant"

    def test_chat_stops_after_max_tool_rounds(self, session):
        tool_name = f"loop_probe_{uuid4().hex}"

        @tool(name=tool_name, description="Loop probe")
        def loop_probe() -> str:
            return "again"

        provider = Mock()
        provider.chat.return_value = SimpleNamespace(
            content="",
            tool_calls=[
                {
                    "id": "call_loop",
                    "type": "function",
                    "function": {"name": tool_name, "arguments": "{}"},
                }
            ],
        )

        agent = AgentCore(provider, session, max_tool_rounds=2)
        errors = []

        def on_error(event):
            if event.session_id == session.id:
                errors.append(event)

        agent.event_bus.subscribe(EventType.ERROR, on_error)
        try:
            with pytest.raises(RuntimeError, match="maximum tool rounds"):
                agent.chat("loop")
        finally:
            agent.event_bus.unsubscribe(EventType.ERROR, on_error)

        assert provider.chat.call_count == 2
        assert errors
        assert "maximum tool rounds" in errors[0].data["message"]
