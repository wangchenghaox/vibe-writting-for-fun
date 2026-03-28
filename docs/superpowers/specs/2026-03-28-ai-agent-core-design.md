# AI Agent核心系统设计文档

**日期**: 2026-03-28
**版本**: 1.0
**项目**: 网文自动生成AI工具

## 1. 项目概述

构建一个AI Agent核心系统，作为网文自动生成工具的基础。该系统支持多轮对话、工具调用、技能加载、子代理管理、任务跟踪和上下文压缩等核心能力。

## 2. 技术栈

- **后端框架**: Python + FastAPI
- **AI框架**: 基于LangChain的轻量封装
- **默认LLM**: Moonshot Kimi API
- **存储**: 待定（后续工作流阶段确定）

## 3. 整体架构

系统采用分层架构设计：

```
┌─────────────────────────────────────┐
│      Agent API Layer (FastAPI)     │  ← HTTP接口层
├─────────────────────────────────────┤
│      Agent Core (对话引擎)          │  ← 核心逻辑层
│  - 多轮对话管理                      │
│  - Context压缩                       │
│  - Tool/Skill调度                    │
├─────────────────────────────────────┤
│   LLM Provider Adapter (多模型)     │  ← 适配层
│  - Kimi / Claude / OpenAI / 其他    │
├─────────────────────────────────────┤
│   Capability Layer (能力层)         │
│  - Tool Registry (工具注册)         │
│  - Skill Loader (技能加载)          │
│  - SubAgent Manager (子代理管理)    │
│  - Task Manager (任务管理)          │
├─────────────────────────────────────┤
│   Storage Layer (存储层)            │
│  - 对话历史                          │
│  - 执行记录                          │
└─────────────────────────────────────┘
```

**设计原则**:
- 分层清晰，每层职责单一
- 适配器模式支持多LLM切换
- 插件化设计，Tool和Skill可插拔

## 4. 核心组件设计

### 4.1 Agent Core (对话引擎)

**职责**: 管理对话会话，协调各个能力模块

**核心类设计**:
```python
class AgentCore:
    session: Session  # 会话状态（消息历史、上下文）
    llm_provider: LLMProvider  # LLM适配器
    tool_registry: ToolRegistry  # 工具注册表
    skill_loader: SkillLoader  # 技能加载器
    subagent_manager: SubAgentManager  # 子代理管理器
    task_manager: TaskManager  # 任务管理器

    def chat(message: str) -> str:
        """处理用户消息，返回响应"""

    def compress_context() -> None:
        """压缩上下文"""

    def execute_tool(tool_name: str, params: dict) -> Any:
        """执行工具"""

    def load_skill(skill_name: str) -> None:
        """加载技能到当前会话"""
```

### 4.2 Context压缩策略

采用混合压缩策略，平衡上下文质量和token效率：

**保留规则**:
- 最近5-10条消息（完整保留）
- 包含tool调用的消息（关键操作记录）
- 用户明确标记的重要消息
- System prompt和当前加载的skill

**压缩规则**:
- 中间历史消息使用LLM生成摘要
- 摘要保留关键信息：决策点、重要结论、上下文依赖

**触发条件**:
- Token数超过模型上下文窗口的70%时自动触发

### 4.3 Tool注册机制

使用装饰器模式实现函数注册：

```python
@tool(name="生成章节", description="根据大纲生成章节内容")
def generate_chapter(outline: str, chapter_num: int, previous_content: str = "") -> str:
    """
    生成章节内容

    Args:
        outline: 章节大纲
        chapter_num: 章节编号
        previous_content: 前文内容（可选）

    Returns:
        生成的章节内容
    """
    # 实现逻辑
    pass
```

**自动化处理**:
- 系统自动提取函数签名和docstring
- 生成符合LLM要求的tool schema
- 注册到tool_registry
- LLM调用时自动执行并返回结果

## 5. Skill系统设计

### 5.1 Skill文件格式

Skill使用Markdown格式定义，包含frontmatter元数据：

