#!/bin/bash

cd "$(dirname "$0")"

echo "启动后端..."
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

echo "等待后端启动..."
sleep 3

echo "启动前端..."
cd ../frontend
npm install > /dev/null 2>&1
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✓ 服务已启动"
echo "前端: http://localhost:5173"
echo "后端: http://localhost:8000"
echo ""
echo "按 Ctrl+C 停止服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
