"""
Integration tests for the MCP → Tools → Skills → Skillsets chain.

These tests verify the complete tool materialization pipeline WITHOUT
requiring LLM API keys. They test:
1. MCP server connection
2. Tool materialization from MCP
3. Skill building with tools
4. Skillset resolution to tools

Run with: python -m pytest tests/integration/test_toolchain.py -v -s
"""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "e2e" / "fixtures"
TEST_CONFIG = FIXTURES_DIR / "test_config.yaml"


class TestMCPToolChain:
    """Tests for MCP → Tools → Skills → Skillsets pipeline."""

    @pytest.mark.asyncio
    async def test_full_toolchain_initialization(self):
        """Test the complete toolchain initialization."""
        from maos.config.loader import ConfigLoader
        from maos.mcp.registry import MCPRegistry
        from maos.skills.registry import SkillRegistry, SkillsetRegistry
        from maos.tools.registry import ToolRegistry

        # Load configuration
        loader = ConfigLoader()
        config = loader.load(str(TEST_CONFIG))

        print("\n=== Configuration Loaded ===")
        print(f"MCP Servers: {list(config.mcp_servers.keys())}")
        print(f"Tools: {list(config.tools.keys())}")
        print(f"Skills: {list(config.skills.keys())}")
        print(f"Skillsets: {list(config.skillsets.keys())}")
        print(f"Agents: {list(config.agents.keys())}")

        # Initialize MCP registry
        mcp_registry = MCPRegistry()
        for name, server_config in config.mcp_servers.items():
            await mcp_registry.register(name, server_config)
            print(f"Registered MCP server: {name}")

        # Connect to MCP servers
        await mcp_registry.connect_all()
        print("\n=== MCP Servers Connected ===")

        # Verify connection
        connection = mcp_registry.get_connection("test_tools")
        assert connection is not None, "test_tools MCP server should be connected"
        print("Connection to test_tools: OK")

        # List tools from MCP server
        print(f"MCP tools available: {[t.name for t in connection.tools]}")

        # Initialize Tool registry and materialize
        tool_registry = ToolRegistry(mcp_registry=mcp_registry)
        await tool_registry.materialize(config.tools)
        print("\n=== Tools Materialized ===")

        # Verify tools
        for tool_id in config.tools.keys():
            tool = tool_registry.get(tool_id)
            assert tool is not None, f"Tool '{tool_id}' should be materialized"
            print(f"Tool: {tool_id} -> {tool.name} (server: {tool.server})")

        # Initialize Skills
        skill_registry = SkillRegistry(tool_registry=tool_registry)
        skill_registry.build(config.skills)
        print("\n=== Skills Built ===")

        for skill_name in config.skills.keys():
            skill = skill_registry.get(skill_name)
            assert skill is not None, f"Skill '{skill_name}' should exist"
            tools = skill.get_tools(tool_registry)
            print(f"Skill: {skill_name} -> tools: {[t.name for t in tools]}")

        # Initialize Skillsets
        skillset_registry = SkillsetRegistry(
            skill_registry=skill_registry,
            tool_registry=tool_registry
        )
        skillset_registry.build(config.skillsets)
        print("\n=== Skillsets Built ===")

        for skillset_name in config.skillsets.keys():
            skillset = skillset_registry.get(skillset_name)
            assert skillset is not None, f"Skillset '{skillset_name}' should exist"
            tools = skillset_registry.get_all_tools(skillset_name)
            print(f"Skillset: {skillset_name} -> tools: {[t.name for t in tools]}")

        # Verify specific skillset->skill->tool chain
        print("\n=== Verifying Skillset Chains ===")

        # time_and_math skillset should have get_current_time and calculate
        time_math_tools = skillset_registry.get_all_tools("time_and_math")
        time_math_names = [t.name for t in time_math_tools]
        assert "get_current_time" in time_math_names, "time_and_math should have get_current_time"
        assert "calculate" in time_math_names, "time_and_math should have calculate"
        print(f"time_and_math: {time_math_names} ✓")

        # full_access should have all 4 tools
        full_access_tools = skillset_registry.get_all_tools("full_access")
        full_access_names = [t.name for t in full_access_tools]
        assert len(full_access_names) == 4, f"full_access should have 4 tools, got {len(full_access_names)}"
        print(f"full_access: {full_access_names} ✓")

        # Cleanup
        await mcp_registry.disconnect_all()
        print("\n=== Test Complete ===")

    @pytest.mark.asyncio
    async def test_tool_invocation_via_mcp(self):
        """Test that tools can actually be invoked via MCP."""
        from maos.config.loader import ConfigLoader
        from maos.mcp.registry import MCPRegistry
        from maos.tools.registry import ToolRegistry

        # Load configuration
        loader = ConfigLoader()
        config = loader.load(str(TEST_CONFIG))

        # Initialize and connect MCP
        mcp_registry = MCPRegistry()
        for name, server_config in config.mcp_servers.items():
            await mcp_registry.register(name, server_config)
        await mcp_registry.connect_all()

        # Materialize tools
        tool_registry = ToolRegistry(mcp_registry=mcp_registry)
        await tool_registry.materialize(config.tools)

        print("\n=== Testing Tool Invocation ===")

        # Test calculator tool
        calc_tool = tool_registry.get("calculator")
        assert calc_tool is not None, "calculator tool should exist"

        result = await calc_tool.call({"expression": "10 + 20"})
        print(f"Calculator result: {result}")
        assert "30" in str(result), f"Expected '30' in result, got: {result}"

        # Test echo tool
        echo_tool = tool_registry.get("echo_tool")
        assert echo_tool is not None, "echo_tool should exist"

        result = await echo_tool.call({"message": "Hello Test"})
        print(f"Echo result: {result}")
        assert "Hello Test" in str(result), f"Expected 'Hello Test' in result, got: {result}"

        # Test file reader tool
        file_tool = tool_registry.get("file_reader")
        assert file_tool is not None, "file_reader tool should exist"

        result = await file_tool.call({"filename": "test.txt"})
        print(f"File reader result: {result}")
        assert "test file" in str(result).lower(), f"Expected 'test file' in result, got: {result}"

        # Cleanup
        await mcp_registry.disconnect_all()
        print("\n=== Tool Invocation Complete ===")

    @pytest.mark.asyncio
    async def test_agent_tool_ids_from_skillset(self):
        """Test that agents get correct tool IDs from their skillsets."""
        from maos.agents.factory import AgentFactory
        from maos.config.loader import ConfigLoader
        from maos.llm.registry import LLMRegistry
        from maos.mcp.registry import MCPRegistry
        from maos.skills.registry import SkillRegistry, SkillsetRegistry
        from maos.tools.registry import ToolRegistry

        # Load configuration
        loader = ConfigLoader()
        config = loader.load(str(TEST_CONFIG))

        # Initialize MCP and connect
        mcp_registry = MCPRegistry()
        for name, server_config in config.mcp_servers.items():
            await mcp_registry.register(name, server_config)
        await mcp_registry.connect_all()

        # Initialize Tool registry
        tool_registry = ToolRegistry(mcp_registry=mcp_registry)
        await tool_registry.materialize(config.tools)

        # Initialize Skills and Skillsets
        skill_registry = SkillRegistry(tool_registry=tool_registry)
        skill_registry.build(config.skills)

        skillset_registry = SkillsetRegistry(
            skill_registry=skill_registry,
            tool_registry=tool_registry
        )
        skillset_registry.build(config.skillsets)

        # Mock LLM registry (we don't need real LLMs for this test)
        llm_registry = LLMRegistry()

        # Initialize Agent factory
        agent_factory = AgentFactory(
            llm_registry=llm_registry,
            skillset_registry=skillset_registry,
            skill_registry=skill_registry,
            tool_registry=tool_registry
        )

        print("\n=== Testing Agent Tool IDs ===")

        # Test analyst agent (should have time_and_math skillset)
        analyst_config = config.agents["analyst"]
        analyst = agent_factory.create_worker("analyst", analyst_config)
        print(f"Analyst skillset: {analyst.skillset}")
        print(f"Analyst tool_ids: {analyst.tool_ids}")

        assert analyst.skillset == "time_and_math"
        assert "current_time" in analyst.tool_ids, "analyst should have current_time"
        assert "calculator" in analyst.tool_ids, "analyst should have calculator"
        assert len(analyst.tool_ids) == 2, f"analyst should have 2 tools, got {len(analyst.tool_ids)}"

        # Test researcher agent (should have file_access skillset)
        researcher_config = config.agents["researcher"]
        researcher = agent_factory.create_worker("researcher", researcher_config)
        print(f"\nResearcher skillset: {researcher.skillset}")
        print(f"Researcher tool_ids: {researcher.tool_ids}")

        assert researcher.skillset == "file_access"
        assert "file_reader" in researcher.tool_ids, "researcher should have file_reader"

        # Test assistant agent (should have full_access skillset - all tools)
        assistant_config = config.agents["assistant"]
        assistant = agent_factory.create_worker("assistant", assistant_config)
        print(f"\nAssistant skillset: {assistant.skillset}")
        print(f"Assistant tool_ids: {assistant.tool_ids}")

        assert assistant.skillset == "full_access"
        assert len(assistant.tool_ids) == 4, f"assistant should have 4 tools, got {len(assistant.tool_ids)}"

        # Cleanup
        await mcp_registry.disconnect_all()
        print("\n=== Agent Tool IDs Test Complete ===")


