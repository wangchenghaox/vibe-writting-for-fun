from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from jose import jwt, JWTError
import sys
import os

from app.db.base import get_db
from app.models.user import User
from app.models.novel import Novel
from app.core.config import settings

router = APIRouter()

@router.websocket("/ws/chat/{novel_id}")
async def websocket_chat(websocket: WebSocket, novel_id: str, token: str = Query(...), db: Session = Depends(get_db)):
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

    user = db.query(User).filter(User.id == user_id).first()
    novel = db.query(Novel).filter(Novel.novel_id == novel_id, Novel.user_id == user_id).first()
    if not user or not novel:
        await websocket.close(code=1008)
        return

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "message":
                await websocket.send_json({"type": "message_sent", "content": f"收到: {data['content']}"})
    except WebSocketDisconnect:
        pass
