# AI 小说生成器 Web 应用

基于 FastAPI + Vue.js 的多用户 AI 小说创作平台。

## 功能特性

- 用户注册/登录（JWT 认证）
- 小说管理（创建、查看、统计）
- 实时对话创作（WebSocket）
- 章节审查历史
- 多用户数据隔离

## 技术栈

**后端：**
- FastAPI - Web 框架
- SQLAlchemy - ORM
- SQLite - 数据库
- JWT - 身份认证
- WebSocket - 实时通信

**前端：**
- Vue.js 3 - 前端框架
- Vite - 构建工具
- Element Plus - UI 组件库
- Pinia - 状态管理
- Axios - HTTP 客户端

## 项目结构

```
ai-agent-web/
├── backend/          # FastAPI 后端
│   ├── app/
│   │   ├── api/      # API 路由
│   │   ├── core/     # 核心配置
│   │   ├── db/       # 数据库
│   │   └── models/   # 数据模型
│   └── pyproject.toml
├── frontend/         # Vue.js 前端
│   ├── src/
│   │   ├── api/      # API 调用
│   │   ├── views/    # 页面组件
│   │   ├── stores/   # 状态管理
│   │   └── router/   # 路由配置
│   └── package.json
└── start.sh          # 一键启动脚本
```

## 快速开始

### 本地开发

**一键启动：**
```bash
cd ai-agent-web
./start.sh
```

访问：
- 前端：http://localhost:5173
- 后端：http://localhost:8000

**手动启动：**

后端：
```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

前端：
```bash
cd frontend
npm install
npm run dev
```

### 部署到服务器

1. **配置前端环境变量：**
```bash
cd frontend
cp .env.example .env
# 编辑 .env，设置服务器地址
```

2. **修改 `.env` 文件：**
```
VITE_API_URL=http://your-server-ip:8000
VITE_WS_URL=ws://your-server-ip:8000
```

3. **开放安全组端口：**
   - 8000（后端 API）
   - 5173（前端）

4. **启动服务：**
```bash
./start.sh
```

## API 文档

启动后端后访问：http://localhost:8000/docs

## 主要功能

### 用户认证
- POST `/api/auth/register` - 注册
- POST `/api/auth/login` - 登录
- GET `/api/auth/me` - 获取当前用户

### 小说管理
- GET `/api/novels` - 获取小说列表
- POST `/api/novels` - 创建小说
- GET `/api/novels/{id}` - 获取小说详情

### 实时对话
- WebSocket `/ws/chat/{novel_id}` - 对话连接

### 审查历史
- GET `/api/chapters/{chapter_id}/reviews` - 获取审查记录

## 开发说明

- 后端使用 `uv` 管理依赖
- 前端使用 `npm` 管理依赖
- 数据库文件位于 `backend/data/web.db`
- CORS 已配置允许跨域访问

## License

MIT


