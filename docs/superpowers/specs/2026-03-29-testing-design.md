# AI 小说生成器测试设计

**日期**: 2026-03-29
**版本**: 1.0

## 1. 测试目标

确保CLI和Web服务的核心功能可用、稳定、符合设计要求。

## 2. 测试策略

### 2.1 测试金字塔

```
       E2E Tests (5%)
      ---------------
    Integration Tests (15%)
   -----------------------
  Unit Tests (80%)
```

### 2.2 测试类型

**单元测试（Unit Tests）**
- 目标：测试单个组件功能
- 覆盖率：80%+
- 执行时间：<1秒

**集成测试（Integration Tests）**
- 目标：测试组件间交互
- 覆盖率：关键路径100%
- 执行时间：1-5秒

**E2E测试（End-to-End Tests）**
- 目标：测试完整用户流程
- 覆盖率：核心场景100%
- 执行时间：5-30秒

## 3. 单元测试设计

### 3.1 已有测试
- ✅ test_agent_core.py - AgentCore基础功能
- ✅ test_session.py - Session消息管理
- ✅ test_tools.py - 工具注册
- ✅ test_events.py - 事件总线
- ✅ test_context_compressor.py - 上下文压缩

### 3.2 需补充的单元测试

**test_llm_provider.py**
- 测试LLM Provider适配器
- Mock API调用
- 测试错误处理

**test_skill_loader.py**
- 测试技能加载
- 测试技能卸载
- 测试文件不存在场景

**test_subagent_manager.py**
- 测试子代理创建
- 测试子代理执行
- 测试子代理移除

**test_task_manager.py**
- 测试任务创建
- 测试状态更新
- 测试任务查询

## 4. 集成测试设计

### 4.1 API集成测试

**test_api_auth.py**
- 测试用户注册
- 测试用户登录
- 测试JWT认证
- 测试权限验证

**test_api_novels.py**
- 测试小说创建
- 测试小说列表
- 测试小说详情
- 测试用户隔离

**test_websocket.py**
- 测试WebSocket连接
- 测试消息发送
- 测试AI响应
- 测试断线重连

### 4.2 数据库集成测试

**test_db_operations.py**
- 测试CRUD操作
- 测试事务处理
- 测试外键约束
- 测试并发访问

## 5. E2E测试设计

### 5.1 CLI E2E测试

**test_cli_e2e.py**
- 场景1：创建小说并生成章节
- 场景2：加载已有小说继续创作
- 场景3：使用命令查看内容
- 场景4：审查章节并修改

### 5.2 Web E2E测试

**test_web_e2e.py**
- 场景1：用户注册→登录→创建小说→对话创作
- 场景2：查看小说列表→进入对话→生成章节
- 场景3：多用户并发创作
- 场景4：WebSocket断线恢复

## 6. 测试工具和依赖

```toml
[project.optional-dependencies]
test = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "httpx>=0.25.0",
    "faker>=20.0.0",
]
```

## 7. 测试执行策略

### 7.1 本地开发
```bash
# 运行所有测试
pytest tests/ -v

# 运行单元测试
pytest tests/unit/ -v

# 运行集成测试
pytest tests/integration/ -v

# 运行E2E测试
pytest tests/e2e/ -v

# 生成覆盖率报告
pytest tests/ --cov=app --cov-report=html
```

### 7.2 CI/CD流程
1. 代码提交触发
2. 运行单元测试（必须通过）
3. 运行集成测试（必须通过）
4. 运行E2E测试（可选）
5. 生成覆盖率报告
6. 部署到测试环境

## 8. 测试数据管理

### 8.1 测试数据库
- 使用SQLite内存数据库
- 每个测试独立事务
- 测试后自动清理

### 8.2 测试fixtures
```python
@pytest.fixture
def test_db():
    # 创建测试数据库
    yield db
    # 清理
```

## 9. 测试用例优先级

### P0 - 核心功能（必须通过）
- 用户认证
- 小说创建
- AI对话
- WebSocket连接

### P1 - 重要功能
- 章节管理
- 工具调用
- 事件推送
- 数据持久化

### P2 - 辅助功能
- 上下文压缩
- 技能加载
- 任务管理

## 10. 成功标准

- 单元测试覆盖率 ≥ 80%
- 集成测试通过率 = 100%
- E2E测试通过率 = 100%
- 无P0级别bug
- 响应时间 < 2秒（API）
- WebSocket延迟 < 500ms
