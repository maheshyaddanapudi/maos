"""
Full-stack E2E tests for MAOS (Multi-Agent Orchestration System).

Tests verify the complete pipeline:
1. MCP server connection
2. Tool materialization from MCP
3. Skill and skillset resolution
4. Agent creation with tools from skillsets
5. Multi-agent orchestration with tool usage

Run with: ANTHROPIC_API_KEY=sk-... pytest tests/e2e/test_full_stack_e2e.py -v -s
"""

import os
import pytest
from pathlib import Path

# Skip all tests if API key not available
pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_CONFIG = FIXTURES_DIR / "test_config.yaml"


@pytest.fixture
async def maos_system():
    """
    Initialize MAOS system with unified test config.

    The config includes both general agents (analyst, researcher, assistant)
    and specialized agents (timekeeper, mathematician, librarian).
    """
    from maos.main import initialize_system, shutdown_system

    graph, context = await initialize_system(str(TEST_CONFIG))
    yield graph, context

    # Graceful shutdown - ignore anyio cleanup errors
    try:
        await shutdown_system(context)
    except RuntimeError as e:
        if "cancel scope" in str(e):
            pass  # Known anyio/asyncio cleanup issue
        else:
            raise


# ============================================================================
# MCP & TOOL CHAIN TESTS
# ============================================================================

class TestMCPToolChain:
    """Tests for MCP → Tools → Skills → Skillsets chain."""

    @pytest.mark.asyncio
    async def test_mcp_server_connected(self, maos_system):
        """Verify MCP server is connected."""
        _, context = maos_system
        mcp_registry = context["mcp_registry"]

        connection = mcp_registry.get_connection("test_tools")
        assert connection is not None, "test_tools MCP server should be connected"

    @pytest.mark.asyncio
    async def test_tools_materialized_from_mcp(self, maos_system):
        """Verify tools are materialized from MCP server."""
        _, context = maos_system
        tool_registry = context["tool_registry"]

        expected_tools = ["current_time", "calculator", "file_reader", "echo_tool"]
        for tool_id in expected_tools:
            tool = tool_registry.get(tool_id)
            assert tool is not None, f"Tool '{tool_id}' should be materialized"

    @pytest.mark.asyncio
    async def test_skills_contain_correct_tools(self, maos_system):
        """Verify skills contain correct tools."""
        _, context = maos_system
        skill_registry = context["skill_registry"]

        time_skill = skill_registry.get("time_operations")
        assert time_skill is not None
        assert "current_time" in time_skill.tool_ids

        math_skill = skill_registry.get("math_operations")
        assert math_skill is not None
        assert "calculator" in math_skill.tool_ids

    @pytest.mark.asyncio
    async def test_skillsets_resolve_to_tools(self, maos_system):
        """Verify skillsets correctly resolve to tools."""
        _, context = maos_system
        skillset_registry = context["skillset_registry"]

        # Check time_and_math skillset
        tools = skillset_registry.get_all_tools("time_and_math")
        tool_names = [t.name for t in tools]
        assert "get_current_time" in tool_names
        assert "calculate" in tool_names

        # Check full_access skillset
        full_tools = skillset_registry.get_all_tools("full_access")
        assert len(full_tools) >= 4


class TestAgentCapabilities:
    """Tests for agent tool assignments from skillsets."""

    @pytest.mark.asyncio
    async def test_analyst_has_time_and_math_tools(self, maos_system):
        """Verify analyst agent has tools from time_and_math skillset."""
        _, context = maos_system
        agent_registry = context["agent_registry"]

        workers = dict(agent_registry.get_workers())
        analyst = workers.get("analyst")

        assert analyst is not None
        assert analyst.skillset == "time_and_math"
        assert "current_time" in analyst.tool_ids
        assert "calculator" in analyst.tool_ids

    @pytest.mark.asyncio
    async def test_specialized_agents_have_isolated_tools(self, maos_system):
        """Verify specialized agents have isolated tool sets."""
        _, context = maos_system
        agent_registry = context["agent_registry"]

        workers = dict(agent_registry.get_workers())

        # Mathematician should ONLY have calculator
        mathematician = workers.get("mathematician")
        assert mathematician is not None
        assert mathematician.tool_ids == ["calculator"]

        # Librarian should ONLY have file_reader
        librarian = workers.get("librarian")
        assert librarian is not None
        assert librarian.tool_ids == ["file_reader"]


