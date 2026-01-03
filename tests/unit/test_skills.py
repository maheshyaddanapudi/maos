"""
Unit tests for skills module.
"""

from unittest.mock import MagicMock

import pytest

from maos.config.models import SkillConfig, SkillsetConfig
from maos.mcp.registry import MCPRegistry
from maos.skills.models import Skill, Skillset
from maos.skills.registry import SkillRegistry, SkillsetRegistry
from maos.tools.models import Tool
from maos.tools.registry import ToolRegistry


class TestSkillModels:
    """Tests for skill models."""

    def test_skill_creation(self):
        skill = Skill(
            name="research",
            tool_ids=["search", "summarize"],
            description="Research skill",
        )
        assert skill.name == "research"
        assert len(skill.tool_ids) == 2

    def test_skillset_creation(self):
        skillset = Skillset(
            name="researcher",
            skill_names=["research", "writing"],
            description="Research skillset",
        )
        assert skillset.name == "researcher"
        assert len(skillset.skill_names) == 2


class TestSkillRegistry:
    """Tests for SkillRegistry."""

    @pytest.fixture
    def tool_registry(self):
        """Tool registry with mock tools."""
        mcp_registry = MCPRegistry()
        registry = ToolRegistry(mcp_registry)

        # We can't easily add tools without MCP, so we use a mock
        mock_tool = MagicMock(spec=Tool)
        mock_tool.id = "search"

        # Manually add to internal store
        registry._tools["search"] = mock_tool
        return registry

    def test_build_from_configs(self, tool_registry):
        configs = {
            "research": SkillConfig(
                tools=["search"],
                description="Research skill",
            ),
        }

        registry = SkillRegistry(tool_registry)
        registry.build(configs)

        skill = registry.get("research")
        assert skill is not None
        assert skill.name == "research"

    def test_get_nonexistent(self, tool_registry):
        registry = SkillRegistry(tool_registry)
        assert registry.get("nonexistent") is None

    def test_list_skills(self, tool_registry):
        configs = {
            "a": SkillConfig(tools=["search"], description="A"),
            "b": SkillConfig(tools=["search"], description="B"),
        }

        registry = SkillRegistry(tool_registry)
        registry.build(configs)

        skills = registry.list_all()
        assert len(skills) == 2


class TestSkillsetRegistry:
    """Tests for SkillsetRegistry."""

    @pytest.fixture
    def registries(self):
        """Skill and tool registries."""
        mcp_registry = MCPRegistry()
        tool_registry = ToolRegistry(mcp_registry)

        # Add a mock tool
        mock_tool = MagicMock(spec=Tool)
        mock_tool.id = "search"
        tool_registry._tools["search"] = mock_tool

        skill_registry = SkillRegistry(tool_registry)
        skill_registry.build({
            "research": SkillConfig(tools=["search"], description="Research"),
        })

        return skill_registry, tool_registry

    def test_build_from_configs(self, registries):
        skill_registry, tool_registry = registries

        configs = {
            "researcher": SkillsetConfig(
                skills=["research"],
                description="Research skillset",
            ),
        }

        registry = SkillsetRegistry(skill_registry, tool_registry)
        registry.build(configs)

        skillset = registry.get("researcher")
        assert skillset is not None
        assert skillset.name == "researcher"

    def test_get_nonexistent(self, registries):
        skill_registry, tool_registry = registries
        registry = SkillsetRegistry(skill_registry, tool_registry)
        assert registry.get("nonexistent") is None

    def test_list_skillsets(self, registries):
        skill_registry, tool_registry = registries

        configs = {
            "a": SkillsetConfig(skills=["research"]),
            "b": SkillsetConfig(skills=["research"]),
        }

        registry = SkillsetRegistry(skill_registry, tool_registry)
        registry.build(configs)

        skillsets = registry.list_all()
        assert len(skillsets) == 2
