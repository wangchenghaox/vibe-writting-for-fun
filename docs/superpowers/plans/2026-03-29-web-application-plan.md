# Web 应用实现计划

基于设计文档：`docs/superpowers/specs/2026-03-29-web-application-design.md`

## 任务列表

### 任务 1: 创建项目目录结构
**目标：** 建立 Web 应用的基础目录结构

**步骤：**
1. 创建 `ai-agent-web/` 根目录
2. 创建 `backend/` 子目录（FastAPI 后端）
3. 创建 `frontend/` 子目录（Vue.js 前端）
4. 创建 `docs/` 子目录

**验证：**
```bash
ls -la ai-agent-web/
# 应该看到 backend/, frontend/, docs/ 目录
```

---

### 任务 2: 设置后端基础架构
**目标：** 初始化 FastAPI 后端项目和数据库

**步骤：**
1. 在 `backend/` 创建 `pyproject.toml`，添加依赖：
   - fastapi
   - uvicorn
   - sqlalchemy
   - python-jose[cryptography]
   - passlib[bcrypt]
   - python-multipart
2. 创建 `backend/app/` 目录结构：
   - `models/` - 数据库模型
   - `api/` - API 路由
   - `core/` - 核心配置
   - `db/` - 数据库连接
3. 创建 `backend/app/db/base.py` - SQLAlchemy 基础配置
4. 创建 `backend/app/core/config.py` - 环境变量配置
5. 创建 `backend/.env.example` - 环境变量模板

**验证：**
```bash
cd backend && uv sync
# 依赖安装成功
```

---

### 任务 3: 实现用户认证系统
**目标：** 实现用户注册、登录和 JWT 认证

**步骤：**
1. 创建 `backend/app/models/user.py` - User 模型
2. 创建 `backend/app/core/security.py` - 密码哈希和 JWT 工具函数
3. 创建 `backend/app/api/auth.py` - 认证 API 路由
4. 创建 `backend/app/core/deps.py` - JWT 依赖注入
5. 在 `backend/app/main.py` 注册路由

**验证：**
```bash
# 测试注册
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'

# 测试登录
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'
# 应该返回 token
```

---

### 任务 4: 实现小说管理 API
**目标：** 创建小说 CRUD API

**步骤：**
1. 创建 `backend/app/models/novel.py` - Novel, Session, ReviewHistory 模型
2. 创建 `backend/app/api/novels.py` - 小说管理路由
3. 实现文件系统集成（读取 data/novels/）
4. 实现统计计算逻辑

**验证：**
```bash
# 测试获取小说列表
curl http://localhost:8000/api/novels \
  -H "Authorization: Bearer <token>"
```

---

### 任务 5: 实现 WebSocket 对话服务
**目标：** 创建 WebSocket 实时对话功能

**步骤：**
1. 创建 `backend/app/api/websocket.py` - WebSocket 端点
2. 创建 `backend/app/services/chat_service.py` - 集成 AgentCore
3. 实现事件推送逻辑
4. 实现会话自动保存

**验证：**
```bash
# 使用 WebSocket 客户端测试连接
wscat -c "ws://localhost:8000/ws/chat/test_novel?token=<token>"
```

---

### 任务 6: 初始化 Vue.js 前端项目
**目标：** 创建 Vue.js 前端应用

**步骤：**
1. 使用 Vite 创建项目：`npm create vite@latest frontend -- --template vue-ts`
2. 安装依赖：`npm install vue-router pinia element-plus axios`
3. 配置路由（`src/router/index.ts`）
4. 配置状态管理（`src/stores/`）
5. 创建基础布局组件

**验证：**
```bash
cd frontend && npm run dev
# 访问 http://localhost:5173
```

---

### 任务 7: 实现前端认证页面
**目标：** 创建登录和注册页面

**步骤：**
1. 创建 `src/views/Login.vue` - 登录页面
2. 创建 `src/views/Register.vue` - 注册页面
3. 创建 `src/api/auth.ts` - 认证 API 调用
4. 创建 `src/stores/user.ts` - 用户状态管理
5. 实现路由守卫（`src/router/index.ts`）

**验证：**
- 访问 /login，输入账号密码，成功登录后跳转到 /novels

---

### 任务 8: 实现小说列表和详情页
**目标：** 创建小说管理界面

**步骤：**
1. 创建 `src/views/NovelList.vue` - 小说列表页
2. 创建 `src/views/NovelDetail.vue` - 小说详情页
3. 创建 `src/api/novels.ts` - 小说 API 调用
4. 创建 `src/stores/novels.ts` - 小说状态管理

**验证：**
- 访问 /novels，看到小说列表
- 点击小说卡片，进入详情页，看到章节列表和统计

---

### 任务 9: 实现对话界面组件
**目标：** 创建实时对话界面

**步骤：**
1. 创建 `src/views/Chat.vue` - 对话页面（三栏布局）
2. 创建 `src/components/ChatMessage.vue` - 消息组件
3. 创建 `src/composables/useWebSocket.ts` - WebSocket 连接管理
4. 实现虚拟滚动（使用 vue-virtual-scroller）

**验证：**
- 访问 /novels/:id/chat
- 发送消息，看到实时响应
- 看到思考过程和工具调用

---

### 任务 10: 实现审查历史功能
**目标：** 创建章节审查历史展示

**步骤：**
1. 创建 `src/components/ReviewHistory.vue` - 审查历史组件
2. 创建 `src/api/reviews.ts` - 审查 API 调用
3. 在对话界面集成审查历史

**验证：**
- 在对话界面左侧看到审查历史列表
- 点击查看审查详情

---

### 任务 11: 完善错误处理和优化
**目标：** 添加错误处理和性能优化

**步骤：**
1. 后端：创建统一错误处理中间件
2. 前端：创建 API 请求拦截器（axios）
3. 实现 WebSocket 自动重连逻辑
4. 添加加载状态和错误提示
5. 实现路由懒加载

**验证：**
- 测试 401 错误自动跳转登录
- 测试 WebSocket 断开重连
- 测试网络错误提示

---

## 实施顺序

按照任务编号顺序执行：1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11

**关键依赖：**
- 任务 3 必须在任务 4、5 之前完成（认证是基础）
- 任务 6 必须在任务 7、8、9 之前完成（前端基础）
- 任务 5 必须在任务 9 之前完成（WebSocket 后端）

**预计时间：** 10-15 天

