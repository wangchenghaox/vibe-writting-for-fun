# AI 小说生成器

基于 AI Agent 的智能小说创作平台，支持 CLI 和 Web 两种使用方式。

## 功能特性

- AI 对话式创作（支持工具调用）
- 大纲/章节管理
- 章节审查机制
- 会话持久化
- 多用户 Web 平台（JWT 认证）
- 实时创作反馈（WebSocket）

## 技术栈

**后端：**
- FastAPI - Web 框架
- AI Agent Core - 对话引擎
- 多 LLM 支持（Kimi/Claude/OpenAI）
- SQLAlchemy + SQLite
- WebSocket 实时通信

**前端：**
- Vue.js 3 + Vite
- Element Plus
- Pinia 状态管理

## 项目结构

```
vibe-writting-for-fun/
├── backend/          # 统一后端
│   ├── app/
│   │   ├── agent/    # Agent 核心
│   │   ├── llm/      # LLM 提供者
│   │   ├── tools/    # 工具集
│   │   ├── api/      # Web API
│   │   └── models/   # 数据模型
│   ├── config/       # 配置文件
│   ├── data/         # 数据存储
│   └── tests/        # 单元测试
├── frontend/         # Web 前端
└── start.sh          # 一键启动
```

## 快速开始

### Web 应用

**一键启动：**
```bash
./start.sh
```

访问：
- 前端：http://localhost:5173
- 后端：http://localhost:8000
- API 文档：http://localhost:8000/docs

### 环境配置

创建 `backend/.env` 文件：
```bash
KIMI_API_KEY=your_api_key_here
JWT_SECRET_KEY=your_secret_key
```

### 运行测试

```bash
cd backend
uv run pytest tests/ -v
```

## License

MIT


