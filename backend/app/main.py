from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.config import settings
from app.db.base import engine, Base
from app.models import user, novel
from app.api import auth, novels, websocket, reviews
from app.core.exceptions import http_exception_handler, validation_exception_handler
import os

os.makedirs("data", exist_ok=True)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Novel Generator API")

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(novels.router)
app.include_router(websocket.router)
app.include_router(reviews.router)

@app.get("/")
def root():
    return {"message": "AI Novel Generator API"}
