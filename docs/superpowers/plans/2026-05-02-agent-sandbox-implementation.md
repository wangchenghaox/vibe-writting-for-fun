# Agent Sandbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local filesystem sandbox system where the main agent can read, create/switch controlled novel sandboxes, and dispatch role-scoped sub-agents, while only sub-agents can write content inside the active sandbox.

**Architecture:** Add `SandboxManager` for controlled novel roots and path resolution, add role-aware tool policy metadata to the tool registry, then wire AgentCore/SubAgentManager/Web/CLI contexts through `sandbox_id`, `sandbox_root`, `agent_role`, and stable business `agent_name`. File and domain tools enforce sandbox roots at execution time; memory isolation continues to use `user_id + novel_id + agent_name`.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, SQLite, pytest, existing `uv run pytest` workflow.

---

## File Structure

- Create `backend/app/capability/sandbox_manager.py`: local sandbox dataclass, path resolver, context update helpers, controlled create/switch operations.
- Create `backend/app/capability/tool_policy.py`: access constants and role policy checks used by schema filtering and execution.
- Modify `backend/app/capability/tool_registry.py`: add `access` metadata to `@tool`, filter schemas by agent role, reject disallowed execution.
- Modify `backend/app/tools/file_tools.py`: replace global allowed roots with sandbox-only resolution and hidden context params.
- Modify `backend/app/tools/novel_tools.py`: make domain read/write tools sandbox-aware and mark legacy `create_novel` as non-main write access.
- Create `backend/app/tools/orchestration_tools.py`: main-only `create_sandbox`, `switch_sandbox`, `create_subagent`, `run_subagent`.
- Modify `backend/app/tools/__init__.py`: import orchestration tools so registration side effects happen.
- Modify `backend/app/agent/core.py`: default context roles, inject sandbox/subagent managers into hidden tool context, filter tool schemas by role.
- Modify `backend/app/capability/subagent_manager.py`: normalize business roles, bind sub-agents to sandbox and role-scoped memory identity.
- Modify `backend/app/services/web_agent.py`: initialize default sandbox for the current novel.
- Modify `backend/app/ui/cli.py` and `backend/app/ui/commands.py`: initialize and refresh sandbox context for CLI sessions and `/load`.
- Test files:
  - Create `backend/tests/test_sandbox_manager.py`
  - Create `backend/tests/test_tool_policy.py`
  - Modify `backend/tests/test_file_tools.py`
  - Modify `backend/tests/test_tools.py`
  - Modify `backend/tests/test_agent_core.py`
  - Modify `backend/tests/test_subagent_manager.py`
  - Modify `backend/tests/test_memory_tools.py`
  - Modify `backend/tests/test_cli.py`
  - Modify `backend/tests/test_p1_regressions.py`

## Task 1: Sandbox Manager

**Files:**
- Create: `backend/app/capability/sandbox_manager.py`
- Test: `backend/tests/test_sandbox_manager.py`

- [ ] **Step 1: Write failing sandbox manager tests**

Add `backend/tests/test_sandbox_manager.py`:

```python
from pathlib import Path

import pytest

from app.capability.sandbox_manager import (
    SandboxManager,
    SandboxPathError,
    normalize_subagent_role,
)
from app.core.config import settings


def test_create_default_novel_sandbox_updates_context(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    session_context = {"user_id": 7, "agent_instance_id": "web_novel_a"}
    tool_context = dict(session_context)

    manager = SandboxManager()
    sandbox = manager.create_or_switch_novel_sandbox(
        novel_id="novel_a",
        title="测试小说",
        description="描述",
        user_id=7,
        created_by_agent_instance_id="web_novel_a",
        session_context=session_context,
        tool_context=tool_context,
    )

    assert sandbox.id == "novel_novel_a"
    assert sandbox.root == (tmp_path / "data" / "novels" / "novel_a").resolve()
    assert (sandbox.root / "chapters").is_dir()
    assert (sandbox.root / "outlines").is_dir()
    assert session_context["novel_id"] == "novel_a"
    assert session_context["sandbox_id"] == sandbox.id
    assert tool_context["sandbox_root"] == str(sandbox.root)


def test_resolve_path_stays_inside_sandbox(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    manager = SandboxManager()
    root = (tmp_path / "data" / "novels" / "novel_a").resolve()
    root.mkdir(parents=True)

    assert manager.resolve_path("chapters/1.md", root, "novel_a") == root / "chapters" / "1.md"
    assert manager.resolve_path("novels/novel_a/chapters/1.md", root, "novel_a") == root / "chapters" / "1.md"


def test_resolve_path_rejects_escape_and_other_novel(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    manager = SandboxManager()
    root = (tmp_path / "data" / "novels" / "novel_a").resolve()
    root.mkdir(parents=True)

    with pytest.raises(SandboxPathError):
        manager.resolve_path("../outside.md", root, "novel_a")
    with pytest.raises(SandboxPathError):
        manager.resolve_path("novels/novel_b/chapters/1.md", root, "novel_a")
    with pytest.raises(SandboxPathError):
        manager.resolve_path(str((tmp_path / "outside.md").resolve()), root, "novel_a")


def test_normalize_subagent_role():
    assert normalize_subagent_role("Writer") == "writer"
    assert normalize_subagent_role("reviewer-1") == "reviewer-1"

    for invalid in ("main", "../writer", "", "writer role"):
        with pytest.raises(ValueError):
            normalize_subagent_role(invalid)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/test_sandbox_manager.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.capability.sandbox_manager'`.

- [ ] **Step 3: Implement `SandboxManager`**

Create `backend/app/capability/sandbox_manager.py`:

