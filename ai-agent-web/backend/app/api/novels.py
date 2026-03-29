from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from pathlib import Path
import json
from app.db.base import get_db
from app.models.novel import Novel
from app.models.user import User
from app.core.deps import get_current_user

router = APIRouter(prefix="/api/novels", tags=["novels"])

class CreateNovelRequest(BaseModel):
    novel_id: str
    title: str
    description: str = ""

@router.get("")
def list_novels(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    novels = db.query(Novel).filter(Novel.user_id == user.id).all()
    result = []
    for novel in novels:
        novel_path = Path(f"../../ai-agent-core/data/novels/{novel.novel_id}")
        chapters_dir = novel_path / "chapters"
        chapter_count = len(list(chapters_dir.glob("*.json"))) if chapters_dir.exists() else 0

        total_words = 0
        if chapters_dir.exists():
            for chapter_file in chapters_dir.glob("*.json"):
                with open(chapter_file, 'r', encoding='utf-8') as f:
                    chapter = json.load(f)
                    total_words += len(chapter.get('content', ''))

        result.append({
            "id": novel.id,
            "novel_id": novel.novel_id,
            "title": novel.title,
            "description": novel.description,
            "created_at": novel.created_at,
            "chapter_count": chapter_count,
            "total_words": total_words
        })
    return result

@router.post("")
def create_novel(req: CreateNovelRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.query(Novel).filter(Novel.novel_id == req.novel_id).first():
        raise HTTPException(status_code=400, detail="Novel ID already exists")

    novel = Novel(user_id=user.id, novel_id=req.novel_id, title=req.title, description=req.description)
    db.add(novel)
    db.commit()
    db.refresh(novel)
    return {"id": novel.id, "novel_id": novel.novel_id, "title": novel.title, "description": novel.description, "created_at": novel.created_at}

@router.get("/{novel_id}")
def get_novel(novel_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    novel = db.query(Novel).filter(Novel.id == novel_id, Novel.user_id == user.id).first()
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    novel_path = Path(f"../../ai-agent-core/data/novels/{novel.novel_id}")
    chapters_dir = novel_path / "chapters"
    chapters = []
    if chapters_dir.exists():
        for chapter_file in sorted(chapters_dir.glob("*.json")):
            with open(chapter_file, 'r', encoding='utf-8') as f:
                chapter = json.load(f)
                chapters.append({"id": chapter['id'], "title": chapter['title'], "content": chapter['content'], "word_count": len(chapter['content'])})

    return {"id": novel.id, "novel_id": novel.novel_id, "title": novel.title, "description": novel.description, "chapters": chapters, "created_at": novel.created_at}
