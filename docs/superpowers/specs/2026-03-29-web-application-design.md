# AI 小说生成器 Web 应用设计

## 概述

基于现有 CLI 功能，设计一个多用户协作平台的 Web 应用。用户通过简单的账号密码认证，独立管理自己的小说创作。

## 系统架构

### 整体架构

```
┌─────────────────┐
│   前端 (Vue.js)  │
│  - 小说管理界面  │
│  - 实时对话组件  │
│  - 章节编辑器    │
└────┬────────┘
         │ HTTP/WebSocket
┌────────▼────────┐
│  后端 (FastAPI)  │
│  - REST API      │
│  - WebSocket服务 │
│  - Agent Core    │
└────────┬────────┘
         │
┌────────▼────────┐
│  数据库 (SQLite) │
│  - 用户表        │
│  - 小说表        │
│  - 会话表        │
│  - 审查记录表    │
└─────────────────┘
```

### 技术栈

**前端：**
- 框架：Vue.js 3 + TypeScript
- 路由：Vue Router
- 状态管理：Pinia
- UI 组件库：Element Plus 或 Naive UI
- WebSocket：原生 WebSocket API
- 构建工具：Vite

**后端：**
- 框架：FastAPI
- ORM：SQLAlchemy
- 数据库：SQLite（开发）/ PostgreSQL（生产）
- 认证：JWT (python-jose)
- 密码哈希：bcrypt
- WebSocket：FastAPI WebSocket

**复用现有代码：**
- AgentCore：对话引擎
- LLM Provider：Kimi/Anthropic 适配器
- Tool Registry：工具系统
- Event Bus：事件系统

## 数据库设计

### 表结构

**users 表：**
```sql
- id: INTEGER PRIMARY KEY
- username: VARCHAR(50) UNIQUE NOT NULL
- password_hash: VARCHAR(255) NOT NULL
- created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

**novels 表：**
```sql
- id: INTEGER PRIMARY KEY
- user_id: INTEGER FOREIGN KEY
- novel_id: VARCHAR(100) UNIQUE NOT NULL
- title: VARCHAR(200) NOT NULL
- description: TEXT
- created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

**sessions 表：**
```sql
- id: INTEGER PRIMARY KEY
- novel_id: INTEGER FOREIGN KEY
- messages_json: TEXT (JSON 格式存储对话历史)
- updated_at: TIMESTAMP
```

