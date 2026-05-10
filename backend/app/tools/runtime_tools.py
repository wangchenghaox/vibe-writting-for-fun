import json
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
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
    "find",
    "rg",
    "grep",
    "cat",
    "head",
    "tail",
    "wc",
    "sort",
    "uniq",
    "cut",
    "echo",
    "git",
    "pytest",
    "uv",
}
READ_ONLY_GIT_COMMANDS = {"status", "diff", "log", "show", "branch", "rev-parse"}
PIPELINE_UNSAFE_COMMANDS = set()
FIND_MUTATING_FLAGS = {
    "-delete",
    "-exec",
    "-execdir",
    "-ok",
    "-okdir",
    "-fls",
    "-fprint",
    "-fprint0",
    "-fprintf",
}
GIT_OUTPUT_FLAGS = {"--output"}
GIT_BRANCH_MUTATING_FLAGS = {
    "-d",
    "-D",
    "-m",
    "-M",
    "-c",
    "-C",
    "--delete",
    "--move",
    "--copy",
    "--set-upstream-to",
    "--unset-upstream",
    "--edit-description",
}
GIT_BRANCH_READ_ONLY_FLAGS = {
    "-a",
    "--all",
    "-r",
    "--remotes",
    "-v",
    "-vv",
    "--verbose",
    "--show-current",
    "--list",
}


@dataclass
class BashCommand:
    args: list[str]
    stdout_to_devnull: bool = False
    stderr_to_devnull: bool = False


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


def _parse_bash_command_tokens(tokens: list[str]) -> tuple[Optional[BashCommand], Optional[str]]:
    args = []
    stdout_to_devnull = False
    stderr_to_devnull = False
    index = 0

    while index < len(tokens):
        token = tokens[index]
        fd = None
        target = None

        if token in {">", "1>", "2>"}:
            if index + 1 >= len(tokens):
                return None, "操作被拒绝: 重定向缺少目标"
            fd = "2" if token == "2>" else "1"
            target = tokens[index + 1]
            index += 2
        else:
            match = re.fullmatch(r"([12]?)>(.+)", token)
            if match:
                fd = match.group(1) or "1"
                target = match.group(2)
                index += 1
            else:
                args.append(token)
                index += 1
                continue

        if target != "/dev/null":
            return None, "操作被拒绝: 受限 bash 只允许重定向到 /dev/null"
        if fd == "2":
            stderr_to_devnull = True
        else:
            stdout_to_devnull = True

    if not args:
        return None, "操作被拒绝: 重定向必须跟随命令"

    return BashCommand(
        args=args,
        stdout_to_devnull=stdout_to_devnull,
        stderr_to_devnull=stderr_to_devnull,
    ), None


def _split_command_chain(command: str) -> tuple[Optional[list[tuple[Optional[str], list[BashCommand]]]], Optional[str]]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="|&")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError as exc:
        return None, f"命令解析失败: {exc}"

    if not tokens:
        return None, "command 不能为空"

    chain = []
    commands = []
    command_tokens = []
    pending_operator = None
    for token in tokens:
        if token in {"&&", "||"}:
            if not command_tokens:
                return None, "操作被拒绝: &&/|| 两侧必须是完整命令"
            parsed, error = _parse_bash_command_tokens(command_tokens)
            if error:
                return None, error
            commands.append(parsed)
            chain.append((pending_operator, commands))
            commands = []
            command_tokens = []
            pending_operator = token
            continue
        if token == "&":
            return None, "操作被拒绝: 受限 bash 仅支持 && 或 || 命令串联"
        if token == "|":
            if not command_tokens:
                return None, "操作被拒绝: 管道两侧必须是完整命令"
            parsed, error = _parse_bash_command_tokens(command_tokens)
            if error:
                return None, error
            commands.append(parsed)
            command_tokens = []
            continue
        command_tokens.append(token)

    if not command_tokens:
        return None, "操作被拒绝: 管道两侧必须是完整命令"

    parsed, error = _parse_bash_command_tokens(command_tokens)
    if error:
        return None, error
    commands.append(parsed)
    chain.append((pending_operator, commands))
    return chain, None


def _validate_bash_segment(command: BashCommand, root: Path, pipeline_length: int) -> Optional[str]:
    args = command.args
    command_name = Path(args[0]).name
    if command_name in BLOCKED_COMMANDS:
        return f"操作被拒绝: 不允许执行 {command_name}"
    if command_name not in ALLOWED_COMMANDS:
        return f"操作被拒绝: 受限 bash 暂不允许执行 {command_name}"
    if pipeline_length > 1 and command_name in PIPELINE_UNSAFE_COMMANDS:
        return f"操作被拒绝: {command_name} 不能用于管道"
    if command_name == "git" and len(args) > 1 and args[1] not in READ_ONLY_GIT_COMMANDS:
        return f"操作被拒绝: git {args[1]} 不在只读白名单内"
    if command_name == "git" and any(arg in GIT_OUTPUT_FLAGS or arg.startswith("--output=") for arg in args[2:]):
        return "操作被拒绝: git 输出到文件会修改工作区"
    if command_name == "git" and len(args) > 1 and args[1] == "branch":
        if any(
            arg in GIT_BRANCH_MUTATING_FLAGS
            or arg.startswith("--set-upstream-to=")
            for arg in args[2:]
        ):
            return "操作被拒绝: git branch 仅允许只读查看"
        if any(not arg.startswith("--format=") and arg not in GIT_BRANCH_READ_ONLY_FLAGS for arg in args[2:]):
            return "操作被拒绝: git branch 仅允许只读查看"
    if command_name == "uv" and args[1:3] != ["run", "pytest"]:
        return "操作被拒绝: uv 仅允许执行 uv run pytest"
    if command_name == "find" and any(arg in FIND_MUTATING_FLAGS for arg in args[1:]):
        return "操作被拒绝: find 仅允许只读查找"
    if command_name == "sort" and any(
        arg == "-o" or arg == "--output" or arg.startswith("--output=")
        for arg in args[1:]
    ):
        return "操作被拒绝: sort 输出到文件会修改工作区"

    for arg in args[1:]:
        if arg.startswith("-") or not _looks_like_path_arg(arg):
            continue
        error = _validate_path_arg(arg, root)
        if error:
            return error

    return None


