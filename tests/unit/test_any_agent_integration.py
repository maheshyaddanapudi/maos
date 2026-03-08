"""Tests for any-agent multi-framework integration.

Covers:
- model_id building from LLMConfig
- LangChain tool → callable conversion
- any-agent worker graph creation (mocked)
- framework branching in GraphFactory.build()
- config validation for non-langchain frameworks
- step-limit callback
- AgentCancel vs AgentRunError distinction
- cleanup tracking
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool

from maos.config.models import (
    AgentConfig,
    AgentKind,
    Config,
    GraphConfig,
    LLMConfig,
    LLMProvider,
    ServingConfig,
)
from maos.graph.factory import (
    _ANYAGENT_FRAMEWORK_MAP,
    _DEFAULT_MAX_STEPS,
    _StepLimitExceeded,
    _convert_langchain_tools_to_callables,
    _make_step_limit_callback,
    build_any_agent_model_id,
    create_any_agent_worker_graph,
)


# ---------------------------------------------------------------------------
# build_any_agent_model_id
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestBuildAnyAgentModelId:
    """Test model_id construction from LLMConfig."""

    def test_openai_provider(self):
        cfg = LLMConfig(provider=LLMProvider.OPENAI, model="gpt-4o")
        assert build_any_agent_model_id(cfg) == "openai/gpt-4o"

    def test_anthropic_provider(self):
        cfg = LLMConfig(provider=LLMProvider.ANTHROPIC, model="claude-3-5-sonnet-20241022")
        assert build_any_agent_model_id(cfg) == "anthropic/claude-3-5-sonnet-20241022"

    def test_google_provider(self):
        cfg = LLMConfig(provider=LLMProvider.GOOGLE, model="gemini-2.0-flash")
        assert build_any_agent_model_id(cfg) == "gemini/gemini-2.0-flash"

    def test_ollama_provider(self):
        cfg = LLMConfig(provider=LLMProvider.OLLAMA, model="llama3")
        assert build_any_agent_model_id(cfg) == "ollama/llama3"

    def test_openai_compatible_provider(self):
        cfg = LLMConfig(provider=LLMProvider.OPENAI_COMPATIBLE, model="my-model")
        assert build_any_agent_model_id(cfg) == "openai/my-model"

    def test_azure_openai_provider(self):
        cfg = LLMConfig(provider=LLMProvider.AZURE_OPENAI, model="gpt-4o-deployment")
        assert build_any_agent_model_id(cfg) == "azure/gpt-4o-deployment"


# ---------------------------------------------------------------------------
# _convert_langchain_tools_to_callables
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestConvertLangchainToolsToCallables:
    """Test converting LangChain tools to plain callables."""

    def test_empty_list(self):
        assert _convert_langchain_tools_to_callables([]) == []

    def test_structured_tool_with_coroutine(self):
        async def my_func(x: str) -> str:
            return f"result: {x}"

        tool = StructuredTool.from_function(
            coroutine=my_func,
            name="my_tool",
            description="A test tool",
        )
        result = _convert_langchain_tools_to_callables([tool])
        assert len(result) == 1
        assert result[0] is my_func

    def test_structured_tool_with_sync_func(self):
        def my_func(x: str) -> str:
            return f"result: {x}"

        tool = StructuredTool.from_function(
            func=my_func,
            name="my_tool",
            description="A test tool",
        )
        result = _convert_langchain_tools_to_callables([tool])
        assert len(result) == 1
        assert result[0] is my_func

    def test_fallback_wrapper_for_unknown_tool(self):
        """Tools without func/coroutine get wrapped via ainvoke."""
        tool = MagicMock(spec=["name", "description", "ainvoke"])
        tool.name = "wrapped_tool"
        tool.description = "A wrapped tool"
        result = _convert_langchain_tools_to_callables([tool])
        assert len(result) == 1
        assert result[0].__name__ == "wrapped_tool"
        assert result[0].__doc__ == "A wrapped tool"

    def test_multiple_tools(self):
        async def func_a(x: str) -> str:
            return x

        async def func_b(y: int) -> str:
            return str(y)

        tool_a = StructuredTool.from_function(coroutine=func_a, name="a", description="Tool A")
        tool_b = StructuredTool.from_function(coroutine=func_b, name="b", description="Tool B")
        result = _convert_langchain_tools_to_callables([tool_a, tool_b])
        assert len(result) == 2
        assert result[0] is func_a
        assert result[1] is func_b


# ---------------------------------------------------------------------------
# _ANYAGENT_FRAMEWORK_MAP
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestFrameworkMap:
    """Verify the framework name mapping is complete."""

    def test_all_non_langchain_frameworks_mapped(self):
        """Every non-langchain framework in AgentConfig must have a mapping."""
        import typing

        framework_field = AgentConfig.model_fields["framework"]
        literal_args = typing.get_args(framework_field.annotation)
        for fw in literal_args:
            if fw != "langchain":
                assert fw in _ANYAGENT_FRAMEWORK_MAP, f"Missing mapping for framework: {fw}"

    def test_llamaindex_maps_to_llama_index(self):
        """MAOS uses 'llamaindex' but any-agent expects 'llama_index'."""
        assert _ANYAGENT_FRAMEWORK_MAP["llamaindex"] == "llama_index"


# ---------------------------------------------------------------------------
# Step-limit callback
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestStepLimitCallback:
    """Test the step-limiting callback."""

    def test_callback_counts_llm_calls(self):
        callback = _make_step_limit_callback(3)
        context = MagicMock()
        context.shared = {}

        # Should succeed for first 3 calls
        for _ in range(3):
            callback.before_llm_call(context)

        # 4th call should raise
        with pytest.raises(_StepLimitExceeded, match="step limit of 3"):
            callback.before_llm_call(context)

    def test_default_max_steps_is_reasonable(self):
        assert _DEFAULT_MAX_STEPS > 0
        assert _DEFAULT_MAX_STEPS <= 100


# ---------------------------------------------------------------------------
# create_any_agent_worker_graph (mocked any-agent)
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestCreateAnyAgentWorkerGraph:
    """Test the StateGraph wrapper around any-agent."""

    @patch("any_agent.AnyAgent")
    @patch("any_agent.AgentConfig")
    async def test_creates_compiled_graph(self, MockConfig, MockAnyAgent):
        """The wrapper returns a compiled graph with correct name."""
        mock_instance = MagicMock()
        MockAnyAgent.create_async = AsyncMock(return_value=mock_instance)

        result = await create_any_agent_worker_graph(
            name="test_worker",
            framework="openai",
            model_id="gpt-4o",
            system_prompt="You are a test agent.",
        )

        # Verify it's a compiled graph (has invoke/ainvoke)
        assert hasattr(result, "ainvoke")
        assert result.name == "test_worker"

        # Verify AnyAgent.create_async was called with correct framework
        MockAnyAgent.create_async.assert_called_once()
        call_args = MockAnyAgent.create_async.call_args
        assert call_args[0][0] == "openai"  # framework

    @patch("any_agent.AnyAgent")
    @patch("any_agent.AgentConfig")
    async def test_config_includes_step_callback(self, MockConfig, MockAnyAgent):
        """AgentConfig receives a step-limiting callback."""
        mock_instance = MagicMock()
        MockAnyAgent.create_async = AsyncMock(return_value=mock_instance)

        await create_any_agent_worker_graph(
            name="worker",
            framework="google",
            model_id="gemini/gemini-2.0-flash",
            system_prompt="Analyze data.",
            max_steps=10,
        )

        # Verify callbacks were passed
        config_call = MockConfig.call_args
        assert "callbacks" in config_call[1]
        callbacks = config_call[1]["callbacks"]
        assert len(callbacks) == 1

    @patch("any_agent.AnyAgent")
    @patch("any_agent.AgentConfig")
    async def test_graph_extracts_task_from_human_message(self, MockConfig, MockAnyAgent):
        """The graph node extracts the task from the last human message."""
        mock_instance = MagicMock()
        mock_trace = MagicMock()
        mock_trace.final_output = "The answer is 42."
        mock_instance.run_async = AsyncMock(return_value=mock_trace)
        MockAnyAgent.create_async = AsyncMock(return_value=mock_instance)

        graph = await create_any_agent_worker_graph(
            name="worker",
            framework="openai",
            model_id="gpt-4o",
            system_prompt="Answer questions.",
        )

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="What is the meaning of life?")]}
        )

        mock_instance.run_async.assert_called_once_with("What is the meaning of life?")
        last_msg = result["messages"][-1]
        assert isinstance(last_msg, AIMessage)
        assert last_msg.content == "The answer is 42."
        assert last_msg.name == "worker"

    @patch("any_agent.AnyAgent")
    @patch("any_agent.AgentConfig")
    async def test_graph_handles_no_task(self, MockConfig, MockAnyAgent):
        """Returns fallback message when no human message found."""
        mock_instance = MagicMock()
        MockAnyAgent.create_async = AsyncMock(return_value=mock_instance)

        graph = await create_any_agent_worker_graph(
            name="worker",
            framework="openai",
            model_id="gpt-4o",
            system_prompt="Test.",
        )

        result = await graph.ainvoke({"messages": []})
        last_msg = result["messages"][-1]
        assert "No task provided" in last_msg.content

    @patch("any_agent.AnyAgent")
    @patch("any_agent.AgentConfig")
    async def test_graph_handles_agent_error(self, MockConfig, MockAnyAgent):
        """Returns error message when any-agent raises."""
        mock_instance = MagicMock()
        mock_instance.run_async = AsyncMock(side_effect=RuntimeError("LLM timeout"))
        MockAnyAgent.create_async = AsyncMock(return_value=mock_instance)

        graph = await create_any_agent_worker_graph(
            name="worker",
            framework="openai",
            model_id="gpt-4o",
            system_prompt="Test.",
        )

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="Do something")]}
        )
        last_msg = result["messages"][-1]
        assert "encountered an error" in last_msg.content

    @patch("any_agent.AnyAgent")
    @patch("any_agent.AgentConfig")
    async def test_graph_handles_agent_cancel(self, MockConfig, MockAnyAgent):
        """AgentCancel is reported as 'stopped', not 'error'."""
        # Create a concrete AgentCancel subclass (can't instantiate ABC directly)
        from any_agent import AgentCancel

        class TestCancel(AgentCancel):
            pass

        mock_instance = MagicMock()
        cancel_exc = TestCancel("Step limit reached")
        cancel_exc._trace = MagicMock()
        cancel_exc._trace.final_output = "partial answer"
        mock_instance.run_async = AsyncMock(side_effect=cancel_exc)
        MockAnyAgent.create_async = AsyncMock(return_value=mock_instance)

        graph = await create_any_agent_worker_graph(
            name="worker",
            framework="openai",
            model_id="gpt-4o",
            system_prompt="Test.",
        )

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="Do something")]}
        )
        last_msg = result["messages"][-1]
        assert "stopped" in last_msg.content
        assert "partial answer" in last_msg.content

    @patch("any_agent.AnyAgent")
    @patch("any_agent.AgentConfig")
    async def test_graph_handles_none_final_output(self, MockConfig, MockAnyAgent):
        """Returns fallback when trace.final_output is None."""
        mock_instance = MagicMock()
        mock_trace = MagicMock()
        mock_trace.final_output = None
        mock_instance.run_async = AsyncMock(return_value=mock_trace)
        MockAnyAgent.create_async = AsyncMock(return_value=mock_instance)

        graph = await create_any_agent_worker_graph(
            name="worker",
            framework="openai",
            model_id="gpt-4o",
            system_prompt="Test.",
        )

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="Hello")]}
        )
        last_msg = result["messages"][-1]
        assert last_msg.content == "No response."

    @patch("any_agent.AnyAgent")
    @patch("any_agent.AgentConfig")
    async def test_llamaindex_framework_mapped(self, MockConfig, MockAnyAgent):
        """llamaindex maps to llama_index for any-agent."""
        mock_instance = MagicMock()
        MockAnyAgent.create_async = AsyncMock(return_value=mock_instance)

        await create_any_agent_worker_graph(
            name="worker",
            framework="llamaindex",
            model_id="gpt-4o",
            system_prompt="Test.",
        )

        call_args = MockAnyAgent.create_async.call_args
        assert call_args[0][0] == "llama_index"

    @patch("any_agent.AnyAgent")
    @patch("any_agent.AgentConfig")
    async def test_missing_framework_package_raises_import_error(self, MockConfig, MockAnyAgent):
        """NameError from missing framework package is wrapped as ImportError."""
        MockAnyAgent.create_async = AsyncMock(
            side_effect=NameError("name 'BaseConverter' is not defined")
        )

        with pytest.raises(ImportError, match="requires additional dependencies"):
            await create_any_agent_worker_graph(
                name="worker",
                framework="openai",
                model_id="openai/gpt-4o",
                system_prompt="Test.",
            )


# ---------------------------------------------------------------------------
# GraphFactory framework branching
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestGraphFactoryFrameworkBranching:
    """Test that GraphFactory.build() routes to correct path based on framework."""

    def _make_config(self, worker_framework="langchain"):
        """Create a minimal Config with one supervisor and one worker."""
        return Config(
            llms={
                "default": LLMConfig(provider=LLMProvider.OPENAI, model="gpt-4o"),
            },
            agents={
                "supervisor": AgentConfig(
                    kind=AgentKind.SUPERVISOR,
                    system_prompt="Route tasks.",
                ),
                "worker": AgentConfig(
                    kind=AgentKind.NATIVE_WORKER,
                    framework=worker_framework,
                    system_prompt="Do work.",
                ),
            },
        )

    @patch("maos.graph.factory.create_any_agent_worker_graph", new_callable=AsyncMock)
    @patch("maos.graph.factory.create_react_agent")
    @patch("maos.graph.factory.create_supervisor")
    async def test_langchain_uses_create_react_agent(
        self, mock_supervisor, mock_react, mock_anyagent
    ):
        """framework=langchain must use create_react_agent, NOT any-agent."""
        from maos.agents.factory import AgentFactory
        from maos.agents.registry import AgentRegistry
        from maos.llm.factory import LLMFactory

        config = self._make_config("langchain")

        mock_llm_factory = MagicMock(spec=LLMFactory)
        mock_llm_factory.create_chat_model.return_value = MagicMock()

        mock_react.return_value = MagicMock()
        mock_supervisor.return_value = MagicMock()

        agent_factory = MagicMock(spec=AgentFactory)
        from maos.agents.models import SupervisorAgent, WorkerAgent

        agent_factory.create_worker.return_value = WorkerAgent(
            name="worker",
            system_prompt="Do work.",
            framework="langchain",
            llm_name="default",
        )
        agent_factory.create_supervisor.return_value = SupervisorAgent(
            name="supervisor",
            system_prompt="Route tasks.",
            roster=["worker"],
            llm_name="default",
        )
        registry = AgentRegistry(agent_factory)
        registry.build(config)

        from maos.graph.factory import GraphFactory
        from maos.tools.registry import ToolRegistry

        tool_registry = MagicMock(spec=ToolRegistry)

        factory = GraphFactory(config, registry, mock_llm_factory, tool_registry)
        await factory.build()

        mock_react.assert_called_once()
        mock_anyagent.assert_not_called()

    @patch("maos.graph.factory.create_any_agent_worker_graph", new_callable=AsyncMock)
    @patch("maos.graph.factory.create_react_agent")
    @patch("maos.graph.factory.create_supervisor")
    async def test_openai_uses_any_agent(self, mock_supervisor, mock_react, mock_anyagent):
        """framework=openai must use any-agent, NOT create_react_agent."""
        from maos.agents.factory import AgentFactory
        from maos.agents.registry import AgentRegistry
        from maos.llm.factory import LLMFactory

        config = self._make_config("openai")

        mock_llm_factory = MagicMock(spec=LLMFactory)
        mock_llm_factory.create_chat_model.return_value = MagicMock()

        mock_react.return_value = MagicMock()
        mock_anyagent.return_value = MagicMock()
        mock_supervisor.return_value = MagicMock()

        agent_factory = MagicMock(spec=AgentFactory)
        from maos.agents.models import SupervisorAgent, WorkerAgent

        agent_factory.create_worker.return_value = WorkerAgent(
            name="worker",
            system_prompt="Do work.",
            framework="openai",
            llm_name="default",
        )
        agent_factory.create_supervisor.return_value = SupervisorAgent(
            name="supervisor",
            system_prompt="Route tasks.",
            roster=["worker"],
            llm_name="default",
        )
        registry = AgentRegistry(agent_factory)
        registry.build(config)

        from maos.graph.factory import GraphFactory
        from maos.tools.registry import ToolRegistry

        tool_registry = MagicMock(spec=ToolRegistry)

        factory = GraphFactory(config, registry, mock_llm_factory, tool_registry)
        await factory.build()

        mock_anyagent.assert_called_once()
        mock_react.assert_not_called()
        # Verify model_id was built correctly
        call_kwargs = mock_anyagent.call_args[1]
        assert call_kwargs["model_id"] == "openai/gpt-4o"
        assert call_kwargs["framework"] == "openai"


# ---------------------------------------------------------------------------
# GraphFactory cleanup
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestGraphFactoryCleanup:
    """Test any-agent instance cleanup."""

    async def test_cleanup_calls_cleanup_async(self):
        """cleanup_any_agents() calls cleanup_async on tracked instances."""
        from maos.graph.factory import GraphFactory

        factory = GraphFactory.__new__(GraphFactory)
        factory._any_agent_instances = []

        mock_instance = MagicMock()
        mock_instance.cleanup_async = AsyncMock()
        factory._any_agent_instances.append(mock_instance)

        await factory.cleanup_any_agents()

        mock_instance.cleanup_async.assert_called_once()
        assert len(factory._any_agent_instances) == 0

    async def test_cleanup_handles_errors_gracefully(self):
        """Cleanup doesn't crash if an instance fails to clean up."""
        from maos.graph.factory import GraphFactory

        factory = GraphFactory.__new__(GraphFactory)
        factory._any_agent_instances = []

        mock_instance = MagicMock()
        mock_instance.cleanup_async = AsyncMock(side_effect=RuntimeError("fail"))
        factory._any_agent_instances.append(mock_instance)

        # Should not raise
        await factory.cleanup_any_agents()
        assert len(factory._any_agent_instances) == 0


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestConfigValidationFramework:
    """Test config.validate_references() for framework availability."""

    def test_langchain_framework_no_errors(self):
        """langchain framework never triggers any-agent check."""
        config = Config(
            llms={"default": LLMConfig(provider=LLMProvider.OPENAI, model="gpt-4o")},
            agents={
                "supervisor": AgentConfig(
                    kind=AgentKind.SUPERVISOR, system_prompt="Route."
                ),
                "worker": AgentConfig(
                    kind=AgentKind.NATIVE_WORKER,
                    framework="langchain",
                    system_prompt="Work.",
                ),
            },
        )
        errors = config.validate_references()
        assert not any("any-agent" in e for e in errors)

    def test_non_langchain_with_any_agent_installed_no_errors(self):
        """No errors when any-agent is installed and framework is non-langchain."""
        config = Config(
            llms={"default": LLMConfig(provider=LLMProvider.OPENAI, model="gpt-4o")},
            agents={
                "supervisor": AgentConfig(
                    kind=AgentKind.SUPERVISOR, system_prompt="Route."
                ),
                "worker": AgentConfig(
                    kind=AgentKind.NATIVE_WORKER,
                    framework="openai",
                    system_prompt="Work.",
                ),
            },
        )
        # any-agent IS installed in our test env
        errors = config.validate_references()
        assert not any("any-agent" in e for e in errors)
