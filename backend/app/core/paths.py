from pathlib import Path

from app.core.config import settings


def data_path(*parts: str) -> Path:
    return Path(settings.DATA_DIR).joinpath(*parts)


def novels_path() -> Path:
    return data_path("novels")


def novel_path(novel_id: str) -> Path:
    return novels_path() / novel_id
