# Agent 记忆系统设计

**日期**: 2026-04-30
**版本**: 1.0
**项目**: 中文 AI 小说生成器

## 1. 目标

为现有 Agent 增加可记录、可查询、可隔离、可追溯的长期记忆系统。记忆系统服务于小说创作流程，使 Agent 能在多轮、多会话中保存人物设定、世界观规则、用户偏好、写作约束、剧情事实和重要决策。

第一版以 SQLite 为主存储，保留文件导出能力。检索方式先支持结构化过滤和关键词查询，表结构预留后续语义检索和自动抽取扩展。

## 2. 非目标

- 第一版不引入向量数据库或 embedding provider。
- 第一版不实现全自动长期记忆抽取 worker。
- 第一版不开放跨用户、跨小说、跨 agent 的记忆互查。
- 第一版不把小说正文、大纲、章节迁入数据库；这些内容继续使用现有文件存储。

## 3. 命名空间与隔离

每条记忆和每条原始事件都必须绑定到同一个命名空间：

```text
user_id + novel_id + agent_name
```

- `user_id`: Web 用户数据库 ID。
- `novel_id`: 业务小说 ID，即 `Novel.novel_id` 字符串，不使用数据库自增 ID。
- `agent_name`: Agent 身份名称。第一版默认 `main`，后续可扩展为 `writer`、`reviewer`、`worldbuilding` 等。

`agent_name` 是稳定角色名，不是运行时临时 ID。CLI 或 Web 中多次创建同名 subagent 时，只要它们的稳定角色名相同，就共享该角色的长期记忆。

运行时实例另有 `agent_instance_id`，用于 Raw Log 追踪某次具体执行：

```text
agent_name = writer
agent_instance_id = subagent_writer_20260430_01
```

`agent_instance_id` 不参与长期记忆隔离，避免每次重启或重新创建 subagent 都产生孤岛记忆。

所有查询和写入必须在服务层强制注入命名空间。LLM 不能自行指定或覆盖 `user_id`，默认也不能查询其他 agent 的私有记忆。

### 3.1 记忆可见范围

长期记忆需要支持有条件共享，因此 `agent_memories` 增加 `scope`：

```text
scope = agent
scope = novel
```

- `agent`: 默认值，只对当前 `agent_name` 可见。
- `novel`: 当前 `user_id + novel_id` 下所有 agent 可见，用于小说正典、世界观规则、全局剧情状态等共享事实。

查询默认返回：

```text
当前 agent 的 agent-scope 记忆
+
当前小说的 novel-scope 共享记忆
```

例子：

- `writer` 的写作风格偏好使用 `scope = agent`。
- “女主不能使用火系能力”这类小说正典使用 `scope = novel`。
- `reviewer` 的审稿策略使用 `scope = agent`。
- 临时 subagent 的过程性推理只进入 Raw Log，不写长期记忆。

## 4. 分层模型

记忆系统分为三层。

### 4.1 Raw Log 层

Raw Log 保存原始对话和工具执行事件，作为审计、回放、抽取来源和问题排查依据。

保存内容包括：

- 用户消息
- assistant 最终回复
- assistant tool call
- tool result
- 错误事件
- 上下文压缩事件

Raw Log 是事实来源，不参与人工编辑。写入失败不应阻断聊天，但必须记录后端日志。

### 4.2 Explicit Memory 层

Explicit Memory 是 agent 主动调用记忆工具写入的长期记忆。它比 Raw Log 更结构化，质量和可信度更高。

适合保存：

- 用户偏好：喜欢紧凑节奏、讨厌过度解释
- 小说正典：女主不能使用火系能力
- 人物设定：男主对师门有亏欠感
- 剧情状态：第三章结尾主角已得到钥匙
- 风格约束：战斗描写要短句、强动作

Explicit Memory 可查询、归档和更新。

### 4.3 Extracted Memory 层

Extracted Memory 是后续自动抽取模块从 Raw Log 中生成的记忆。第一版只在数据模型中预留，不自动生成。

