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


def test_selects_matching_skills_by_regex_trigger(tmp_path):
    (tmp_path / "chapter-writer.md").write_text(
        """---
name: chapter-writer
description: 章节写作
triggers:
  - "re:(写|生成|创作|保存).{0,12}第[0-9一二三四五六七八九十百千万两]+章"
priority: 10
---
chapter body
""",
        encoding="utf-8",
    )

    loader = SkillLoader(skills_dir=tmp_path)

    assert [skill.name for skill in loader.select_skills("请创作第二章")] == ["chapter-writer"]
    assert [skill.name for skill in loader.select_skills("保存第2章的内容")] == ["chapter-writer"]


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
        "requirement-confirmer",
        "content-reviewer",
        "chapter-writer",
        "outline-generator",
        "character-designer",
    }.issubset(skills)
    assert "read_file" in skills["content-reviewer"].allowed_tools
    assert "write_file" in skills["content-reviewer"].allowed_tools
    assert "edit_file" in skills["content-reviewer"].allowed_tools
    assert "save_novel_document" not in skills["content-reviewer"].allowed_tools
    assert "load_novel_document" not in skills["content-reviewer"].allowed_tools
    assert "load_chapter" not in skills["content-reviewer"].allowed_tools
    assert "review_chapter" not in skills["content-reviewer"].allowed_tools


def test_requirement_confirmer_triggers_before_creation_skills():
    loader = SkillLoader()

    cases = [
        ("请创作第二章", "chapter-writer"),
        ("设计一个主角", "character-designer"),
        ("写个大纲", "outline-generator"),
        ("帮我想一个玄幻故事", "requirement-confirmer"),
    ]

    for message, expected_skill in cases:
        selected_names = [skill.name for skill in loader.select_skills(message)]
        assert selected_names[0] == "requirement-confirmer"
        assert expected_skill in selected_names


def test_requirement_confirmer_uses_safe_tools_and_option_guidance():
    skill = SkillLoader().discover_skills()["requirement-confirmer"]

    assert skill.priority > SkillLoader().discover_skills()["content-reviewer"].priority
    assert "save_novel_document" not in skill.allowed_tools
    assert "write_file" not in skill.allowed_tools
    assert "edit_file" not in skill.allowed_tools
    assert set(skill.allowed_tools) == {
        "get_novel",
        "read_file",
        "list_files",
        "search_files",
    }
    assert "先确认再创作" in skill.content
    assert "1-3 个可行方案" in skill.content
    assert "未确认不调用保存工具" in skill.content
    assert "只问关键问题" in skill.content


def test_default_business_skills_have_refined_operational_sections():
    loader = SkillLoader()
    skills = loader.discover_skills()

    for skill_name in (
        "requirement-confirmer",
        "chapter-writer",
        "outline-generator",
        "character-designer",
        "content-reviewer",
        "skill-curator",
    ):
        content = skills[skill_name].content
        assert "## 适用场景" in content
        assert "## 工作流程" in content
        assert "## 输出要求" in content
        assert "## 常见误区" in content


def test_default_business_skills_encode_tool_and_safety_rules():
    loader = SkillLoader()
    skills = loader.discover_skills()

    chapter_writer = skills["chapter-writer"].content
    assert "先输出完整章节正文" in chapter_writer
    assert "不要先调用保存工具" in chapter_writer
    assert "content" in chapter_writer
    assert "不要空保存" in chapter_writer

    outline_generator = skills["outline-generator"].content
    assert "总纲" in outline_generator
    assert "卷纲" in outline_generator
    assert "章节细纲" in outline_generator
    assert "不要空保存" in outline_generator

    character_designer = skills["character-designer"].content
    assert "角色卡" in character_designer
    assert "关系网" in character_designer
    assert "成长弧" in character_designer
    assert "先询问用户确认" in character_designer

    content_reviewer = skills["content-reviewer"].content
    assert "严重程度" in content_reviewer
    assert "位置" in content_reviewer
    assert "不要在未读取章节内容时假装已经审查" in content_reviewer

    skill_curator = skills["skill-curator"].content
    assert "可复用" in skill_curator
    assert "一次性" in skill_curator
    assert "目标文件" in skill_curator
    assert "Markdown" in skill_curator
    assert ".md" in skill_curator
    assert "不要使用 `delete_file`" in skill_curator


def test_creation_skills_write_markdown_with_basic_file_tools():
    skills = SkillLoader().discover_skills()

    for skill_name in (
        "chapter-writer",
        "outline-generator",
        "character-designer",
        "content-reviewer",
    ):
        skill = skills[skill_name]
        assert "write_file" in skill.allowed_tools
        assert "edit_file" in skill.allowed_tools
        assert "save_novel_document" not in skill.allowed_tools
        assert "load_novel_document" not in skill.allowed_tools
        assert "Markdown" in skill.content
        assert ".md" in skill.content
        assert "固定格式" in skill.content

    assert "novels/{novel_id}/chapters/{chapter_id}.md" in skills["chapter-writer"].content
    assert "novels/{novel_id}/outlines/{outline_id}.md" in skills["outline-generator"].content
    assert "novels/{novel_id}/characters/{character_id}.md" in skills["character-designer"].content
    assert "novels/{novel_id}/reviews/{chapter_id}_review.md" in skills["content-reviewer"].content


def test_outline_and_character_skills_confirm_after_design_before_followup_actions():
    skills = SkillLoader().discover_skills()

    outline_generator = skills["outline-generator"].content
    assert "设计完成后" in outline_generator
    assert "请用户确认" in outline_generator
    assert "用户确认前不要保存" in outline_generator

    character_designer = skills["character-designer"].content
    assert "设计完成后" in character_designer
    assert "请用户确认" in character_designer
    assert "用户确认前不要保存" in character_designer


def test_default_chapter_writer_matches_ordinal_chapter_requests():
    loader = SkillLoader()

    for message in ("创作第二章", "写第2章", "保存第二章的内容"):
        selected_names = [skill.name for skill in loader.select_skills(message)]
        assert "chapter-writer" in selected_names


def test_skill_curator_is_discoverable_with_file_tools():
    loader = SkillLoader()

    skill = loader.discover_skills()["skill-curator"]

    assert "优化 skill" in skill.triggers
    assert "write_file" in skill.allowed_tools
    assert "edit_file" in skill.allowed_tools
    assert "delete_file" not in skill.allowed_tools