```python
import re
from dataclasses import dataclass
from pathlib import Path
from typing import MutableMapping

from app.core.config import settings


ROLE_PATTERN = re.compile(r"^[a-z0-9_-]{1,40}$")
NOVEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


class SandboxPathError(ValueError):
    pass


@dataclass(frozen=True)
class Sandbox:
    id: str
    root: Path
    owner_user_id: int | None
    novel_id: str | None
    title: str = ""
    created_by_agent_instance_id: str = ""


def normalize_subagent_role(role: str) -> str:
    normalized = (role or "").strip().lower()
    if normalized == "main" or not ROLE_PATTERN.fullmatch(normalized):
        raise ValueError(f"无效 sub-agent 角色 {role}")
    return normalized


def validate_novel_id(novel_id: str) -> str:
    normalized = (novel_id or "").strip()
    if not NOVEL_ID_PATTERN.fullmatch(normalized):
        raise ValueError(f"无效 novel_id: {novel_id}")
    return normalized


class SandboxManager:
    def novels_root(self) -> Path:
        return (Path(settings.DATA_DIR) / "novels").resolve()

    def create_or_switch_novel_sandbox(
        self,
        novel_id: str,
        title: str = "",
        description: str = "",
        user_id: int | None = None,
        created_by_agent_instance_id: str = "",
        session_context: MutableMapping | None = None,
        tool_context: MutableMapping | None = None,
        create: bool = True,
    ) -> Sandbox:
        normalized_id = validate_novel_id(novel_id)
        root = (self.novels_root() / normalized_id).resolve()
        if not root.is_relative_to(self.novels_root()):
            raise SandboxPathError("操作被拒绝: sandbox 必须位于 novels 根目录内")
        if create:
            (root / "chapters").mkdir(parents=True, exist_ok=True)
            (root / "outlines").mkdir(parents=True, exist_ok=True)
        elif not root.exists():
            raise SandboxPathError(f"操作被拒绝: 无法访问小说 {normalized_id}")

        sandbox = Sandbox(
            id=f"novel_{normalized_id}",
            root=root,
            owner_user_id=user_id,
            novel_id=normalized_id,
            title=title or normalized_id,
            created_by_agent_instance_id=created_by_agent_instance_id or "",
        )
        self.apply_to_context(sandbox, session_context=session_context, tool_context=tool_context)
        return sandbox

    def apply_to_context(
        self,
        sandbox: Sandbox,
        session_context: MutableMapping | None = None,
        tool_context: MutableMapping | None = None,
    ) -> None:
        for context in (session_context, tool_context):
            if context is None:
                continue
            context["novel_id"] = sandbox.novel_id
            context["sandbox_id"] = sandbox.id
            context["sandbox_root"] = str(sandbox.root)

    def resolve_path(self, path: str, sandbox_root: str | Path | None, novel_id: str | None = None) -> Path:
        if not sandbox_root:
            raise SandboxPathError("操作被拒绝: 当前 agent 未绑定 sandbox")
        root = Path(sandbox_root).resolve(strict=False)
        raw = Path(path or "")

        if raw.is_absolute():
            candidate = raw
        else:
            parts = raw.parts
            if len(parts) >= 2 and parts[0] == "novels":
                if novel_id and parts[1] != novel_id:
                    raise SandboxPathError(f"操作被拒绝: 当前 sandbox 只允许访问小说 {novel_id}")
                candidate = root.joinpath(*parts[2:])
            else:
                candidate = root / raw

        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(root):
            raise SandboxPathError("操作被拒绝: 路径必须位于当前 sandbox 内")
        return resolved

    def display_path(self, path: Path, sandbox_root: str | Path, novel_id: str | None = None) -> str:
        root = Path(sandbox_root).resolve(strict=False)
        relative = path.resolve(strict=False).relative_to(root)
        if novel_id:
            return str(Path("novels") / novel_id / relative)
        return f"sandbox:/{relative.as_posix()}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/test_sandbox_manager.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/capability/sandbox_manager.py backend/tests/test_sandbox_manager.py
git commit -m "feat: add sandbox manager"
```

## Task 2: Tool Policy And Registry Metadata

**Files:**
- Create: `backend/app/capability/tool_policy.py`
- Modify: `backend/app/capability/tool_registry.py`
- Test: `backend/tests/test_tool_policy.py`
- Test: `backend/tests/test_tools.py`

- [ ] **Step 1: Write failing tool policy tests**

Add `backend/tests/test_tool_policy.py`:

```python
from app.capability.tool_registry import execute_tool, get_tool_schemas, tool
from app.capability.tool_policy import AccessType


def test_main_agent_cannot_see_or_execute_write_tools():
    @tool(name="policy_write_probe", description="write", access=AccessType.FILESYSTEM_WRITE)
    def policy_write_probe() -> str:
        return "wrote"

    schemas = get_tool_schemas(context={"agent_role": "main"})
    names = {schema["function"]["name"] for schema in schemas}

    assert "policy_write_probe" not in names
    assert execute_tool("policy_write_probe", {}, context={"agent_role": "main"}).startswith("操作被拒绝")


def test_subagent_can_see_write_tools_but_not_orchestration():
    @tool(name="policy_write_allowed", description="write", access=AccessType.FILESYSTEM_WRITE)
    def policy_write_allowed() -> str:
        return "wrote"

    @tool(name="policy_orchestrate", description="orchestrate", access=AccessType.ORCHESTRATION)
    def policy_orchestrate() -> str:
        return "orchestrated"

    schemas = get_tool_schemas(context={"agent_role": "subagent"})
    names = {schema["function"]["name"] for schema in schemas}

    assert "policy_write_allowed" in names
    assert "policy_orchestrate" not in names
    assert execute_tool("policy_write_allowed", {}, context={"agent_role": "subagent"}) == "wrote"
    assert execute_tool("policy_orchestrate", {}, context={"agent_role": "subagent"}).startswith("操作被拒绝")


def test_main_agent_can_see_sandbox_management():
    @tool(name="policy_switch_sandbox", description="switch", access=AccessType.SANDBOX_MANAGEMENT)
    def policy_switch_sandbox() -> str:
        return "switched"

    schemas = get_tool_schemas(context={"agent_role": "main"})
    names = {schema["function"]["name"] for schema in schemas}

    assert "policy_switch_sandbox" in names
    assert execute_tool("policy_switch_sandbox", {}, context={"agent_role": "main"}) == "switched"
```

