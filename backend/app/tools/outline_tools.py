from .novel_tools import load_novel_document, save_novel_document

def save_outline(outline_id: str, content: str, novel_id: str = None) -> str:
    return save_novel_document("outline", outline_id, content, novel_id=novel_id)

def load_outline(outline_id: str, novel_id: str = None) -> str:
    return load_novel_document("outline", outline_id, novel_id=novel_id)
