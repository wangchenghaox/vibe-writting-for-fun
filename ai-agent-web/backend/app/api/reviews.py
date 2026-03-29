from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.novel import ReviewHistory
from app.models.user import User
from app.core.deps import get_current_user

router = APIRouter(prefix="/api/chapters", tags=["reviews"])

@router.get("/{chapter_id}/reviews")
def get_reviews(chapter_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    reviews = db.query(ReviewHistory).filter(ReviewHistory.chapter_id == chapter_id).all()
    return [{"id": r.id, "review_content": r.review_content, "status": r.status, "created_at": r.created_at} for r in reviews]
