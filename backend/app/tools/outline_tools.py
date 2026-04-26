import os
import json
from ..capability.tool_registry import tool
from app.core.paths import novel_path

@tool(name="save_outline", description="Save an outline to file")
def save_outline(outline_id: str, content: str, novel_id: str = None) -> str:
    if novel_id is None:
        novel_id = os.getenv('CURRENT_NOVEL_ID', 'default')
    path_dir = novel_path(novel_id) / "outlines"
    os.makedirs(path_dir, exist_ok=True)
    path = path_dir / f"{outline_id}.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({"id": outline_id, "content": content}, f, ensure_ascii=False, indent=2)
    return f"Outline saved: {path}"

@tool(name="load_outline", description="Load an outline from file")
def load_outline(outline_id: str, novel_id: str = None) -> str:
    if novel_id is None:
        novel_id = os.getenv('CURRENT_NOVEL_ID', 'default')
    path = novel_path(novel_id) / "outlines" / f"{outline_id}.json"
    if not path.exists():
        return f"Outline {outline_id} not found"
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return json.dumps(data, ensure_ascii=False)
