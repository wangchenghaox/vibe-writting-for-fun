import os
import json
from datetime import datetime
from ..capability.tool_registry import tool

@tool(name="create_novel", description="Create a new novel project")
def create_novel(novel_id: str, title: str, description: str = "") -> str:
    base_path = f"data/novels/{novel_id}"
    os.makedirs(f"{base_path}/chapters", exist_ok=True)
    os.makedirs(f"{base_path}/outlines", exist_ok=True)

    meta = {
        "id": novel_id,
        "title": title,
        "description": description,
        "created_at": datetime.now().isoformat()
    }

    with open(f"{base_path}/meta.json", 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 保存当前作品ID到环境变量，供其他工具使用
    os.environ['CURRENT_NOVEL_ID'] = novel_id

    return f"Novel created: {base_path}. Current novel_id set to: {novel_id}"

@tool(name="list_novels", description="List all novel projects")
def list_novels() -> str:
    if not os.path.exists("data/novels"):
        return "No novels found"
    novels = []
    for novel_id in os.listdir("data/novels"):
        meta_path = f"data/novels/{novel_id}/meta.json"
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                novels.append(json.load(f))
    return json.dumps(novels, ensure_ascii=False)

@tool(name="get_novel_info", description="Get novel project information")
def get_novel_info(novel_id: str) -> str:
    meta_path = f"data/novels/{novel_id}/meta.json"
    if not os.path.exists(meta_path):
        return f"Novel {novel_id} not found"
    with open(meta_path, 'r', encoding='utf-8') as f:
        return json.dumps(json.load(f), ensure_ascii=False)

