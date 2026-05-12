import json
import re
from pathlib import Path
from typing import Optional

from app.capability.tool_registry import tool
from app.core.config import settings


TODO_STATUSES = {"pending", "in_progress", "completed"}


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False)


def _workdir(workdir: str = None) -> Path:
    configured = workdir or getattr(settings, "WORKDIR", None)
    if not configured:
        configured = Path(settings.DATA_DIR) / "novels"
    root = Path(configured).expanduser().resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _todo_file(workdir: str = None) -> Path:
    return _workdir(workdir) / ".agent" / "todo_list.json"


def _load_todos(path: Path) -> dict:
    if not path.exists():
        return {"items": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return {"items": []}
    return data


def _save_todos(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json(data), encoding="utf-8")


def _next_todo_id(items: list[dict]) -> str:
    max_seen = 0
    for item in items:
        match = re.fullmatch(r"todo_(\d+)", str(item.get("id", "")))
        if match:
            max_seen = max(max_seen, int(match.group(1)))
    return f"todo_{max_seen + 1}"


def _find_todo(items: list[dict], todo_id: str) -> Optional[dict]:
    return next((item for item in items if item.get("id") == todo_id), None)


@tool(
    name="todo_list",
    description=(
        "Maintain a persistent todo list stored in the current workspace file .agent/todo_list.json. "
        "Actions: add, list, update, remove, clear."
    ),
    context_params=["workdir"],
    parameter_descriptions={
        "action": "One of add, list, update, remove, clear.",
        "content": "Todo content for add, or replacement content for update.",
        "todo_id": "Todo id for update or remove.",
        "status": "Todo status: pending, in_progress, or completed.",
    },
)
def todo_list(
    action: str,
    content: str = None,
    todo_id: str = None,
    status: str = None,
    workdir: str = None,
) -> str:
    action = (action or "").strip().lower()
    path = _todo_file(workdir)
    data = _load_todos(path)
    items = data["items"]

    if action == "list":
        _save_todos(path, data)
        return _json(data)

    if action == "add":
        if not content or not content.strip():
            return "content 不能为空"
        item_status = status or "pending"
        if item_status not in TODO_STATUSES:
            return f"无效状态: {item_status}"
        item = {"id": _next_todo_id(items), "content": content.strip(), "status": item_status}
        items.append(item)
        _save_todos(path, data)
        return _json({"item": item, "items": items})

    if action == "update":
        if not todo_id:
            return "todo_id 不能为空"
        item = _find_todo(items, todo_id)
        if item is None:
            return f"todo 不存在: {todo_id}"
        if content is not None and content.strip():
            item["content"] = content.strip()
        if status is not None:
            if status not in TODO_STATUSES:
                return f"无效状态: {status}"
            item["status"] = status
        _save_todos(path, data)
        return _json({"item": item, "items": items})

    if action == "remove":
        if not todo_id:
            return "todo_id 不能为空"
        remaining = [item for item in items if item.get("id") != todo_id]
        if len(remaining) == len(items):
            return f"todo 不存在: {todo_id}"
        data["items"] = remaining
        _save_todos(path, data)
        return _json(data)

    if action == "clear":
        data = {"items": []}
        _save_todos(path, data)
        return _json(data)

    return "无效 action: 必须是 add、list、update、remove 或 clear"


@tool(
    name="create_sub_agent",
    description=(
        "Create a one-level sub-agent that inherits the main agent context. The sub-agent cannot create more "
        "sub-agents. Optionally run an initial task synchronously."
    ),
    context_params=[
        "provider",
        "subagent_manager",
        "parent_session",
        "tool_context",
        "memory_enabled",
        "can_create_sub_agent",
        "max_tool_rounds",
        "sub_agent_timeout",
    ],
    parameter_descriptions={
        "name": "Short sub-agent name, such as writer, reviewer, or planner.",
        "task": (
            "Optional initial task to execute immediately with the sub-agent. Use this as a 任务单: describe the "
            "goal, constraints, context paths to read, output format, target file path, and acceptance criteria. "
            "不要把主 Agent 自己生成的大段正文、大纲、改写稿或审稿意见放进 task 让子 Agent 只负责保存。"
        ),
    },
)
def create_sub_agent(
    name: str,
    task: str = "",
    provider=None,
    subagent_manager=None,
    parent_session=None,
    tool_context: dict = None,
    memory_enabled: bool = False,
    can_create_sub_agent: bool = True,
    max_tool_rounds: int = 100,
    sub_agent_timeout: Optional[float] = None,
) -> str:
    if not can_create_sub_agent:
        return "操作被拒绝: 子 Agent 不允许创建新的子 Agent"
    if provider is None or subagent_manager is None or parent_session is None:
        return "创建子 Agent 失败: 缺少运行时上下文"
    if not name or not name.strip():
        return "name 不能为空"

    agent_name = name.strip()
    create_kwargs = {
        "tool_context": dict(tool_context or {}),
        "memory_enabled": memory_enabled,
        "blocked_tool_names": {"create_sub_agent"},
        "max_tool_rounds": max_tool_rounds,
        "sub_agent_timeout": settings.SUB_AGENT_TIMEOUT if sub_agent_timeout is None else sub_agent_timeout,
    }
    if hasattr(subagent_manager, "get_or_create_subagent"):
        subagent_id, created = subagent_manager.get_or_create_subagent(
            agent_name,
            provider,
            parent_session,
            **create_kwargs,
        )
    else:
        subagent_id = subagent_manager.create_subagent(
            agent_name,
            provider,
            parent_session,
            **create_kwargs,
        )
        created = True
    result = None
    if task and task.strip():
        result = subagent_manager.execute_subagent(subagent_id, task.strip())

    return _json({
        "subagent_id": subagent_id,
        "agent_name": agent_name,
        "created": created,
        "reused": not created,
        "result": result,
    })
