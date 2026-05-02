# Agent Sandbox 系统设计

**日期**: 2026-05-02
**版本**: 1.0
**项目**: 中文 AI 小说生成器

## 1. 目标

为现有 Agent 系统新增第一版 sandbox 能力，使所有 LLM 暴露工具的文件读写都被限制在明确创建的本地文件夹内。

第一版采用本地文件系统 sandbox，不引入容器、进程隔离或操作系统权限模型。系统目标是先建立清晰的 Agent 权限边界：

- 主 agent 负责和用户交互、理解需求、制定计划，并通过受控编排能力创建、切换和管理 sandbox、创建并调度 sub-agent。默认 sandbox 由 Web/CLI 入口在创建主 agent 前建立，避免主 agent 在没有 sandbox 的状态下读取文件。
- 主 agent 只能通过工具读取和检索当前 sandbox 内文件。唯一允许的写入副作用是 sandbox 管理工具创建小说 sandbox 时产生的受控目录和最小元数据；主 agent 不能创建、写入、编辑、删除或重命名正文、大纲、审稿、技能等内容文件。
- sub-agent 负责具体实施，拥有当前 sandbox 内文件的完整读写改删权限。
- 所有文件工具和领域落盘工具都必须通过 sandbox 路径校验，不能访问 sandbox 外部路径。

## 2. 非目标

- 第一版不实现 Docker、chroot、macOS sandbox-exec、Linux namespace 或独立进程用户隔离。
- 第一版不阻止后端 Python 服务自身读取配置、加载技能、写数据库或记录日志；sandbox 只约束 LLM 可调用工具的文件系统能力。
- 第一版不迁移现有 SQLite 元数据、记忆系统或 Web 登录体系。
- 第一版不允许 sub-agent 继续创建新的 sub-agent，避免递归代理和权限链路过早复杂化。
- 第一版不解决恶意第三方代码执行问题；当前系统没有向 LLM 暴露 shell 执行工具。

## 3. 方案选择

采用“角色化工具权限 + 本地 sandbox 路径约束”。

路径层约束负责确保任何文件路径最终都落在 sandbox 根目录下。角色化工具权限负责让主 agent 从 schema 层就看不到写入工具，并在执行层再次拦截伪造或异常的写入调用。

这比只做路径限制更适合当前产品：主 agent 不会反复尝试不可用的写入工具；同时 sub-agent 可以保持完整实施能力。它也比 OS/container sandbox 更轻，适合先验证 Agent 工作流和测试边界。

## 4. 权限模型

### 4.1 Agent 角色

系统内置两个运行时角色：

```text
main
subagent
```

角色来自 `AgentCore.tool_context["agent_role"]`。如果缺省，默认为 `main`，保证旧入口默认按更保守权限运行。

### 4.2 主 agent 权限

主 agent 可见工具类型：

- 文件读取和检索：`read_file`、`list_files`、`grep_files`、`search_files`
- 领域读取：`get_novel`、`load_novel_document`、`list_novel_documents`、`review_chapter`
- 记忆工具：继续按现有 `user_id + novel_id + agent_name` 上下文规则暴露
- 外部读取工具：例如 `web_search`
- sandbox 管理工具：`create_sandbox`、`switch_sandbox`
- sub-agent 编排工具：`create_subagent`、`run_subagent`

主 agent 不可见也不可执行的工具类型：

- 通用文件写入：`write_file`、`edit_file`、`delete_file`、`rename_file`
- 领域内容落盘：`save_novel_document`
- legacy 小说创建工具：`create_novel`，主 agent 使用新的 `create_sandbox` 受控创建小说 sandbox，不直接暴露旧工具
- 后续新增的任何带文件写入、文件删除、文件移动副作用的工具

主 agent 的 `create_sandbox` 是受控例外：它只能为当前用户创建新的小说 sandbox，并只能写入目录结构和最小元数据，不能接收任意文件内容。

### 4.3 sub-agent 权限

sub-agent 可见工具类型：

- 文件读取、检索、写入、编辑、删除、重命名
- 领域读取和领域落盘工具
- 记忆工具
- 外部读取工具

sub-agent 不可见 sandbox 管理和编排工具：`create_sandbox`、`switch_sandbox`、`create_subagent`、`run_subagent`。第一版由主 agent 统一调度。

