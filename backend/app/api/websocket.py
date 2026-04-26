from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from jose import jwt, JWTError
import logging
import asyncio
from contextlib import suppress
from concurrent.futures import ThreadPoolExecutor

from app.db.base import get_db
from app.models.user import User
from app.models.novel import Novel
from app.core.config import settings
from app.services.web_agent import WebAgentService

router = APIRouter()
logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=4)

@router.websocket("/ws/chat/{novel_id}")
async def websocket_chat(websocket: WebSocket, novel_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    await websocket.accept()

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008)
            return
    except JWTError:
        await websocket.close(code=1008)
        return

    user = db.query(User).filter(User.id == int(user_id)).first()
    novel = db.query(Novel).filter(Novel.id == novel_id, Novel.user_id == int(user_id)).first()
    if not user or not novel:
        await websocket.close(code=1008)
        return

    loop = asyncio.get_running_loop()
    event_queue = asyncio.Queue()
    send_lock = asyncio.Lock()

    async def send_payload(payload):
        async with send_lock:
            await websocket.send_json(payload)

    async def send_events():
        while True:
            event = await event_queue.get()
            try:
                await send_payload({
                    "type": event.type.value,
                    "data": event.data
                })
            finally:
                event_queue.task_done()

    def enqueue_event(event):
        loop.call_soon_threadsafe(event_queue.put_nowait, event)

    agent_service = WebAgentService(str(novel_id), on_event=enqueue_event)
    event_task = asyncio.create_task(send_events())

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "message":
                user_msg = data['content']
                logger.info(f"收到消息: {user_msg}")

                try:
                    ai_response = await loop.run_in_executor(executor, agent_service.chat, user_msg)
                    logger.info(f"AI响应: {ai_response[:100]}...")

                    await asyncio.sleep(0)
                    await event_queue.join()
                    await send_payload({
                        "type": "message_sent",
                        "content": ai_response
                    })
                except Exception as e:
                    logger.error(f"AI处理错误: {e}", exc_info=True)
                    await send_payload({
                        "type": "message_sent",
                        "content": f"处理失败: {str(e)}"
                    })
    except WebSocketDisconnect:
        logger.info("WebSocket断开连接")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
    finally:
        agent_service.close()
        event_task.cancel()
        with suppress(asyncio.CancelledError):
            await event_task
