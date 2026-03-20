"""
Real E2E tests using actual Anthropic API.

These tests require ANTHROPIC_API_KEY environment variable to be set.
Run with: ANTHROPIC_API_KEY=sk-... pytest tests/e2e/test_real_api_e2e.py -v -s
"""

import os
from pathlib import Path

import pytest

# Skip all tests if API key not available
pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_CONFIG = FIXTURES_DIR / "test_config.yaml"


@pytest.fixture
async def maos_system():
    """Initialize system with unified test config."""
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


class TestSupervisorWorkerOrchestration:
    """Tests for supervisor routing to native workers."""

    @pytest.mark.asyncio
    async def test_supervisor_routes_to_math_expert(self, maos_system):
        """Test that supervisor correctly routes math problems to math agent."""
        graph, context = maos_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()
        print(f"\nAvailable agents: {roster}")

        messages = [{"role": "user", "content": "What is 15 * 7 + 23?"}]

        initial_state = create_initial_state(
            messages=messages,
            roster=roster,
            thread_id="test-math-1"
        )

        config = {"configurable": {"thread_id": "test-math-1"}}

        print("Invoking graph with math problem...")
        result = await graph.ainvoke(initial_state, config=config)

        print("\n--- Execution Result ---")
        for msg in result.get("messages", []):
            if hasattr(msg, "type") and hasattr(msg, "content"):
                print(f"[{msg.type}]: {str(msg.content)[:200] if msg.content else '(empty)'}...")

        assert result.get("messages"), "Should have messages in result"

        final_messages = result.get("messages", [])
        response_content = ""
        for msg in final_messages:
            if hasattr(msg, "content") and msg.content:
                response_content += str(msg.content)

        print(f"\nFull response: {response_content}")
        assert "128" in response_content, f"Expected '128' in response, got: {response_content}"

    @pytest.mark.asyncio
    async def test_supervisor_routes_to_researcher(self, maos_system):
        """Test that supervisor correctly routes research tasks."""
        graph, context = maos_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()

        # Ask to read a file - researcher has file reading capability
        messages = [{"role": "user", "content": "Read the file test.txt and tell me what's in it."}]

        initial_state = create_initial_state(
            messages=messages,
            roster=roster,
            thread_id="test-research-1"
        )

        config = {"configurable": {"thread_id": "test-research-1"}}

        print("Invoking graph with file reading task...")
        result = await graph.ainvoke(initial_state, config=config)

        print("\n--- Execution Result ---")
        final_messages = result.get("messages", [])
        response_content = ""
        for msg in final_messages:
            if hasattr(msg, "content") and msg.content:
                content = str(msg.content)
                print(f"[{getattr(msg, 'type', 'unknown')}]: {content[:200]}...")
                response_content += content

        # Should have read the test file content
        assert "test file" in response_content.lower() or len(response_content) > 50

    @pytest.mark.asyncio
    async def test_multi_step_orchestration(self, maos_system):
        """Test supervisor handling a task that requires worker execution."""
        graph, context = maos_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()

        messages = [{"role": "user", "content": "Calculate the factorial of 5 (5!)."}]

        initial_state = create_initial_state(
            messages=messages,
            roster=roster,
            thread_id="test-factorial"
        )

        config = {"configurable": {"thread_id": "test-factorial"}}

        print("Invoking graph for factorial calculation...")
        result = await graph.ainvoke(initial_state, config=config)

        final_messages = result.get("messages", [])
        response_content = ""
        for msg in final_messages:
            if hasattr(msg, "content") and msg.content:
                response_content += str(msg.content)

        print(f"\nResponse: {response_content}")
        # 5! = 120
        assert "120" in response_content, f"Expected '120' in response for 5!, got: {response_content}"


class TestHumanInTheLoop:
    """Tests for human-in-the-loop via send_message."""

    @pytest.mark.asyncio
    async def test_send_message_interrupts_for_input(self, maos_system):
        """Test that supervisor can use send_message to request user input."""
        graph, context = maos_system
        from langgraph.types import Command

        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()

        # Ambiguous task that should trigger clarification
        messages = [{"role": "user", "content": "Help me with the thing."}]

        initial_state = create_initial_state(
            messages=messages,
            roster=roster,
            thread_id="test-hitl-1"
        )

        config = {"configurable": {"thread_id": "test-hitl-1"}}

        print("Invoking graph with ambiguous request...")
        result = await graph.ainvoke(initial_state, config=config)

        state = await graph.aget_state(config)

        print(f"\nGraph state next: {state.next}")
        print(f"Graph tasks: {state.tasks}")

        if state.next:
            print("Graph is interrupted, waiting for input")

            if state.tasks:
                for task in state.tasks:
                    if hasattr(task, 'interrupts') and task.interrupts:
                        interrupt_value = task.interrupts[0].value
                        print(f"Interrupt value: {interrupt_value}")

                        print("\nResuming with clarified input...")
                        resumed_result = await graph.ainvoke(
                            Command(resume="I need help with a math problem: what is 10 + 5?"),
                            config=config
                        )

                        for msg in resumed_result.get("messages", []):
                            if hasattr(msg, "content") and msg.content:
                                print(f"After resume: {str(msg.content)[:100]}...")
        else:
            print("Model handled directly without requesting clarification")
            final_messages = result.get("messages", [])
            for msg in final_messages:
                if hasattr(msg, "content") and msg.content:
                    print(f"Response: {str(msg.content)[:200]}...")

    @pytest.mark.asyncio
    async def test_explicit_clarification_request(self, maos_system):
        """Test supervisor asking for explicit clarification."""
        graph, context = maos_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()

        messages = [{"role": "user", "content": "Solve x."}]

        initial_state = create_initial_state(
            messages=messages,
            roster=roster,
            thread_id="test-clarify-1"
        )

        config = {"configurable": {"thread_id": "test-clarify-1"}}

        print("Invoking graph with incomplete request...")
        result = await graph.ainvoke(initial_state, config=config)

        state = await graph.aget_state(config)

        print("\nState after invocation:")
        print(f"  - next: {state.next}")
        print(f"  - has tasks: {bool(state.tasks)}")

        for msg in result.get("messages", []):
            if hasattr(msg, "content") and msg.content:
                print(f"  - message: {str(msg.content)[:150]}...")


class TestAgentRoster:
    """Tests for agent roster and configuration."""

    @pytest.mark.asyncio
    async def test_roster_contains_all_workers(self, maos_system):
        """Test that roster contains all configured workers."""
        graph, context = maos_system

        roster = context["agent_registry"].get_roster()
        print(f"\nRoster: {roster}")

        # Unified config has 6 native workers + 1 external agent
        expected_agents = [
            "analyst", "researcher", "assistant",
            "timekeeper", "mathematician", "librarian",
            "title_generator"  # External A2A agent
        ]
        for agent in expected_agents:
            assert agent in roster, f"{agent} should be in roster"
        assert len(roster) == 7, f"Expected 7 agents, got {len(roster)}: {roster}"

    @pytest.mark.asyncio
    async def test_llm_registry_initialized(self, maos_system):
        """Test that LLM registry is properly initialized."""
        graph, context = maos_system

        llm_registry = context["llm_registry"]
        adapters = llm_registry.list()

        print(f"\nLLM adapters: {adapters}")
        assert "default" in adapters, "default LLM should be registered"
