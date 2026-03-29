import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

# 查找根目录的 .env 文件
ROOT_DIR = Path(__file__).parent.parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"

class Settings(BaseSettings):
    model_config = ConfigDict(extra='ignore', env_file=str(ENV_FILE))

    DATABASE_URL: str = "sqlite:///./data/web.db"
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 7
    KIMI_API_KEY: str = ""

    @property
    def CORS_ORIGINS(self):
        return ["*"]

settings = Settings()