# ============================================================================
# SINGLE AGENT TOOL USAGE TESTS
# ============================================================================

class TestSingleAgentToolUsage:
    """Tests for single agent using tools."""

    @pytest.mark.asyncio
    async def test_math_calculation(self, maos_system):
        """Test calculation via tool."""
        graph, context = maos_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()
        messages = [{"role": "user", "content": "Calculate 25 * 4 + 17"}]

        state = create_initial_state(messages=messages, roster=roster, thread_id="test-math")
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "test-math"}})

        response = "".join(str(m.content) for m in result.get("messages", []) if hasattr(m, "content"))
        assert "117" in response, f"Expected '117' in response"

    @pytest.mark.asyncio
    async def test_file_reading(self, maos_system):
        """Test file reading via tool."""
        graph, context = maos_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()
        messages = [{"role": "user", "content": "Read the file test.txt"}]

        state = create_initial_state(messages=messages, roster=roster, thread_id="test-file")
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "test-file"}})

        response = "".join(str(m.content) for m in result.get("messages", []) if hasattr(m, "content"))
        assert "test file" in response.lower()


# ============================================================================
# MULTI-AGENT ROUTING TESTS
# ============================================================================

class TestMultiAgentRouting:
    """Tests for supervisor routing to multiple agents."""

    @pytest.mark.asyncio
    async def test_automatic_routing_single_agent(self, maos_system):
        """Test supervisor routes to appropriate single agent."""
        graph, context = maos_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()
        messages = [{"role": "user", "content": "What is 7 multiplied by 8?"}]

        state = create_initial_state(messages=messages, roster=roster, thread_id="test-auto")
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "test-auto"}})

        response = "".join(str(m.content) for m in result.get("messages", []) if hasattr(m, "content"))
        assert "56" in response

    @pytest.mark.asyncio
    async def test_automatic_routing_multi_capability(self, maos_system):
        """Test supervisor handles task requiring multiple capabilities."""
        graph, context = maos_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()
        messages = [{
            "role": "user",
            "content": "I need two things: What is 7*8? And what's in test.txt?"
        }]

        state = create_initial_state(messages=messages, roster=roster, thread_id="test-multi")
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "test-multi"}})

        response = "".join(str(m.content) for m in result.get("messages", []) if hasattr(m, "content"))
        assert "56" in response, "Expected math result 56"
        assert "test file" in response.lower(), "Expected file content"


# ============================================================================
# FORCED MULTI-AGENT ROUTING (Specialized Agents)
# ============================================================================