Modify `backend/tests/test_tools.py` so existing calls to `get_tool_schemas()` that expect every registered tool use `include_all=True`:

```python
def test_tool_registration():
    @tool(name="test_tool", description="A test tool")
    def my_tool(arg1: str) -> str:
        return f"Result: {arg1}"

    schemas = get_tool_schemas(include_all=True)
    tool_names = [s["function"]["name"] for s in schemas]
    assert "test_tool" in tool_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/test_tool_policy.py tests/test_tools.py::test_tool_registration -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.capability.tool_policy'` or `TypeError` for unsupported `access`.

- [ ] **Step 3: Implement tool policy**

Create `backend/app/capability/tool_policy.py`:

```python
from enum import StrEnum


class AccessType(StrEnum):
    FILESYSTEM_READ = "filesystem_read"
    FILESYSTEM_WRITE = "filesystem_write"
    DOMAIN_READ = "domain_read"
    DOMAIN_WRITE = "domain_write"
    MEMORY = "memory"
    EXTERNAL_READ = "external_read"
    ORCHESTRATION = "orchestration"
    SANDBOX_MANAGEMENT = "sandbox_management"


MAIN_ALLOWED = {
    AccessType.FILESYSTEM_READ,
    AccessType.DOMAIN_READ,
    AccessType.MEMORY,
    AccessType.EXTERNAL_READ,
    AccessType.ORCHESTRATION,
    AccessType.SANDBOX_MANAGEMENT,
}

SUBAGENT_ALLOWED = {
    AccessType.FILESYSTEM_READ,
    AccessType.FILESYSTEM_WRITE,
    AccessType.DOMAIN_READ,
    AccessType.DOMAIN_WRITE,
    AccessType.MEMORY,
    AccessType.EXTERNAL_READ,
}


def normalize_agent_role(role: str | None) -> str:
    return role if role in {"main", "subagent"} else "main"


def access_allowed(agent_role: str | None, access: str | AccessType) -> bool:
    role = normalize_agent_role(agent_role)
    access_type = AccessType(access)
    if role == "subagent":
        return access_type in SUBAGENT_ALLOWED
    return access_type in MAIN_ALLOWED


def denied_message(agent_role: str | None, access: str | AccessType) -> str:
    access_type = AccessType(access)
    role = normalize_agent_role(agent_role)
    if role == "main" and access_type in {AccessType.FILESYSTEM_WRITE, AccessType.DOMAIN_WRITE}:
        return "操作被拒绝: main agent 只能读取文件，请交给 sub-agent 执行"
    if role == "subagent" and access_type in {AccessType.ORCHESTRATION, AccessType.SANDBOX_MANAGEMENT}:
        return "操作被拒绝: sub-agent 不能创建、切换 sandbox 或调度其他 agent"
    return "操作被拒绝: 当前 agent 无权调用该工具"
```

- [ ] **Step 4: Extend `tool_registry.py`**

Modify `backend/app/capability/tool_registry.py`:

```python
from .tool_policy import AccessType, access_allowed, denied_message


def tool(
    name: str,
    description: str,
    context_params: Optional[Sequence[str]] = None,
    access: str | AccessType = AccessType.DOMAIN_READ,
):
    def decorator(func: Callable):
        # Keep the existing signature parsing and schema generation code here.
        _tool_registry[name] = {
            "schema": schema,
            "func": func,
            "signature": sig,
            "context_params": hidden_context_params,
            "access": AccessType(access),
        }
        return func
    return decorator


def get_tool_schemas(
    allowed_names: Optional[Sequence[str]] = None,
    context: Optional[Dict[str, Any]] = None,
    include_all: bool = False,
) -> List[Dict[str, Any]]:
    allowed = set(allowed_names) if allowed_names is not None else None
    role = (context or {}).get("agent_role", "main")
    schemas = []
    for name, entry in _tool_registry.items():
        if allowed is not None and name not in allowed:
            continue
        if not include_all and not access_allowed(role, entry.get("access", AccessType.DOMAIN_READ)):
            continue
        schemas.append(entry["schema"])
    return schemas
```

In `execute_tool()`, reject disallowed calls before injecting arguments:

```python
    agent_role = (context or {}).get("agent_role", "main")
    access = entry.get("access", AccessType.DOMAIN_READ)
    if not access_allowed(agent_role, access):
        return denied_message(agent_role, access)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/test_tool_policy.py tests/test_tools.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/capability/tool_policy.py backend/app/capability/tool_registry.py backend/tests/test_tool_policy.py backend/tests/test_tools.py
git commit -m "feat: add role-aware tool policy"
```

## Task 3: Sandbox File Tools

**Files:**
- Modify: `backend/app/tools/file_tools.py`
- Test: `backend/tests/test_file_tools.py`

- [ ] **Step 1: Replace file tool tests with sandbox-context behavior**

Modify `backend/tests/test_file_tools.py`:

