import pytest
from unittest.mock import Mock
from app.agent.core import AgentCore
from app.agent.session import Session


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