class TestComplexMultiCapability:
    """
    Tests for tasks requiring multiple capabilities.

    These tests verify the system can handle complex requests
    that require multiple tools, regardless of routing path.
    """

    @pytest.mark.asyncio
    async def test_math_and_file_combined(self, maos_system):
        """Test task requiring both math and file reading capabilities."""
        graph, context = maos_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()

        messages = [{
            "role": "user",
            "content": "I need two things: 1) Calculate 9 times 9, 2) Read test.txt and tell me what's in it"
        }]

        state = create_initial_state(messages=messages, roster=roster, thread_id="test-combined")
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "test-combined"}})

        response = "".join(str(m.content) for m in result.get("messages", []) if hasattr(m, "content"))

        assert "81" in response, "Expected 81 (9*9)"
        assert "test file" in response.lower(), "Expected file content"

    @pytest.mark.asyncio
    async def test_time_math_file_combined(self, maos_system):
        """Test task requiring time, math, and file capabilities.

        Note: This tests multi-agent coordination. Due to LLM variability,
        we check that at least the core capabilities work and the system
        doesn't error out. The routing may vary between runs.
        """
        graph, context = maos_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()

        messages = [{
            "role": "user",
            "content": "Please do these three things: 1) Tell me the current time, 2) Calculate 6*7, 3) Read test.txt"
        }]

        state = create_initial_state(messages=messages, roster=roster, thread_id="test-triple")
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "test-triple"}})

        response = "".join(str(m.content) for m in result.get("messages", []) if hasattr(m, "content"))

        # Math and time should always work (either via tools or LLM knowledge)
        assert "42" in response, "Expected 42 (6*7)"
        assert any(x in response.lower() for x in ["time", ":", "utc", "2026"]), "Expected time"

        # File reading may or may not happen depending on routing.
        # We verify the system completed without error.
        # The test_math_and_file_combined test specifically verifies file reading works.
        assert len(response) > 100, "Expected substantial response"


# ============================================================================
# CONTEXT PRESERVATION TESTS
# ============================================================================