```python
import json

from app.tools.file_tools import (
    delete_file,
    edit_file,
    grep_files,
    list_files,
    read_file,
    rename_file,
    search_files,
    write_file,
)


def sandbox_context(tmp_path):
    root = tmp_path / "sandbox"
    root.mkdir()
    return {"sandbox_root": str(root), "novel_id": "novel_a", "agent_role": "subagent"}, root


def test_file_tools_read_write_edit_rename_delete_inside_sandbox(tmp_path):
    context, root = sandbox_context(tmp_path)

    assert "已写入文件" in write_file("chapters/notes.txt", "hello world", **context)
    assert (root / "chapters" / "notes.txt").read_text(encoding="utf-8") == "hello world"
    assert read_file("chapters/notes.txt", sandbox_root=context["sandbox_root"], novel_id="novel_a") == "hello world"

    assert "已修改文件" in edit_file("chapters/notes.txt", "world", "sandbox", **context)
    assert read_file("chapters/notes.txt", sandbox_root=context["sandbox_root"], novel_id="novel_a") == "hello sandbox"

    assert "已重命名" in rename_file("chapters/notes.txt", "chapters/renamed.txt", **context)
    assert "已删除文件" in delete_file("chapters/renamed.txt", **context)
    assert "不存在" in read_file("chapters/renamed.txt", sandbox_root=context["sandbox_root"], novel_id="novel_a")


def test_file_tools_require_sandbox_root():
    assert write_file("notes.txt", "nope").startswith("操作被拒绝")
    assert read_file("notes.txt").startswith("操作被拒绝")


def test_file_tools_block_escape_and_other_novel(tmp_path):
    context, _root = sandbox_context(tmp_path)

    assert write_file("../outside.txt", "nope", **context).startswith("操作被拒绝")
    assert read_file("novels/novel_b/notes.txt", sandbox_root=context["sandbox_root"], novel_id="novel_a").startswith("操作被拒绝")


def test_file_tools_list_grep_and_search_use_display_paths(tmp_path):
    context, root = sandbox_context(tmp_path)
    write_file("chapters/chapter_1.txt", "第一章\n用户喜欢先审稿再改写", **context)
    write_file("notes.md", "固定 SOP: 先总结，再保存", **context)

    listed = json.loads(list_files("chapters", pattern="*.txt", sandbox_root=context["sandbox_root"], novel_id="novel_a"))
    assert listed == ["novels/novel_a/chapters/chapter_1.txt"]

    grep_result = json.loads(grep_files("审稿", path="", file_glob="*.txt", sandbox_root=context["sandbox_root"], novel_id="novel_a"))
    assert grep_result == [{
        "path": "novels/novel_a/chapters/chapter_1.txt",
        "line_number": 2,
        "line": "用户喜欢先审稿再改写",
    }]

    search_result = json.loads(search_files("notes", sandbox_root=context["sandbox_root"], novel_id="novel_a"))
    assert search_result == ["novels/novel_a/notes.md"]
    assert str(root) not in listed[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/test_file_tools.py -v
```

Expected: FAIL because current tools still use global allowed roots and do not require `sandbox_root`.

- [ ] **Step 3: Update file tools to use `SandboxManager`**

Modify decorators and helpers in `backend/app/tools/file_tools.py`:

```python
from app.capability.sandbox_manager import SandboxManager, SandboxPathError
from app.capability.tool_policy import AccessType


SANDBOX_CONTEXT = ["sandbox_root", "novel_id"]


def _resolve_safe_path(path: str, sandbox_root: str = None, novel_id: str = None):
    try:
        return SandboxManager().resolve_path(path, sandbox_root, novel_id), None
    except SandboxPathError as exc:
        return None, str(exc)


def _display_path(path: Path, sandbox_root: str = None, novel_id: str = None) -> str:
    return SandboxManager().display_path(path, sandbox_root, novel_id)
```

Update tool signatures:

```python
@tool(
    name="read_file",
    description="Read a text file from the current sandbox",
    access=AccessType.FILESYSTEM_READ,
    context_params=SANDBOX_CONTEXT,
)
def read_file(path: str, max_chars: int = 20000, sandbox_root: str = None, novel_id: str = None) -> str:
    resolved, error = _resolve_safe_path(path, sandbox_root, novel_id)
    if error:
        return error
    if not resolved.exists():
        return f"文件不存在: {_display_path(resolved, sandbox_root, novel_id)}"
    if not resolved.is_file():
        return f"不是文件: {_display_path(resolved, sandbox_root, novel_id)}"
    content = resolved.read_text(encoding="utf-8")
    return content[:max_chars]
```

Apply the same hidden context params to `write_file`, `edit_file`, `delete_file`, `rename_file`, `list_files`, `grep_files`, and `search_files`; mark write/edit/delete/rename as `AccessType.FILESYSTEM_WRITE` and list/read/grep/search as `AccessType.FILESYSTEM_READ`.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/test_file_tools.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tools/file_tools.py backend/tests/test_file_tools.py
git commit -m "feat: enforce sandbox file tools"
```

## Task 4: Domain Tools And Orchestration Tools

**Files:**
- Modify: `backend/app/tools/novel_tools.py`
- Modify: `backend/app/tools/review_tools.py`
- Create: `backend/app/tools/orchestration_tools.py`
- Modify: `backend/app/tools/__init__.py`
- Test: `backend/tests/test_tools.py`
- Test: `backend/tests/test_tool_policy.py`

- [ ] **Step 1: Write failing orchestration and domain tests**

Append to `backend/tests/test_tools.py`:

```python
from pathlib import Path

from app.capability.tool_registry import execute_tool
from app.tools.novel_tools import load_novel_document, save_novel_document


def test_domain_documents_use_sandbox_context(tmp_path):
    root = tmp_path / "novel_a"
    context = {"sandbox_root": str(root), "novel_id": "novel_a", "agent_role": "subagent"}

    assert "Document saved" in save_novel_document("outline", "main", "总纲", **context)
    assert (root / "outlines" / "main.json").exists()
    assert '"content": "总纲"' in load_novel_document("outline", "main", sandbox_root=str(root), novel_id="novel_a")
    assert save_novel_document("outline", "main", "错写", novel_id="novel_b", sandbox_root=str(root)).startswith("操作被拒绝")


