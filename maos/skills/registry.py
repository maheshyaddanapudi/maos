"""Registries for skills and skillsets."""

import structlog

from maos.config.models import SkillConfig, SkillsetConfig
from maos.skills.models import Skill, Skillset
from maos.tools.models import Tool
from maos.tools.registry import ToolRegistry

logger = structlog.get_logger()


class SkillRegistry:
    """Registry of skills (tool groupings)."""

    def __init__(self, tool_registry: ToolRegistry):
        """
        Initialize the skill registry.

        Args:
            tool_registry: Registry of tools.
        """
        self._tool_registry = tool_registry
        self._skills: dict[str, Skill] = {}

    def build(self, skill_configs: dict[str, SkillConfig]) -> None:
        """
        Build skills from configuration.

        Args:
            skill_configs: Skill configurations keyed by name.
        """
        for name, config in skill_configs.items():
            self._build_skill(name, config)

    def _build_skill(self, name: str, config: SkillConfig) -> None:
        """Build a single skill."""
        # Validate tool references
        missing_tools = []
        for tool_id in config.tools:
            if tool_id not in self._tool_registry:
                missing_tools.append(tool_id)

        if missing_tools:
            logger.warning("skill_has_missing_tools", skill=name, missing_tools=missing_tools)

        skill = Skill(name=name, description=config.description, tool_ids=config.tools)
        self._skills[name] = skill
        logger.debug("built_skill", skill=name, tools=len(config.tools))

    def register(self, skill: Skill) -> None:
        """Register a skill."""
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def get_or_raise(self, name: str) -> Skill:
        """Get a skill by name, raising if not found."""
        skill = self._skills.get(name)
        if skill is None:
            raise KeyError(f"Skill not found: {name}")
        return skill

    def get_tools_for_skill(self, name: str) -> list[Tool]:
        """Get resolved tools for a skill."""
        skill = self.get(name)
        if skill is None:
            return []
        return skill.get_tools(self._tool_registry)

    def find_skills_with_tool(self, tool_id: str) -> list[Skill]:
        """Find skills containing a specific tool."""
        return [skill for skill in self._skills.values() if tool_id in skill.tool_ids]

    def list_all(self) -> list[Skill]:
        """List all skills."""
        return list(self._skills.values())

    def list_names(self) -> list[str]:
        """List all skill names."""
        return list(self._skills.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __len__(self) -> int:
        return len(self._skills)


class SkillsetRegistry:
    """Registry of skillsets (skill groupings)."""

    def __init__(self, skill_registry: SkillRegistry, tool_registry: ToolRegistry):
        """
        Initialize the skillset registry.

        Args:
            skill_registry: Registry of skills.
            tool_registry: Registry of tools.
        """
        self._skill_registry = skill_registry
        self._tool_registry = tool_registry
        self._skillsets: dict[str, Skillset] = {}

    def build(self, skillset_configs: dict[str, SkillsetConfig]) -> None:
        """
        Build skillsets from configuration.

        Args:
            skillset_configs: Skillset configurations keyed by name.
        """
        for name, config in skillset_configs.items():
            self._build_skillset(name, config)

    def _build_skillset(self, name: str, config: SkillsetConfig) -> None:
        """Build a single skillset."""
        # Validate skill references
        missing_skills = []
        for skill_name in config.skills:
            if skill_name not in self._skill_registry:
                missing_skills.append(skill_name)

        if missing_skills:
            logger.warning(
                "skillset_has_missing_skills", skillset=name, missing_skills=missing_skills
            )

        skillset = Skillset(
            name=name, description=config.description or "", skill_names=config.skills
        )
        self._skillsets[name] = skillset
        logger.debug("built_skillset", skillset=name, skills=len(config.skills))

    def register(self, skillset: Skillset) -> None:
        """Register a skillset."""
        self._skillsets[skillset.name] = skillset

    def get(self, name: str) -> Skillset | None:
        """Get a skillset by name."""
        return self._skillsets.get(name)

    def get_or_raise(self, name: str) -> Skillset:
        """Get a skillset by name, raising if not found."""
        skillset = self._skillsets.get(name)
        if skillset is None:
            raise KeyError(f"Skillset not found: {name}")
        return skillset

    def get_all_tools(self, name: str) -> list[Tool]:
        """Get all tools across all skills in a skillset."""
        skillset = self.get(name)
        if skillset is None:
            return []
        return skillset.get_all_tools(self._skill_registry, self._tool_registry)

    def get_skill_names(self, name: str) -> list[str]:
        """Get skill names in a skillset."""
        skillset = self.get(name)
        if skillset is None:
            return []
        return skillset.skill_names

    def list_all(self) -> list[Skillset]:
        """List all skillsets."""
        return list(self._skillsets.values())

    def list_names(self) -> list[str]:
        """List all skillset names."""
        return list(self._skillsets.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._skillsets

    def __len__(self) -> int:
        return len(self._skillsets)
