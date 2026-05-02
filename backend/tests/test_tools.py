import json

from app.capability.tool_registry import tool, execute_tool, get_tool_schemas
import app.tools as _tools  # noqa: F401
from app.tools.novel_tools import (
    create_novel,
    get_novel,
    list_novel_documents,
    load_novel_document,
    save_novel_document,
)
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


def test_json_domain_tools_are_not_exposed_to_agent_schema():
    tool_names = {schema["function"]["name"] for schema in get_tool_schemas()}

    assert {
        "create_novel",
        "get_novel",
        "save_novel_document",
        "load_novel_document",
        "list_novel_documents",
        "review_chapter",
        "list_novels",
        "get_novel_info",
        "save_outline",
        "load_outline",
        "save_chapter",
        "load_chapter",
        "list_chapters",
    }.isdisjoint(tool_names)

    assert {
        "read_file",
        "write_file",
        "edit_file",
        "list_files",
        "search_files",
        "grep_files",
    }.issubset(tool_names)


def test_legacy_json_helpers_manage_novels_and_documents(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)

    assert "Novel created" in create_novel("novel_slim", "瘦身测试", "描述")

    novels = json.loads(get_novel())
    assert novels == [{
        "id": "novel_slim",
        "title": "瘦身测试",
        "description": "描述",
        "created_at": novels[0]["created_at"],
    }]

    novel_info = json.loads(get_novel("novel_slim"))
    assert novel_info["title"] == "瘦身测试"

    assert "Document saved" in save_novel_document(
        "outline",
        "main",
        "总大纲",
        novel_id="novel_slim",
    )
    assert json.loads(load_novel_document("outline", "main", novel_id="novel_slim")) == {
        "id": "main",
        "content": "总大纲",
    }

    assert "Document saved" in save_novel_document(
        "chapter",
        "chapter_1",
        "正文",
        title="第一章",
        novel_id="novel_slim",
    )
    assert json.loads(load_novel_document("chapter", "chapter_1", novel_id="novel_slim")) == {
        "id": "chapter_1",
        "title": "第一章",
        "content": "正文",
    }
    assert json.loads(list_novel_documents("chapter", novel_id="novel_slim")) == ["chapter_1"]


def test_legacy_json_helpers_return_error_for_invalid_document_type(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)

    assert save_novel_document("note", "n1", "content", novel_id="novel_slim").startswith(
        "Invalid document_type"
    )
    assert load_novel_document("note", "n1", novel_id="novel_slim").startswith(
        "Invalid document_type"
    )
    assert list_novel_documents("note", novel_id="novel_slim").startswith(
        "Invalid document_type"
    )


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
