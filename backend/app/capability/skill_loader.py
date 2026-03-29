"""
Skill加载器 - 动态加载和管理技能
"""
import os
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class SkillLoader:
    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self.loaded_skills: Dict[str, str] = {}

    def load_skill(self, skill_name: str) -> Optional[str]:
        """加载技能内容"""
        skill_path = self.skills_dir / f"{skill_name}.md"

        if not skill_path.exists():
            logger.warning(f"技能文件不存在: {skill_path}")
            return None

        try:
            with open(skill_path, 'r', encoding='utf-8') as f:
                content = f.read()

            self.loaded_skills[skill_name] = content
            logger.info(f"加载技能: {skill_name}")
            return content
        except Exception as e:
            logger.error(f"加载技能失败: {e}")
            return None

    def unload_skill(self, skill_name: str):
        """卸载技能"""
        if skill_name in self.loaded_skills:
            del self.loaded_skills[skill_name]
            logger.info(f"卸载技能: {skill_name}")

    def get_loaded_skills(self) -> Dict[str, str]:
        """获取已加载的技能"""
        return self.loaded_skills.copy()
