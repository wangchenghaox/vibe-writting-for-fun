import json
from pathlib import Path

from app.core.config import settings
from app.tools.file_tools import (
    delete_file,
    edit_file,
    grep_files,
    list_files,
    read_file,
    rename_file,
    search_files,
    write_file,
)


def test_file_tools_read_write_edit_rename_delete_inside_novels(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "WORKDIR", None)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")

    assert "已写入文件" in write_file("novels/novel_a/notes.txt", "hello world")
    assert read_file("novels/novel_a/notes.txt") == "hello world"

    assert "已修改文件" in edit_file("novels/novel_a/notes.txt", "world", "skill")
    assert read_file("novels/novel_a/notes.txt") == "hello skill"

    assert "已重命名" in rename_file(
        "novels/novel_a/notes.txt",
        "novels/novel_a/renamed.txt",
    )
    assert read_file("novels/novel_a/renamed.txt") == "hello skill"

    assert "已删除文件" in delete_file("novels/novel_a/renamed.txt")
    assert "不存在" in read_file("novels/novel_a/renamed.txt")


def test_file_tools_block_path_traversal(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "WORKDIR", None)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")

    assert write_file("../outside.txt", "nope").startswith("操作被拒绝")
    assert read_file("../outside.txt").startswith("操作被拒绝")
    assert rename_file("novels/a.txt", "../outside.txt").startswith("操作被拒绝")


def test_file_tools_use_workdir_as_only_sandbox(monkeypatch, tmp_path):
    sandbox = tmp_path / "sandbox"
    outside = tmp_path / "outside.txt"
    backend_skill_path = Path(__file__).resolve().parents[1] / "skills" / "chapter-writer.md"
    sandbox.mkdir()
    outside.write_text("outside", encoding="utf-8")
    monkeypatch.setattr(settings, "WORKDIR", sandbox)

    assert "已写入文件" in write_file("drafts/chapter_1.md", "正文")
    assert (sandbox / "drafts" / "chapter_1.md").read_text(encoding="utf-8") == "正文"
    assert read_file("drafts/chapter_1.md") == "正文"

    assert read_file(str(outside)).startswith("操作被拒绝")
    assert read_file("../outside.txt").startswith("操作被拒绝")
    assert read_file(backend_skill_path).startswith("操作被拒绝")


def test_file_tools_list_grep_and_search(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "WORKDIR", None)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    write_file("novels/novel_a/chapter_1.txt", "第一章\n用户喜欢先审稿再改写")
    write_file("novels/novel_a/notes.md", "固定 SOP: 先总结，再保存")

    listed = json.loads(list_files("novels/novel_a", pattern="*.txt"))
    assert listed == ["novels/novel_a/chapter_1.txt"]

    grep_result = json.loads(grep_files("审稿", path="novels/novel_a"))
    assert grep_result == [
        {
            "path": "novels/novel_a/chapter_1.txt",
            "line_number": 2,
            "line": "用户喜欢先审稿再改写",
        }
    ]

    search_result = json.loads(search_files("notes", path="novels/novel_a"))
    assert search_result == ["novels/novel_a/notes.md"]
