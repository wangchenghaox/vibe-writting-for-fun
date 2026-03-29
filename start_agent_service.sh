#!/bin/bash
cd "$(dirname "$0")"
cd ai-agent-core/src
uv run uvicorn api_service:app --host 0.0.0.0 --port 8001
