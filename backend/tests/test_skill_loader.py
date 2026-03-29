import pytest
from app.capability.skill_loader import SkillLoader


def test_load_nonexistent_skill():
    loader = SkillLoader()
    result = loader.load_skill("nonexistent")
    assert result is None


def test_get_loaded_skills():
    loader = SkillLoader()
    skills = loader.get_loaded_skills()
    assert isinstance(skills, dict)
