from app.capability.skill_loader import SkillLoader


def test_load_nonexistent_skill():
    loader = SkillLoader()
    result = loader.load_skill("nonexistent")
    assert result is None


def test_get_loaded_skills():
    loader = SkillLoader()
    skills = loader.get_loaded_skills()
    assert isinstance(skills, dict)


def test_discovers_skill_frontmatter(tmp_path):
    skill_file = tmp_path / "content-reviewer.md"
    skill_file.write_text(
        """---
name: content-reviewer
description: 审查章节质量
triggers:
  - 审查
  - review
allowed_tools:
  - load_chapter
priority: 20
---
# 内容审查

请检查情节、人物和文风。
""",
        encoding="utf-8",
    )

    loader = SkillLoader(skills_dir=tmp_path)
    skills = loader.discover_skills()

    skill = skills["content-reviewer"]
    assert skill.name == "content-reviewer"
    assert skill.description == "审查章节质量"
    assert skill.triggers == ["审查", "review"]
    assert skill.allowed_tools == ["load_chapter"]
    assert skill.priority == 20
    assert "请检查情节" in skill.content


def test_selects_matching_skills_by_trigger_and_priority(tmp_path):
    (tmp_path / "low.md").write_text(
        """---
name: low
description: low priority
triggers: [审查]
priority: 1
---
low body
""",
        encoding="utf-8",
    )
    (tmp_path / "high.md").write_text(
        """---
name: high
description: high priority
triggers: [审查]
priority: 10
---
high body
""",
        encoding="utf-8",
    )

    loader = SkillLoader(skills_dir=tmp_path)

    selected = loader.select_skills("请帮我审查第一章")

    assert [skill.name for skill in selected] == ["high", "low"]


def test_builds_active_skill_prompt(tmp_path):
    (tmp_path / "writer.md").write_text(
        """---
name: chapter-writer
description: 章节写作
triggers: [写章节]
allowed_tools: [load_outline, save_chapter]
---
# 章节写作

按大纲写作。
""",
        encoding="utf-8",
    )

    loader = SkillLoader(skills_dir=tmp_path)
    skill = loader.select_skills("写章节")[0]

    prompt = loader.build_prompt([skill])

    assert "已启用技能: chapter-writer" in prompt
    assert "允许工具: load_outline, save_chapter" in prompt
    assert "按大纲写作。" in prompt


def test_default_business_skills_are_discoverable():
    loader = SkillLoader()

    skills = loader.discover_skills()

    assert {
        "content-reviewer",
        "chapter-writer",
        "outline-generator",
        "character-designer",
    }.issubset(skills)
    assert "load_chapter" in skills["content-reviewer"].allowed_tools
    assert "review_chapter" not in skills["content-reviewer"].allowed_tools


def test_skill_curator_is_discoverable_with_file_tools():
    loader = SkillLoader()

    skill = loader.discover_skills()["skill-curator"]

    assert "优化 skill" in skill.triggers
    assert "write_file" in skill.allowed_tools
    assert "edit_file" in skill.allowed_tools
    assert "delete_file" not in skill.allowed_tools
