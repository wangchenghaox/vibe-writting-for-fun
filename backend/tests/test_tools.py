import pytest
from app.capability.tool_registry import tool, execute_tool, get_tool_schemas


def test_tool_registration():
    @tool(name="test_tool", description="A test tool")
    def my_tool(arg1: str) -> str:
        return f"Result: {arg1}"

    schemas = get_tool_schemas()
    tool_names = [s["function"]["name"] for s in schemas]
    assert "test_tool" in tool_names

    result = execute_tool("test_tool", {"arg1": "hello"})
    assert result == "Result: hello"


def test_tool_schema_generation():
    @tool(name="schema_test", description="Test schema")
    def schema_tool(name: str, age: int) -> str:
        return f"{name} is {age}"

    schemas = get_tool_schemas()
    tool_names = [s["function"]["name"] for s in schemas]
    assert "schema_test" in tool_names