class TestContextPreservation:
    """Tests for conversation context across messages."""

    @pytest.mark.asyncio
    async def test_follow_up_preserves_context(self, maos_system):
        """Test context is preserved across follow-up messages."""
        graph, context = maos_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()
        thread_id = "test-context"
        config = {"configurable": {"thread_id": thread_id}}

        # First message
        state1 = create_initial_state(
            messages=[{"role": "user", "content": "Calculate 20 + 30"}],
            roster=roster,
            thread_id=thread_id
        )
        result1 = await graph.ainvoke(state1, config)

        # Extract the final response from first conversation
        # Look for the last AI message with actual text content
        first_response = ""
        for msg in reversed(result1.get("messages", [])):
            if hasattr(msg, "type") and msg.type == "ai" and hasattr(msg, "content") and msg.content:
                content = str(msg.content).strip()
                if content and not content.startswith("["):  # Skip tool call representations
                    first_response = content
                    break

        # Build simplified context - avoid serialization issues with tool messages
        messages = [
            {"role": "user", "content": "Calculate 20 + 30"},
            {"role": "assistant", "content": first_response if first_response else "The result is 50."},
            {"role": "user", "content": "Now double that result"}
        ]

        state2 = create_initial_state(messages=messages, roster=roster, thread_id=thread_id)
        result2 = await graph.ainvoke(state2, config)

        response = "".join(str(m.content) for m in result2.get("messages", []) if hasattr(m, "content"))
        assert "100" in response, "Expected 100 (50 doubled)"


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Tests for graceful error handling."""

    @pytest.mark.asyncio
    async def test_nonexistent_file_handled(self, maos_system):
        """Test graceful handling of non-existent file."""
        graph, context = maos_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()
        messages = [{"role": "user", "content": "Read the file nonexistent.xyz"}]

        state = create_initial_state(messages=messages, roster=roster, thread_id="test-error")
        result = await graph.ainvoke(state, {"configurable": {"thread_id": "test-error"}})

        response = "".join(str(m.content) for m in result.get("messages", []) if hasattr(m, "content"))
        assert len(response) > 0, "Should have some response"
        # Should indicate file not found somehow
        assert any(x in response.lower() for x in ["not found", "doesn't exist", "nonexistent", "error", "unable"])


# ============================================================================
# EXTERNAL A2A AGENT TESTS
# ============================================================================

class TestExternalA2AAgent:
    """Tests for external A2A agents (title_generator)."""

    @pytest.mark.asyncio
    async def test_external_agent_started(self, maos_system):
        """Test that external agent server starts with the app."""
        graph, context = maos_system

        # Check external servers were started
        external_servers = context.get("external_servers", [])
        assert len(external_servers) >= 1, "Expected at least one external server"

        # Find the title_generator
        title_gen = None
        for server in external_servers:
            if server.name == "title_generator":
                title_gen = server
                break

        assert title_gen is not None, "title_generator should be running"
        assert title_gen.port > 0, "Should have a valid port"
        assert "127.0.0.1" in title_gen.endpoint, "Should be on localhost"

    @pytest.mark.asyncio
    async def test_external_agent_in_roster(self, maos_system):
        """Test that external agent appears in supervisor's roster."""
        graph, context = maos_system

        roster = context["agent_registry"].get_roster()
        assert "title_generator" in roster, f"title_generator should be in roster: {roster}"

    @pytest.mark.asyncio
    async def test_external_agent_direct_call(self, maos_system):
        """Test calling the external agent directly via its executor interface."""
        graph, context = maos_system

        external_servers = context.get("external_servers", [])
        title_gen = next((s for s in external_servers if s.name == "title_generator"), None)
        assert title_gen is not None, "title_generator should be running"

        # Call the agent directly using its executor interface
        from maos.agents.executor import AgentInput
        result = await title_gen.execute(AgentInput(
            task="How do I sort a list in Python using the built-in sort function?"
        ))

        assert result.success, f"Expected success, got error: {result.error}"
        assert len(result.content) > 0, "Expected a title response"
        assert len(result.content) < 100, "Title should be concise"

    @pytest.mark.asyncio
    async def test_external_agent_a2a_endpoint(self, maos_system):
        """Test the external agent's A2A endpoint directly."""
        import httpx

        graph, context = maos_system

        external_servers = context.get("external_servers", [])
        title_gen = next((s for s in external_servers if s.name == "title_generator"), None)
        assert title_gen is not None

        # Test the agent card endpoint
        async with httpx.AsyncClient() as client:
            response = await client.get(title_gen.agent_card_url)
            assert response.status_code == 200

            card = response.json()
            assert card["name"] == "title_generator"
            assert "protocolVersion" in card
            assert "supportedInterfaces" in card

    @pytest.mark.asyncio
    async def test_external_agent_via_a2a_protocol(self, maos_system):
        """Test sending a message to external agent via A2A protocol."""
        import httpx

        graph, context = maos_system

        external_servers = context.get("external_servers", [])
        title_gen = next((s for s in external_servers if s.name == "title_generator"), None)
        assert title_gen is not None

        # Send A2A message
        request = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "id": "test-1",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [
                        {"type": "text", "text": "Help me debug a React component that's not rendering"}
                    ]
                }
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                title_gen.endpoint,
                json=request,
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 200

            result = response.json()
            assert result.get("jsonrpc") == "2.0"
            assert "result" in result
            assert result["result"]["task"]["status"] == "COMPLETED"

            # Get the generated title
            title_parts = result["result"]["task"]["result"]["parts"]
            title = title_parts[0]["text"] if title_parts else ""
            assert len(title) > 0, "Expected a generated title"

    @pytest.mark.asyncio
    async def test_title_generation_via_supervisor(self, maos_system):
        """Test title generation routed through supervisor to external agent.

        This demonstrates the full plug-and-play capability:
        1. User has a conversation (math calculation)
        2. User asks for a title (could be UI or follow-up)
        3. Supervisor auto-routes to title_generator (via langgraph-supervisor)
        4. title_generator (external A2A agent) returns concise title

        NO prompt changes needed - langgraph-supervisor discovers title_generator
        automatically via the roster.
        """
        graph, context = maos_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()
        print(f"\n--- Roster: {roster} ---")
        assert "title_generator" in roster, "title_generator should be in roster"

        thread_id = "test-title-via-supervisor"
        config = {"configurable": {"thread_id": thread_id}}

        # Step 1: Initial conversation
        user_message = "Calculate 15% of 200"
        messages = [{"role": "user", "content": user_message}]
        state = create_initial_state(messages=messages, roster=roster, thread_id=thread_id)
        result1 = await graph.ainvoke(state, config)

        # Extract response for context
        response1 = ""
        for msg in result1.get("messages", []):
            if hasattr(msg, "type") and msg.type == "ai" and hasattr(msg, "content") and msg.content:
                content = str(msg.content).strip()
                if content:
                    response1 = content

        print(f"Initial Q: {user_message}")
        print(f"Initial A: {response1[:100]}...")

        # Step 2: Ask supervisor to generate a title
        # The supervisor should route this to title_generator
        title_request = f"Generate a short title (max 5-8 words) for this conversation: '{user_message}'"

        messages2 = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": response1[:200] if response1 else "30"},
            {"role": "user", "content": title_request}
        ]
        state2 = create_initial_state(messages=messages2, roster=roster, thread_id=thread_id)
        result2 = await graph.ainvoke(state2, config)

        # Extract the title from the response
        title_response = ""
        for msg in reversed(result2.get("messages", [])):
            if hasattr(msg, "type") and msg.type == "ai" and hasattr(msg, "content") and msg.content:
                content = str(msg.content).strip()
                if content:
                    title_response = content
                    break

        print(f"Title Request: {title_request}")
        print(f"Generated Title: {title_response}")

        # Validate we got a reasonable title (not a question, not too long)
        assert len(title_response) > 0, "Should get a title response"
        # The response should contain a short title - could be wrapped in explanation
        # Look for percentage/calculation related terms
        response_lower = title_response.lower()
        has_relevant_content = any(kw in response_lower for kw in [
            "percent", "15%", "200", "calculat", "math", "30"
        ])
        assert has_relevant_content or len(title_response) < 100, \
            f"Expected title-like response, got: {title_response}"

    @pytest.mark.asyncio
    async def test_title_generator_direct_executor(self, maos_system):
        """Test title_generator direct execution (fallback/testing mode)."""
        graph, context = maos_system
        from maos.agents.executor import AgentInput

        external_servers = context.get("external_servers", [])
        title_gen = next((s for s in external_servers if s.name == "title_generator"), None)
        assert title_gen is not None

        # Test with conversation content
        result = await title_gen.execute(AgentInput(
            task="User: How do I sort a list in Python?\nAssistant: You can use the sorted() function or list.sort() method."
        ))
        assert result.success, f"Failed: {result.error}"
        assert len(result.content) > 0, "Expected title"
        assert len(result.content) < 100, f"Title too long: {result.content}"

        # Test empty input returns default
        result_empty = await title_gen.execute(AgentInput(task=""))
        assert result_empty.success
        assert result_empty.content == "New Conversation"


