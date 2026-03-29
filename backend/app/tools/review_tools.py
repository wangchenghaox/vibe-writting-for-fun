import json
from ..capability.tool_registry import tool

@tool(name="review_chapter", description="Review a chapter and provide feedback")
def review_chapter(chapter_id: str, novel_id: str = None) -> str:
    """审查章节内容，返回修改建议"""
    import os
    if novel_id is None:
        novel_id = os.getenv('CURRENT_NOVEL_ID', 'default')

    path = f"data/novels/{novel_id}/chapters/{chapter_id}.json"
    if not os.path.exists(path):
        return f"Chapter {chapter_id} not found"

    with open(path, 'r', encoding='utf-8') as f:
        chapter = json.load(f)

    # 返回章节内容供 LLM 审查
    return json.dumps({
        "chapter_id": chapter_id,
        "title": chapter["title"],
        "content": chapter["content"],
        "instruction": "请审查这个章节，检查：1.情节连贯性 2.人物塑造 3.文风一致性 4.克苏鲁氛围营造。如果没有问题回复'通过'，否则提供具体修改建议。"
    }, ensure_ascii=False)
