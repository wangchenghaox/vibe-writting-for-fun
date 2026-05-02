import os
import json
from datetime import datetime
from pathlib import Path
from app.core.paths import novel_path, novels_path


DOCUMENT_TYPES = {
    "outline": "outlines",
    "outlines": "outlines",
    "chapter": "chapters",
    "chapters": "chapters",
}


def _current_novel_id() -> str:
    return os.getenv("CURRENT_NOVEL_ID", "default")


def _normalize_document_type(document_type: str) -> str:
    normalized = (document_type or "").strip().lower()
    if normalized not in DOCUMENT_TYPES:
        raise ValueError("document_type must be one of: outline, chapter")
    return normalized


def _document_type_error(exc: ValueError) -> str:
    return f"Invalid document_type: {exc}"


def _document_dir(document_type: str, novel_id: str) -> Path:
    return novel_path(novel_id) / DOCUMENT_TYPES[_normalize_document_type(document_type)]


def _document_path(document_type: str, document_id: str, novel_id: str) -> Path:
    return _document_dir(document_type, novel_id) / f"{document_id}.json"


def _document_payload(
    document_type: str,
    document_id: str,
    content: str,
    title: str = "",
) -> dict:
    normalized = _normalize_document_type(document_type)
    if DOCUMENT_TYPES[normalized] == "chapters":
        return {"id": document_id, "title": title, "content": content}
    return {"id": document_id, "content": content}

def create_novel(novel_id: str, title: str, description: str = "") -> str:
    base_path = novel_path(novel_id)
    os.makedirs(base_path / "chapters", exist_ok=True)
    os.makedirs(base_path / "outlines", exist_ok=True)

    meta = {
        "id": novel_id,
        "title": title,
        "description": description,
        "created_at": datetime.now().isoformat()
    }

    with open(base_path / "meta.json", 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return f"Novel created: {base_path}. Current novel_id set to: {novel_id}"


def get_novel(novel_id: str = "") -> str:
    if novel_id:
        return get_novel_info(novel_id)
    return list_novels()


def save_novel_document(
    document_type: str,
    document_id: str,
    content: str,
    title: str = "",
    novel_id: str = None,
) -> str:
    novel_id = novel_id or _current_novel_id()
    try:
        path_dir = _document_dir(document_type, novel_id)
    except ValueError as exc:
        return _document_type_error(exc)
    os.makedirs(path_dir, exist_ok=True)
    path = path_dir / f"{document_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            _document_payload(document_type, document_id, content, title=title),
            f,
            ensure_ascii=False,
            indent=2,
        )
    return f"Document saved: {path}"


def load_novel_document(
    document_type: str,
    document_id: str,
    novel_id: str = None,
) -> str:
    novel_id = novel_id or _current_novel_id()
    try:
        path = _document_path(document_type, document_id, novel_id)
    except ValueError as exc:
        return _document_type_error(exc)
    if not path.exists():
        return f"Document {document_type}/{document_id} not found"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return json.dumps(data, ensure_ascii=False)


def list_novel_documents(document_type: str, novel_id: str = None) -> str:
    novel_id = novel_id or _current_novel_id()
    try:
        path = _document_dir(document_type, novel_id)
    except ValueError as exc:
        return _document_type_error(exc)
    if not path.exists():
        return "[]"
    files = [f.name for f in path.iterdir() if f.name.endswith(".json")]
    return json.dumps([f.replace(".json", "") for f in files], ensure_ascii=False)


def list_novels() -> str:
    base_path = novels_path()
    if not base_path.exists():
        return "No novels found"
    novels = []
    for novel_dir in base_path.iterdir():
        meta_path = novel_dir / "meta.json"
        if meta_path.exists():
            with open(meta_path, 'r', encoding='utf-8') as f:
                novels.append(json.load(f))
    return json.dumps(novels, ensure_ascii=False)


def get_novel_info(novel_id: str) -> str:
    meta_path = novel_path(novel_id) / "meta.json"
    if not meta_path.exists():
        return f"Novel {novel_id} not found"
    with open(meta_path, 'r', encoding='utf-8') as f:
        return json.dumps(json.load(f), ensure_ascii=False)
