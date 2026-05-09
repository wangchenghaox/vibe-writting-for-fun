"""
Skill加载器 - 动态加载和管理技能
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import logging

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    description: str = ""
    triggers: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)
    priority: int = 0
    content: str = ""
    path: Optional[Path] = None


class SkillLoader:
    def __init__(self, skills_dir: str | Path = None):
        if skills_dir is None:
            skills_dir = Path(__file__).resolve().parents[2] / "skills"
        self.skills_dir = Path(skills_dir)
        self.loaded_skills: Dict[str, str] = {}
        self._skill_cache: Optional[Dict[str, SkillDefinition]] = None

    def load_skill(self, skill_name: str) -> Optional[str]:
        """加载技能内容"""
        skill = self.get_skill(skill_name)
        if skill is None:
            skill_path = self.skills_dir / f"{skill_name}.md"
            logger.warning(f"技能文件不存在: {skill_path}")
            return None

        self.loaded_skills[skill.name] = skill.content
        logger.info(f"加载技能: {skill.name}")
        return skill.content

    def unload_skill(self, skill_name: str):
        """卸载技能"""
        if skill_name in self.loaded_skills:
            del self.loaded_skills[skill_name]
            logger.info(f"卸载技能: {skill_name}")

    def get_loaded_skills(self) -> Dict[str, str]:
        """获取已加载的技能"""
        return self.loaded_skills.copy()

    def discover_skills(self) -> Dict[str, SkillDefinition]:
        """扫描技能目录并解析技能定义"""
        if self._skill_cache is not None:
            return self._skill_cache

        skills: Dict[str, SkillDefinition] = {}
        if not self.skills_dir.exists():
            self._skill_cache = skills
            return skills

        for skill_path in sorted(self.skills_dir.glob("*.md")):
            try:
                skill = self._parse_skill_file(skill_path)
            except Exception as e:
                logger.error(f"解析技能失败 {skill_path}: {e}")
                continue
            skills[skill.name] = skill

        self._skill_cache = skills
        return skills

    def get_skill(self, skill_name: str) -> Optional[SkillDefinition]:
        return self.discover_skills().get(skill_name)

    def build_catalog_prompt(self) -> str:
        skills = sorted(
            self.discover_skills().values(),
            key=lambda skill: (-skill.priority, skill.name),
        )
        if not skills:
            return ""

        sections = [
            (
                "你可以使用以下本地创作技能。请根据用户请求和触发时机判断是否需要启用；"
                "完整说明见对应的 skill 说明文件路径。"
            )
        ]
        for skill in skills:
            sections.append(self._format_catalog_entry(skill))
        return "\n\n".join(sections)

    def _parse_skill_file(self, skill_path: Path) -> SkillDefinition:
        raw = skill_path.read_text(encoding="utf-8")
        metadata: Dict[str, object] = {}
        content = raw

        if raw.startswith("---\n"):
            _, frontmatter, content = raw.split("---", 2)
            metadata = yaml.safe_load(frontmatter) or {}
            content = content.lstrip("\n")

        name = str(metadata.get("name") or skill_path.stem)
        return SkillDefinition(
            name=name,
            description=str(metadata.get("description") or ""),
            triggers=self._as_list(metadata.get("triggers")),
            allowed_tools=self._as_list(metadata.get("allowed_tools")),
            priority=int(metadata.get("priority") or 0),
            content=content.strip(),
            path=skill_path,
        )

    def _format_catalog_entry(self, skill: SkillDefinition) -> str:
        trigger_lines = skill.triggers or ["未设置显式触发词"]
        triggers = "\n".join(f"- {trigger}" for trigger in trigger_lines)
        return (
            f"技能: {skill.name}\n"
            f"说明: {skill.description or '无'}\n"
            f"触发时机:\n{triggers}\n"
            f"说明文件: {self._catalog_skill_path(skill)}"
        )

    def _catalog_skill_path(self, skill: SkillDefinition) -> str:
        if skill.path is None:
            return f"skills/{skill.name}.md"

        try:
            relative_path = skill.path.relative_to(self.skills_dir)
        except ValueError:
            relative_path = Path(skill.path.name)

        return str(Path("skills") / relative_path).replace("\\", "/")

    def _as_list(self, value) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, tuple):
            return [str(item) for item in value]
        return [str(value)]