Extracted Memory 必须保留来源事件、置信度和抽取器版本，便于追溯和修正。

## 5. 存储方案

### 5.1 主存储

SQLite 作为记忆系统主存储。原因是记忆需要隔离、查询、更新、归档、去重和来源追溯，SQLite 比纯文件存储更适合这些操作。

### 5.2 文件存储

文件系统继续保存小说资产：

```text
backend/data/novels/{novel_id}/
  meta.json
  outlines/
  chapters/
```

记忆系统可选提供 JSONL 导出：

```text
backend/data/memory_exports/{novel_id}/{agent_name}.jsonl
```

导出用于备份、调试和人工审阅，不作为在线查询主路径。

## 6. 数据库设计

### 6.1 agent_event_logs

保存 Raw Log。

```sql
agent_event_logs
- id: INTEGER PRIMARY KEY
- user_id: INTEGER NOT NULL
- novel_id: VARCHAR(100) NOT NULL
- agent_name: VARCHAR(80) NOT NULL
- agent_instance_id: VARCHAR(160) NULL
- session_id: VARCHAR(160) NOT NULL
- event_type: VARCHAR(40) NOT NULL
- payload_json: TEXT NOT NULL
- created_at: DATETIME NOT NULL
```

索引：

- `(user_id, novel_id, agent_name, created_at)`
- `(agent_instance_id, created_at)`
- `(session_id, created_at)`
- `(event_type, created_at)`

`event_type` 第一版取值：

```text
user_message
assistant_message
tool_call
tool_result
error
context_compressed
```

### 6.2 agent_memories

保存 Explicit Memory 和 Extracted Memory。

```sql
agent_memories
- id: INTEGER PRIMARY KEY
- user_id: INTEGER NOT NULL
- novel_id: VARCHAR(100) NOT NULL
- agent_name: VARCHAR(80) NOT NULL
- scope: VARCHAR(20) NOT NULL
- layer: VARCHAR(20) NOT NULL
- memory_type: VARCHAR(40) NOT NULL
- content: TEXT NOT NULL
- tags_json: TEXT NOT NULL
- importance: INTEGER NOT NULL
- status: VARCHAR(20) NOT NULL
- source_event_id: INTEGER NULL
- source_event_ids_json: TEXT NULL
- confidence: FLOAT NULL
- extractor_version: VARCHAR(80) NULL
- embedding_model: VARCHAR(120) NULL
- embedding_json: TEXT NULL
- created_at: DATETIME NOT NULL
- updated_at: DATETIME NOT NULL
```

索引：

- `(user_id, novel_id, agent_name, status, updated_at)`
- `(user_id, novel_id, scope, status, updated_at)`
- `(user_id, novel_id, agent_name, layer, memory_type)`
- `(source_event_id)`

`scope` 取值：

```text
agent
novel
```

`layer` 取值：

```text
explicit
extracted
```

`memory_type` 第一版取值：

```text
preference
canon
character
plot
style
constraint
note
```

`status` 取值：

```text
active
archived
```

`embedding_model` 和 `embedding_json` 第一版保留为空，用于后续语义检索升级。

## 7. 后端组件

### 7.1 MemoryRepository

底层数据库访问模块，负责：

- 写入 Raw Log
- 创建记忆
- 查询记忆
- 归档记忆
- 按命名空间和 `scope` 可见性过滤所有读写

该模块不依赖 LLM，不了解 AgentCore。

### 7.2 MemoryService

业务服务层，负责：

- 规范化 `agent_name`
- 从工具上下文读取并校验 `user_id`、`novel_id`、`agent_name`
- 校验 `scope`、`memory_type`、`layer`、`importance`、`status`
- 处理标签 JSON 序列化
- 控制查询 limit
- 统一错误返回
- 为工具层提供简单接口

### 7.3 MemoryEventRecorder

Agent 事件记录器，负责把 AgentCore 中的用户消息、assistant 消息、工具调用和工具结果写入 Raw Log。

记录器接受：

