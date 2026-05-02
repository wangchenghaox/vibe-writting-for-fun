import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

# 查找根目录的 .env 文件
ROOT_DIR = Path(__file__).parent.parent.parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
ENV_FILE = ROOT_DIR / ".env"

class Settings(BaseSettings):
    model_config = ConfigDict(extra='ignore', env_file=str(ENV_FILE))

    DATABASE_URL: str = "sqlite:///./data/agent_memory.db"
    MEMORY_ENABLED: bool = False
    KIMI_API_KEY: str = ""
    DATA_DIR: Path = BACKEND_DIR / "data"
    WORKDIR: Optional[Path] = None

settings = Settings()
