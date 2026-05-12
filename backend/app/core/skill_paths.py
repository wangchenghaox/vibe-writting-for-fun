import json
import os
from pathlib import Path
from typing import Iterable

from .config import ROOT_DIR, settings


def _split_skill_dirs(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Path):
        return [str(value)]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]

    text = str(value).strip()
    if not text:
        return []

    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item) for item in parsed]

    separator = "," if "," in text else os.pathsep
    return [part.strip() for part in text.split(separator) if part.strip()]


def _resolve_config_path(path: str | Path) -> Path:
    raw = Path(path).expanduser()
    if raw.is_absolute():
        return raw.resolve(strict=False)
    return (ROOT_DIR / raw).resolve(strict=False)


def configured_skill_roots(value=None) -> list[Path]:
    """Return configured skill directories, de-duplicated in precedence order."""
    raw_value = getattr(settings, "SKILL_DIRS", None) if value is None else value
    roots = []
    seen = set()
    for item in _split_skill_dirs(raw_value):
        root = _resolve_config_path(item)
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        roots.append(root)
    return roots


def is_skill_alias_path(path: str | Path) -> bool:
    raw = Path(path)
    return not raw.is_absolute() and bool(raw.parts) and raw.parts[0] == "skills"


def skill_alias_candidates(path: str | Path, roots: Iterable[Path] | None = None) -> list[Path]:
    raw = Path(path)
    if not is_skill_alias_path(raw):
        return []

    skill_roots = list(configured_skill_roots() if roots is None else roots)
    relative_parts = raw.parts[1:]
    if not relative_parts:
        return skill_roots

    relative = Path(*relative_parts)
    return [root / relative for root in skill_roots]


def display_skill_path(path: Path, roots: Iterable[Path] | None = None) -> str | None:
    resolved = path.resolve(strict=False)
    for root in configured_skill_roots() if roots is None else roots:
        try:
            relative = resolved.relative_to(root.resolve(strict=False))
        except ValueError:
            continue
        return str(Path("skills") / relative).replace("\\", "/")
    return None
