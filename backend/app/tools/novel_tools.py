import os
import json
from datetime import datetime
from ..capability.tool_registry import tool
from app.core.paths import novel_path, novels_path

@tool(name="create_novel", description="Create a new novel project")
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

@tool(name="list_novels", description="List all novel projects")
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

@tool(name="get_novel_info", description="Get novel project information")
def get_novel_info(novel_id: str) -> str:
    meta_path = novel_path(novel_id) / "meta.json"
    if not meta_path.exists():
        return f"Novel {novel_id} not found"
    with open(meta_path, 'r', encoding='utf-8') as f:
        return json.dumps(json.load(f), ensure_ascii=False)
