import json

from app.agent.core import AgentCore
from app.agent.session import Session
from app.capability.tool_registry import execute_tool
from app.llm.provider import Response
import app.tools as _tools  # noqa: F401


def test_bash_runs_simple_command_inside_workdir(tmp_path):
    (tmp_path / "notes.txt").write_text("hello from workspace", encoding="utf-8")

    result = execute_tool(
        "bash",
        {"command": "cat notes.txt"},
        context={"workdir": str(tmp_path)},
    )

    payload = json.loads(result)
    assert payload["exit_code"] == 0
    assert payload["stdout"] == "hello from workspace"
    assert payload["stderr"] == ""


def test_bash_rejects_destructive_or_outside_commands(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    assert execute_tool(
        "bash",
        {"command": "rm notes.txt"},
        context={"workdir": str(tmp_path)},
    ).startswith("操作被拒绝")

    assert execute_tool(
        "bash",
        {"command": "cat ../outside.txt"},
        context={"workdir": str(tmp_path)},
    ).startswith("操作被拒绝")


def test_todo_list_persists_items_to_workdir_file(tmp_path):
    added = json.loads(execute_tool(
        "todo_list",
        {"action": "add", "content": "整理第一章伏笔"},
        context={"workdir": str(tmp_path)},
    ))
    todo_id = added["item"]["id"]

    todo_file = tmp_path / ".agent" / "todo_list.json"
    assert todo_file.exists()

    updated = json.loads(execute_tool(
        "todo_list",
        {"action": "update", "todo_id": todo_id, "status": "completed"},
        context={"workdir": str(tmp_path)},
    ))
    listed = json.loads(execute_tool(
        "todo_list",
        {"action": "list"},
        context={"workdir": str(tmp_path)},
    ))

    assert updated["item"]["status"] == "completed"
    assert listed["items"] == [
        {"id": todo_id, "content": "整理第一章伏笔", "status": "completed"}
    ]
    assert json.loads(todo_file.read_text(encoding="utf-8")) == listed


def test_create_sub_agent_inherits_main_context_and_hides_subagent_tool(tmp_path):
    class FakeProvider:
        def __init__(self):
            self.tool_names_by_call = []
            self.messages_by_call = []

        def chat(self, messages, tools=None):
            self.messages_by_call.append(messages)
            self.tool_names_by_call.append([
                tool["function"]["name"] for tool in (tools or [])
            ])
            if len(self.tool_names_by_call) == 1:
                return Response(
                    content="",
                    tool_calls=[{
                        "id": "call_create_sub_agent",
                        "type": "function",
                        "function": {
                            "name": "create_sub_agent",
                            "arguments": json.dumps({
                                "name": "writer",
                                "task": "写一个简短方案",
                            }, ensure_ascii=False),
                        },
                    }],
                    finish_reason="tool_calls",
                )
            if len(self.tool_names_by_call) == 2:
                return Response(content="子 Agent 结果", tool_calls=None, finish_reason="stop")
            return Response(content="主 Agent 完成", tool_calls=None, finish_reason="stop")

        def chat_stream(self, messages, tools=None):
            yield self.chat(messages, tools).content

    provider = FakeProvider()
    session = Session("main-session")
    agent = AgentCore(
        provider,
        session,
        tool_context={
            "user_id": 0,
            "novel_id": "novel_ctx",
            "workdir": str(tmp_path),
            "agent_name": "main",
            "agent_instance_id": "main-session",
        },
    )

    assert agent.chat("创建一个写作子 Agent") == "主 Agent 完成"

    assert len(agent.subagent_manager.subagents) == 1
    subagent = next(iter(agent.subagent_manager.subagents.values()))
    assert subagent.tool_context["user_id"] == 0
    assert subagent.tool_context["novel_id"] == "novel_ctx"
    assert subagent.tool_context["workdir"] == str(tmp_path)
    assert subagent.tool_context["agent_name"] == "writer"
    assert "create_sub_agent" in provider.tool_names_by_call[0]
    assert "create_sub_agent" not in provider.tool_names_by_call[1]
    assert "write_file" in provider.tool_names_by_call[1]
    assert any(
        msg["role"] == "system"
        and "不能直接与用户对话" in msg["content"]
        for msg in provider.messages_by_call[1]
    )


def test_main_agent_hides_and_blocks_file_mutation_tools(tmp_path):
    target = tmp_path / "draft.md"

    class FakeProvider:
        def __init__(self):
            self.tool_names_by_call = []

        def chat(self, messages, tools=None):
            self.tool_names_by_call.append([
                tool["function"]["name"] for tool in (tools or [])
            ])
            if len(self.tool_names_by_call) == 1:
                return Response(
                    content="",
                    tool_calls=[{
                        "id": "call_write_file",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": json.dumps({
                                "path": "draft.md",
                                "content": "主 Agent 不应该写入",
                            }, ensure_ascii=False),
                        },
                    }],
                    finish_reason="tool_calls",
                )
            return Response(content="我会交给子 Agent 执行。", tool_calls=None, finish_reason="stop")

        def chat_stream(self, messages, tools=None):
            yield self.chat(messages, tools).content

    provider = FakeProvider()
    agent = AgentCore(
        provider,
        Session("main-session"),
        tool_context={
            "workdir": str(tmp_path),
            "agent_name": "main",
            "agent_instance_id": "main-session",
        },
    )

    assert agent.chat("保存草稿") == "我会交给子 Agent 执行。"

    first_tool_names = set(provider.tool_names_by_call[0])
    assert "create_sub_agent" in first_tool_names
    assert "write_file" not in first_tool_names
    assert "edit_file" not in first_tool_names
    assert "delete_file" not in first_tool_names
    assert "rename_file" not in first_tool_names
    assert not target.exists()
    assert any(
        msg["role"] == "tool"
        and msg["name"] == "write_file"
        and "当前 Agent 不允许调用工具" in msg["content"]
        for msg in agent.session.messages
    )