```markdown
---
name: chapter-writer
description: 生成网文章节
trigger: 当用户要求生成章节时
version: 1.0
---

# 章节生成技能

## 目标
根据大纲和前文内容，生成符合网文风格的章节

## 执行步骤
1. 分析大纲和前文，理解故事走向
2. 确定本章节的核心冲突和情节推进
3. 生成章节内容（3000-5000字）
4. 检查节奏把控和伏笔埋设

## 质量标准
- 符合人物设定，行为逻辑自洽
- 情节推进自然，不突兀
- 有悬念或爽点，保持读者兴趣
- 语言流畅，符合网文风格
```

### 5.2 Skill加载机制

- 从 `skills/` 目录扫描所有 `.md` 文件
- 解析frontmatter获取元数据（name, description, trigger等）
- Markdown内容作为system prompt的补充注入到对话上下文
- 支持动态加载和卸载

### 5.3 预定义的必要Skill

1. **chapter-writer.md** - 章节生成
2. **content-reviewer.md** - 内容review
3. **outline-generator.md** - 大纲生成
4. **character-designer.md** - 人物设定

### 5.4 Skill vs System Prompt

**System Prompt适合放**:
- 基础身份和角色定位
- 通用行为准则
- 核心能力的简要说明

**Skill适合放**:
- 具体执行流程和步骤
- 详细质量标准
- 可复用的工作流模板
- 领域知识和技巧

**优势**:
- 灵活性：不同项目可以使用不同skill
- 可维护性：修改逻辑只需更新skill文件
- 可组合性：可以有多个skill变体
- Context效率：skill按需加载

## 6. SubAgent系统设计

### 6.1 SubAgent配置结构

```python
class SubAgentConfig:
    name: str  # 代理名称
    system_prompt: str  # 系统提示词
    available_tools: List[str]  # 可用工具列表
    max_iterations: int  # 最大迭代次数
    llm_provider: str  # 使用的LLM provider（可选，默认继承主Agent）
```

### 6.2 预定义的专用SubAgent

针对网文生成场景，预定义以下SubAgent：

1. **OutlineAgent** - 大纲生成和优化
   - 从idea生成完整大纲
   - 细化和优化已有大纲

2. **ChapterWriter** - 章节内容生成和修改
   - 模式1: 生成新章节（根据大纲+前文）
   - 模式2: 修改章节（根据review意见）

3. **ContentReviewer** - 内容审查
   - 检查质量、逻辑、人设一致性
   - 提供具体的修改建议

4. **DialogueRefiner** - 对话优化
   - 按需调用，改进对话质量
   - 保持人物性格和语言风格

### 6.3 SubAgent执行流程

```
主Agent接收任务
    ↓
创建SubAgent会话（独立上下文）
    ↓
传入初始上下文（大纲、前文、人设等）
    ↓
SubAgent独立执行任务
    ↓
返回结果给主Agent
    ↓
主Agent继续协调流程
```

**关键特性**:
- SubAgent拥有独立的对话会话
- 创建时可选择性传入需要的上下文片段
- 执行完成后会话可以保留或销毁

### 6.4 动态创建机制

主Agent可以通过tool动态创建临时SubAgent：

```python
@tool(name="创建子代理", description="创建临时子代理处理特殊任务")
def create_subagent(role: str, task: str, context: str) -> str:
    """
    动态创建SubAgent

    Args:
        role: 代理角色描述
        task: 具体任务
        context: 需要的上下文

    Returns:
        SubAgent执行结果
    """
    # 系统根据role生成合适的system prompt
    # 创建临时SubAgent并执行
    # 执行完成后自动销毁
    pass
```

## 7. Task系统设计

### 7.1 Task结构

```python
class Task:
    id: str  # 任务ID
    name: str  # 任务名称，如"生成第3章"
    status: str  # pending/running/completed/failed
    steps: List[TaskStep]  # 任务步骤列表
    result: Any  # 任务结果
    error: str  # 错误信息（如果失败）
    created_at: datetime
    updated_at: datetime

class TaskStep:
    name: str  # 步骤名称
    status: str  # pending/running/completed/failed
    agent: str  # 执行的Agent/SubAgent
    input: dict  # 输入参数
    output: Any  # 输出结果
```

### 7.2 使用场景

**场景1: 批量生成章节**
```
用户："生成第1-5章"
→ 主Agent创建Task: "生成1-5章"
→ 分解为5个Step（每章一个）
→ 依次调用ChapterWriter SubAgent
→ 每完成一步更新Task状态
→ 用户可以实时查看进度
```

