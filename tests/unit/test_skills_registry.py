"""Unit tests for skills registry and models."""

from unittest.mock import MagicMock

import pytest

from maos.config.models import SkillConfig, SkillsetConfig
from maos.skills.models import Skill, Skillset
from maos.skills.registry import SkillRegistry, SkillsetRegistry
from maos.tools.models import Tool
from maos.tools.registry import ToolRegistry


def _make_tool(tool_id: str, server: str = "s1") -> Tool:
    """Create a tool with the given ID."""
    return Tool(
        id=tool_id,
        name=tool_id,
        description=f"Tool {tool_id}",
        server=server,
        mcp_tool_name=tool_id,
    )


def _make_tool_registry(*tool_ids: str) -> ToolRegistry:
    """Create a ToolRegistry pre-populated with tools."""
    mcp_reg = MagicMock()
    registry = ToolRegistry(mcp_reg)
    for tid in tool_ids:
        registry.register(_make_tool(tid))
    return registry


@pytest.mark.unit
class TestSkillModel:
    """Tests for the Skill data model."""

    def test_skill_creation(self):
        """Test basic skill creation."""
        skill = Skill(name="search", description="Search skill", tool_ids=["t1", "t2"])
        assert skill.name == "search"
        assert skill.description == "Search skill"
        assert skill.tool_ids == ["t1", "t2"]

    def test_skill_default_values(self):
        """Test skill with default values."""
        skill = Skill(name="empty")
        assert skill.description == ""
        assert skill.tool_ids == []

    def test_get_tools_resolves_existing(self):
        """Test get_tools resolves tool IDs to Tool objects."""
        tool_reg = _make_tool_registry("t1", "t2", "t3")
        skill = Skill(name="s", tool_ids=["t1", "t3"])

        tools = skill.get_tools(tool_reg)
        assert len(tools) == 2
        assert {t.id for t in tools} == {"t1", "t3"}

    def test_get_tools_skips_missing(self):
        """Test get_tools silently skips missing tools."""
        tool_reg = _make_tool_registry("t1")
        skill = Skill(name="s", tool_ids=["t1", "missing_tool"])

        tools = skill.get_tools(tool_reg)
        assert len(tools) == 1
        assert tools[0].id == "t1"


@pytest.mark.unit
class TestSkillsetModel:
    """Tests for the Skillset data model."""

    def test_skillset_creation(self):
        """Test basic skillset creation."""
        ss = Skillset(name="research", description="Research skillset", skill_names=["s1", "s2"])
        assert ss.name == "research"
        assert ss.skill_names == ["s1", "s2"]

    def test_get_skills_resolves(self):
        """Test get_skills resolves skill names to Skill objects."""
        tool_reg = _make_tool_registry("t1", "t2")
        skill_reg = SkillRegistry(tool_reg)
        skill_reg.register(Skill(name="s1", tool_ids=["t1"]))
        skill_reg.register(Skill(name="s2", tool_ids=["t2"]))

        ss = Skillset(name="all", skill_names=["s1", "s2"])
        skills = ss.get_skills(skill_reg)
        assert len(skills) == 2

    def test_get_skills_skips_missing(self):
        """Test get_skills silently skips missing skills."""
        tool_reg = _make_tool_registry()
        skill_reg = SkillRegistry(tool_reg)
        skill_reg.register(Skill(name="s1", tool_ids=[]))

        ss = Skillset(name="partial", skill_names=["s1", "nonexistent"])
        skills = ss.get_skills(skill_reg)
        assert len(skills) == 1

    def test_get_all_tools(self):
        """Test get_all_tools collects tools across all skills."""
        tool_reg = _make_tool_registry("t1", "t2", "t3")
        skill_reg = SkillRegistry(tool_reg)
        skill_reg.register(Skill(name="s1", tool_ids=["t1", "t2"]))
        skill_reg.register(Skill(name="s2", tool_ids=["t2", "t3"]))

        ss = Skillset(name="all", skill_names=["s1", "s2"])
        tools = ss.get_all_tools(skill_reg, tool_reg)

        # Should deduplicate t2
        assert len(tools) == 3
        assert {t.id for t in tools} == {"t1", "t2", "t3"}

    def test_get_all_tool_ids(self):
        """Test get_all_tool_ids collects unique tool IDs."""
        tool_reg = _make_tool_registry("t1", "t2")
        skill_reg = SkillRegistry(tool_reg)
        skill_reg.register(Skill(name="s1", tool_ids=["t1", "t2"]))
        skill_reg.register(Skill(name="s2", tool_ids=["t2"]))

        ss = Skillset(name="all", skill_names=["s1", "s2"])
        ids = ss.get_all_tool_ids(skill_reg)
        assert set(ids) == {"t1", "t2"}