class TestToolInvocationResults:
    """Tests for verifying tool results match expectations."""

    @pytest.mark.asyncio
    async def test_calculator_expressions(self):
        """Test various calculator expressions."""
        from maos.config.loader import ConfigLoader
        from maos.mcp.registry import MCPRegistry
        from maos.tools.registry import ToolRegistry

        loader = ConfigLoader()
        config = loader.load(str(TEST_CONFIG))

        mcp_registry = MCPRegistry()
        for name, server_config in config.mcp_servers.items():
            await mcp_registry.register(name, server_config)
        await mcp_registry.connect_all()

        tool_registry = ToolRegistry(mcp_registry=mcp_registry)
        await tool_registry.materialize(config.tools)

        calc = tool_registry.get("calculator")

        print("\n=== Testing Calculator Expressions ===")

        test_cases = [
            ("1 + 1", "2"),
            ("10 * 5", "50"),
            ("100 / 4", "25"),
            ("2 ** 3", "8"),
            ("(3 + 5) * 2", "16"),
        ]

        for expression, expected in test_cases:
            result = await calc.call({"expression": expression})
            result_str = str(result)
            assert expected in result_str, f"Expression '{expression}' should result in '{expected}', got: {result_str}"
            print(f"  {expression} = {expected} ✓")

        await mcp_registry.disconnect_all()
        print("=== Calculator Tests Complete ===")

    @pytest.mark.asyncio
    async def test_file_reader_files(self):
        """Test file reader with different files."""
        from maos.config.loader import ConfigLoader
        from maos.mcp.registry import MCPRegistry
        from maos.tools.registry import ToolRegistry

        loader = ConfigLoader()
        config = loader.load(str(TEST_CONFIG))

        mcp_registry = MCPRegistry()
        for name, server_config in config.mcp_servers.items():
            await mcp_registry.register(name, server_config)
        await mcp_registry.connect_all()

        tool_registry = ToolRegistry(mcp_registry=mcp_registry)
        await tool_registry.materialize(config.tools)

        reader = tool_registry.get("file_reader")

        print("\n=== Testing File Reader ===")

        # Test existing files
        test_files = [
            ("test.txt", "test file content"),
            ("data.json", "key"),
            ("readme.md", "test readme"),
        ]

        for filename, expected_content in test_files:
            result = await reader.call({"filename": filename})
            result_str = str(result).lower()
            assert expected_content.lower() in result_str, \
                f"File '{filename}' should contain '{expected_content}', got: {result_str}"
            print(f"  {filename}: contains '{expected_content}' ✓")

        # Test non-existent file
        result = await reader.call({"filename": "nonexistent.xyz"})
        result_str = str(result).lower()
        assert "not found" in result_str, f"Non-existent file should say 'not found', got: {result_str}"
        print("  nonexistent.xyz: 'not found' ✓")

        await mcp_registry.disconnect_all()
        print("=== File Reader Tests Complete ===")
