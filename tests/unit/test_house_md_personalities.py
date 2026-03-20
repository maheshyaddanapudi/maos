"""Tests for House MD personality system."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from maos.house_md.personalities.base import (
    BIAS_DESCRIPTIONS,
    CognitiveBias,
    PersonalityConfig,
    PersonalityWrapper,
    TeamContext,
)
from maos.house_md.personalities.team import (
    CAMERON_PERSONALITY,
    CHASE_PERSONALITY,
    FOREMAN_PERSONALITY,
    HOUSE_PERSONALITY,
    PERSONALITY_CONFIGS,
    THIRTEEN_PERSONALITY,
    WILSON_PERSONALITY,
    TeamActivation,
)

# ── CognitiveBias ────────────────────────────────────────────────────────────


class TestCognitiveBias:
    def test_all_biases_have_descriptions(self):
        for bias in CognitiveBias:
            assert bias in BIAS_DESCRIPTIONS
            assert len(BIAS_DESCRIPTIONS[bias]) > 10

    def test_bias_values_are_strings(self):
        for bias in CognitiveBias:
            assert isinstance(bias.value, str)

    def test_bias_enum_count(self):
        assert len(CognitiveBias) == 8


# ── PersonalityConfig ────────────────────────────────────────────────────────


class TestPersonalityConfig:
    def test_default_values(self):
        config = PersonalityConfig(
            name="Test",
            role_description="A test role",
            system_prompt_additions="Test prompt",
        )
        assert config.challenge_threshold == 0.5
        assert config.compliance_threshold == 0.5
        assert config.manipulation_enabled is False
        assert config.cognitive_biases == []
        assert config.big_five["openness"] == 0.5

    def test_custom_values(self):
        config = PersonalityConfig(
            name="Custom",
            role_description="Custom role",
            system_prompt_additions="Custom prompt",
            cognitive_biases=[CognitiveBias.CONTRARIAN],
            challenge_threshold=0.9,
            big_five={"openness": 0.9, "conscientiousness": 0.3,
                      "extraversion": 0.2, "agreeableness": 0.1,
                      "neuroticism": 0.6},
        )
        assert config.challenge_threshold == 0.9
        assert config.cognitive_biases == [CognitiveBias.CONTRARIAN]
        assert config.big_five["openness"] == 0.9


# ── PersonalityWrapper ───────────────────────────────────────────────────────


class TestPersonalityWrapper:
    def test_build_enhanced_prompt(self):
        wrapper = PersonalityWrapper(
            base_agent=MagicMock(),
            personality=HOUSE_PERSONALITY,
        )
        prompt = wrapper.build_enhanced_prompt("Original prompt")
        assert "House" in prompt
        assert "Lead diagnostician" in prompt
        assert "EVERYBODY LIES" in prompt
        assert "Original prompt" in prompt
        assert "<house_md_personality>" in prompt

    def test_build_enhanced_prompt_with_team_context(self):
        context = TeamContext(
            active_agents=["foreman", "chase"],
            hypotheses=[{"hypothesis": "test"}],
        )
        wrapper = PersonalityWrapper(
            base_agent=MagicMock(),
            personality=HOUSE_PERSONALITY,
            team_context=context,
        )
        prompt = wrapper.build_enhanced_prompt("Test")
        assert "foreman, chase" in prompt

    def test_enhance_state_with_system_message(self):
        wrapper = PersonalityWrapper(
            base_agent=MagicMock(),
            personality=CHASE_PERSONALITY,
        )
        state = {
            "messages": [
                SystemMessage(content="Original system prompt"),
                HumanMessage(content="Hello"),
            ]
        }
        enhanced = wrapper.enhance_state(state)
        first_msg = enhanced["messages"][0]
        assert isinstance(first_msg, SystemMessage)
        assert "Chase" in first_msg.content
        assert "Original system prompt" in first_msg.content

    def test_enhance_state_without_system_message(self):
        wrapper = PersonalityWrapper(
            base_agent=MagicMock(),
            personality=FOREMAN_PERSONALITY,
        )
        state = {
            "messages": [HumanMessage(content="Hello")]
        }
        enhanced = wrapper.enhance_state(state)
        assert isinstance(enhanced["messages"][0], SystemMessage)
        assert "Foreman" in enhanced["messages"][0].content

    def test_enhance_state_with_dict_messages(self):
        wrapper = PersonalityWrapper(
            base_agent=MagicMock(),
            personality=CAMERON_PERSONALITY,
        )
        state = {
            "messages": [
                {"role": "system", "content": "Original"},
                {"role": "user", "content": "Hello"},
            ]
        }
        enhanced = wrapper.enhance_state(state)
        # enhance_state now returns SystemMessage objects (merging dict system msgs)
        assert isinstance(enhanced["messages"][0], SystemMessage)
        assert "Cameron" in enhanced["messages"][0].content

    def test_enhance_state_no_messages(self):
        wrapper = PersonalityWrapper(
            base_agent=MagicMock(),
            personality=HOUSE_PERSONALITY,
        )
        state = {"other_key": "value"}
        enhanced = wrapper.enhance_state(state)
        assert "other_key" in enhanced
        # Now creates a messages list with a personality SystemMessage
        assert "messages" in enhanced
        assert len(enhanced["messages"]) == 1
        assert isinstance(enhanced["messages"][0], SystemMessage)

    def test_enhance_state_adds_team_context(self):
        context = TeamContext(
            active_agents=["house", "chase"],
            hypotheses=[{"hypothesis": "memory leak"}],
        )
        wrapper = PersonalityWrapper(
            base_agent=MagicMock(),
            personality=THIRTEEN_PERSONALITY,
            team_context=context,
        )
        state = {"messages": [HumanMessage(content="test")]}
        enhanced = wrapper.enhance_state(state)
        assert "team_context" in enhanced
        assert enhanced["team_context"]["my_role"] == "Thirteen"

    @pytest.mark.asyncio
    async def test_invoke_with_ainvoke(self):
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="Result")],
        })
        wrapper = PersonalityWrapper(
            base_agent=mock_agent,
            personality=CHASE_PERSONALITY,
        )
        result = await wrapper.invoke(
            {"messages": [HumanMessage(content="Do something")]}
        )
        assert result["metadata"]["personality"] == "Chase"
        assert "action_oriented" in result["metadata"]["biases"]
        assert wrapper.invocation_count == 1

    @pytest.mark.asyncio
    async def test_invoke_with_invoke(self):
        mock_agent = MagicMock()
        mock_agent.invoke = MagicMock(return_value={
            "messages": [AIMessage(content="Result")],
        })
        # Remove ainvoke so it falls through to invoke
        del mock_agent.ainvoke
        wrapper = PersonalityWrapper(
            base_agent=mock_agent,
            personality=FOREMAN_PERSONALITY,
        )
        result = await wrapper.invoke(
            {"messages": [HumanMessage(content="Review this")]}
        )
        assert result["metadata"]["personality"] == "Foreman"

    @pytest.mark.asyncio
    async def test_invoke_with_callable(self):
        async def mock_fn(state):
            return {"messages": [AIMessage(content="Callable result")]}

        wrapper = PersonalityWrapper(
            base_agent=mock_fn,
            personality=WILSON_PERSONALITY,
        )
        result = await wrapper.invoke(
            {"messages": [HumanMessage(content="Think about it")]}
        )
        assert result["metadata"]["personality"] == "Wilson"

    @pytest.mark.asyncio
    async def test_ainvoke_delegates_to_invoke(self):
        """ainvoke is an alias for invoke (LangGraph convention)."""
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="via ainvoke")],
        })
        wrapper = PersonalityWrapper(
            base_agent=mock_agent,
            personality=CHASE_PERSONALITY,
        )
        result = await wrapper.ainvoke(
            {"messages": [HumanMessage(content="test")]}
        )
        assert result["metadata"]["personality"] == "Chase"
        assert wrapper.invocation_count == 1

    @pytest.mark.asyncio
    async def test_invoke_not_invocable(self):
        wrapper = PersonalityWrapper(
            base_agent="not_callable",
            personality=HOUSE_PERSONALITY,
        )
        with pytest.raises(TypeError, match="not invocable"):
            await wrapper.invoke({"messages": []})

    @pytest.mark.asyncio
    async def test_invoke_non_dict_result(self):
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value="string_result")
        wrapper = PersonalityWrapper(
            base_agent=mock_agent,
            personality=HOUSE_PERSONALITY,
        )
        result = await wrapper.invoke({"messages": []})
        assert result == "string_result"

    def test_should_challenge_contrarian_bias(self):
        wrapper = PersonalityWrapper(
            base_agent=MagicMock(),
            personality=HOUSE_PERSONALITY,  # Has CONTRARIAN bias
        )
        # With high challenge threshold + contrarian, should almost always challenge
        challenges = sum(
            wrapper.should_challenge({"hypothesis": "test"}, "chase")
            for _ in range(100)
        )
        assert challenges > 80  # Should challenge most of the time

    def test_should_challenge_conservative_with_risky_proposal(self):
        wrapper = PersonalityWrapper(
            base_agent=MagicMock(),
            personality=FOREMAN_PERSONALITY,  # Has CONSERVATIVE bias
        )
        # Conservative + risky proposal should increase challenge rate
        risky = {"hypothesis": "test", "novelty": 0.8, "risk": 0.9}
        challenges = sum(
            wrapper.should_challenge(risky, "chase") for _ in range(100)
        )
        assert challenges > 70

    def test_invocation_count_increments(self):
        wrapper = PersonalityWrapper(
            base_agent=MagicMock(),
            personality=HOUSE_PERSONALITY,
        )
        assert wrapper.invocation_count == 0


# ── TeamContext ───────────────────────────────────────────────────────────────


class TestTeamContext:
    def test_defaults(self):
        ctx = TeamContext()
        assert ctx.active_agents == []
        assert ctx.hypotheses == []
        assert ctx.current_phase == "intake"
        assert ctx.whiteboard is None

    def test_with_values(self):
        ctx = TeamContext(
            active_agents=["house", "foreman"],
            hypotheses=[{"hypothesis": "test"}],
            current_phase="differential",
        )
        assert len(ctx.active_agents) == 2
        assert ctx.current_phase == "differential"


# ── PERSONALITY_CONFIGS ───────────────────────────────────────────────────────


class TestPersonalityConfigs:
    def test_all_configs_present(self):
        expected = ["house", "foreman", "cameron", "chase",
                    "thirteen", "wilson", "cuddy"]
        for name in expected:
            assert name in PERSONALITY_CONFIGS

    def test_house_config(self):
        house = PERSONALITY_CONFIGS["house"]
        assert house.name == "House"
        assert house.manipulation_enabled is True
        assert house.challenge_threshold == 0.9
        assert CognitiveBias.EVERYBODY_LIES in house.cognitive_biases

    def test_foreman_config(self):
        foreman = PERSONALITY_CONFIGS["foreman"]
        assert foreman.name == "Foreman"
        assert CognitiveBias.CONSERVATIVE in foreman.cognitive_biases
        assert CognitiveBias.BY_THE_BOOK in foreman.cognitive_biases

    def test_cameron_config(self):
        cameron = PERSONALITY_CONFIGS["cameron"]
        assert CognitiveBias.EMPATHY_DRIVEN in cameron.cognitive_biases
        assert cameron.big_five["agreeableness"] == 0.9

    def test_chase_config(self):
        chase = PERSONALITY_CONFIGS["chase"]
        assert CognitiveBias.ACTION_ORIENTED in chase.cognitive_biases
        assert chase.compliance_threshold == 0.7

    def test_thirteen_config(self):
        thirteen = PERSONALITY_CONFIGS["thirteen"]
        assert CognitiveBias.RISK_TOLERANT in thirteen.cognitive_biases
        assert thirteen.compliance_threshold == 0.3

    def test_wilson_config(self):
        wilson = PERSONALITY_CONFIGS["wilson"]
        assert CognitiveBias.EMPATHY_DRIVEN in wilson.cognitive_biases
        assert wilson.big_five["agreeableness"] == 0.8

    def test_cuddy_config(self):
        cuddy = PERSONALITY_CONFIGS["cuddy"]
        assert CognitiveBias.CONSERVATIVE in cuddy.cognitive_biases
        assert cuddy.manipulation_enabled is False

    def test_all_configs_have_big_five(self):
        big_five_keys = {"openness", "conscientiousness", "extraversion",
                         "agreeableness", "neuroticism"}
        for name, config in PERSONALITY_CONFIGS.items():
            assert set(config.big_five.keys()) == big_five_keys, (
                f"{name} missing Big Five keys"
            )
            for key, val in config.big_five.items():
                assert 0.0 <= val <= 1.0, f"{name}.{key} out of range"


# ── TeamActivation ────────────────────────────────────────────────────────────


class TestTeamActivation:
    def test_quick_fix(self):
        assert TeamActivation.QUICK_FIX == ["chase"]

    def test_standard(self):
        assert "house" in TeamActivation.STANDARD
        assert "foreman" in TeamActivation.STANDARD
        assert "chase" in TeamActivation.STANDARD

    def test_full_differential(self):
        assert len(TeamActivation.FULL_DIFFERENTIAL) == 5

    def test_crisis(self):
        assert TeamActivation.CRISIS == ["house", "wilson"]

    def test_for_complexity_low(self):
        team = TeamActivation.for_complexity(0.1)
        assert team == TeamActivation.QUICK_FIX

    def test_for_complexity_medium(self):
        team = TeamActivation.for_complexity(0.5)
        assert team == TeamActivation.STANDARD

    def test_for_complexity_high(self):
        team = TeamActivation.for_complexity(0.9)
        assert team == TeamActivation.FULL_DIFFERENTIAL

    def test_for_complexity_security(self):
        team = TeamActivation.for_complexity(0.5, domain="security")
        assert team == TeamActivation.SECURITY

    def test_for_complexity_user_facing(self):
        team = TeamActivation.for_complexity(0.5, domain="user_facing")
        assert team == TeamActivation.USER_FACING

    def test_for_complexity_novel(self):
        team = TeamActivation.for_complexity(0.7, domain="novel")
        assert team == TeamActivation.EXPLORATION

    def test_all_teams(self):
        teams = TeamActivation.all_teams()
        assert len(teams) == 7
        assert "quick_fix" in teams
        assert "crisis" in teams
