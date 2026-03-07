"""Skill and skillset data models."""

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from maos.tools.models import Tool
    from maos.tools.registry import ToolRegistry


class Skill(BaseModel):
    """A skill groups related tools."""

    name: str
    description: str = ""
    tool_ids: list[str] = Field(default_factory=list)

    def get_tools(self, tool_registry: "ToolRegistry") -> list["Tool"]:
        """
        Resolve tool IDs to Tool objects.

        Args:
            tool_registry: Registry containing the tools.

        Returns:
            List of Tool objects.
        """
        tools = []
        for tool_id in self.tool_ids:
            tool = tool_registry.get(tool_id)
            if tool:
                tools.append(tool)
        return tools


class Skillset(BaseModel):
    """A skillset groups related skills for an agent."""

    name: str
    description: str = ""
    skill_names: list[str] = Field(default_factory=list)

    def get_skills(self, skill_registry: "SkillRegistry") -> list[Skill]:
        """
        Resolve skill names to Skill objects.

        Args:
            skill_registry: Registry containing the skills.

        Returns:
            List of Skill objects.
        """
        skills = []
        for skill_name in self.skill_names:
            skill = skill_registry.get(skill_name)
            if skill:
                skills.append(skill)
        return skills

    def get_all_tools(
        self, skill_registry: "SkillRegistry", tool_registry: "ToolRegistry"
    ) -> list["Tool"]:
        """
        Get all tools across all skills in this skillset.

        Args:
            skill_registry: Registry containing the skills.
            tool_registry: Registry containing the tools.

        Returns:
            List of unique Tool objects.
        """
        tools = []
        seen_ids = set()
        for skill in self.get_skills(skill_registry):
            for tool in skill.get_tools(tool_registry):
                if tool.id not in seen_ids:
                    tools.append(tool)
                    seen_ids.add(tool.id)
        return tools

    def get_all_tool_ids(self, skill_registry: "SkillRegistry") -> list[str]:
        """
        Get all tool IDs across all skills.

        Args:
            skill_registry: Registry containing the skills.

        Returns:
            List of unique tool IDs.
        """
        tool_ids = set()
        for skill in self.get_skills(skill_registry):
            tool_ids.update(skill.tool_ids)
        return list(tool_ids)


# Import here to avoid circular dependency
from maos.skills.registry import SkillRegistry  # noqa: E402