**场景2: 复杂工作流**
```
用户："完成第3章的生成和review"
→ 主Agent创建Task: "第3章生成+review"
→ Step1: ChapterWriter生成章节
→ Step2: ContentReviewer审查
→ Step3: 根据review决定是否修改
→ Step4: (如需要) ChapterWriter修改
```

### 7.3 Task与SubAgent的关系

- Task是任务跟踪和状态管理机制
- SubAgent是具体的执行单元
- 一个Task可以包含多个SubAgent调用
- Task记录完整的执行历史，便于调试和回溯

## 8. LLM Provider适配层设计

### 8.1 统一接口

```python
class LLMProvider(ABC):
    @abstractmethod
    def chat(self, messages: List[Message], tools: List[Tool] = None) -> Response:
        """同步对话"""
        pass

    @abstractmethod
    def stream_chat(self, messages: List[Message], tools: List[Tool] = None) -> Iterator[Response]:
        """流式对话"""
        pass

    @abstractmethod
    def count_tokens(self, messages: List[Message]) -> int:
        """计算token数"""
        pass
```

### 8.2 支持的Provider

1. **KimiProvider** - Moonshot Kimi API（默认）
2. **ClaudeProvider** - Anthropic Claude API
3. **OpenAIProvider** - OpenAI GPT API
4. **CustomProvider** - 自定义API（兼容OpenAI格式）

### 8.3 配置方式

```yaml
llm:
  default: kimi
  providers:
    kimi:
      api_key: ${KIMI_API_KEY}
      model: moonshot-v1-128k
      base_url: https://api.moonshot.cn/v1
    claude:
      api_key: ${CLAUDE_API_KEY}
      model: claude-3-5-sonnet-20241022
    openai:
      api_key: ${OPENAI_API_KEY}
      model: gpt-4-turbo
```

### 8.4 切换机制

- 全局默认provider（配置文件指定）
- 可以为特定SubAgent指定provider
  - 例如：ContentReviewer使用更便宜的模型
  - ChapterWriter使用质量更高的模型

## 9. 会话持久化与恢复机制

### 9.1 设计目标

支持会话的保存和恢复，允许用户中断后继续工作，不丢失上下文和执行状态。

### 9.2 持久化内容

**会话状态（Session State）**:
- 会话ID和元数据（创建时间、最后活跃时间）
- 完整的消息历史
- 当前加载的Skill列表
- 工程上下文（大纲、人设、已生成章节等）

**执行记录（Execution Log）**:
- Tool调用记录（参数、返回值、时间戳）
- SubAgent执行记录（输入、输出、状态）
- Task执行历史（步骤、状态变更）

**检查点（Checkpoint）**:
- 关键操作后自动创建检查点
- 用户可手动创建检查点
- 支持回滚到指定检查点

### 9.3 存储结构

```python
class SessionStore:
    def save_session(session_id: str, session: Session) -> None:
        """保存会话状态"""

    def load_session(session_id: str) -> Session:
        """加载会话状态"""

    def list_sessions() -> List[SessionMetadata]:
        """列出所有会话"""

    def delete_session(session_id: str) -> None:
        """删除会话"""

class CheckpointManager:
    def create_checkpoint(session_id: str, name: str = None) -> str:
        """创建检查点，返回checkpoint_id"""

    def restore_checkpoint(checkpoint_id: str) -> Session:
        """恢复到指定检查点"""

    def list_checkpoints(session_id: str) -> List[Checkpoint]:
        """列出会话的所有检查点"""
```

### 9.4 文件存储格式

```
data/
├── sessions/
│   ├── {session_id}/
│   │   ├── metadata.json       # 会话元数据
│   │   ├── messages.jsonl      # 消息历史（每行一条）
│   │   ├── context.json        # 工程上下文
│   │   └── execution_log.jsonl # 执行记录
│   └── ...
└── checkpoints/
    ├── {checkpoint_id}.json    # 检查点快照
    └── ...
```

### 9.5 自动保存策略

- 每次对话后自动保存会话状态
- Tool执行后追加执行记录
- 关键操作后自动创建检查点：
  - 章节生成完成
  - Review完成
  - 大纲确定