```text
user_id
novel_id
agent_name
agent_instance_id
session_id
```

Web 入口必须提供完整命名空间。CLI 暂无用户身份，第一版可以使用固定 `user_id = 0`、当前 `CURRENT_NOVEL_ID` 或 `default`，并使用 `agent_name = main`。

## 8. 记忆工具

新增工具文件：

```text
backend/app/tools/memory_tools.py
```

并在 `backend/app/tools/__init__.py` 导入，确保注册副作用生效。

第一版工具：

```text
remember_memory(content, memory_type="note", tags="", importance=3, scope="agent")
search_memory(query="", memory_type=None, tags="", scope=None, limit=5)
list_memories(memory_type=None, tags="", scope=None, limit=10)
archive_memory(memory_id)
```

这些工具需要隐藏上下文参数：

```text
user_id
novel_id
agent_name
agent_instance_id
```

当前 `ToolRegistry` 会把函数签名参数全部暴露给模型，因此实现时需要扩展工具注册机制，支持 context-only 参数。推荐接口：

```python
@tool(
    "remember_memory",
    "记录一条长期记忆",
    context_params=["user_id", "novel_id", "agent_name", "agent_instance_id"],
)
def remember_memory(
    content: str,
    memory_type: str = "note",
    tags: str = "",
    importance: int = 3,
    scope: str = "agent",
    user_id: int = None,
    novel_id: str = None,
    agent_name: str = "main",
    agent_instance_id: str = None,
) -> str:
    ...
```

`context_params` 中的参数参与 `execute_tool(..., context=self.tool_context)` 注入，但不出现在 LLM tool schema 中。

安全约束：

- `user_id` 不暴露为模型可填参数。
- `novel_id` 不暴露为模型可填参数。
- `agent_name` 不暴露为模型可填参数。
- `agent_instance_id` 不暴露为模型可填参数。
- `scope` 暴露给模型，但只允许 `agent` 或 `novel`。
- `execute_tool` 对 context-only 参数使用上下文值覆盖模型参数，避免绕过 schema 的调用污染命名空间。
- `archive_memory` 只能归档当前查询可见范围内的记忆，即当前 agent 的私有记忆或当前小说的共享记忆。

工具返回中文字符串或 JSON 字符串，方便当前 Agent 消费。

## 9. Agent 集成

### 9.1 WebAgentService

`WebAgentService` 构造参数扩展为：

```python
WebAgentService(
    user_id: int,
    novel_id: str,
    agent_name: str = "main",
    agent_instance_id: str | None = None,
    on_event: Callable = None,
)
```

并将完整上下文注入 AgentCore：

```python
tool_context={
    "user_id": user_id,
    "novel_id": novel_id,
    "agent_name": agent_name,
    "agent_instance_id": agent_instance_id,
}
```

WebSocket 路由仍接收数据库自增 `Novel.id`，校验通过后使用 `novel.novel_id` 作为记忆命名空间。

### 9.2 AgentCore

AgentCore 第一版只需要两个集成点：

- `_start_turn` 写入 `user_message` Raw Log。
- assistant 回复、tool call、tool result 写入 Raw Log。

主动长期记忆由 LLM 调用 `remember_memory` 完成。第一版不在每轮开始自动注入所有记忆，避免污染上下文。

### 9.3 SubAgent 身份规则

Subagent 创建时必须区分稳定角色名和运行时实例 ID：

```text
agent_name: writer
agent_instance_id: subagent_writer_<session-or-uuid>
```

长期记忆按 `agent_name` 共享。因此 CLI 这次新建 `writer` subagent，下次重新打开后再次新建 `writer` subagent，默认共享 `writer` 的长期记忆。

不同 `agent_name` 默认隔离。例如 `writer` 和 `reviewer` 不共享 `scope = agent` 的私有记忆。需要跨 agent 共享的小说事实，应写入 `scope = novel`。

第一版不提供“临时实例独占长期记忆”。如果确实需要临时隔离，只记录 Raw Log，或使用新的稳定 `agent_name`。