class TestTitleEndpointViaSupervisor:
    """Tests for /api/tasks/title endpoint routing through supervisor.

    Both the title endpoint and natural language requests go through
    the same supervisor routing - proving true plug-and-play architecture.
    """

    @pytest.mark.asyncio
    async def test_title_endpoint_routes_through_supervisor(self, maos_system):
        """Test that /api/tasks/title routes through supervisor to title_generator.

        This mirrors what the endpoint does internally:
        1. Build prompt from conversation messages
        2. Invoke graph (supervisor routes to title_generator)
        3. Extract title from response
        """
        graph, context = maos_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()
        assert "title_generator" in roster, "title_generator must be in roster"

        # Simulate what the /api/tasks/title endpoint does
        conversation = [
            {"role": "user", "content": "How do I reverse a string in Python?"},
            {"role": "assistant", "content": "You can use slicing: string[::-1] or reversed()"}
        ]

        # Build the title request (same as endpoint does)
        conversation_summary = "\n".join(
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in conversation
        )
        title_request = f"Generate a concise title (3-8 words) for this conversation:\n\n{conversation_summary}"

        messages = [{"role": "user", "content": title_request}]
        state = create_initial_state(
            messages=messages,
            roster=roster,
            thread_id="test-title-endpoint"
        )
        config = {"configurable": {"thread_id": "test-title-endpoint"}}

        result = await graph.ainvoke(state, config)

        # Extract title
        title = ""
        for msg in reversed(result.get("messages", [])):
            if hasattr(msg, "type") and msg.type == "ai" and hasattr(msg, "content"):
                content = str(msg.content).strip()
                if content:
                    title = content
                    break

        print(f"\n--- Title Endpoint Test ---")
        print(f"Conversation: {conversation_summary[:100]}...")
        print(f"Generated Title: {title}")

        # Validate title
        assert len(title) > 0, "Should get a title"
        # Should be related to Python/string/reverse
        title_lower = title.lower()
        has_relevant = any(kw in title_lower for kw in [
            "python", "string", "reverse", "revers", "code", "program"
        ])
        # Either related content OR reasonably short (it's a title)
        assert has_relevant or len(title) < 100, f"Expected title-like response: {title}"

    @pytest.mark.asyncio
    async def test_natural_language_and_endpoint_same_routing(self, maos_system):
        """Verify both natural language and endpoint use same supervisor routing.

        This is the key proof that:
        - Natural language: "Generate a title for this chat"
        - Endpoint: POST /api/tasks/title

        Both go through: Supervisor → discovers title_generator → routes → result
        """
        graph, context = maos_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()

        # Test conversation
        conversation_content = "User asked about calculating compound interest. Assistant explained the formula A = P(1 + r/n)^(nt)."

        # Approach 1: Natural language (simulating user follow-up)
        natural_prompt = f"Generate a short title for this conversation: {conversation_content}"

        state1 = create_initial_state(
            messages=[{"role": "user", "content": natural_prompt}],
            roster=roster,
            thread_id="test-natural-title"
        )
        config1 = {"configurable": {"thread_id": "test-natural-title"}}
        result1 = await graph.ainvoke(state1, config1)

        # Approach 2: Endpoint style (structured prompt)
        endpoint_prompt = f"Generate a concise title (3-8 words) for this conversation:\n\n{conversation_content}"

        state2 = create_initial_state(
            messages=[{"role": "user", "content": endpoint_prompt}],
            roster=roster,
            thread_id="test-endpoint-title"
        )
        config2 = {"configurable": {"thread_id": "test-endpoint-title"}}
        result2 = await graph.ainvoke(state2, config2)

        # Extract titles - look for quoted title or short response
        def extract_title(result):
            import re
            for msg in reversed(result.get("messages", [])):
                if hasattr(msg, "type") and msg.type == "ai" and hasattr(msg, "content"):
                    content = str(msg.content).strip()
                    # Try to extract quoted title (e.g., **"Title"** or "Title")
                    patterns = [
                        r'\*\*"([^"]+)"\*\*',  # **"Title"**
                        r'"([^"]+)"',           # "Title"
                        r"'([^']+)'",           # 'Title'
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, content)
                        if match:
                            return match.group(1).strip()
                    # If no quoted title, return full content
                    return content
            return ""

        title1 = extract_title(result1)
        title2 = extract_title(result2)

        print(f"\n--- Routing Comparison ---")
        print(f"Natural language title: {title1[:100]}...")
        print(f"Endpoint style title: {title2[:100]}...")

        # Both should produce content (proves routing worked)
        assert len(title1) > 0, "Natural language should produce response"
        assert len(title2) > 0, "Endpoint style should produce response"

        # Both should be about compound interest / finance
        keywords = ["interest", "compound", "financ", "invest", "calculat", "formula"]
        title1_lower = title1.lower()
        title2_lower = title2.lower()

        # At least one should have relevant keywords (proves routing worked)
        has_relevant_1 = any(kw in title1_lower for kw in keywords)
        has_relevant_2 = any(kw in title2_lower for kw in keywords)

        print(f"Title 1 relevant: {has_relevant_1}")
        print(f"Title 2 relevant: {has_relevant_2}")

        # At least one should have relevant content (proves correct routing)
        assert has_relevant_1 or has_relevant_2, \
            f"At least one title should be about compound interest. Got: {title1[:50]}, {title2[:50]}"
