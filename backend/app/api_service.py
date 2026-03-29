from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import sys

# 添加src到路径
sys.path.insert(0, os.path.dirname(__file__))

from agent.core import AgentCore
from agent.session import Session
from llm.config import create_provider

app = FastAPI(title="AI Agent Service")

class ChatRequest(BaseModel):
    novel_id: str
    message: str

class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        os.environ['CURRENT_NOVEL_ID'] = req.novel_id
        provider = create_provider()
        session = Session(f"web_{req.novel_id}")
        agent = AgentCore(provider, session)

        # agent.chat是同步的，需要在线程中运行
        import asyncio
        loop = asyncio.get_event_loop()
        response_text = await loop.run_in_executor(None, agent.chat, req.message)
        return ChatResponse(response=response_text or "处理完成")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}