sub-agent 也不负责切换当前会话的 sandbox。sandbox 切换只由主 agent 通过 `switch_sandbox` 完成。

### 4.4 执行层防护

工具 schema 过滤只是第一层。`execute_tool()` 还必须根据当前 `agent_role` 和工具元数据做执行前校验：

- 主 agent 调用文件写入类工具时返回中文拒绝信息，不执行函数。
- sub-agent 调用编排工具时返回中文拒绝信息，不执行函数。
- 文件类工具缺少 `sandbox_root` 时失败关闭。
- 工具参数中传入的 `novel_id`、绝对路径或 `../` 不能绕过 sandbox。
- `run_subagent()` 必须校验目标 sub-agent 的 `sandbox_id` 和主 agent 当前 `sandbox_id` 一致，避免切换小说后误用旧 sub-agent 写入旧 sandbox。

## 5. Sandbox 模型

### 5.1 Sandbox 数据

第一版 sandbox 是内存运行时对象，不新增数据库表。

```python
@dataclass(frozen=True)
class Sandbox:
    id: str
    root: Path
    owner_user_id: int | None
    novel_id: str | None
    title: str
    created_by_agent_instance_id: str
```

`root` 必须是解析后的绝对路径。创建时立即 `mkdir(parents=True, exist_ok=True)`，并保存到主 agent 和 sub-agent 的 `tool_context`：

```python
tool_context["sandbox_id"] = sandbox.id
tool_context["sandbox_root"] = str(sandbox.root)
```

当前会话同一时间只有一个 active sandbox。创建或切换 sandbox 时必须同步更新：

```python
session.context["novel_id"] = sandbox.novel_id
session.context["sandbox_id"] = sandbox.id
session.context["sandbox_root"] = str(sandbox.root)
tool_context["novel_id"] = sandbox.novel_id
tool_context["sandbox_id"] = sandbox.id
tool_context["sandbox_root"] = str(sandbox.root)
```

已创建的 sub-agent 绑定创建时的 sandbox。主 agent 切换 active sandbox 后，旧 sub-agent 不能继续通过 `run_subagent()` 执行，除非显式切回同一个 sandbox。

### 5.2 默认根目录

Web 小说会话默认使用当前小说文件夹作为 sandbox 根：

```text
backend/data/novels/{Novel.novel_id}/
```

这样现有前端详情页仍能读取 `chapters/` 等内容，避免第一版引入文件迁移。

CLI 默认使用：

```text
backend/data/novels/{CURRENT_NOVEL_ID or "default"}/
```

未来如果需要编辑 `backend/skills/`，应由受信任的应用入口显式创建以 `backend/skills/` 为根的 sandbox；普通小说会话不会默认获得该能力。

### 5.3 新建与切换 sandbox

主 agent 需要支持用户在聊天过程中说“新建一本小说”或“切换到另一部小说”。这类操作属于 sandbox 管理，不属于正文写入。

新建小说 sandbox：

1. 主 agent 调用 `create_sandbox(novel_id, title, description)`。
2. 后端校验 `novel_id` 格式、当前用户是否已有同名小说、目标路径是否位于 `backend/data/novels/`。
3. 后端创建 `backend/data/novels/{novel_id}/` 及必要子目录。
4. Web 场景下同步创建或复用 `Novel` 数据库记录；CLI 场景下写入最小 `meta.json`，保证 CLI 命令和文件读取可用。
5. 当前 session 和 `tool_context` 切换到新 sandbox。
6. 后续写章节、大纲、审稿仍必须由 sub-agent 完成。

切换小说 sandbox：

1. 主 agent 调用 `switch_sandbox(novel_id)`。
2. Web 场景下必须校验该小说属于当前用户；CLI 场景下必须校验目标目录位于允许的 novels 根下。
3. 后端更新当前 session 和 `tool_context` 的 `novel_id`、`sandbox_id`、`sandbox_root`。
4. 新建 sub-agent 时继承切换后的 active sandbox。

`create_sandbox` 和 `switch_sandbox` 不允许接收任意本地绝对路径。它们只能在受信任的 novels 根目录内工作。

### 5.4 路径解析规则

所有文件工具统一调用 sandbox 路径解析函数：

```text
resolve_sandbox_path(input_path, sandbox_root, novel_id)
```

