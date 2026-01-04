"""
MAOS Skill Models.

Data structures for skills and skillsets.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maos.tools.models import Tool
    from maos.tools.registry import ToolRegistry


@dataclass
class Skill:
    """A skill groups related tools."""

    name: str
    description: str = ""
    tool_ids: list[str] = field(default_factory=list)

    def get_tools(self, tool_registry: "ToolRegistry") -> list["Tool"]:
        """Resolve tool IDs to Tool objects.

        Args:
            tool_registry: Tool registry to resolve from

        Returns:
            List of Tool objects
        """
        return tool_registry.get_tools_by_ids(self.tool_ids)

    def has_tool(self, tool_id: str) -> bool:
        """Check if skill contains a tool.

        Args:
            tool_id: Tool ID to check

        Returns:
            True if skill contains the tool
        """
        return tool_id in self.tool_ids

    def __repr__(self) -> str:
        return f"Skill(name={self.name!r}, tools={self.tool_ids})"


@dataclass
class Skillset:
    """A skillset groups related skills for an agent."""

    name: str
    description: str = ""
    skill_names: list[str] = field(default_factory=list)

    def get_skills(self, skill_registry: "SkillRegistry") -> list[Skill]:
        """Resolve skill names to Skill objects.

        Args:
            skill_registry: Skill registry to resolve from

        Returns:
            List of Skill objects
        """
        skills = []
        for skill_name in self.skill_names:
            skill = skill_registry.get(skill_name)
            if skill:
                skills.append(skill)
        return skills

    def get_all_tools(
        self,
        skill_registry: "SkillRegistry",
        tool_registry: "ToolRegistry",
    ) -> list["Tool"]:
        """Get all tools across all skills in this skillset.

        Args:
            skill_registry: Skill registry to resolve skills
            tool_registry: Tool registry to resolve tools

        Returns:
            List of Tool objects (deduplicated)
        """
        tools = []
        seen_ids: set[str] = set()

        for skill in self.get_skills(skill_registry):
            for tool in skill.get_tools(tool_registry):
                if tool.id not in seen_ids:
                    tools.append(tool)
                    seen_ids.add(tool.id)

        return tools

    def get_all_tool_ids(self, skill_registry: "SkillRegistry") -> list[str]:
        """Get all tool IDs across all skills.

        Args:
            skill_registry: Skill registry to resolve skills

        Returns:
            List of tool IDs (deduplicated)
        """
        tool_ids: set[str] = set()
        for skill in self.get_skills(skill_registry):
            tool_ids.update(skill.tool_ids)
        return list(tool_ids)

    def __repr__(self) -> str:
        return f"Skillset(name={self.name!r}, skills={self.skill_names})"


# Import SkillRegistry here to avoid circular import in type hints
from maos.skills.registry import SkillRegistry