def test_main_orchestration_tools_are_registered_and_write_tools_are_hidden():
    tool_names = {schema["function"]["name"] for schema in get_tool_schemas(context={"agent_role": "main"})}

    assert {"create_sandbox", "switch_sandbox", "create_subagent", "run_subagent"}.issubset(tool_names)
    assert "save_novel_document" not in tool_names
    assert "create_novel" not in tool_names
```

Append to `backend/tests/test_tool_policy.py`:

```python
def test_subagent_cannot_see_orchestration_tools():
    import app.tools as _tools  # noqa: F401

    tool_names = {schema["function"]["name"] for schema in get_tool_schemas(context={"agent_role": "subagent"})}

    assert "create_sandbox" not in tool_names
    assert "switch_sandbox" not in tool_names
    assert "create_subagent" not in tool_names
    assert "run_subagent" not in tool_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/test_tools.py::test_domain_documents_use_sandbox_context tests/test_tools.py::test_main_orchestration_tools_are_registered_and_write_tools_are_hidden tests/test_tool_policy.py::test_subagent_cannot_see_orchestration_tools -v
```

Expected: FAIL because orchestration tools do not exist and domain tools do not accept sandbox context.

- [ ] **Step 3: Make domain tools sandbox-aware**

Modify `backend/app/tools/novel_tools.py`:

```python
from app.capability.sandbox_manager import SandboxManager, SandboxPathError
from app.capability.tool_policy import AccessType


CONTEXT_PARAMS = ["novel_id", "sandbox_root"]


def _require_matching_novel(requested: str | None, context_novel_id: str | None) -> str:
    novel_id = requested or context_novel_id or _current_novel_id()
    if context_novel_id and novel_id != context_novel_id:
        raise SandboxPathError(f"操作被拒绝: 当前 sandbox 只允许访问小说 {context_novel_id}")
    return novel_id


def _document_dir(document_type: str, novel_id: str, sandbox_root: str = None) -> Path:
    if sandbox_root:
        base = SandboxManager().resolve_path("", sandbox_root, novel_id)
    else:
        base = novel_path(novel_id)
    return base / DOCUMENT_TYPES[_normalize_document_type(document_type)]
```

Mark decorators:

```python
@tool(name="create_novel", description="Create a new novel project", access=AccessType.DOMAIN_WRITE)
def create_novel(novel_id: str, title: str, description: str = "") -> str:
    # Keep the existing legacy create body; role policy hides this tool from main agents.

@tool(name="get_novel", description="List all novel projects, or get one novel by novel_id", access=AccessType.DOMAIN_READ)
def get_novel(novel_id: str = "") -> str:
    # Keep the existing read-only body.

@tool(
    name="save_novel_document",
    description="Save an outline or chapter document for the current novel; content is required and must contain the full text to save",
    context_params=CONTEXT_PARAMS,
    access=AccessType.DOMAIN_WRITE,
)
def save_novel_document(
    document_type: str,
    document_id: str,
    content: str,
    title: str = "",
    novel_id: str = None,
    sandbox_root: str = None,
) -> str:
    try:
        novel_id = _require_matching_novel(novel_id, novel_id if sandbox_root else None)
        path_dir = _document_dir(document_type, novel_id, sandbox_root=sandbox_root)
    except (ValueError, SandboxPathError) as exc:
        return str(exc) if isinstance(exc, SandboxPathError) else _document_type_error(exc)
    os.makedirs(path_dir, exist_ok=True)
    path = path_dir / f"{document_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            _document_payload(document_type, document_id, content, title=title),
            f,
            ensure_ascii=False,
            indent=2,
        )
    return f"Document saved: {path}"
```

Use the same hidden params and `AccessType.DOMAIN_READ` for `load_novel_document` and `list_novel_documents`. Update `review_chapter()` similarly with `sandbox_root`.

- [ ] **Step 4: Add orchestration tools**

Create `backend/app/tools/orchestration_tools.py`:

```python
import json

from app.capability.sandbox_manager import SandboxManager, SandboxPathError, normalize_subagent_role
from app.capability.tool_policy import AccessType
from app.capability.tool_registry import tool


ORCHESTRATION_CONTEXT = [
    "user_id",
    "novel_id",
    "agent_instance_id",
    "sandbox_id",
    "sandbox_root",
    "_provider",
    "_session",
    "_sandbox_manager",
    "_subagent_manager",
    "_memory_recorder_factory",
]


def _json(payload):
    return json.dumps(payload, ensure_ascii=False)


@tool(
    name="create_sandbox",
    description="Create and switch to a controlled novel sandbox",
    context_params=ORCHESTRATION_CONTEXT,
    access=AccessType.SANDBOX_MANAGEMENT,
)
def create_sandbox(
    novel_id: str,
    title: str = "",
    description: str = "",
    user_id: int = None,
    agent_instance_id: str = "",
    _session=None,
    _sandbox_manager: SandboxManager = None,
    **_ignored,
) -> str:
    manager = _sandbox_manager or SandboxManager()
    try:
        sandbox = manager.create_or_switch_novel_sandbox(
            novel_id=novel_id,
            title=title,
            description=description,
            user_id=user_id,
            created_by_agent_instance_id=agent_instance_id or "",
            session_context=_session.context if _session else None,
            tool_context=_ignored,
            create=True,
        )
        return _json({"ok": True, "sandbox_id": sandbox.id, "novel_id": sandbox.novel_id})
    except (ValueError, SandboxPathError) as exc:
        return _json({"ok": False, "error": str(exc)})
