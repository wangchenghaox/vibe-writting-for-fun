from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime
from app.db.base import Base

class Novel(Base):
    __tablename__ = "novels"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    novel_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, unique=True, index=True)
    messages_json = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ReviewHistory(Base):
    __tablename__ = "review_history"

    id = Column(Integer, primary_key=True, index=True)
    chapter_id = Column(String(100), nullable=False, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    review_content = Column(Text)
    status = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