def _validate_bash_command(
    command: str,
    root: Path,
) -> tuple[Optional[list[tuple[Optional[str], list[BashCommand]]]], Optional[str]]:
    if not command or not command.strip():
        return None, "command 不能为空"
    if any(token in command for token in (";", "<", "`", "$(", "\n")):
        return None, "操作被拒绝: 受限 bash 不支持 ;、输入重定向、命令替换或多行命令"

    command_chain, error = _split_command_chain(command)
    if error:
        return None, error

    for _, commands in command_chain:
        for args in commands:
            error = _validate_bash_segment(args, root, pipeline_length=len(commands))
            if error:
                return None, error

    return command_chain, None


def _run_bash_process(command: BashCommand, root: Path, timeout: int, input_text: str = None):
    completed = subprocess.run(
        command.args,
        cwd=root,
        input=input_text,
        stdout=subprocess.DEVNULL if command.stdout_to_devnull else subprocess.PIPE,
        stderr=subprocess.DEVNULL if command.stderr_to_devnull else subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.stdout is None:
        completed.stdout = ""
    if completed.stderr is None:
        completed.stderr = ""
    return completed


def _run_bash_pipeline(commands: list[BashCommand], root: Path, timeout: int):
    if len(commands) == 1:
        return _run_bash_process(commands[0], root, timeout)

    stdout = None
    stderr_parts = []
    deadline = time.monotonic() + timeout
    completed = None
    for args in commands:
        remaining = max(1, deadline - time.monotonic())
        completed = _run_bash_process(args, root, remaining, input_text=stdout)
        stdout = completed.stdout
        if completed.stderr:
            stderr_parts.append(completed.stderr.rstrip("\n"))

    completed.stderr = "\n".join(stderr_parts)
    return completed


def _run_bash_commands(command_chain: list[tuple[Optional[str], list[BashCommand]]], root: Path, timeout: int):
    stdout_parts = []
    stderr_parts = []
    completed = SimpleNamespace(returncode=0, stdout="", stderr="")
    deadline = time.monotonic() + timeout

    for operator, commands in command_chain:
        if operator == "&&" and completed.returncode != 0:
            continue
        if operator == "||" and completed.returncode == 0:
            continue

        remaining = max(1, deadline - time.monotonic())
        completed = _run_bash_pipeline(commands, root, remaining)
        if completed.stdout:
            stdout_parts.append(completed.stdout.rstrip("\n"))
        if completed.stderr:
            stderr_parts.append(completed.stderr.rstrip("\n"))

    completed.stdout = "\n".join(stdout_parts)
    completed.stderr = "\n".join(stderr_parts)
    return completed


@tool(
    name="bash",
    description=(
        "受限 bash 工具：只能在当前工作区内执行只读查询和测试命令，例如 pwd、ls、find、rg、grep、cat、"
        "head、tail、wc、sort、uniq、cut、只读 git 命令、pytest 或 uv run pytest。支持简单管道、"
        "&&/|| 串联，以及重定向到 /dev/null。权限边界：禁止创建、删除、移动、重命名或修改文件/目录，"
        "禁止网络访问、权限修改、后台进程、命令替换、输入重定向、写入文件重定向和工作区外路径。"
        "需要修改文件时不要调用 bash，应使用 write_file 或 edit_file。"
    ),
    context_params=["workdir"],
    parameter_descriptions={
        "command": (
            "只传简单的只读或测试命令，如 `pwd`、`ls drafts`、`rg 关键词`、`cat notes.md`、"
            "`git status` 或 `uv run pytest`；禁止把 bash 用于写入、修改文件、创建目录、删除、移动、"
            "网络请求、权限变更、后台执行或文件重定向。"
        ),
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
        first_command = commands[0][1][0].args[0] if commands and commands[0][1] else command
        return f"命令不存在: {first_command}"
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
        "max_tool_rounds",
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
    max_tool_rounds: int = 20,
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
        max_tool_rounds=max_tool_rounds,
    )
    result = None
    if task and task.strip():
        result = subagent_manager.execute_subagent(subagent_id, task.strip())

    return _json({
        "subagent_id": subagent_id,
        "agent_name": agent_name,
        "result": result,
    })