```

Add the other orchestration tools in the same file:

```python
@tool(
    name="switch_sandbox",
    description="Switch to an existing controlled novel sandbox",
    context_params=ORCHESTRATION_CONTEXT,
    access=AccessType.SANDBOX_MANAGEMENT,
)
def switch_sandbox(
    novel_id: str,
    user_id: int = None,
    agent_instance_id: str = "",
    _session=None,
    _sandbox_manager: SandboxManager = None,
    **_ignored,
) -> str:
    manager = _sandbox_manager or SandboxManager()
    try:
        sandbox = manager.create_or_switch_novel_sandbox(
            novel_id=novel_id,
            user_id=user_id,
            created_by_agent_instance_id=agent_instance_id or "",
            session_context=_session.context if _session else None,
            tool_context=_ignored,
            create=False,
        )
        return _json({"ok": True, "sandbox_id": sandbox.id, "novel_id": sandbox.novel_id})
    except (ValueError, SandboxPathError) as exc:
        return _json({"ok": False, "error": str(exc)})


@tool(
    name="create_subagent",
    description="Create a role-scoped sub-agent bound to the current sandbox",
    context_params=ORCHESTRATION_CONTEXT,
    access=AccessType.ORCHESTRATION,
)
def create_subagent(
    role: str,
    instructions: str = "",
    _provider=None,
    _session=None,
    _subagent_manager=None,
    _memory_recorder_factory=None,
    **context,
) -> str:
    try:
        normalized_role = normalize_subagent_role(role)
    except ValueError as exc:
        return _json({"ok": False, "error": str(exc)})
    if _provider is None or _session is None or _subagent_manager is None:
        return _json({"ok": False, "error": "操作被拒绝: 缺少 sub-agent 运行上下文"})
    subagent_id = _subagent_manager.create_subagent(
        normalized_role,
        _provider,
        _session,
        tool_context=context,
        memory_recorder_factory=_memory_recorder_factory,
    )
    if subagent_id is None:
        return _json({"ok": False, "error": f"操作被拒绝: 无效 sub-agent 角色 {role}"})
    return _json({"ok": True, "subagent_id": subagent_id, "agent_name": normalized_role})


@tool(
    name="run_subagent",
    description="Run a role-scoped sub-agent task in the current sandbox",
    context_params=ORCHESTRATION_CONTEXT,
    access=AccessType.ORCHESTRATION,
)
def run_subagent(
    subagent_id: str,
    task: str,
    sandbox_id: str = None,
    _subagent_manager=None,
    **_context,
) -> str:
    if _subagent_manager is None:
        return _json({"ok": False, "error": "操作被拒绝: 缺少 sub-agent manager"})
    subagent = _subagent_manager.subagents.get(subagent_id)
    if subagent is None:
        return _json({"ok": False, "error": f"sub-agent 不存在: {subagent_id}"})
    if subagent.tool_context.get("sandbox_id") != sandbox_id:
        return _json({"ok": False, "error": "操作被拒绝: sub-agent 绑定的 sandbox 与当前 sandbox 不一致"})
    result = _subagent_manager.execute_subagent(subagent_id, task)
    return _json({"ok": True, "subagent_id": subagent_id, "result": result})
```

Modify `backend/app/tools/__init__.py`:

```python
from . import chapter_tools, file_tools, memory_tools, novel_tools, orchestration_tools, outline_tools, review_tools, search_tools
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/test_tools.py tests/test_tool_policy.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/tools/novel_tools.py backend/app/tools/review_tools.py backend/app/tools/orchestration_tools.py backend/app/tools/__init__.py backend/tests/test_tools.py backend/tests/test_tool_policy.py
git commit -m "feat: add sandbox orchestration tools"
```

## Task 5: AgentCore And SubAgentManager Wiring

**Files:**
- Modify: `backend/app/agent/core.py`
- Modify: `backend/app/capability/subagent_manager.py`
- Test: `backend/tests/test_agent_core.py`
- Test: `backend/tests/test_subagent_manager.py`

- [ ] **Step 1: Write failing AgentCore and sub-agent tests**

Append to `backend/tests/test_agent_core.py`:

```python
def test_main_agent_filters_write_tools_and_keeps_orchestration(session):
    import app.tools as _tools  # noqa: F401

    provider = Mock()
    provider.chat.return_value = SimpleNamespace(content="done", tool_calls=None)
    agent = AgentCore(
        provider,
        session,
        tool_context={
            "user_id": 1,
            "novel_id": "novel_a",
            "agent_name": "main",
            "agent_instance_id": "main_1",
            "sandbox_root": "/tmp/sandbox",
            "sandbox_id": "novel_novel_a",
        },
    )

    assert agent.chat("hi") == "done"
    _messages, tools = provider.chat.call_args.args
    names = {schema["function"]["name"] for schema in tools}
    assert "read_file" in names
    assert "create_subagent" in names
    assert "run_subagent" in names
    assert "write_file" not in names
    assert "save_novel_document" not in names


def test_subagent_filters_orchestration_tools(session):
    import app.tools as _tools  # noqa: F401

    provider = Mock()
    provider.chat.return_value = SimpleNamespace(content="done", tool_calls=None)
    agent = AgentCore(
        provider,
        session,
        tool_context={
            "user_id": 1,
            "novel_id": "novel_a",
            "agent_role": "subagent",
            "agent_name": "writer",
            "agent_instance_id": "subagent_writer_0",
            "sandbox_root": "/tmp/sandbox",
            "sandbox_id": "novel_novel_a",
        },
    )

    assert agent.chat("hi") == "done"
    _messages, tools = provider.chat.call_args.args
    names = {schema["function"]["name"] for schema in tools}
    assert "write_file" in names
    assert "create_subagent" not in names
    assert "switch_sandbox" not in names
```

Append to `backend/tests/test_subagent_manager.py`:

```python
def test_create_subagent_sets_permission_role_business_role_and_sandbox():
    mock_provider = Mock()
    session = Session("parent")
    manager = SubAgentManager()

    agent_id = manager.create_subagent(
        "Writer",
        mock_provider,
        session,
        tool_context={
            "user_id": 1,
            "novel_id": "novel_a",
            "sandbox_id": "novel_novel_a",
            "sandbox_root": "/tmp/novel_a",
        },
    )

    subagent = manager.subagents[agent_id]
    assert agent_id == "subagent_writer_0"
    assert subagent.tool_context["agent_role"] == "subagent"
    assert subagent.tool_context["agent_name"] == "writer"
    assert subagent.tool_context["sandbox_id"] == "novel_novel_a"
    assert subagent.session.context["agent_name"] == "writer"


