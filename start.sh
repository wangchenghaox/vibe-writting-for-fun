#!/bin/bash

cd "$(dirname "$0")"

# 加载环境变量
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

echo "启动后端..."
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port ${SERVER_PORT:-8000} --reload &
BACKEND_PID=$!

echo "等待后端启动..."
sleep 3

echo "启动前端..."
cd ../frontend

# 生成前端 .env
cat > .env << EOF
VITE_API_URL=http://${SERVER_HOST:-localhost}:${SERVER_PORT:-8000}
VITE_WS_URL=ws://${SERVER_HOST:-localhost}:${SERVER_PORT:-8000}
EOF

npm install > /dev/null 2>&1
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✓ 服务已启动"
echo "前端: http://localhost:5173"
echo "后端: http://${SERVER_HOST:-localhost}:${SERVER_PORT:-8000}"
echo ""
echo "按 Ctrl+C 停止服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