**review_history 表：**
```sql
- id: INTEGER PRIMARY KEY
- chapter_id: VARCHAR(100) NOT NULL
- novel_id: INTEGER FOREIGN KEY
- review_content: TEXT
- status: VARCHAR(20) (passed/needs_revision)
- created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

### 索引设计
- users.username (唯一索引)
- novels.user_id (普通索引)
- novels.novel_id (唯一索引)
- sessions.novel_id (唯一索引)
- review_history.chapter_id (普通索引)

## 核心功能流程

### 1. 用户认证流程

```
用户输入账号密码 → 后端验证 → 生成 JWT Token → 前端存储 Token → 后续请求携带 Token
```

**实现细节：**
- 使用 JWT 进行无状态认证
- Token 有效期：7 天
- Token 存储：localStorage
- 密码哈希：bcrypt (cost factor: 12)
- 请求头：`Authorization: Bearer <token>`

### 2. 对话流程（WebSocket）

```
1. 用户加载小说 → 建立 WebSocket 连接 (ws://host/ws/chat/{novel_id}?token=xxx)
2. 前端发送消息 → 后端接收
3. AgentCore 处理 → 发送事件：
   - thinking: 思考内容
   - tool_called: 工具调用
   - tool_result: 工具结果
   - message_sent: 最终回复
4. 前端实时显示各个事件
5. 自动保存会话到数据库
```

**会话管理：**
- 每个小说一个持久会话
- 会话自动保存（每条消息后）
- 页面刷新自动恢复会话历史
- WebSocket 断开自动重连（最多 3 次，间隔 1s/2s/5s）

### 3. 章节审查流程

```
1. 章节生成完成 → 自动触发 review_chapter 工具
2. 审查结果保存到 review_history 表
3. 如有修改建议 → Agent 自动修改 → 再次审查
4. 审查通过 → 继续下一章
5. 用户可在界面查看审查历史
```

**审查记录展示：**
- 左侧边栏显示审查历史列表
- 点击查看详细的审查内容和修改建议
- 标记审查状态（通过/需修改）
- 支持按章节筛选

### 4. 会话恢复流程

```
1. 用户打开小说详情页
2. 后端加载该小说的会话记录（从 sessions 表）
3. 前端显示历史对话
4. 用户继续对话 → 追加到现有会话
```

## API 设计

### 认证相关

**POST /api/auth/register**
- 请求：`{username, password}`
- 响应：`{message: "注册成功"}`

**POST /api/auth/login**
- 请求：`{username, password}`
- 响应：`{token: "jwt_token", user: {id, username}}`

**GET /api/auth/me**
- 请求头：`Authorization: Bearer <token>`
- 响应：`{id, username, created_at}`

### 小说管理

**GET /api/novels**
- 响应：`[{id, novel_id, title, description, created_at, chapter_count, total_words}]`

**POST /api/novels**
- 请求：`{novel_id, title, description}`
- 响应：`{id, novel_id, title, description, created_at}`

**GET /api/novels/{id}**
- 响应：`{id, novel_id, title, description, chapters: [...], created_at}`

**GET /api/novels/{id}/chapters**
- 响应：`[{id, title, content, word_count}]`

**GET /api/novels/{id}/outline**
- 响应：`{outlines: [{id, content}]}`

**GET /api/novels/{id}/stats**
- 响应：`{total_chapters, total_words, avg_words_per_chapter}`

### 会话管理

**GET /api/novels/{id}/session**
- 响应：`{messages: [{role, content, timestamp}]}`

**WS /ws/chat/{novel_id}?token=xxx**
- 客户端发送：`{type: "message", content: "继续写第三章"}`
- 服务端推送：
  - `{type: "thinking", content: "..."}`
  - `{type: "tool_called", name: "save_chapter", args: {...}}`
  - `{type: "tool_result", name: "save_chapter", result: "..."}`
  - `{type: "message_sent", content: "..."}`

### 审查记录

**GET /api/chapters/{chapter_id}/reviews**
- 响应：`[{id, review_content, status, created_at}]`

## 前端设计

### 页面路由

```
/login              - 登录页
/register           - 注册页
/novels             - 小说列表（首页）
/novels/:id         - 小说详情（章节列表、统计、大纲）
/novels/:id/chat    - 对话界面（核心功能）
```

### 页面结构

**1. 登录/注册页 (/login, /register)**
- 简洁的表单设计
- 用户名、密码输入框
- 登录/注册按钮
- 错误提示

**2. 小说列表页 (/novels)**
- 顶部导航栏：用户信息、退出按钮
- "创建新小说"按钮
- 小说卡片网格布局：
  - 标题、描述
  - 章节数、总字数
  - 创建时间
  - 点击进入详情页

**3. 小说详情页 (/novels/:id)**
- 左侧（70%）：
  - 章节列表（可折叠）
  - 点击展开查看章节内容
- 右侧（30%）：
  - 创作统计卡片
  - 大纲显示区域
  - "开始对话"按钮

**4. 对话界面 (/novels/:id/chat)**

布局：三栏式

- **左侧边栏（20%）：**
  - 当前小说信息
  - 快捷命令按钮（/list, /chapters, /current）
  - 审查历史列表（可点击查看详情）

- **中间主区域（60%）：**
  - 对话历史区域（虚拟滚动）
  - 消息类型：
    - 用户消息（右对齐，蓝色）
    - AI 回复（左对齐，灰色）
    - 思考过程（浅色背景，斜体）
    - 工具调用（黄色标签）
    - 工具结果（绿色标签）
  - 底部输入框 + 发送按钮

- **右侧边栏（20%，可折叠）：**
  - 章节快速预览
  - 创作进度条

## 错误处理和优化

### 错误处理

**WebSocket 连接：**
- 连接断开自动重连（最多 3 次，间隔 1s/2s/5s）
- 重连时恢复会话状态
- 超时提示用户（30秒无响应）
- 连接失败显示友好错误信息

**API 请求：**
- 统一错误响应格式：`{error: {code, message}}`
- 401 未授权 → 自动跳转登录页
- 403 禁止访问 → 提示权限不足
- 404 资源不存在 → 友好提示
- 500 服务器错误 → 提示稍后重试
- 网络错误 → 显示离线提示

**数据一致性：**
- 会话自动保存（每条消息后）
- 章节生成失败时回滚
- 审查记录独立存储，不影响主流程
- 乐观更新 + 失败回滚

### 性能优化

**前端：**
- 对话历史虚拟滚动（处理长对话，每次渲染 50 条）
- 章节内容懒加载（点击时加载）
- WebSocket 消息节流（100ms）
- 路由懒加载
- 图片/静态资源 CDN

**后端：**
- 数据库连接池（最大 10 个连接）
- 会话数据 JSON 压缩存储
- API 响应缓存（小说列表缓存 5 分钟）
- 分页查询（章节列表每页 20 条）

### 安全考虑

**认证安全：**
- 密码使用 bcrypt 哈希（cost factor: 12）
- JWT 签名验证（HS256 算法）
- Token 过期时间：7 天
- 密码最小长度：6 位

**API 安全：**
- SQL 注入防护（使用 SQLAlchemy ORM）
- XSS 防护（前端自动转义）
- CSRF 防护（JWT 无状态认证）
- CORS 配置（仅允许前端域名）
- 请求频率限制（每用户每分钟 60 次）

**数据安全：**
- 敏感数据不记录日志
- 数据库定期备份
- 用户数据隔离（通过 user_id 过滤）

## 部署方案

### 开发环境
- 前端：`npm run dev` (Vite 开发服务器，端口 5173)
- 后端：`uvicorn app:app --reload` (端口 8000)
- 数据库：SQLite (data/web.db)

### 生产环境
- 前端：构建静态文件，Nginx 托管
- 后端：Gunicorn + Uvicorn workers
- 数据库：PostgreSQL
- 反向代理：Nginx (处理 WebSocket 升级)

### 环境变量
```
DATABASE_URL=sqlite:///data/web.db
JWT_SECRET_KEY=<随机生成>
JWT_ALGORITHM=HS256
CORS_ORIGINS=http://localhost:5173
```

## 开发计划

### 阶段 1：基础架构（2-3 天）
- 数据库模型和迁移
- 用户认证 API
- JWT 中间件

### 阶段 2：小说管理（2-3 天）
- 小说 CRUD API
- 章节、大纲、统计 API
- 前端小说列表和详情页

### 阶段 3：对话功能（3-4 天）
- WebSocket 服务
- 集成 AgentCore
- 前端对话界面
- 实时事件显示

### 阶段 4：审查功能（1-2 天）
- 审查记录 API
- 前端审查历史展示

### 阶段 5：优化和测试（2-3 天）
- 错误处理完善
- 性能优化
- 安全加固
- 端到端测试

**总计：10-15 天**

