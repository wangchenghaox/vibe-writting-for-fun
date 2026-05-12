import json
from pathlib import Path

from app.core.config import settings
from app.tools.file_tools import (
    copy_file,
    delete_file,
    edit_file,
    grep_files,
    list_files,
    make_directory,
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


def test_make_directory_creates_workspace_directories(monkeypatch, tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setattr(settings, "WORKDIR", sandbox)

    result = make_directory("drafts/chapter_01/scenes")

    assert "已创建目录" in result
    assert (sandbox / "drafts" / "chapter_01" / "scenes").is_dir()
    assert make_directory("skills/generated").startswith("操作被拒绝")


def test_copy_file_copies_workspace_files_without_overwriting_by_default(monkeypatch, tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setattr(settings, "WORKDIR", sandbox)
    write_file("drafts/source.md", "第一版")

    result = copy_file("drafts/source.md", "drafts/copy.md")

    assert "已复制文件" in result
    assert read_file("drafts/copy.md") == "第一版"
    assert copy_file("drafts/source.md", "drafts/copy.md").startswith("目标文件已存在")

    write_file("drafts/source.md", "第二版")
    assert "已复制文件" in copy_file("drafts/source.md", "drafts/copy.md", overwrite=True)
    assert read_file("drafts/copy.md") == "第二版"


def test_copy_file_can_copy_readonly_skill_files_into_workspace(monkeypatch, tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setattr(settings, "WORKDIR", sandbox)

    result = copy_file("skills/chapter-writer.md", "templates/chapter-writer.md")

    assert "已复制文件" in result
    assert "# 章节写作" in read_file("templates/chapter-writer.md")
    assert copy_file("drafts/missing.md", "templates/missing.md").startswith("文件不存在")
    assert copy_file("skills/chapter-writer.md", "skills/copy.md").startswith("操作被拒绝")


def test_read_file_supports_offset_for_chunked_reads(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "WORKDIR", None)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")

    write_file("novels/novel_a/long.txt", "0123456789")

    assert read_file("novels/novel_a/long.txt", max_chars=4) == "0123"
    assert read_file("novels/novel_a/long.txt", max_chars=4, offset=4) == "4567"


def test_file_tools_block_path_traversal(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "WORKDIR", None)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")

    assert write_file("../outside.txt", "nope").startswith("操作被拒绝")
    assert read_file("../outside.txt").startswith("操作被拒绝")
    assert rename_file("novels/a.txt", "../outside.txt").startswith("操作被拒绝")


def test_file_tools_use_workdir_and_readonly_skill_roots(monkeypatch, tmp_path):
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
    assert "# 章节写作" in read_file(backend_skill_path)
    assert edit_file("skills/chapter-writer.md", "章节写作", "nope").startswith("操作被拒绝")


def test_read_file_resolves_skill_alias_when_workdir_is_configured(monkeypatch, tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setattr(settings, "WORKDIR", sandbox)

    content = read_file("skills/outline-generator.md")

    assert "# 大纲生成" in content


def test_file_read_tools_allow_configured_skill_dirs(monkeypatch, tmp_path):
    sandbox = tmp_path / "sandbox"
    skill_dir_a = tmp_path / "skill_a"
    skill_dir_b = tmp_path / "skill_b"
    sandbox.mkdir()
    skill_dir_a.mkdir()
    skill_dir_b.mkdir()
    (skill_dir_a / "alpha.md").write_text("alpha skill body", encoding="utf-8")
    (skill_dir_b / "beta.md").write_text("beta unique marker", encoding="utf-8")
    monkeypatch.setattr(settings, "WORKDIR", sandbox)
    monkeypatch.setattr(settings, "SKILL_DIRS", f"{skill_dir_a},{skill_dir_b}")

    assert read_file("skills/alpha.md") == "alpha skill body"
    assert read_file("skills/beta.md") == "beta unique marker"
    assert json.loads(list_files("skills", pattern="*.md")) == [
        "skills/alpha.md",
        "skills/beta.md",
    ]
    assert json.loads(search_files("beta", path="skills")) == ["skills/beta.md"]
    assert json.loads(grep_files("unique", path="skills")) == [
        {
            "path": "skills/beta.md",
            "line_number": 1,
            "line": "beta unique marker",
        }
    ]
    assert write_file("skills/new.md", "nope").startswith("操作被拒绝")


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