@pytest.mark.unit
class TestSkillRegistry:
    """Tests for SkillRegistry."""

    def test_init_empty(self):
        """Test empty skill registry."""
        tool_reg = _make_tool_registry()
        reg = SkillRegistry(tool_reg)
        assert len(reg) == 0
        assert reg.list_all() == []

    def test_build_from_config(self):
        """Test building skills from config."""
        tool_reg = _make_tool_registry("t1", "t2")
        reg = SkillRegistry(tool_reg)

        configs = {
            "search": SkillConfig(tools=["t1"], description="Search"),
            "write": SkillConfig(tools=["t2"], description="Write"),
        }
        reg.build(configs)

        assert len(reg) == 2
        assert "search" in reg
        assert "write" in reg

    def test_build_with_missing_tools_still_builds(self):
        """Test that missing tool references produce a warning but skill is still created."""
        tool_reg = _make_tool_registry()  # No tools
        reg = SkillRegistry(tool_reg)

        configs = {"bad_skill": SkillConfig(tools=["missing_tool"], description="bad")}
        reg.build(configs)

        # Skill should still be registered
        assert len(reg) == 1
        assert "bad_skill" in reg

    def test_get_returns_none_for_missing(self):
        """Test get returns None for non-existent skill."""
        reg = SkillRegistry(_make_tool_registry())
        assert reg.get("nope") is None

    def test_get_or_raise_raises(self):
        """Test get_or_raise raises KeyError for missing skill."""
        reg = SkillRegistry(_make_tool_registry())
        with pytest.raises(KeyError, match="Skill not found"):
            reg.get_or_raise("nope")

    def test_register_skill(self):
        """Test registering a pre-built skill."""
        reg = SkillRegistry(_make_tool_registry("t1"))
        skill = Skill(name="manual", tool_ids=["t1"])
        reg.register(skill)

        assert reg.get("manual") is skill

    def test_get_tools_for_skill(self):
        """Test resolving tools through skill registry."""
        tool_reg = _make_tool_registry("t1", "t2")
        reg = SkillRegistry(tool_reg)
        reg.register(Skill(name="s", tool_ids=["t1", "t2"]))

        tools = reg.get_tools_for_skill("s")
        assert len(tools) == 2

    def test_get_tools_for_missing_skill(self):
        """Test get_tools_for_skill returns empty for missing skill."""
        reg = SkillRegistry(_make_tool_registry())
        assert reg.get_tools_for_skill("nonexistent") == []

    def test_find_skills_with_tool(self):
        """Test finding skills that contain a specific tool."""
        tool_reg = _make_tool_registry("t1", "t2")
        reg = SkillRegistry(tool_reg)
        reg.register(Skill(name="s1", tool_ids=["t1", "t2"]))
        reg.register(Skill(name="s2", tool_ids=["t2"]))
        reg.register(Skill(name="s3", tool_ids=["t1"]))

        skills = reg.find_skills_with_tool("t2")
        assert len(skills) == 2
        assert {s.name for s in skills} == {"s1", "s2"}

    def test_list_names(self):
        """Test listing all skill names."""
        tool_reg = _make_tool_registry("t1")
        reg = SkillRegistry(tool_reg)
        reg.register(Skill(name="a", tool_ids=["t1"]))
        reg.register(Skill(name="b", tool_ids=["t1"]))

        assert set(reg.list_names()) == {"a", "b"}


