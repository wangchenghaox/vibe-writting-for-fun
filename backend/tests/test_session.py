import pytest
from app.agent.session import Session


class TestSession:
    def test_session_creation(self):
        session = Session("test_session")
        assert session.id == "test_session"
        assert len(session.messages) == 0

    def test_add_user_message(self):
        session = Session("test")
        session.add_message("user", "Hello")
        assert len(session.messages) == 1
        assert session.messages[0]["role"] == "user"
        assert session.messages[0]["content"] == "Hello"

    def test_add_assistant_message(self):
        session = Session("test")
        session.add_message("assistant", "Hi there")
        assert len(session.messages) == 1
        assert session.messages[0]["role"] == "assistant"

    def test_add_tool_message(self):
        session = Session("test")
        session.add_message("tool", "result", tool_call_id="call_123", name="test_tool")
        assert len(session.messages) == 1
        assert session.messages[0]["role"] == "tool"
        assert session.messages[0]["tool_call_id"] == "call_123"

    def test_session_serialization(self):
        session1 = Session("serialize_test")
        session1.add_message("user", "Test message")

        data = session1.to_dict()
        session2 = Session.from_dict(data)

        assert session2.id == "serialize_test"
        assert len(session2.messages) == 1
        assert session2.messages[0]["content"] == "Test message"
