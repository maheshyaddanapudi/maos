"""
MAOS Skill Registry.

Manages skills and skillsets.
"""

import structlog

from maos.config.models import SkillConfig, SkillsetConfig
from maos.skills.models import Skill, Skillset
from maos.tools.models import Tool
from maos.tools.registry import ToolRegistry

log = structlog.get_logger()


class SkillRegistry:
    """Registry of skills (tool groupings)."""

    def __init__(self, tool_registry: ToolRegistry | None = None):
        self._tool_registry = tool_registry
        self._skills: dict[str, Skill] = {}

    def set_tool_registry(self, tool_registry: ToolRegistry) -> None:
        """Set the tool registry for validation.

        Args:
            tool_registry: Tool registry
        """
        self._tool_registry = tool_registry

    def build(self, skill_configs: dict[str, SkillConfig]) -> None:
        """Build skills from configuration.

        Args:
            skill_configs: Dictionary of skill configurations keyed by name
        """
        if not skill_configs:
            log.info("no_skills_configured")
            return

        log.info("building_skills", count=len(skill_configs))

        for name, config in skill_configs.items():
            # Validate tool references if registry available
            if self._tool_registry:
                missing_tools = [
                    tid for tid in config.tools
                    if tid not in self._tool_registry
                ]
                if missing_tools:
                    log.warning(
                        "skill_missing_tools",
                        skill=name,
                        missing=missing_tools,
                    )

            skill = Skill(
                name=name,
                description=config.description,
                tool_ids=config.tools,
            )
            self._skills[name] = skill
            log.debug("skill_registered", name=name, tool_count=len(config.tools))

        log.info("skills_built", count=len(self._skills))

    def register(self, skill: Skill) -> None:
        """Register a skill.

        Args:
            skill: Skill to register
        """
        self._skills[skill.name] = skill
        log.debug("skill_registered", name=skill.name)

    def get(self, name: str) -> Skill | None:
        """Get skill by name.

        Args:
            name: Skill name

        Returns:
            Skill or None if not found
        """
        return self._skills.get(name)

    def get_tools_for_skill(self, name: str) -> list[Tool]:
        """Get resolved tools for a skill.

        Args:
            name: Skill name

        Returns:
            List of Tool objects
        """
        if not self._tool_registry:
            return []

        skill = self.get(name)
        if not skill:
            return []

        return skill.get_tools(self._tool_registry)

    def find_skills_with_tool(self, tool_id: str) -> list[Skill]:
        """Find skills containing a specific tool.

        Args:
            tool_id: Tool ID to search for

        Returns:
            List of skills containing the tool
        """
        return [s for s in self._skills.values() if s.has_tool(tool_id)]

    def list_all(self) -> list[Skill]:
        """List all registered skills.

        Returns:
            List of skills
        """
        return list(self._skills.values())

    def list_names(self) -> list[str]:
        """List all skill names.

        Returns:
            List of skill names
        """
        return list(self._skills.keys())

    def __len__(self) -> int:
        return len(self._skills)

    def __contains__(self, name: str) -> bool:
        return name in self._skills


class SkillsetRegistry:
    """Registry of skillsets (skill groupings)."""

    def __init__(self, skill_registry: SkillRegistry, tool_registry: ToolRegistry | None = None):
        self._skill_registry = skill_registry
        self._tool_registry = tool_registry
        self._skillsets: dict[str, Skillset] = {}

    def set_tool_registry(self, tool_registry: ToolRegistry) -> None:
        """Set the tool registry.

        Args:
            tool_registry: Tool registry
        """
        self._tool_registry = tool_registry

    def build(self, skillset_configs: dict[str, SkillsetConfig]) -> None:
        """Build skillsets from configuration.

        Args:
            skillset_configs: Dictionary of skillset configurations keyed by name
        """
        if not skillset_configs:
            log.info("no_skillsets_configured")
            return

        log.info("building_skillsets", count=len(skillset_configs))

        for name, config in skillset_configs.items():
            # Validate skill references
            missing_skills = [
                sname for sname in config.skills
                if sname not in self._skill_registry
            ]
            if missing_skills:
                log.warning(
                    "skillset_missing_skills",
                    skillset=name,
                    missing=missing_skills,
                )

            skillset = Skillset(
                name=name,
                description=config.description or "",
                skill_names=config.skills,
            )
            self._skillsets[name] = skillset
            log.debug("skillset_registered", name=name, skill_count=len(config.skills))

        log.info("skillsets_built", count=len(self._skillsets))

    def register(self, skillset: Skillset) -> None:
        """Register a skillset.

        Args:
            skillset: Skillset to register
        """
        self._skillsets[skillset.name] = skillset
        log.debug("skillset_registered", name=skillset.name)

    def get(self, name: str) -> Skillset | None:
        """Get skillset by name.

        Args:
            name: Skillset name

        Returns:
            Skillset or None if not found
        """
        return self._skillsets.get(name)

    def get_all_tools(self, name: str) -> list[Tool]:
        """Get all tools across all skills in skillset.

        Args:
            name: Skillset name

        Returns:
            List of Tool objects
        """
        if not self._tool_registry:
            return []

        skillset = self.get(name)
        if not skillset:
            return []

        return skillset.get_all_tools(self._skill_registry, self._tool_registry)

    def get_skill_names(self, name: str) -> list[str]:
        """Get skill names for a skillset.

        Args:
            name: Skillset name

        Returns:
            List of skill names
        """
        skillset = self.get(name)
        if not skillset:
            return []
        return skillset.skill_names

    def list_all(self) -> list[Skillset]:
        """List all registered skillsets.

        Returns:
            List of skillsets
        """
        return list(self._skillsets.values())

    def list_names(self) -> list[str]:
        """List all skillset names.

        Returns:
            List of skillset names
        """
        return list(self._skillsets.keys())

    def __len__(self) -> int:
        return len(self._skillsets)

    def __contains__(self, name: str) -> bool:
        return name in self._skillsets
