import json

from app.capability.tool_registry import tool, execute_tool, get_tool_schemas
from app.tools.review_tools import review_chapter


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


def test_tool_schema_filtering_by_allowed_names():
    @tool(name="allowed_schema_tool", description="Allowed")
    def allowed_schema_tool() -> str:
        return "allowed"

    @tool(name="blocked_schema_tool", description="Blocked")
    def blocked_schema_tool() -> str:
        return "blocked"

    schemas = get_tool_schemas(allowed_names=["allowed_schema_tool"])

    assert [schema["function"]["name"] for schema in schemas] == ["allowed_schema_tool"]


def test_review_chapter_returns_payload_without_embedded_review_policy(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    chapter_dir = tmp_path / "novels" / "novel_review" / "chapters"
    chapter_dir.mkdir(parents=True)
    (chapter_dir / "chapter_1.json").write_text(
        json.dumps({"id": "chapter_1", "title": "第一章", "content": "正文"}),
        encoding="utf-8",
    )

    payload = json.loads(review_chapter("chapter_1", novel_id="novel_review"))

    assert payload == {
        "chapter_id": "chapter_1",
        "title": "第一章",
        "content": "正文",
    }


def test_tool_context_params_are_hidden_from_schema_and_injected():
    @tool(
        name="context_hidden_tool",
        description="Context hidden",
        context_params=["user_id", "novel_id"],
    )
    def context_hidden_tool(public: str, user_id: int = None, novel_id: str = None) -> str:
        return f"{public}:{user_id}:{novel_id}"

    schema = next(
        item for item in get_tool_schemas(allowed_names=["context_hidden_tool"])
        if item["function"]["name"] == "context_hidden_tool"
    )

    assert set(schema["function"]["parameters"]["properties"]) == {"public"}
    assert schema["function"]["parameters"]["required"] == ["public"]

    result = execute_tool(
        "context_hidden_tool",
        {"public": "hello", "user_id": 999, "novel_id": "spoof"},
        context={"user_id": 7, "novel_id": "novel_ctx"},
    )

    assert result == "hello:7:novel_ctx"


def test_non_context_params_keep_existing_injection_behavior():
    @tool(name="context_optional_tool", description="Optional context")
    def context_optional_tool(novel_id: str = None) -> str:
        return novel_id or "missing"

    assert execute_tool(
        "context_optional_tool",
        {},
        context={"novel_id": "novel_ctx"},
    ) == "novel_ctx"
