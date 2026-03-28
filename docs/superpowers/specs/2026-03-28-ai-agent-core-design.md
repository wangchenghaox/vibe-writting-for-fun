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

## 9. 核心Tool列表

除了SubAgent相关的tool，系统还需要以下基础tool：

1. **analyze_plot** - 分析情节结构、节奏、冲突
2. **save_chapter** - 保存章节内容
3. **load_chapter** - 加载章节内容
4. **list_chapters** - 列出所有章节
5. **save_outline** - 保存大纲
6. **load_outline** - 加载大纲
7. **create_subagent** - 动态创建SubAgent
8. **create_task** - 创建任务
9. **get_task_status** - 查询任务状态

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
│   │   └── repository.py        # 存储接口
│   └── api/
│       └── routes.py            # FastAPI路由
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
├── tests/
└── requirements.txt
```

## 11. 实现优先级

### Phase 1: 核心基础（MVP）
1. LLM Provider适配层（Kimi）
2. AgentCore基础对话能力
3. Tool注册机制
4. 基础的章节生成tool

### Phase 2: 能力扩展
1. Skill系统
2. SubAgent系统（预定义的4个SubAgent）
3. Context压缩
4. 更多Provider支持

### Phase 3: 高级特性
1. Task系统
2. 动态SubAgent创建
3. 性能优化
4. 完善的错误处理

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