def test_create_subagent_rejects_main_role():
    manager = SubAgentManager()

    assert manager.create_subagent("main", Mock(), Session("parent")) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/test_agent_core.py::TestAgentCore::test_main_agent_filters_write_tools_and_keeps_orchestration tests/test_agent_core.py::TestAgentCore::test_subagent_filters_orchestration_tools tests/test_subagent_manager.py::test_create_subagent_sets_permission_role_business_role_and_sandbox tests/test_subagent_manager.py::test_create_subagent_rejects_main_role -v
```

Expected: FAIL because AgentCore is not passing context to `get_tool_schemas()` and SubAgentManager does not normalize roles.

- [ ] **Step 3: Wire AgentCore context**

Modify `backend/app/agent/core.py`:

```python
from ..capability.sandbox_manager import SandboxManager
from ..memory.event_recorder import MemoryEventRecorder
```

Inside `AgentCore.__init__()`, replace `self.tool_context = tool_context or {}` with:

```python
self.tool_context = dict(tool_context or {})
self.tool_context.setdefault("agent_role", "main")
self.tool_context.setdefault("agent_name", "main")
```

After `self.subagent_manager = SubAgentManager()`, insert:

```python
self.sandbox_manager = SandboxManager()
self.tool_context["_provider"] = provider
self.tool_context["_session"] = session
self.tool_context["_sandbox_manager"] = self.sandbox_manager
self.tool_context["_subagent_manager"] = self.subagent_manager
self.tool_context["_memory_recorder_factory"] = MemoryEventRecorder
```

Change `_get_tools_for_skills()`:

```python
tools = get_tool_schemas(allowed_names=allowed_tools or None, context=self.tool_context)
```

- [ ] **Step 4: Wire SubAgentManager role normalization**

Modify `backend/app/capability/subagent_manager.py`:

```python
from ..capability.sandbox_manager import normalize_subagent_role


def create_subagent(
    self,
    name: str,
    provider,
    session,
    tool_context: dict | None = None,
    memory_recorder_factory=None,
) -> str | None:
    try:
        role = normalize_subagent_role(name)
    except ValueError:
        logger.error("无效 sub-agent 角色: %s", name)
        return None
    from ..agent.core import AgentCore
    from ..memory.event_recorder import MemoryEventRecorder

    index = self._next_subagent_index
    self._next_subagent_index += 1
    subagent_id = f"subagent_{role}_{index}"
    context = dict(tool_context or {})
    context["agent_role"] = "subagent"
    context["agent_name"] = role
    context["agent_instance_id"] = subagent_id
    session.context.update(context)
    recorder_factory = memory_recorder_factory or MemoryEventRecorder
    memory_recorder = recorder_factory(
        user_id=context.get("user_id"),
        novel_id=context.get("novel_id"),
        agent_name=role,
        agent_instance_id=subagent_id,
        session_id=session.id,
    )
    subagent = AgentCore(provider, session, tool_context=context, memory_recorder=memory_recorder)
    self.subagents[subagent_id] = subagent
    logger.info("创建子代理: %s", subagent_id)
    return subagent_id
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/test_agent_core.py tests/test_subagent_manager.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/core.py backend/app/capability/subagent_manager.py backend/tests/test_agent_core.py backend/tests/test_subagent_manager.py
git commit -m "feat: wire sandboxed subagent roles"
```

## Task 6: Memory Isolation Regression Tests

**Files:**
- Modify: `backend/tests/test_memory_tools.py`

- [ ] **Step 1: Add role-scoped memory tests**

Append to `backend/tests/test_memory_tools.py`:

```python
def test_subagent_role_memories_do_not_mix(test_db):
    writer_context = {
        "user_id": 1,
        "novel_id": "novel_a",
        "agent_name": "writer",
        "agent_instance_id": "subagent_writer_0",
    }
    reviewer_context = {
        "user_id": 1,
        "novel_id": "novel_a",
        "agent_name": "reviewer",
        "agent_instance_id": "subagent_reviewer_1",
    }

    execute_tool("remember_memory", {"content": "writer 私有节奏偏好", "scope": "agent"}, context=writer_context)
    execute_tool("remember_memory", {"content": "reviewer 私有审稿标准", "scope": "agent"}, context=reviewer_context)
    execute_tool("remember_memory", {"content": "全局正典事实", "scope": "novel"}, context=writer_context)

    writer_payload = json.loads(execute_tool("search_memory", {"query": ""}, context=writer_context))
    reviewer_payload = json.loads(execute_tool("search_memory", {"query": ""}, context=reviewer_context))

    writer_contents = {item["content"] for item in writer_payload["result"]["items"]}
    reviewer_contents = {item["content"] for item in reviewer_payload["result"]["items"]}

    assert "writer 私有节奏偏好" in writer_contents
    assert "reviewer 私有审稿标准" not in writer_contents
    assert "全局正典事实" in writer_contents
    assert "reviewer 私有审稿标准" in reviewer_contents
    assert "writer 私有节奏偏好" not in reviewer_contents
    assert "全局正典事实" in reviewer_contents


def test_same_role_different_novels_do_not_share_memories(test_db):
    novel_a_context = {
        "user_id": 1,
        "novel_id": "novel_a",
        "agent_name": "writer",
        "agent_instance_id": "subagent_writer_0",
    }
    novel_b_context = {
        "user_id": 1,
        "novel_id": "novel_b",
        "agent_name": "writer",
        "agent_instance_id": "subagent_writer_1",
    }

    execute_tool("remember_memory", {"content": "novel_a writer memory", "scope": "agent"}, context=novel_a_context)

    payload = json.loads(execute_tool("search_memory", {"query": ""}, context=novel_b_context))
    contents = {item["content"] for item in payload["result"]["items"]}

    assert "novel_a writer memory" not in contents
