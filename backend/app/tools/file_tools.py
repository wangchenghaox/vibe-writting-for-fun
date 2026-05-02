import json
import re
from pathlib import Path
from typing import Optional

from app.capability.tool_registry import tool
from app.core.config import settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


def _skills_root() -> Path:
    return BACKEND_ROOT / "skills"


def _workdir_root() -> Optional[Path]:
    workdir = getattr(settings, "WORKDIR", None)
    if not workdir:
        return None
    return Path(workdir).expanduser().resolve(strict=False)


def _allowed_roots() -> list[Path]:
    workdir = _workdir_root()
    if workdir is not None:
        return [workdir]

    return [
        (Path(settings.DATA_DIR) / "novels").resolve(),
        _skills_root().resolve(),
    ]


def _path_candidates(path: str) -> list[Path]:
    raw = Path(path)
    workdir = _workdir_root()
    if workdir is not None:
        if raw.is_absolute():
            return [raw]
        return [workdir / raw]

    if raw.is_absolute():
        return [raw]

    candidates = []
    if raw.parts and raw.parts[0] == "novels":
        candidates.append(Path(settings.DATA_DIR) / raw)
    if raw.parts and raw.parts[0] == "skills":
        candidates.append(BACKEND_ROOT / raw)

    candidates.extend([REPO_ROOT / raw, BACKEND_ROOT / raw])
    return candidates


def _resolve_safe_path(path: str) -> tuple[Optional[Path], Optional[str]]:
    for candidate in _path_candidates(path):
        resolved = candidate.resolve(strict=False)
        if any(resolved.is_relative_to(root) for root in _allowed_roots()):
            return resolved, None

    roots = ", ".join(str(root) for root in _allowed_roots())
    return None, f"操作被拒绝: 路径必须位于允许目录内 ({roots})"


def _display_path(path: Path) -> str:
    workdir = _workdir_root()
    if workdir is not None:
        try:
            relative = path.resolve(strict=False).relative_to(workdir)
        except ValueError:
            return str(path)
        return "." if str(relative) == "." else str(relative)

    for label, root in (
        ("novels", (Path(settings.DATA_DIR) / "novels").resolve()),
        ("skills", _skills_root().resolve()),
    ):
        try:
            return str(Path(label) / path.resolve(strict=False).relative_to(root))
        except ValueError:
            continue
    return str(path)


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False)


@tool(name="read_file", description="Read a text file from allowed novel or skill directories")
def read_file(path: str, max_chars: int = 20000) -> str:
    resolved, error = _resolve_safe_path(path)
    if error:
        return error
    if not resolved.exists():
        return f"文件不存在: {_display_path(resolved)}"
    if not resolved.is_file():
        return f"不是文件: {_display_path(resolved)}"

    content = resolved.read_text(encoding="utf-8")
    return content[:max_chars]


@tool(name="write_file", description="Write a text file within allowed novel or skill directories")
def write_file(path: str, content: str, overwrite: bool = True) -> str:
    resolved, error = _resolve_safe_path(path)
    if error:
        return error
    if resolved.exists() and not overwrite:
        return f"文件已存在: {_display_path(resolved)}"

    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return f"已写入文件: {_display_path(resolved)}"


@tool(name="edit_file", description="Replace text in a file within allowed novel or skill directories")
def edit_file(path: str, old_text: str, new_text: str, replace_all: bool = False) -> str:
    resolved, error = _resolve_safe_path(path)
    if error:
        return error
    if not resolved.exists():
        return f"文件不存在: {_display_path(resolved)}"
    if not resolved.is_file():
        return f"不是文件: {_display_path(resolved)}"

    content = resolved.read_text(encoding="utf-8")
    if old_text not in content:
        return f"未找到要替换的内容: {_display_path(resolved)}"

    count = -1 if replace_all else 1
    updated = content.replace(old_text, new_text, count)
    resolved.write_text(updated, encoding="utf-8")
    return f"已修改文件: {_display_path(resolved)}"


@tool(name="delete_file", description="Delete a file from allowed novel or skill directories")
def delete_file(path: str) -> str:
    resolved, error = _resolve_safe_path(path)
    if error:
        return error
    if not resolved.exists():
        return f"文件不存在: {_display_path(resolved)}"
    if not resolved.is_file():
        return f"拒绝删除非文件路径: {_display_path(resolved)}"

    resolved.unlink()
    return f"已删除文件: {_display_path(resolved)}"


@tool(name="rename_file", description="Rename or move a file within allowed novel or skill directories")
def rename_file(source_path: str, target_path: str, overwrite: bool = False) -> str:
    source, source_error = _resolve_safe_path(source_path)
    if source_error:
        return source_error
    target, target_error = _resolve_safe_path(target_path)
    if target_error:
        return target_error
    if not source.exists():
        return f"文件不存在: {_display_path(source)}"
    if not source.is_file():
        return f"不是文件: {_display_path(source)}"
    if target.exists() and not overwrite:
        return f"目标文件已存在: {_display_path(target)}"

    target.parent.mkdir(parents=True, exist_ok=True)
    source.rename(target)
    return f"已重命名: {_display_path(source)} -> {_display_path(target)}"


@tool(name="list_files", description="List files under allowed novel or skill directories")
def list_files(path: str = "", pattern: str = "*", max_results: int = 100) -> str:
    if path:
        base, error = _resolve_safe_path(path)
        if error:
            return error
        bases = [base]
    else:
        bases = _allowed_roots()

    files = []
    for base in bases:
        if not base.exists():
            continue
        if base.is_file():
            matches = [base] if base.match(pattern) else []
        else:
            matches = [p for p in base.rglob(pattern) if p.is_file()]
        files.extend(_display_path(path) for path in matches)
        if len(files) >= max_results:
            break

    return _json(sorted(files)[:max_results])


@tool(name="grep_files", description="Search file contents with a regex under allowed directories")
def grep_files(pattern: str, path: str = "", file_glob: str = "*", max_results: int = 50) -> str:
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"无效正则: {e}"

    if path:
        base, error = _resolve_safe_path(path)
        if error:
            return error
        bases = [base]
    else:
        bases = _allowed_roots()

    results = []
    for base in bases:
        if not base.exists():
            continue
        files = [base] if base.is_file() else [p for p in base.rglob(file_glob) if p.is_file()]
        for file_path in files:
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(lines, 1):
                if regex.search(line):
                    results.append({
                        "path": _display_path(file_path),
                        "line_number": line_number,
                        "line": line,
                    })
                    if len(results) >= max_results:
                        return _json(results)

    return _json(results)


@tool(name="search_files", description="Search file names under allowed novel or skill directories")
def search_files(query: str, path: str = "", max_results: int = 50) -> str:
    needle = query.lower()
    if path:
        base, error = _resolve_safe_path(path)
        if error:
            return error
        bases = [base]
    else:
        bases = _allowed_roots()

    results = []
    for base in bases:
        if not base.exists():
            continue
        files = [base] if base.is_file() else [p for p in base.rglob("*") if p.is_file()]
        for file_path in files:
            display = _display_path(file_path)
            if needle in display.lower():
                results.append(display)
                if len(results) >= max_results:
                    return _json(sorted(results))

    return _json(sorted(results))
