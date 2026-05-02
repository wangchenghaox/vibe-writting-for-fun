from .novel_tools import (
    list_novel_documents,
    load_novel_document,
    save_novel_document,
)

def save_chapter(chapter_id: str, title: str, content: str, novel_id: str = None) -> str:
    return save_novel_document(
        "chapter",
        chapter_id,
        content,
        title=title,
        novel_id=novel_id,
    )

def load_chapter(chapter_id: str, novel_id: str = None) -> str:
    return load_novel_document("chapter", chapter_id, novel_id=novel_id)

def list_chapters(novel_id: str = None) -> str:
    return list_novel_documents("chapter", novel_id=novel_id)
