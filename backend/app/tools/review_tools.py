import json
from app.core.paths import novel_path

def review_chapter(chapter_id: str, novel_id: str = None) -> str:
    """读取章节内容，供 skill 驱动的审查流程使用"""
    import os
    if novel_id is None:
        novel_id = os.getenv('CURRENT_NOVEL_ID', 'default')

    path = novel_path(novel_id) / "chapters" / f"{chapter_id}.json"
    if not path.exists():
        return f"Chapter {chapter_id} not found"

    with open(path, 'r', encoding='utf-8') as f:
        chapter = json.load(f)

    # 返回章节内容；审查标准由 content-reviewer skill 提供。
    return json.dumps({
        "chapter_id": chapter_id,
        "title": chapter["title"],
        "content": chapter["content"],
    }, ensure_ascii=False)
