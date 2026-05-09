import json
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Optional

from app.capability.tool_registry import tool
from app.core.config import settings


TODO_STATUSES = {"pending", "in_progress", "completed"}
MAX_BASH_TIMEOUT_SECONDS = 30
MAX_BASH_OUTPUT_CHARS = 12000
BLOCKED_COMMANDS = {
    "rm",
    "rmdir",
    "mv",
    "chmod",
    "chown",
    "sudo",
    "su",
    "kill",
    "pkill",
    "curl",
    "wget",
    "ssh",
    "scp",
    "python",
    "python3",
    "pip",
}
ALLOWED_COMMANDS = {
    "pwd",
    "ls",
    "mkdir",
    "find",
    "rg",
    "grep",
    "cat",
    "head",
    "tail",
    "wc",
    "sed",
    "sort",
    "uniq",
    "cut",
    "git",
    "pytest",
    "uv",
}
READ_ONLY_GIT_COMMANDS = {"status", "diff", "log", "show", "branch", "rev-parse"}
PIPELINE_UNSAFE_COMMANDS = {"mkdir"}


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False)


def _workdir(workdir: str = None) -> Path:
    configured = workdir or getattr(settings, "WORKDIR", None)
    if not configured:
        configured = Path(settings.DATA_DIR) / "novels"
    root = Path(configured).expanduser().resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _is_within(path: Path, root: Path) -> bool:
    return path.resolve(strict=False).is_relative_to(root)


def _looks_like_path_arg(arg: str) -> bool:
    if arg in {".", ".."}:
        return True
    if arg.startswith(("/", "./", "../", "~")):
        return True
    if "/" in arg or "\\" in arg:
        return True
    path_part = arg.split("::", 1)[0]
    return bool(Path(path_part).suffix)


def _validate_path_arg(arg: str, root: Path) -> Optional[str]:
    path_part = arg.split("::", 1)[0]
    raw = Path(path_part).expanduser()
    resolved = raw.resolve(strict=False) if raw.is_absolute() else (root / raw).resolve(strict=False)
    if not _is_within(resolved, root):
        return f"操作被拒绝: 命令路径必须位于工作区内 ({root})"
    return None


def _split_pipeline(command: str) -> tuple[Optional[list[list[str]]], Optional[str]]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="|")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError as exc:
        return None, f"命令解析失败: {exc}"

    if not tokens:
        return None, "command 不能为空"

    commands = [[]]
    for token in tokens:
        if token == "|":
            if not commands[-1]:
                return None, "操作被拒绝: 管道两侧必须是完整命令"
            commands.append([])
            continue
        commands[-1].append(token)

    if not commands[-1]:
        return None, "操作被拒绝: 管道两侧必须是完整命令"

    return commands, None


def _validate_bash_segment(args: list[str], root: Path, pipeline_length: int) -> Optional[str]:
    command_name = Path(args[0]).name
    if command_name in BLOCKED_COMMANDS:
        return f"操作被拒绝: 不允许执行 {command_name}"
    if command_name not in ALLOWED_COMMANDS:
        return f"操作被拒绝: 受限 bash 暂不允许执行 {command_name}"
    if pipeline_length > 1 and command_name in PIPELINE_UNSAFE_COMMANDS:
        return f"操作被拒绝: {command_name} 不能用于管道"
    if command_name == "git" and len(args) > 1 and args[1] not in READ_ONLY_GIT_COMMANDS:
        return f"操作被拒绝: git {args[1]} 不在只读白名单内"
    if command_name == "uv" and args[1:3] != ["run", "pytest"]:
        return "操作被拒绝: uv 仅允许执行 uv run pytest"
    if command_name == "sed" and any(arg == "-i" or arg.startswith("-i") for arg in args[1:]):
        return "操作被拒绝: sed -i 会修改文件"

    for arg in args[1:]:
        if arg.startswith("-") or not _looks_like_path_arg(arg):
            continue
        error = _validate_path_arg(arg, root)
        if error:
            return error

    return None


def _validate_bash_command(command: str, root: Path) -> tuple[Optional[list[list[str]]], Optional[str]]:
    if not command or not command.strip():
        return None, "command 不能为空"
    if any(token in command for token in ("&&", "||", ";", "<", ">", "`", "$(", "\n")):
        return None, "操作被拒绝: 受限 bash 不支持重定向、命令串联或命令替换"

    commands, error = _split_pipeline(command)
    if error:
        return None, error

    for args in commands:
        error = _validate_bash_segment(args, root, pipeline_length=len(commands))
        if error:
            return None, error

    return commands, None


def _run_bash_commands(commands: list[list[str]], root: Path, timeout: int):
    if len(commands) == 1:
        return subprocess.run(
            commands[0],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    stdout = None
    stderr_parts = []
    deadline = time.monotonic() + timeout
    completed = None
    for args in commands:
        remaining = max(1, deadline - time.monotonic())
        completed = subprocess.run(
            args,
            cwd=root,
            input=stdout,
            capture_output=True,
            text=True,
            timeout=remaining,
            check=False,
        )
        stdout = completed.stdout
        if completed.stderr:
            stderr_parts.append(completed.stderr.rstrip("\n"))

    completed.stderr = "\n".join(stderr_parts)
    return completed


@tool(
    name="bash",
    description=(
        "Run a restricted shell command inside the current workspace. Allows common read/search/test commands, "
        "mkdir inside workdir, and simple pipelines. Rejects destructive commands, command chaining, redirects, "
        "command substitution, and paths outside workdir."
    ),
    context_params=["workdir"],
    parameter_descriptions={
        "command": "A simple command such as `pwd`, `ls drafts`, `rg 关键词`, `cat notes.md`, or `uv run pytest`.",
        "timeout_seconds": "Execution timeout in seconds. Maximum is 30.",
    },
)
def bash(command: str, timeout_seconds: int = 10, workdir: str = None) -> str:
    root = _workdir(workdir)
    commands, error = _validate_bash_command(command, root)
    if error:
        return error

    timeout = max(1, min(timeout_seconds, MAX_BASH_TIMEOUT_SECONDS))
    try:
        completed = _run_bash_commands(commands, root, timeout)
    except FileNotFoundError:
        return f"命令不存在: {commands[0][0]}"
    except subprocess.TimeoutExpired:
        return f"命令超时: 超过 {timeout} 秒"

    return _json({
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-MAX_BASH_OUTPUT_CHARS:].rstrip("\n"),
        "stderr": completed.stderr[-MAX_BASH_OUTPUT_CHARS:].rstrip("\n"),
    })


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
) -> str:
    if not can_create_sub_agent:
        return "操作被拒绝: 子 Agent 不允许创建新的子 Agent"
    if provider is None or subagent_manager is None or parent_session is None:
        return "创建子 Agent 失败: 缺少运行时上下文"
    if not name or not name.strip():
        return "name 不能为空"

    agent_name = name.strip()
    subagent_id = subagent_manager.create_subagent(
        agent_name,
        provider,
        parent_session,
        tool_context=dict(tool_context or {}),
        memory_enabled=memory_enabled,
        blocked_tool_names={"create_sub_agent"},
    )
    result = None
    if task and task.strip():
        result = subagent_manager.execute_subagent(subagent_id, task.strip())

    return _json({
        "subagent_id": subagent_id,
        "agent_name": agent_name,
        "result": result,
    })