### 9.6 恢复流程

```
用户请求恢复会话
    ↓
加载会话元数据
    ↓
恢复消息历史
    ↓
恢复工程上下文（大纲、人设等）
    ↓
重新加载Skill
    ↓
恢复执行状态（未完成的Task）
    ↓
继续对话
```

## 9. 会话持久化与恢复机制

### 9.1 设计目标

支持会话的保存和恢复，允许用户中断后继续工作，不丢失上下文和执行状态。

### 9.2 持久化内容

**会话状态（Session State）**:
- 会话ID和元数据（创建时间、最后活跃时间）
- 完整的消息历史
- 当前加载的Skill列表
- 工程上下文（大纲、人设、已生成章节等）

**执行记录（Execution Log）**:
- Tool调用记录（参数、返回值、时间戳）
- SubAgent执行记录（输入、输出、状态）
- Task执行历史（步骤、状态变更）

**检查点（Checkpoint）**:
- 关键操作后自动创建检查点
- 用户可手动创建检查点
- 支持回滚到指定检查点

### 9.3 存储结构

```python
class SessionStore:
    def save_session(session_id: str, session: Session) -> None:
        """保存会话状态"""

    def load_session(session_id: str) -> Session:
        """加载会话状态"""

    def list_sessions() -> List[SessionMetadata]:
        """列出所有会话"""

    def delete_session(session_id: str) -> None:
        """删除会话"""

class CheckpointManager:
    def create_checkpoint(session_id: str, name: str = None) -> str:
        """创建检查点，返回checkpoint_id"""

    def restore_checkpoint(checkpoint_id: str) -> Session:
        """恢复到指定检查点"""

    def list_checkpoints(session_id: str) -> List[Checkpoint]:
        """列出会话的所有检查点"""
```

### 9.4 文件存储格式

```
data/
├── sessions/
│   ├── {session_id}/
│   │   ├── metadata.json       # 会话元数据
│   │   ├── messages.jsonl      # 消息历史（每行一条）
│   │   ├── context.json        # 工程上下文
│   │   └── execution_log.jsonl # 执行记录
│   └── ...
└── checkpoints/
    ├── {checkpoint_id}.json    # 检查点快照
    └── ...
```

### 9.5 自动保存策略

- 每次对话后自动保存会话状态
- Tool执行后追加执行记录
- 关键操作后自动创建检查点：
  - 章节生成完成
  - Review完成
  - 大纲确定

### 9.6 恢复流程

```
用户请求恢复会话
    ↓
加载会话元数据
    ↓
恢复消息历史
    ↓
恢复工程上下文（大纲、人设等）
    ↓
重新加载Skill
    ↓
恢复执行状态（未完成的Task）
    ↓
继续对话
```

## 10. 实时反馈与可观测性

### 10.1 设计目标

所有生成的内容、执行状态、中间结果都需要实时反馈给用户，支持CLI和Web两种界面。

### 10.2 事件流机制

使用事件驱动架构，所有关键操作都发出事件：

```python
class EventType(Enum):
    # 对话事件
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"

    # 内容生成事件
    OUTLINE_GENERATED = "outline_generated"
    CHAPTER_STARTED = "chapter_started"
    CHAPTER_PROGRESS = "chapter_progress"  # 流式生成中
    CHAPTER_COMPLETED = "chapter_completed"

    # Review事件
    REVIEW_STARTED = "review_started"
    REVIEW_COMPLETED = "review_completed"
    REVIEW_ISSUE_FOUND = "review_issue_found"

    # Task事件
    TASK_CREATED = "task_created"
    TASK_STEP_STARTED = "task_step_started"
    TASK_STEP_COMPLETED = "task_step_completed"
    TASK_COMPLETED = "task_completed"

    # Tool/SubAgent事件
    TOOL_CALLED = "tool_called"
    TOOL_RESULT = "tool_result"
    SUBAGENT_STARTED = "subagent_started"
    SUBAGENT_COMPLETED = "subagent_completed"

class Event:
    type: EventType
    timestamp: datetime
    data: dict
    session_id: str
```

### 10.3 实时推送机制

**CLI模式**:
- 使用rich库实现实时更新的终端UI
- 显示当前执行状态、进度条、日志流