### 9.4 记忆查询策略

第一版依靠模型主动调用 `search_memory`。Agent 可以在需要回忆设定、偏好或剧情事实时查询。

第二阶段可在 `_start_turn` 前做轻量关键词检索，把 top 3-5 条相关 active memory 注入 system prompt。

## 10. 查询语义

第一版查询使用 SQLite 结构化过滤和 `LIKE` 关键词匹配。

查询条件：

- 必选：`user_id`、`novel_id`、`status = active`
- 默认可见性：`(scope = agent AND agent_name = 当前 agent_name) OR scope = novel`
- 可选：`scope`
- 可选：`memory_type`
- 可选：标签过滤
- 可选：`content LIKE %query%`

排序：

```text
importance DESC, updated_at DESC
```

limit 默认 5，最大 20。

## 11. 错误处理

- Raw Log 写入失败：记录后端日志，不阻断聊天。
- Explicit Memory 写入失败：工具返回明确错误，让 agent 和用户可见。
- 查询失败：工具返回错误 JSON 或中文错误信息。
- 参数非法：返回可理解的校验信息，例如“不支持的 memory_type: xxx”。
- 数据库表缺失：应用启动时通过 `Base.metadata.create_all` 创建表，测试环境同样使用 in-memory SQLite 初始化。

## 12. 测试计划

后端单元测试：

- `MemoryRepository` 可按命名空间写入和查询。
- 不同 `user_id` 的记忆互不可见。
- 不同 `novel_id` 的记忆互不可见。
- 不同 `agent_name` 的 `scope = agent` 私有记忆互不可见。
- 同一 `user_id + novel_id` 下的 `scope = novel` 共享记忆对不同 agent 可见。
- `archive_memory` 只能影响当前查询可见范围内的记忆。
- `search_memory` 支持关键词、类型、标签、limit。

Agent 集成测试：

- `AgentCore` 调用工具时能注入 `user_id`、`novel_id`、`agent_name`、`agent_instance_id`。
- `remember_memory` 能保存到当前命名空间。
- 同名 subagent 跨会话共享同一 `agent_name` 的长期记忆。
- WebSocket 初始化 `WebAgentService` 时传入正确的业务 `novel.novel_id`。
- Raw Log 至少记录 user message、assistant message、tool call、tool result。

回归测试：

- 现有小说工具仍按 `novel_id` 文件路径落盘。
- 未提供记忆上下文时，CLI 可以使用默认上下文工作。
- 记忆工具注册不影响现有工具 schema 生成。

## 13. 分阶段实施

### 第一阶段

- 增加数据库模型。
- 增加 `MemoryRepository`、`MemoryService`。
- 增加记忆工具。
- Web 入口注入 `user_id + novel_id + agent_name + agent_instance_id`。
- SubAgent 管理器区分稳定 `agent_name` 和运行时 `agent_instance_id`。
- AgentCore 写 Raw Log。
- 补充单元和集成测试。

### 第二阶段

- 增加会话恢复到 `sessions` 表，或将会话恢复与 Raw Log 回放打通。
- 在每轮对话开始前可选注入少量相关记忆。
- 增加记忆导出 JSONL。

### 第三阶段

- 增加自动抽取任务。
- 从 Raw Log 生成 Extracted Memory。
- 增加去重、合并、置信度、来源追踪 UI。
- 接入 embedding 和语义检索。

## 14. 验收标准

- Agent 可以通过工具主动记录长期记忆。
- Agent 可以查询当前用户、当前小说、当前 agent 的私有 active 记忆，以及当前小说的共享 active 记忆。
- 不同用户、小说、agent 私有记忆不会串。
- 同名 subagent 跨 CLI/Web 会话共享稳定角色记忆，临时实例只用于 Raw Log 追踪。
- Raw Log 能记录基本对话与工具事件。
- 第一版不依赖外部向量库、embedding 服务或后台 worker。
- 所有新增测试通过，现有测试不回退。