规则：

- 空路径表示 sandbox 根。
- 普通相对路径解析为 `sandbox_root / input_path`。
- `novels/{novel_id}/...` 作为兼容别名，映射到 `sandbox_root / ...`。
- `novels/{other_novel_id}/...` 被拒绝。
- 绝对路径只有在解析后仍位于 `sandbox_root` 内才允许；返回给 LLM 的展示路径仍使用 sandbox 相对路径。
- `../`、符号链接或大小写变体导致的逃逸都必须通过 `Path.resolve(strict=False)` 后的 `is_relative_to(sandbox_root)` 检查拒绝。

### 5.5 展示路径

工具结果不要暴露完整服务器路径。返回给 agent 和用户的路径使用：

```text
sandbox:/chapters/chapter_1.md
```

或兼容旧 skill 的相对形式：

```text
novels/{novel_id}/chapters/chapter_1.md
```

## 6. 组件设计

### 6.1 SandboxManager

新增 `backend/app/capability/sandbox_manager.py`。

职责：

- 创建本地文件系统 sandbox。
- 根据 `user_id`、`novel_id`、`agent_instance_id` 生成稳定可读的 `sandbox_id`。
- 创建或切换小说 sandbox 时同步更新 session context 和 tool context。
- 返回注入 Agent 上下文所需的 `sandbox_id` 和 `sandbox_root`。
- 暴露 `resolve_path()`，供文件工具和领域工具复用。

`SandboxManager` 不接受来自 LLM 的任意本地路径作为根目录。第一版只允许从受信任入口传入的当前小说目录，或在已配置的 novels/sandbox base 目录下创建、切换小说 sandbox。

第一版不做持久化注册表。WebSocket 或 CLI 会话关闭后，sandbox 文件保留，运行时对象可丢弃。

### 6.2 Tool 元数据

扩展 `@tool()` 装饰器，增加可选元数据：

```python
@tool(
    name="write_file",
    description="Write a text file within the sandbox",
    access="filesystem_write",
    context_params=["sandbox_root", "novel_id"],
)
```

第一版工具访问类型：

```text
filesystem_read
filesystem_write
domain_read
domain_write
memory
external_read
orchestration
sandbox_management
```

现有工具需要显式标注。未知访问类型默认按主 agent 不可写的原则处理：只有 `main` 明确允许的类型会进入主 agent schema。

### 6.3 ToolPolicy

新增轻量策略函数，放在 `backend/app/capability/tool_registry.py` 或独立 `tool_policy.py`：

```text
allowed_access_for_role("main")
allowed_access_for_role("subagent")
```

`AgentCore._get_tools_for_skills()` 在现有 skill allow-list 和 memory 上下文过滤之后，再按角色过滤工具 schema。

`execute_tool()` 在调用函数前再次执行同一套策略，并返回中文拒绝信息：

```text
操作被拒绝: main agent 不能写入、编辑或删除文件，请创建 sub-agent 执行。
```

### 6.4 编排工具

新增 `backend/app/tools/orchestration_tools.py`，只对主 agent 暴露。

第一版工具：

```text
create_sandbox(novel_id: str, title: str = "", description: str = "") -> str
switch_sandbox(novel_id: str) -> str
create_subagent(name: str, instructions: str = "") -> str
run_subagent(subagent_id: str, task: str) -> str
```

这些工具通过隐藏上下文获取当前 `SandboxManager`、`SubAgentManager`、provider、session、sandbox 信息和 memory recorder factory。`create_sandbox()` 只允许在受控 novels 根目录内创建新的小说 sandbox，不能接收任意 root path。`switch_sandbox()` 只允许切换到当前用户可访问的小说 sandbox。`create_subagent()` 创建的 sub-agent 继承当前 active sandbox，但角色强制为 `subagent`，并覆盖 `agent_name` 和 `agent_instance_id`。

### 6.5 AgentCore 上下文

`AgentCore.__init__()` 继续接收 `tool_context`，并补齐默认值：

```python
tool_context.setdefault("agent_role", "main")
```

`AgentCore` 初始化时把运行时编排对象放入工具上下文，但这些对象必须作为 `context_params` 隐藏，不出现在 LLM schema 中：