**Web模式**:
- 使用Server-Sent Events (SSE) 推送事件
- 前端实时更新UI显示

```python
class EventBus:
    def publish(event: Event) -> None:
        """发布事件到所有订阅者"""

    def subscribe(event_types: List[EventType], callback: Callable) -> str:
        """订阅特定类型的事件"""

    def unsubscribe(subscription_id: str) -> None:
        """取消订阅"""
```

### 10.4 可观测的内容类型

**1. 生成内容**
- 大纲：完整结构、章节列表
- 人物设定：角色信息、关系图
- 章节内容：实时流式显示生成过程
- 对话优化：修改前后对比

**2. 执行状态**
- 当前正在执行的Task
- Task的步骤进度（如：生成第3章，步骤2/4）
- SubAgent执行状态（如：ContentReviewer正在审查）

**3. Review意见**
- 问题列表（按严重程度分类）
- 具体位置标注
- 修改建议
- 是否已修复状态

**4. 工程视图**
- 章节列表（已完成/进行中/待生成）
- 对话历史
- 执行记录时间线
- 检查点列表

### 10.5 CLI展示设计

使用rich库实现分区布局：

```
┌─────────────────────────────────────────────────────────┐
│ 工程: 《修仙传奇》              状态: 生成中            │
├─────────────────────────────────────────────────────────┤
│ 当前任务: 生成第3章                                      │
│ 进度: ████████░░░░░░░░░░ 40% (2/5步骤)                  │
│ 执行: ChapterWriter SubAgent                            │
├─────────────────────────────────────────────────────────┤
│ [对话区域]                                               │
│ 用户: 生成第3章                                          │
│ Agent: 好的，开始生成第3章...                            │
│                                                          │
│ [生成内容实时显示]                                       │
│ 第三章 初入宗门                                          │
│ 　　清晨的阳光洒在青石台阶上...                          │
├─────────────────────────────────────────────────────────┤
│ [状态栏]                                                 │
│ 章节: 2已完成 | 1进行中 | 7待生成                        │
│ Review: 0问题                                            │
└─────────────────────────────────────────────────────────┘
```

### 10.6 Web界面展示设计

**主界面布局**:
```
┌──────────┬─────────────────────────────────────┬──────────┐
│          │                                     │          │
│  工程    │         对话区域                     │  侧边栏  │
│  列表    │                                     │          │
│          │  [消息1]                            │  章节    │
│  工程1   │  [消息2]                            │  - 第1章 │
│  工程2   │  [生成中的内容实时显示]              │  - 第2章 │
│  工程3   │                                     │  - 第3章 │
│          │                                     │          │
│          │  [输入框]                           │  大纲    │
│          │                                     │  人设    │
│          ├─────────────────────────────────────┤  Review  │
│          │  执行状态: ChapterWriter 生成中...   │  历史    │
│          │  进度: 40%                          │          │
└──────────┴─────────────────────────────────────┴──────────┘
```

**侧边栏内容**:
- 章节列表（点击查看内容）
- 大纲（可折叠）
- 人设（可折叠）
- Review意见（按章节分组）
- 对话历史（可搜索）
- 执行记录（时间线）

### 10.7 实时更新示例

**章节生成流程的事件序列**:
```
1. TASK_CREATED: "生成第3章"
   → CLI/Web显示: 创建任务

2. TASK_STEP_STARTED: "ChapterWriter开始生成"
   → CLI/Web显示: 进度条开始，状态更新

3. CHAPTER_PROGRESS: 流式内容片段
   → CLI/Web显示: 实时追加显示生成的文字

4. CHAPTER_COMPLETED: 完整章节
   → CLI/Web显示: 进度100%，章节列表更新

5. TASK_STEP_STARTED: "ContentReviewer开始审查"
   → CLI/Web显示: 状态切换到Review

6. REVIEW_COMPLETED: Review结果
   → CLI/Web显示: Review意见列表，问题标注
```

## 11. 核心Tool列表

除了SubAgent相关的tool，系统还需要以下基础tool：

**内容管理类**:
1. **save_chapter** - 保存章节内容
2. **load_chapter** - 加载章节内容
3. **list_chapters** - 列出所有章节
4. **save_outline** - 保存大纲
5. **load_outline** - 加载大纲

