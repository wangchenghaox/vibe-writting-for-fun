import json
import re
import shutil
from pathlib import Path
from typing import Optional

from app.capability.tool_registry import tool
from app.core.config import settings
from app.core.skill_paths import (
    configured_skill_roots,
    display_skill_path,
    is_skill_alias_path,
    skill_alias_candidates,
)


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


def _skills_root() -> Path:
    return BACKEND_ROOT / "skills"


def _workdir_root() -> Optional[Path]:
    workdir = getattr(settings, "WORKDIR", None)
    if not workdir:
        return None
    return Path(workdir).expanduser().resolve(strict=False)


def _workspace_roots() -> list[Path]:
    workdir = _workdir_root()
    if workdir is not None:
        return [workdir]

    return [(Path(settings.DATA_DIR) / "novels").resolve()]


def _read_roots(include_skills: bool = True) -> list[Path]:
    roots = _workspace_roots()
    if include_skills:
        roots.extend(configured_skill_roots())
    return roots


def _path_candidates(path: str, include_skills: bool = False) -> list[Path]:
    raw = Path(path)
    workdir = _workdir_root()
    if include_skills and is_skill_alias_path(raw):
        return skill_alias_candidates(raw)
    if workdir is not None:
        if raw.is_absolute():
            return [raw]
        return [workdir / raw]

    if raw.is_absolute():
        return [raw]

    candidates = []
    if raw.parts and raw.parts[0] == "novels":
        candidates.append(Path(settings.DATA_DIR) / raw)
    if include_skills and raw.parts and raw.parts[0] == "skills":
        candidates.extend(skill_alias_candidates(raw))

    candidates.extend([REPO_ROOT / raw, BACKEND_ROOT / raw])
    return candidates


def _resolve_safe_path(
    path: str,
    allow_skill_alias: bool = False,
    include_skills: bool = False,
    prefer_existing: bool = False,
) -> tuple[Optional[Path], Optional[str]]:
    if not (allow_skill_alias or include_skills) and is_skill_alias_path(path):
        return None, "操作被拒绝: skill 目录为只读，请改用工作区内的其他路径"

    roots = _read_roots(include_skills=include_skills or allow_skill_alias)
    allowed = []
    for candidate in _path_candidates(path, include_skills=include_skills or allow_skill_alias):
        resolved = candidate.resolve(strict=False)
        if any(resolved.is_relative_to(root.resolve(strict=False)) for root in roots):
            allowed.append(resolved)
            if not prefer_existing or resolved.exists():
                return resolved, None

    if allowed:
        return allowed[0], None

    roots_display = ", ".join(str(root) for root in roots)
    return None, f"操作被拒绝: 路径必须位于允许目录内 ({roots_display})"


def _resolve_read_bases(path: str) -> tuple[Optional[list[Path]], Optional[str]]:
    if not path:
        return _workspace_roots(), None

    raw = Path(path)
    if is_skill_alias_path(raw) and len(raw.parts) == 1:
        return configured_skill_roots(), None

    base, error = _resolve_safe_path(
        path,
        allow_skill_alias=True,
        include_skills=True,
        prefer_existing=True,
    )
    if error:
        return None, error
    return [base], None


def _display_path(path: Path) -> str:
    skill_path = display_skill_path(path)
    if skill_path is not None:
        return skill_path

    workdir = _workdir_root()
    if workdir is not None:
        try:
            relative = path.resolve(strict=False).relative_to(workdir)
        except ValueError:
            return str(path)
        return "." if str(relative) == "." else str(relative)

    for label, root in (
        ("novels", (Path(settings.DATA_DIR) / "novels").resolve()),
    ):
        try:
            return str(Path(label) / path.resolve(strict=False).relative_to(root))
        except ValueError:
            continue
    return str(path)


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False)


@tool(name="read_file", description="Read a text file from allowed novel or skill directories")
def read_file(path: str, max_chars: int = 20000, offset: int = 0) -> str:
    resolved, error = _resolve_safe_path(
        path,
        allow_skill_alias=True,
        include_skills=True,
        prefer_existing=True,
    )
    if error:
        return error
    if not resolved.exists():
        return f"文件不存在: {_display_path(resolved)}"
    if not resolved.is_file():
        return f"不是文件: {_display_path(resolved)}"
    if offset < 0:
        return "offset 必须大于等于 0"
    if max_chars < 0:
        return "max_chars 必须大于等于 0"

    content = resolved.read_text(encoding="utf-8")
    return content[offset:offset + max_chars]


@tool(
    name="write_file",
    description=(
        "Write a text file within the current workspace. Skill directories are read-only. Use this only when the exact full file "
        "content is already available in the conversation or has just been generated. Requires both path and "
        "complete content; 不要在没有完整内容时调用，不要用 write_file 仅声明保存意图。"
    ),
    parameter_descriptions={
        "path": "Target file path under the current workspace.",
        "content": "完整文件正文。必填，不能省略；必须传入要写入文件的完整 Markdown 文本，不要只传路径，也不要用空字符串占位。",
        "overwrite": "Whether to overwrite an existing file. Defaults to true.",
    },
)
def write_file(path: str, content: str, overwrite: bool = True) -> str:
    resolved, error = _resolve_safe_path(path)
    if error:
        return error
    if resolved.exists() and not overwrite:
        return f"文件已存在: {_display_path(resolved)}"

    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return f"已写入文件: {_display_path(resolved)}"


@tool(name="make_directory", description="Create a directory within the current workspace. Skill directories are read-only.")
def make_directory(path: str) -> str:
    resolved, error = _resolve_safe_path(path)
    if error:
        return error
    if resolved.exists() and not resolved.is_dir():
        return f"路径已存在且不是目录: {_display_path(resolved)}"

    resolved.mkdir(parents=True, exist_ok=True)
    return f"已创建目录: {_display_path(resolved)}"


@tool(name="copy_file", description="Copy a file into the current workspace. Source may be workspace or read-only skill files.")
def copy_file(source_path: str, target_path: str, overwrite: bool = False) -> str:
    source, source_error = _resolve_safe_path(
        source_path,
        allow_skill_alias=True,
        include_skills=True,
        prefer_existing=True,
    )
    if source_error:
        return source_error
    target, target_error = _resolve_safe_path(target_path)
    if target_error:
        return target_error
    if not source.exists():
        return f"文件不存在: {_display_path(source)}"
    if not source.is_file():
        return f"不是文件: {_display_path(source)}"
    if target.exists() and not target.is_file():
        return f"目标路径不是文件: {_display_path(target)}"
    if target.exists() and not overwrite:
        return f"目标文件已存在: {_display_path(target)}"

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return f"已复制文件: {_display_path(source)} -> {_display_path(target)}"


@tool(name="edit_file", description="Replace text in a file within the current workspace. Skill directories are read-only.")
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


@tool(name="delete_file", description="Delete a file from the current workspace. Skill directories are read-only.")
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


@tool(name="rename_file", description="Rename or move a file within the current workspace. Skill directories are read-only.")
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
    bases, error = _resolve_read_bases(path)
    if error:
        return error

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

    bases, error = _resolve_read_bases(path)
    if error:
        return error

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
    bases, error = _resolve_read_bases(path)
    if error:
        return error

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