@pytest.mark.unit
class TestSkillsetRegistry:
    """Tests for SkillsetRegistry."""

    def _setup_registries(self):
        """Create tool, skill, and skillset registries with test data."""
        tool_reg = _make_tool_registry("t1", "t2", "t3")
        skill_reg = SkillRegistry(tool_reg)
        skill_reg.register(Skill(name="search", tool_ids=["t1"]))
        skill_reg.register(Skill(name="write", tool_ids=["t2", "t3"]))
        ss_reg = SkillsetRegistry(skill_reg, tool_reg)
        return tool_reg, skill_reg, ss_reg

    def test_init_empty(self):
        """Test empty skillset registry."""
        _, skill_reg, ss_reg = self._setup_registries()
        assert len(ss_reg) == 0
        assert ss_reg.list_all() == []

    def test_build_from_config(self):
        """Test building skillsets from config."""
        _, skill_reg, ss_reg = self._setup_registries()
        configs = {
            "research": SkillsetConfig(skills=["search", "write"], description="Research"),
        }
        ss_reg.build(configs)

        assert len(ss_reg) == 1
        assert "research" in ss_reg

    def test_build_with_missing_skills_still_builds(self):
        """Test that missing skill references produce warning but skillset is still created."""
        _, skill_reg, ss_reg = self._setup_registries()
        configs = {
            "broken": SkillsetConfig(skills=["nonexistent"], description="Broken"),
        }
        ss_reg.build(configs)
        assert "broken" in ss_reg

    def test_get_returns_none_for_missing(self):
        """Test get returns None for non-existent skillset."""
        _, _, ss_reg = self._setup_registries()
        assert ss_reg.get("nope") is None

    def test_get_or_raise_raises(self):
        """Test get_or_raise raises KeyError for missing skillset."""
        _, _, ss_reg = self._setup_registries()
        with pytest.raises(KeyError, match="Skillset not found"):
            ss_reg.get_or_raise("nope")

    def test_register_skillset(self):
        """Test registering a pre-built skillset."""
        _, _, ss_reg = self._setup_registries()
        ss = Skillset(name="custom", skill_names=["search"])
        ss_reg.register(ss)
        assert ss_reg.get("custom") is ss

    def test_get_all_tools(self):
        """Test getting all tools for a skillset."""
        _, skill_reg, ss_reg = self._setup_registries()
        ss_reg.register(Skillset(name="all", skill_names=["search", "write"]))

        tools = ss_reg.get_all_tools("all")
        assert len(tools) == 3
        assert {t.id for t in tools} == {"t1", "t2", "t3"}

    def test_get_all_tools_missing_skillset(self):
        """Test get_all_tools returns empty for missing skillset."""
        _, _, ss_reg = self._setup_registries()
        assert ss_reg.get_all_tools("nonexistent") == []

    def test_get_skill_names(self):
        """Test get_skill_names returns skill list."""
        _, _, ss_reg = self._setup_registries()
        ss_reg.register(Skillset(name="rs", skill_names=["search", "write"]))
        assert ss_reg.get_skill_names("rs") == ["search", "write"]

    def test_get_skill_names_missing_skillset(self):
        """Test get_skill_names returns empty for missing skillset."""
        _, _, ss_reg = self._setup_registries()
        assert ss_reg.get_skill_names("nonexistent") == []

    def test_list_names(self):
        """Test listing all skillset names."""
        _, _, ss_reg = self._setup_registries()
        ss_reg.register(Skillset(name="a", skill_names=[]))
        ss_reg.register(Skillset(name="b", skill_names=[]))
        assert set(ss_reg.list_names()) == {"a", "b"}

    def test_full_chain_resolution(self):
        """Test the full chain: skillset -> skill -> tool resolution."""
        tool_reg = _make_tool_registry("calc", "search", "format")
        skill_reg = SkillRegistry(tool_reg)
        skill_reg.register(Skill(name="math", tool_ids=["calc"]))
        skill_reg.register(Skill(name="research", tool_ids=["search"]))
        skill_reg.register(Skill(name="output", tool_ids=["format"]))

        ss_reg = SkillsetRegistry(skill_reg, tool_reg)
        ss_reg.register(Skillset(name="analyst", skill_names=["math", "research", "output"]))

        tools = ss_reg.get_all_tools("analyst")
        assert len(tools) == 3
        assert {t.id for t in tools} == {"calc", "search", "format"}
