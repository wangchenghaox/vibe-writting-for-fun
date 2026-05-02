from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.agent.core import AgentCore
from app.agent.session import Session
from app.capability.tool_registry import get_tool_schemas, tool


def test_cli_import_exposes_file_memory_and_search_tools_without_json_domain_tools():
    import app.cli.app  # noqa: F401

    tool_names = {schema["function"]["name"] for schema in get_tool_schemas()}

    assert {
        "read_file",
        "write_file",
        "edit_file",
        "list_files",
        "search_files",
        "grep_files",
        "web_search",
        "remember_memory",
        "search_memory",
        "list_memories",
        "archive_memory",
    }.issubset(tool_names)
    assert {
        "get_novel",
        "save_novel_document",
        "load_novel_document",
        "list_novel_documents",
    }.isdisjoint(tool_names)


def test_agent_injects_context_novel_id_when_tool_call_omits_it():
    tool_name = f"context_probe_{uuid4().hex}"

    @tool(name=tool_name, description="Return the injected novel id")
    def context_probe(novel_id: str = None) -> str:
        return novel_id or "missing"

    provider = Mock()
    provider.chat.side_effect = [
        SimpleNamespace(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": tool_name, "arguments": "{}"},
                }
            ],
        ),
        SimpleNamespace(content="done", tool_calls=None),
    ]

    agent = AgentCore(provider, Session("ctx-session"), tool_context={"novel_id": "novel_ctx"})

    assert agent.chat("run") == "done"
    second_call_messages = provider.chat.call_args_list[1].args[0]
    assert any(
        msg["role"] == "tool" and msg["content"] == "novel_ctx"
        for msg in second_call_messages
    )
