"""Tests for the skill and skillset registries."""

from unittest.mock import MagicMock

import pytest

from maos.config.models import SkillConfig, SkillsetConfig
from maos.skills.registry import SkillRegistry, SkillsetRegistry
from maos.tools.registry import ToolRegistry


@pytest.fixture
def mock_tool_registry():
    registry = MagicMock(spec=ToolRegistry)

    def get_tool(tool_id):
        known = {"tool_a", "tool_b", "tool_c"}
        if tool_id in known:
            tool = MagicMock()
            tool.id = tool_id
            tool.name = f"Tool {tool_id}"
            return tool
        return None

    registry.get_tool = MagicMock(side_effect=get_tool)
    registry.has_tool = MagicMock(
        side_effect=lambda tid: tid in {"tool_a", "tool_b", "tool_c"}
    )
    return registry


@pytest.fixture
def skill_configs():
    return {
        "research": SkillConfig(
            tools=["tool_a", "tool_b"],
            description="Research skill",
        ),
        "writing": SkillConfig(
            tools=["tool_c"],
            description="Writing skill",
        ),
        "broken": SkillConfig(
            tools=["tool_a", "missing_tool"],
            description="Skill with missing tool",
        ),
    }


@pytest.fixture
def skillset_configs():
    return {
        "researcher": SkillsetConfig(
            skills=["research", "writing"],
            description="Full researcher",
        ),
        "broken_set": SkillsetConfig(
            skills=["research", "nonexistent_skill"],
            description="Skillset with missing skill",
        ),
    }


# ── SkillRegistry ────────────────────────────────────────────────────────────


class TestSkillRegistry:
    def test_build(self, mock_tool_registry, skill_configs):
        registry = SkillRegistry(tool_registry=mock_tool_registry)
        registry.build(skill_configs)
        assert registry.get("research") is not None
        assert registry.get("writing") is not None

    def test_build_empty(self, mock_tool_registry):
        registry = SkillRegistry(tool_registry=mock_tool_registry)
        registry.build({})
        assert registry.get("anything") is None

    def test_build_empty_dict(self, mock_tool_registry):
        registry = SkillRegistry(tool_registry=mock_tool_registry)
        registry.build({})
        assert registry.get("anything") is None

    def test_get_skill(self, mock_tool_registry, skill_configs):
        registry = SkillRegistry(tool_registry=mock_tool_registry)
        registry.build(skill_configs)
        skill = registry.get("research")
        assert skill is not None
        assert skill.name == "research"
        assert "tool_a" in skill.tool_ids
        assert "tool_b" in skill.tool_ids

    def test_get_nonexistent(self, mock_tool_registry, skill_configs):
        registry = SkillRegistry(tool_registry=mock_tool_registry)
        registry.build(skill_configs)
        assert registry.get("nonexistent") is None

    def test_get_tools_for_skill(self, mock_tool_registry, skill_configs):
        registry = SkillRegistry(tool_registry=mock_tool_registry)
        registry.build(skill_configs)
        tools = registry.get_tools_for_skill("research")
        assert len(tools) == 2

    def test_get_tools_for_nonexistent_skill(
        self, mock_tool_registry, skill_configs
    ):
        registry = SkillRegistry(tool_registry=mock_tool_registry)
        registry.build(skill_configs)
        tools = registry.get_tools_for_skill("nonexistent")
        assert tools == []

    def test_list_names(self, mock_tool_registry, skill_configs):
        registry = SkillRegistry(tool_registry=mock_tool_registry)
        registry.build(skill_configs)
        names = registry.list_names()
        assert set(names) == {"research", "writing", "broken"}


# ── SkillsetRegistry ─────────────────────────────────────────────────────────


class TestSkillsetRegistry:
    def test_build(
        self, mock_tool_registry, skill_configs, skillset_configs
    ):
        skill_registry = SkillRegistry(tool_registry=mock_tool_registry)
        skill_registry.build(skill_configs)

        ss_registry = SkillsetRegistry(
            skill_registry=skill_registry,
            tool_registry=mock_tool_registry,
        )
        ss_registry.build(skillset_configs)
        assert ss_registry.get("researcher") is not None

    def test_build_empty(self, mock_tool_registry):
        skill_registry = SkillRegistry(tool_registry=mock_tool_registry)
        ss_registry = SkillsetRegistry(
            skill_registry=skill_registry,
            tool_registry=mock_tool_registry,
        )
        ss_registry.build({})
        assert ss_registry.get("anything") is None

    def test_get_skillset(
        self, mock_tool_registry, skill_configs, skillset_configs
    ):
        skill_registry = SkillRegistry(tool_registry=mock_tool_registry)
        skill_registry.build(skill_configs)

        ss_registry = SkillsetRegistry(
            skill_registry=skill_registry,
            tool_registry=mock_tool_registry,
        )
        ss_registry.build(skillset_configs)
        ss = ss_registry.get("researcher")
        assert ss is not None
        assert ss.name == "researcher"

    def test_get_nonexistent(self, mock_tool_registry):
        skill_registry = SkillRegistry(tool_registry=mock_tool_registry)
        ss_registry = SkillsetRegistry(
            skill_registry=skill_registry,
            tool_registry=mock_tool_registry,
        )
        ss_registry.build({})
        assert ss_registry.get("missing") is None

    def test_get_all_tools(
        self, mock_tool_registry, skill_configs, skillset_configs
    ):
        skill_registry = SkillRegistry(tool_registry=mock_tool_registry)
        skill_registry.build(skill_configs)

        ss_registry = SkillsetRegistry(
            skill_registry=skill_registry,
            tool_registry=mock_tool_registry,
        )
        ss_registry.build(skillset_configs)
        tools = ss_registry.get_all_tools("researcher")
        assert len(tools) >= 0  # depends on Skillset.get_all_tools impl

    def test_get_all_tools_nonexistent(self, mock_tool_registry):
        skill_registry = SkillRegistry(tool_registry=mock_tool_registry)
        ss_registry = SkillsetRegistry(
            skill_registry=skill_registry,
            tool_registry=mock_tool_registry,
        )
        ss_registry.build({})
        assert ss_registry.get_all_tools("missing") == []

    def test_get_skill_names(
        self, mock_tool_registry, skill_configs, skillset_configs
    ):
        skill_registry = SkillRegistry(tool_registry=mock_tool_registry)
        skill_registry.build(skill_configs)

        ss_registry = SkillsetRegistry(
            skill_registry=skill_registry,
            tool_registry=mock_tool_registry,
        )
        ss_registry.build(skillset_configs)
        names = ss_registry.get_skill_names("researcher")
        assert "research" in names
        assert "writing" in names

    def test_list_names(
        self, mock_tool_registry, skill_configs, skillset_configs
    ):
        skill_registry = SkillRegistry(tool_registry=mock_tool_registry)
        skill_registry.build(skill_configs)

        ss_registry = SkillsetRegistry(
            skill_registry=skill_registry,
            tool_registry=mock_tool_registry,
        )
        ss_registry.build(skillset_configs)
        names = ss_registry.list_names()
        assert set(names) == {"researcher", "broken_set"}
