import os
import json
from ..capability.tool_registry import tool
from app.core.paths import novel_path

@tool(name="save_chapter", description="Save a chapter to file")
def save_chapter(chapter_id: str, title: str, content: str, novel_id: str = None) -> str:
    if novel_id is None:
        novel_id = os.getenv('CURRENT_NOVEL_ID', 'default')
    path_dir = novel_path(novel_id) / "chapters"
    os.makedirs(path_dir, exist_ok=True)
    path = path_dir / f"{chapter_id}.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({"id": chapter_id, "title": title, "content": content}, f, ensure_ascii=False, indent=2)
    return f"Chapter saved: {path}"

@tool(name="load_chapter", description="Load a chapter from file")
def load_chapter(chapter_id: str, novel_id: str = None) -> str:
    if novel_id is None:
        novel_id = os.getenv('CURRENT_NOVEL_ID', 'default')
    path = novel_path(novel_id) / "chapters" / f"{chapter_id}.json"
    if not path.exists():
        return f"Chapter {chapter_id} not found"
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return json.dumps(data, ensure_ascii=False)

@tool(name="list_chapters", description="List all saved chapters")
def list_chapters(novel_id: str = None) -> str:
    if novel_id is None:
        novel_id = os.getenv('CURRENT_NOVEL_ID', 'default')
    path = novel_path(novel_id) / "chapters"
    if not path.exists():
        return "No chapters found"
    files = [f.name for f in path.iterdir() if f.name.endswith('.json')]
    return json.dumps([f.replace('.json', '') for f in files])