```python
tool_context["_provider"] = provider
tool_context["_session"] = session
tool_context["_sandbox_manager"] = self.sandbox_manager
tool_context["_subagent_manager"] = self.subagent_manager
tool_context["_memory_recorder_factory"] = MemoryEventRecorder
```

如果上下文中没有 sandbox，Web 和 CLI 入口应在创建主 agent 前调用 `SandboxManager` 创建默认 sandbox。

### 6.6 文件工具

`backend/app/tools/file_tools.py` 改为只使用 sandbox 允许根，不再默认允许 `backend/skills` 或整个 `backend/data/novels`。

所有文件工具增加隐藏上下文参数：

```text
sandbox_root
novel_id
agent_role
```

写入类工具带 `access="filesystem_write"`。读取检索类工具带 `access="filesystem_read"`。

### 6.7 领域工具

`backend/app/tools/novel_tools.py` 的文件读写也必须经过 sandbox。

第一版建议：

- `get_novel()`、`load_novel_document()`、`list_novel_documents()` 使用当前 sandbox 下的 `meta.json`、`outlines/`、`chapters/`。
- `save_novel_document()` 标注为 `domain_write`，只有 sub-agent 可见。
- legacy `create_novel()` 不再作为主 agent 的小说创建入口；如保留，需要标注为 `domain_write` 或改造成内部服务函数，由 `create_sandbox()` 以受控方式调用。
- 如果传入的 `novel_id` 和当前上下文 `novel_id` 不一致，拒绝访问，避免一个小说会话写到另一个小说目录。

REST API 中 `POST /api/novels` 仍是受信任服务端行为，不属于 LLM 工具权限。

## 7. 数据流

### 7.1 Web 会话

1. 用户进入小说聊天页。
2. WebSocket 路由把数据库自增 `Novel.id` 映射为业务 `Novel.novel_id`。
3. `WebAgentService` 创建默认 sandbox：`backend/data/novels/{novel.novel_id}`。
4. 主 agent 获得 `agent_role=main`、`sandbox_root`、`sandbox_id`。
5. 如果用户要求切换小说，主 agent 调用 `switch_sandbox(novel_id)`，后端校验当前用户拥有该小说后更新 active sandbox。
6. 如果用户要求新建小说，主 agent 调用 `create_sandbox(novel_id, title, description)`，后端创建数据库记录、小说目录和最小元数据，并把 active sandbox 切到新小说。
7. 主 agent 读取资料、制定计划，需要写内容时调用 `create_subagent()` 和 `run_subagent()`。
8. sub-agent 在 active sandbox 内写入章节、大纲、审稿文件。
9. 前端详情页继续从同一小说目录读取章节文件。

### 7.2 CLI 会话

1. CLI 根据 `CURRENT_NOVEL_ID` 或 `default` 创建默认 sandbox。
2. 主 agent 获得只读文件工具、sandbox 管理工具和编排工具。
3. 如果用户要求新建或切换小说，主 agent 可调用 `create_sandbox()` 或 `switch_sandbox()`，CLI 命令 `/load` 也可更新同一份 sandbox context。
4. 写内容任务通过 sub-agent 完成。

### 7.3 Sub-agent 执行

1. 主 agent 创建 sub-agent。
2. `SubAgentManager` 复制父级 `tool_context`。
3. 子上下文覆盖：

```text
agent_role = subagent
agent_name = 用户指定角色名
agent_instance_id = subagent_{name}_{index}
```

4. sub-agent 执行任务并返回结果。
5. 主 agent 把结果总结给用户。

## 8. 错误处理

- 缺少 sandbox：返回 `操作被拒绝: 当前 agent 未绑定 sandbox`。
- 路径逃逸：返回 `操作被拒绝: 路径必须位于当前 sandbox 内`。
- 主 agent 写入：返回 `操作被拒绝: main agent 只能读取文件，请交给 sub-agent 执行`。
- sub-agent 调编排工具：返回 `操作被拒绝: sub-agent 不能创建或调度其他 agent`。
- 不匹配 novel_id：返回 `操作被拒绝: 当前 sandbox 只允许访问小说 {novel_id}`。
- 新建 sandbox 时 novel_id 已存在：返回 `操作被拒绝: 小说 {novel_id} 已存在，请切换到该小说或使用新的 novel_id`。
- 切换 sandbox 时小说不存在或用户无权访问：返回 `操作被拒绝: 无法访问小说 {novel_id}`。
- 切换 sandbox 后运行旧 sub-agent：返回 `操作被拒绝: sub-agent 绑定的 sandbox 与当前 sandbox 不一致`。

