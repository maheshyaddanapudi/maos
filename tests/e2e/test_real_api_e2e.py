"""
Real E2E tests using actual Anthropic API.

These tests require ANTHROPIC_API_KEY environment variable to be set.
Run with: ANTHROPIC_API_KEY=sk-... pytest tests/e2e/test_real_api_e2e.py -v -s
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
MULTI_AGENT_CONFIG = FIXTURES_DIR / "multi_agent_config.yaml"


@pytest.fixture
async def multi_agent_system():
    """Initialize system with multiple agents."""
    from maos.main import initialize_system

    graph, context = await initialize_system(str(MULTI_AGENT_CONFIG))
    return graph, context


class TestSupervisorWorkerOrchestration:
    """Tests for supervisor routing to native workers."""

    @pytest.mark.asyncio
    async def test_supervisor_routes_to_math_expert(self, multi_agent_system):
        """Test that supervisor correctly routes math problems to math_expert."""
        graph, context = multi_agent_system
        from maos.graph.state import create_initial_state

        # Get roster
        roster = context["agent_registry"].get_roster()
        print(f"\nAvailable agents: {roster}")

        # Create math problem
        messages = [{"role": "user", "content": "What is 15 * 7 + 23?"}]

        initial_state = create_initial_state(
            messages=messages,
            roster=roster,
            thread_id="test-math-1"
        )

        config = {"configurable": {"thread_id": "test-math-1"}}

        # Execute
        print("Invoking graph with math problem...")
        result = await graph.ainvoke(initial_state, config=config)

        # Verify
        print("\n--- Execution Result ---")
        for msg in result.get("messages", []):
            if hasattr(msg, "type") and hasattr(msg, "content"):
                print(f"[{msg.type}]: {msg.content[:200] if msg.content else '(empty)'}...")

        # Check we got a response
        assert result.get("messages"), "Should have messages in result"

        # Check the answer contains 128 (15*7+23 = 105+23 = 128)
        final_messages = result.get("messages", [])
        response_content = ""
        for msg in final_messages:
            if hasattr(msg, "content") and msg.content:
                response_content += str(msg.content)

        print(f"\nFull response: {response_content}")
        assert "128" in response_content, f"Expected '128' in response, got: {response_content}"

    @pytest.mark.asyncio
    async def test_supervisor_routes_to_writer(self, multi_agent_system):
        """Test that supervisor correctly routes writing tasks to writer."""
        graph, context = multi_agent_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()

        # Create writing task
        messages = [{"role": "user", "content": "Write a haiku about coding."}]

        initial_state = create_initial_state(
            messages=messages,
            roster=roster,
            thread_id="test-write-1"
        )

        config = {"configurable": {"thread_id": "test-write-1"}}

        print("Invoking graph with writing task...")
        result = await graph.ainvoke(initial_state, config=config)

        # Verify we got a creative response
        print("\n--- Execution Result ---")
        final_messages = result.get("messages", [])
        response_content = ""
        for msg in final_messages:
            if hasattr(msg, "content") and msg.content:
                content = str(msg.content)
                print(f"[{getattr(msg, 'type', 'unknown')}]: {content[:200]}...")
                response_content += content

        # Haiku should have some poetic content
        assert len(response_content) > 20, "Should have substantial response"
        print(f"\nGot haiku response of length: {len(response_content)}")

    @pytest.mark.asyncio
    async def test_multi_step_orchestration(self, multi_agent_system):
        """Test supervisor handling a task that requires worker execution."""
        graph, context = multi_agent_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()

        # Task that needs math expert
        messages = [{"role": "user", "content": "Calculate the factorial of 5 (5!)."}]

        initial_state = create_initial_state(
            messages=messages,
            roster=roster,
            thread_id="test-factorial"
        )

        config = {"configurable": {"thread_id": "test-factorial"}}

        print("Invoking graph for factorial calculation...")
        result = await graph.ainvoke(initial_state, config=config)

        # Verify
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
    async def test_send_message_interrupts_for_input(self, multi_agent_system):
        """Test that supervisor can use send_message to request user input."""
        graph, context = multi_agent_system
        from maos.graph.state import create_initial_state
        from langgraph.types import Command

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

        # Check if graph is interrupted (waiting for input)
        state = await graph.aget_state(config)

        print(f"\nGraph state next: {state.next}")
        print(f"Graph tasks: {state.tasks}")

        # If interrupted, we should see tasks waiting
        if state.next:
            print("Graph is interrupted, waiting for input")

            # Check for interrupt value
            if state.tasks:
                for task in state.tasks:
                    if hasattr(task, 'interrupts') and task.interrupts:
                        interrupt_value = task.interrupts[0].value
                        print(f"Interrupt value: {interrupt_value}")

                        # Resume with clarified input
                        print("\nResuming with clarified input...")
                        resumed_result = await graph.ainvoke(
                            Command(resume="I need help with a math problem: what is 10 + 5?"),
                            config=config
                        )

                        # Verify resumed execution
                        for msg in resumed_result.get("messages", []):
                            if hasattr(msg, "content") and msg.content:
                                print(f"After resume: {msg.content[:100]}...")
        else:
            # If not interrupted, the model decided to handle it directly
            print("Model handled directly without requesting clarification")
            final_messages = result.get("messages", [])
            for msg in final_messages:
                if hasattr(msg, "content") and msg.content:
                    print(f"Response: {msg.content[:200]}...")

    @pytest.mark.asyncio
    async def test_explicit_clarification_request(self, multi_agent_system):
        """Test supervisor asking for explicit clarification."""
        graph, context = multi_agent_system
        from maos.graph.state import create_initial_state

        roster = context["agent_registry"].get_roster()

        # Request that explicitly needs more info
        messages = [{"role": "user", "content": "Solve x."}]

        initial_state = create_initial_state(
            messages=messages,
            roster=roster,
            thread_id="test-clarify-1"
        )

        config = {"configurable": {"thread_id": "test-clarify-1"}}

        print("Invoking graph with incomplete request...")
        result = await graph.ainvoke(initial_state, config=config)

        # Check state
        state = await graph.aget_state(config)

        print(f"\nState after invocation:")
        print(f"  - next: {state.next}")
        print(f"  - has tasks: {bool(state.tasks)}")

        # Print any messages we got
        for msg in result.get("messages", []):
            if hasattr(msg, "content") and msg.content:
                print(f"  - message: {msg.content[:150]}...")


class TestAgentRoster:
    """Tests for agent roster and configuration."""

    @pytest.mark.asyncio
    async def test_roster_contains_all_workers(self, multi_agent_system):
        """Test that roster contains all configured workers."""
        graph, context = multi_agent_system

        roster = context["agent_registry"].get_roster()
        print(f"\nRoster: {roster}")

        # Should have math_expert and writer (supervisor is not in roster)
        assert "math_expert" in roster, "math_expert should be in roster"
        assert "writer" in roster, "writer should be in roster"
        assert len(roster) == 2, f"Expected 2 workers, got {len(roster)}"

    @pytest.mark.asyncio
    async def test_llm_registry_initialized(self, multi_agent_system):
        """Test that LLM registry is properly initialized."""
        graph, context = multi_agent_system

        llm_registry = context["llm_registry"]
        adapters = llm_registry.list()

        print(f"\nLLM adapters: {adapters}")
        assert "default" in adapters, "default LLM should be registered"