**分析类**:
6. **analyze_plot** - 分析情节结构、节奏、冲突

**代理管理类**:
7. **create_subagent** - 动态创建SubAgent
8. **create_task** - 创建任务
9. **get_task_status** - 查询任务状态

**会话管理类**:
10. **save_session** - 保存当前会话
11. **load_session** - 加载历史会话
12. **list_sessions** - 列出所有会话
13. **create_checkpoint** - 创建检查点
14. **restore_checkpoint** - 恢复到检查点

**事件发布类**:
15. **publish_event** - 发布事件到事件总线（内部使用）

## 10. 项目结构

```
ai-agent-core/
├── src/
│   ├── agent/
│   │   ├── core.py              # AgentCore核心类
│   │   ├── session.py           # 会话管理
│   │   └── context_compressor.py  # 上下文压缩
│   ├── llm/
│   │   ├── provider.py          # Provider基类
│   │   ├── kimi.py              # Kimi Provider
│   │   ├── claude.py            # Claude Provider
│   │   └── openai.py            # OpenAI Provider
│   ├── capability/
│   │   ├── tool_registry.py     # Tool注册
│   │   ├── skill_loader.py      # Skill加载
│   │   ├── subagent_manager.py  # SubAgent管理
│   │   └── task_manager.py      # Task管理
│   ├── tools/
│   │   ├── chapter_tools.py     # 章节相关tool
│   │   ├── outline_tools.py     # 大纲相关tool
│   │   └── analysis_tools.py    # 分析相关tool
│   ├── storage/
│   │   ├── repository.py        # 存储接口
│   │   ├── session_store.py     # 会话持久化
│   │   └── checkpoint.py        # 检查点管理
│   ├── events/
│   │   ├── event_bus.py         # 事件总线
│   │   └── event_types.py       # 事件类型定义
│   ├── ui/
│   │   ├── cli.py               # CLI界面
│   │   └── rich_display.py      # Rich终端显示
│   └── api/
│       ├── routes.py            # FastAPI路由
│       └── sse.py               # Server-Sent Events
├── skills/
│   ├── chapter-writer.md
│   ├── content-reviewer.md
│   ├── outline-generator.md
│   └── character-designer.md
├── subagents/
│   ├── outline_agent.yaml
│   ├── chapter_writer.yaml
│   ├── content_reviewer.yaml
│   └── dialogue_refiner.yaml
├── config/
│   └── llm.yaml                 # LLM配置
├── data/                        # 运行时数据目录
│   ├── sessions/
│   └── checkpoints/
├── tests/
└── requirements.txt
```

## 11. 实现优先级

### Phase 1: 核心基础（MVP）
1. LLM Provider适配层（Kimi）
2. AgentCore基础对话能力
3. Tool注册机制
4. 基础的章节生成tool
5. 会话持久化与恢复机制
6. 事件总线和基础CLI显示

### Phase 2: 能力扩展
1. Skill系统
2. SubAgent系统（预定义的4个SubAgent）
3. Context压缩
4. 更多Provider支持
5. 检查点机制
6. Rich终端UI优化

### Phase 3: 高级特性
1. Task系统
2. 动态SubAgent创建
3. Web界面和SSE推送
4. 性能优化
5. 完善的错误处理

## 12. 非功能需求

### 12.1 性能
- 单次对话响应时间 < 30秒（非流式）
- 支持流式输出，提升用户体验
- Context压缩触发时间 < 5秒

### 12.2 可靠性
- Tool执行失败自动重试（最多3次）
- SubAgent执行超时保护（默认5分钟）
- 完善的错误日志和追踪

### 12.3 可扩展性
- 易于添加新的Tool
- 易于添加新的Skill
- 易于添加新的LLM Provider
- 易于添加新的SubAgent类型

## 13. 后续工作

本设计文档聚焦于AI Agent核心系统。后续需要设计的子项目：

1. **工作流引擎** - plan-execute-review-edit流程
2. **Web前端** - 对话界面、工程管理、侧边栏
3. **存储系统** - 对话记录、执行记录、文章内容持久化
4. **Review系统** - AI自动review + 人工介入机制

每个子项目将有独立的设计文档。