```

- [ ] **Step 2: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/test_memory_tools.py -v
```

Expected: PASS. The memory repository already filters by `user_id + novel_id + agent_name`; failures here mean a previous task broke context injection.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_memory_tools.py
git commit -m "test: cover role-scoped agent memory"
```

## Task 7: Web And CLI Entry Points

**Files:**
- Modify: `backend/app/services/web_agent.py`
- Modify: `backend/app/ui/cli.py`
- Modify: `backend/app/ui/commands.py`
- Test: `backend/tests/test_cli.py`
- Test: `backend/tests/test_p1_regressions.py`

- [ ] **Step 1: Add entry-point tests**

Modify existing `backend/tests/test_cli.py` fake agent assertions:

```python
assert agent.tool_context["agent_role"] == "main"
assert agent.tool_context["agent_name"] == "main"
assert agent.tool_context["sandbox_id"] == f"novel_{agent.tool_context['novel_id']}"
assert agent.tool_context["sandbox_root"].endswith(f"data/novels/{agent.tool_context['novel_id']}")
```

Append to `backend/tests/test_p1_regressions.py`:

```python
def test_web_agent_service_initializes_main_sandbox(monkeypatch, tmp_path):
    from app.core.config import settings
    from app.services.web_agent import WebAgentService

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")

    service = WebAgentService(user_id=1, novel_id="novel_ctx")

    assert service.agent.tool_context["agent_role"] == "main"
    assert service.agent.tool_context["agent_name"] == "main"
    assert service.agent.tool_context["sandbox_id"] == "novel_novel_ctx"
    assert service.agent.tool_context["sandbox_root"].endswith("data/novels/novel_ctx")
    assert (tmp_path / "data" / "novels" / "novel_ctx").is_dir()
    service.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/test_cli.py tests/test_p1_regressions.py::test_web_agent_service_initializes_main_sandbox -v
```

Expected: FAIL because entry points do not create sandbox context yet.

- [ ] **Step 3: Wire WebAgentService**

Modify `backend/app/services/web_agent.py`:

```python
from app.capability.sandbox_manager import SandboxManager


manager = SandboxManager()
manager.create_or_switch_novel_sandbox(
    novel_id=novel_id,
    user_id=user_id,
    created_by_agent_instance_id=session_id,
    session_context=self.session.context,
    tool_context=self.session.context,
)
self.session.context["agent_role"] = "main"
self.session.context["agent_name"] = self.agent_name
tool_context = dict(self.session.context)
```

Place this after the base `user_id`, `novel_id`, `agent_name`, and `agent_instance_id` context values are set and before constructing `AgentCore`.

- [ ] **Step 4: Wire CLI and `/load`**

Modify `backend/app/ui/cli.py`:

```python
from ..capability.sandbox_manager import SandboxManager


sandbox_manager = SandboxManager()
session.context["agent_role"] = "main"
session.context["agent_name"] = "main"
sandbox_manager.create_or_switch_novel_sandbox(
    novel_id=session.context["novel_id"],
    user_id=0,
    created_by_agent_instance_id=session_id,
    session_context=session.context,
    tool_context=session.context,
)
```

Modify `backend/app/ui/commands.py` in `_load_novel()` after setting `self.agent.tool_context["novel_id"]`:

```python
from ..capability.sandbox_manager import SandboxManager


SandboxManager().create_or_switch_novel_sandbox(
    novel_id=novel_id,
    user_id=self.agent.tool_context.get("user_id"),
    created_by_agent_instance_id=self.agent.tool_context.get("agent_instance_id", ""),
    session_context=self.agent.session.context,
    tool_context=self.agent.tool_context,
    create=False,
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/test_cli.py tests/test_p1_regressions.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/web_agent.py backend/app/ui/cli.py backend/app/ui/commands.py backend/tests/test_cli.py backend/tests/test_p1_regressions.py
git commit -m "feat: initialize sandbox contexts"
```

## Task 8: Final Verification

**Files:**
- Modify only if a focused fix is needed after verification.

- [ ] **Step 1: Run focused sandbox and agent tests**

Run:

```bash
cd backend
uv run pytest tests/test_sandbox_manager.py tests/test_tool_policy.py tests/test_file_tools.py tests/test_tools.py tests/test_agent_core.py tests/test_subagent_manager.py tests/test_memory_tools.py tests/test_cli.py tests/test_p1_regressions.py -v
```

Expected: PASS.

- [ ] **Step 2: Run full backend test suite**

Run:

```bash
cd backend
uv run pytest
```

Expected: PASS.

- [ ] **Step 3: Inspect changed files**

Run:

```bash
git status --short
git diff --stat
```

Expected: only sandbox implementation and test files are modified, plus pre-existing unrelated dirty files if they were already present before implementation.

- [ ] **Step 4: Commit any verification fixes**

If Step 1 or Step 2 required small fixes, commit them:

```bash
git add backend/app backend/tests
git commit -m "fix: stabilize sandbox integration"
```

Expected: no commit is needed if all previous task commits passed cleanly.

## Self-Review Notes

- Spec coverage: tasks cover controlled sandbox create/switch, sandbox-only path resolution, role-based tool schema and execution policy, sub-agent writer/reviewer memory isolation, Web/CLI initialization, and final full-suite verification.
- Gap scan: no unresolved implementation gaps are intentionally left in this plan.
- Type consistency: plan consistently uses `agent_role` for permissions, `agent_name` for business memory namespace, `sandbox_id`, `sandbox_root`, and `create_subagent(role)`.
