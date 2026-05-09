import json
from types import SimpleNamespace

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


def test_bash_allows_mkdir_inside_workdir(tmp_path):
    result = execute_tool(
        "bash",
        {"command": "mkdir -p drafts/chapter_01"},
        context={"workdir": str(tmp_path)},
    )

    payload = json.loads(result)
    assert payload["exit_code"] == 0
    assert payload["stdout"] == ""
    assert (tmp_path / "drafts" / "chapter_01").is_dir()


def test_bash_rejects_mkdir_outside_workdir(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}_outside_dir"

    result = execute_tool(
        "bash",
        {"command": f"mkdir {outside}"},
        context={"workdir": str(tmp_path)},
    )

    assert result.startswith("操作被拒绝")
    assert not outside.exists()


def test_bash_allows_simple_pipeline_inside_workdir(tmp_path):
    (tmp_path / "notes.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    result = execute_tool(
        "bash",
        {"command": "cat notes.txt | grep beta"},
        context={"workdir": str(tmp_path)},
    )

    payload = json.loads(result)
    assert payload["exit_code"] == 0
    assert payload["stdout"] == "beta"
    assert payload["stderr"] == ""


def test_bash_rejects_blocked_command_inside_pipeline(tmp_path):
    note = tmp_path / "notes.txt"
    note.write_text("alpha\n", encoding="utf-8")

    result = execute_tool(
        "bash",
        {"command": "cat notes.txt | rm notes.txt"},
        context={"workdir": str(tmp_path)},
    )

    assert result.startswith("操作被拒绝")
    assert note.exists()


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


def test_main_agent_prompt_forbids_concrete_creation_review_and_writing(tmp_path):
    class FakeProvider:
        def __init__(self):
            self.messages = None

        def chat(self, messages, tools=None):
            self.messages = messages
            return Response(content="我需要先确认篇幅和目标路径。", tool_calls=None, finish_reason="stop")

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

    agent.chat("帮我生成世界观并保存")

    system_text = "\n".join(
        msg["content"] for msg in provider.messages if msg["role"] == "system"
    )
    assert "主 Agent 不能直接生成正文、大纲、人设、世界观、细纲、改写稿或审稿意见" in system_text
    assert "生成、审稿、改写、整理成稿、保存或文件修改" in system_text
    assert "必须调用 create_sub_agent" in system_text
    assert "任务单" in system_text


def test_create_sub_agent_task_schema_rejects_main_agent_finished_drafts():
    from app.capability.tool_registry import get_tool_schemas

    schema = next(
        item for item in get_tool_schemas(allowed_names=["create_sub_agent"])
        if item["function"]["name"] == "create_sub_agent"
    )

    task_description = schema["function"]["parameters"]["properties"]["task"]["description"]
    assert "不要把主 Agent 自己生成的大段正文" in task_description
    assert "任务单" in task_description


def test_main_agent_retries_with_subagent_when_it_generates_concrete_output(tmp_path):
    class FakeProvider:
        def __init__(self):
            self.calls = []

        def chat(self, messages, tools=None):
            self.calls.append(messages)
            if len(self.calls) == 1:
                return Response(
                    content=(
                        "# 世界观设定\n\n"
                        "## 核心规则\n\n"
                        "灵潮复苏后，城市依赖梦境税维持秩序。\n\n"
                        "## 势力\n\n"
                        "第一势力掌控档案塔，第二势力控制地下剧场。\n\n"
                        "## 分卷大纲\n\n"
                        "第一卷：主角发现自己的小说正在改写现实。\n"
                    ),
                    tool_calls=None,
                    finish_reason="stop",
                )
            if len(self.calls) == 2:
                return Response(
                    content="",
                    tool_calls=[{
                        "id": "call_delegate_worldbuilding",
                        "type": "function",
                        "function": {
                            "name": "create_sub_agent",
                            "arguments": json.dumps({
                                "name": "planner",
                                "task": "根据用户请求生成完整世界观、势力设定和分卷大纲，完成后返回结果；不要等待用户输入。",
                            }, ensure_ascii=False),
                        },
                    }],
                    finish_reason="tool_calls",
                )
            return Response(content="已交给子 Agent 完成。", tool_calls=None, finish_reason="stop")

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

    assert agent.chat("生成完整的世界观、势力设定和分卷大纲") == "已交给子 Agent 完成。"

    assert len(provider.calls) >= 3
    correction_text = "\n".join(
        msg["content"] for msg in provider.calls[1] if msg["role"] == "system"
    )
    assert "主 Agent 刚才输出了具体成品内容" in correction_text
    assert "改为调用 create_sub_agent" in correction_text
    assert all(
        "灵潮复苏后" not in msg.get("content", "")
        for msg in agent.session.messages
    )
    assert any(
        msg["role"] == "tool"
        and msg["name"] == "create_sub_agent"
        and "planner" in msg["content"]
        for msg in agent.session.messages
    )


def test_main_agent_stream_does_not_emit_concrete_output_before_delegation(tmp_path):
    generated = "# 大纲\n\n## 核心设定\n\n主角发现小说会改写现实。\n\n## 分卷\n\n第一卷追查源头。"

    class FakeProvider:
        def __init__(self):
            self.stream_calls = 0

        def chat(self, messages, tools=None):
            return Response(content="子 Agent 已完成大纲。", tool_calls=None, finish_reason="stop")

        def chat_stream_response(self, messages, tools=None):
            self.stream_calls += 1
            if self.stream_calls == 1:
                return iter([
                    SimpleNamespace(type="content_delta", content=generated),
                    SimpleNamespace(
                        type="message_end",
                        response=Response(content=generated, tool_calls=None, finish_reason="stop"),
                    ),
                ])
            if self.stream_calls == 2:
                return iter([
                    SimpleNamespace(
                        type="message_end",
                        response=Response(
                            content="",
                            tool_calls=[{
                                "id": "call_delegate_outline",
                                "type": "function",
                                "function": {
                                    "name": "create_sub_agent",
                                    "arguments": json.dumps({
                                        "name": "planner",
                                        "task": "生成完整大纲并返回结果。",
                                    }, ensure_ascii=False),
                                },
                            }],
                            finish_reason="tool_calls",
                        ),
                    )
                ])
            return iter([
                SimpleNamespace(type="content_delta", content="已交给子 Agent 完成。"),
                SimpleNamespace(
                    type="message_end",
                    response=Response(content="已交给子 Agent 完成。", tool_calls=None, finish_reason="stop"),
                ),
            ])

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

    chunks = list(agent.chat_stream("生成一个完整大纲"))

    assert chunks == ["已交给子 Agent 完成。"]
    assert all(
        "主角发现小说会改写现实" not in msg.get("content", "")
        for msg in agent.session.messages
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
