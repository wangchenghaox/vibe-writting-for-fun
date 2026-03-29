# 测试实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的测试套件，确保CLI和Web服务可用

**Architecture:** 三层测试架构（单元测试→集成测试→E2E测试）

**Tech Stack:** pytest, pytest-asyncio, pytest-cov, httpx, faker

---

## Task 1: 配置测试环境

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: 添加测试依赖**

修改 `backend/pyproject.toml`:
```toml
dependencies = [
    # ... existing dependencies
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "faker>=20.0.0",
]
```

- [ ] **Step 2: 安装依赖**

Run: `cd backend && uv sync`
Expected: 依赖安装成功

- [ ] **Step 3: 创建测试配置**

创建 `backend/tests/conftest.py`:
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
```

- [ ] **Step 4: 提交**

```bash
git add backend/pyproject.toml backend/tests/conftest.py
git commit -m "test: add testing environment setup"
```

## Task 2: 补充单元测试

**Files:**
- Create: `backend/tests/test_skill_loader.py`
- Create: `backend/tests/test_subagent_manager.py`
- Create: `backend/tests/test_task_manager.py`

- [ ] **Step 1: 创建Skill Loader测试**

```python
import pytest
from app.capability.skill_loader import SkillLoader

def test_load_nonexistent_skill():
    loader = SkillLoader()
    result = loader.load_skill("nonexistent")
    assert result is None

def test_get_loaded_skills():
    loader = SkillLoader()
    skills = loader.get_loaded_skills()
    assert isinstance(skills, dict)
```

- [ ] **Step 2: 创建SubAgent Manager测试**

```python
from app.capability.subagent_manager import SubAgentManager

def test_create_subagent(mock_provider, session):
    manager = SubAgentManager()
    agent_id = manager.create_subagent("test", mock_provider, session)
    assert agent_id.startswith("subagent_test")
```

- [ ] **Step 3: 创建Task Manager测试**

```python
from app.capability.task_manager import TaskManager, TaskStatus

def test_create_task():
    manager = TaskManager()
    task = manager.create_task("task1", "Test task")
    assert task.status == TaskStatus.PENDING
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/ -v`
Expected: 所有测试通过

- [ ] **Step 5: 提交**

```bash
git add tests/
git commit -m "test: add unit tests for new components"
```

## Task 3: 创建集成测试

**Files:**
- Create: `backend/tests/integration/test_api_auth.py`
- Create: `backend/tests/integration/test_api_novels.py`

- [ ] **Step 1: 创建API认证测试**

```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_register_and_login():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 注册
        resp = await client.post("/api/auth/register", json={"username": "test", "password": "test123"})
        assert resp.status_code == 200

        # 登录
        resp = await client.post("/api/auth/login", json={"username": "test", "password": "test123"})
        assert resp.status_code == 200
        assert "token" in resp.json()
```

- [ ] **Step 2: 运行集成测试**

Run: `pytest tests/integration/ -v`
Expected: 测试通过

- [ ] **Step 3: 提交**

```bash
git add tests/integration/
git commit -m "test: add integration tests for API"
```

## Task 4: 创建E2E测试

**Files:**
- Create: `backend/tests/e2e/test_web_e2e.py`

- [ ] **Step 1: 创建Web E2E测试**

```python
@pytest.mark.asyncio
async def test_complete_user_flow():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 注册
        await client.post("/api/auth/register", json={"username": "user1", "password": "pass123"})

        # 登录
        resp = await client.post("/api/auth/login", json={"username": "user1", "password": "pass123"})
        token = resp.json()["token"]

        # 创建小说
        resp = await client.post("/api/novels",
            json={"novel_id": "novel1", "title": "测试", "description": "测试"},
            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
```

- [ ] **Step 2: 运行E2E测试**

Run: `pytest tests/e2e/ -v`
Expected: 测试通过

- [ ] **Step 3: 提交**

```bash
git add tests/e2e/
git commit -m "test: add E2E tests"
```

## Task 5: 生成覆盖率报告

- [ ] **Step 1: 运行覆盖率测试**

Run: `pytest tests/ --cov=app --cov-report=html`
Expected: 覆盖率 ≥ 80%

- [ ] **Step 2: 提交最终代码**

```bash
git add .
git commit -m "test: complete test suite implementation"
```