这些错误作为 tool result 返回，不应导致 WebSocket 断开或 CLI 崩溃。

## 9. 测试策略

新增和调整测试集中在 `backend/tests/`：

- `test_sandbox_manager.py`
  - 创建 sandbox 会建立目录并返回绝对根路径。
  - 相对路径、`novels/{novel_id}` 兼容路径解析到 sandbox 内。
  - `../outside.txt`、其他 novel_id、逃逸符号链接被拒绝。

- `test_tool_policy.py`
  - main agent schema 不包含 `write_file`、`edit_file`、`delete_file`、`rename_file`、`create_novel`、`save_novel_document`。
  - main agent schema 包含 `create_sandbox` 和 `switch_sandbox`。
  - sub-agent schema 包含文件写入工具和领域写入工具。
  - sub-agent schema 不包含 `create_sandbox`、`switch_sandbox`、`create_subagent`、`run_subagent`。
  - main agent 伪造执行写入工具时被 `execute_tool()` 拒绝，但可执行受控 sandbox 创建/切换。
  - sub-agent 伪造调用编排工具时被拒绝。

- `test_file_tools.py`
  - sub-agent context 可在 sandbox 内写入、读取、编辑、重命名和删除。
  - 缺少 sandbox_root 时文件工具失败关闭。
  - 文件工具返回展示路径不包含服务器绝对路径。

- `test_subagent_manager.py`
  - 创建 sub-agent 时继承 `sandbox_id` 和 `sandbox_root`。
  - sub-agent 强制覆盖为 `agent_role=subagent`。
  - 切换 active sandbox 后，旧 sub-agent 不能在新 sandbox 下继续执行。
  - sub-agent 仍保留 memory recorder 的运行时身份。

- `test_websocket` 或 `test_p1_regressions.py`
  - WebAgentService 初始化主 agent 时带默认 sandbox context。
  - WebSocket 中 DB id 到业务 novel_id 的映射不被破坏。
  - Web 场景下 `create_sandbox()` 会创建当前用户的 `Novel` 记录并切换 active sandbox。
  - Web 场景下 `switch_sandbox()` 拒绝切换到其他用户的小说。

## 10. 兼容性与迁移

现有小说文件继续保存在：

```text
backend/data/novels/{novel_id}/
```

第一版不迁移 Markdown 或 JSON 文件。已有 skill 文案中的 `novels/{novel_id}/...` 路径通过路径别名兼容。

需要注意：当前 `skill-curator` 可编辑 `backend/skills/`。引入 sandbox 后，普通小说会话不再默认允许 agent 修改技能文件。后续如果仍需要在线维护技能，应为该任务创建单独的技能 sandbox，并明确只让 sub-agent 写入。

## 11. 安全边界

这一版 sandbox 是应用层能力边界，不是操作系统安全边界。它可以防止 LLM 通过已注册工具读写 sandbox 外文件，但不能防止后端代码漏洞、第三方库漏洞或未来新增 shell/代码执行工具带来的风险。

因此后续新增任何工具时必须标注访问类型，并在测试中证明主 agent 不能通过该工具产生文件写入副作用。

## 12. 验收标准

- 主 agent 在普通聊天中只能看到读取、检索、记忆、外部读取、sandbox 管理和编排工具。
- 主 agent 可以通过受控工具创建新小说 sandbox 或切换到当前用户可访问的小说 sandbox。
- 主 agent 直接或伪造调用文件写入/领域落盘工具时不会产生文件修改。
- 主 agent 创建 sandbox 只产生受控目录、最小元数据和 Web 小说记录，不写正文、大纲、审稿或技能文件。
- sub-agent 能在 sandbox 内创建、编辑、删除文件。
- sub-agent 不能访问 sandbox 外路径。
- 切换 sandbox 后，新 sub-agent 继承新的 active sandbox，旧 sub-agent 不能误写当前 sandbox 之外的位置。
- Web 和 CLI 入口都会为主 agent 初始化默认 sandbox。
- 现有小说章节展示路径保持可用。
- 相关后端测试通过。
