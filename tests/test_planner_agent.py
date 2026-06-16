"""
Test Planner Agent

Unit tests for PlannerAgent mission planning functionality.
"""

import pytest
import os
from unittest.mock import Mock, patch
from src.agents import PlannerAgent, PlannerAgentFactory
from src.schemas import (
    MissionCommand,
    RobotAction,
    ActionType,
    RobotState,
    RobotStatus,
    SensorData
)


@pytest.fixture
def api_key():
    """Get OpenAI API key from environment or use mock."""
    return os.getenv("OPENAI_API_KEY", "sk-mock-key-for-testing")


@pytest.fixture
def planner_agent(api_key):
    """Create PlannerAgent instance."""
    return PlannerAgent(
        api_key=api_key,
        model="gpt-4o-mini",  # Use cheaper model for testing
        temperature=0.0,  # Deterministic for testing
        verbose=False
    )


@pytest.fixture
def mock_robot_state():
    """Create mock robot state."""
    return RobotState(
        robot_id="test_robot",
        status=RobotStatus.IDLE,
        sensors=SensorData(
            position_x=0.0,
            position_y=0.0,
            position_z=0.1,
            roll=0.0,
            pitch=0.0,
            yaw=0.0
        )
    )


class TestPlannerAgentInitialization:
    """Test PlannerAgent initialization."""

    def test_initialization(self, api_key):
        """Test basic initialization."""
        agent = PlannerAgent(
            api_key=api_key,
            model="gpt-4o",
            temperature=0.3
        )
        assert agent.model == "gpt-4o"
        assert agent.temperature == 0.3
        assert agent.agent is not None
        assert agent.llm is not None

    def test_factory_singleton(self, api_key):
        """Test factory creates singleton."""
        PlannerAgentFactory.reset()

        agent1 = PlannerAgentFactory.create(api_key=api_key)
        agent2 = PlannerAgentFactory.create(api_key=api_key)

        assert agent1 is agent2  # Same instance


class TestPromptBuilding:
    """Test prompt building for different languages."""

    def test_korean_prompt_building(self, planner_agent):
        """Test Korean prompt generation."""
        mission = MissionCommand(
            command="동쪽으로 3미터 이동 후 생존자 탐색",
            language="ko",
            priority=8
        )

        prompt = planner_agent._build_planning_prompt(mission, None)

        assert "동쪽으로 3미터 이동 후 생존자 탐색" in prompt
        assert "language: ko" in prompt.lower()
        assert "priority: 8" in prompt.lower()
        assert "한국어" in prompt or "Korean" in prompt

    def test_english_prompt_building(self, planner_agent):
        """Test English prompt generation."""
        mission = MissionCommand(
            command="Move 3 meters east then search for survivors",
            language="en",
            priority=7
        )

        prompt = planner_agent._build_planning_prompt(mission, None)

        assert "Move 3 meters east" in prompt
        assert "language: en" in prompt.lower()
        assert "priority: 7" in prompt.lower()

    def test_prompt_with_robot_state(self, planner_agent, mock_robot_state):
        """Test prompt includes robot state context."""
        mission = MissionCommand(
            command="Navigate to safe zone",
            language="en"
        )

        prompt = planner_agent._build_planning_prompt(mission, mock_robot_state)

        assert "X=0.00m" in prompt
        assert "Y=0.00m" in prompt
        assert "Yaw=0.0deg" in prompt


class TestActionParsing:
    """Test action plan parsing."""

    def test_parse_valid_json_array(self, planner_agent):
        """Test parsing valid JSON action array."""
        json_result = """
        [
            {"action": "move", "x": 2.0, "y": 3.0, "speed": 1.0, "reason": "Navigate to target"},
            {"action": "scan", "duration": 5.0, "reason": "Search area"},
            {"action": "rotate", "angle": 90.0, "speed": 0.5, "reason": "Face exit"}
        ]
        """

        actions = planner_agent._parse_action_plan(json_result)

        assert len(actions) == 3
        assert actions[0].action == ActionType.MOVE
        assert actions[0].x == 2.0
        assert actions[0].y == 3.0
        assert actions[1].action == ActionType.SCAN
        assert actions[1].duration == 5.0
        assert actions[2].action == ActionType.ROTATE
        assert actions[2].angle == 90.0

    def test_parse_with_markdown_formatting(self, planner_agent):
        """Test parsing JSON wrapped in markdown code blocks."""
        json_result = """```json
        [
            {"action": "move", "x": 1.0, "y": 1.0, "speed": 1.0, "reason": "Test"}
        ]
        ```"""

        actions = planner_agent._parse_action_plan(json_result)

        assert len(actions) == 1
        assert actions[0].action == ActionType.MOVE

    def test_parse_invalid_json_fails(self, planner_agent):
        """Test that invalid JSON raises error."""
        invalid_json = "This is not JSON"

        with pytest.raises(ValueError, match="Invalid JSON"):
            planner_agent._parse_action_plan(invalid_json)

    def test_parse_non_array_fails(self, planner_agent):
        """Test that non-array JSON raises error."""
        json_result = '{"action": "move", "x": 1.0}'

        with pytest.raises(ValueError, match="Expected JSON array"):
            planner_agent._parse_action_plan(json_result)

    def test_parse_invalid_action_fails(self, planner_agent):
        """Test that invalid action parameters raise error."""
        json_result = '[{"action": "move", "speed": 1.0}]'  # Missing x, y

        with pytest.raises(ValueError, match="Invalid action"):
            planner_agent._parse_action_plan(json_result)


class TestActionPlanValidation:
    """Test action plan validation."""

    def test_validate_empty_plan_fails(self, planner_agent):
        """Test empty plan raises error."""
        mission = MissionCommand(command="Move forward and scan for survivors", language="en")

        with pytest.raises(ValueError, match="empty"):
            planner_agent._validate_action_plan([], mission)

    def test_validate_complex_plan_warns(self, planner_agent):
        """Test very long plan is validated (warning logged but no exception)."""
        mission = MissionCommand(command="Navigate and search for survivors in all areas", language="en")
        actions = [
            RobotAction(action=ActionType.WAIT, duration=1.0)
            for _ in range(25)
        ]

        # Should complete without raising exception despite being complex
        planner_agent._validate_action_plan(actions, mission)
        # If we get here, validation passed (warning would be logged via loguru)

    def test_validate_timeout_check(self, planner_agent):
        """Test timeout warning for long execution (warning logged but no exception)."""
        mission = MissionCommand(
            command="Move slowly to target and search thoroughly",
            language="en",
            timeout_seconds=10.0
        )
        actions = [
            RobotAction(action=ActionType.WAIT, duration=5.0),
            RobotAction(action=ActionType.WAIT, duration=5.0),
            RobotAction(action=ActionType.WAIT, duration=5.0),  # Total 15s > 10s
        ]

        # Should complete without raising exception despite timeout warning
        planner_agent._validate_action_plan(actions, mission)
        # If we get here, validation passed (warning would be logged via loguru)


class TestMissionPlanning:
    """Test full mission planning flow."""

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY environment variable"
    )
    def test_plan_korean_mission(self, planner_agent):
        """Test planning Korean mission (requires API key)."""
        mission = MissionCommand(
            command="앞으로 2미터 이동 후 주변 탐색",
            language="ko",
            priority=5
        )

        action_plan = planner_agent.plan_mission(mission)

        assert len(action_plan) > 0
        assert any(a.action == ActionType.MOVE for a in action_plan)
        assert any(a.action == ActionType.SCAN for a in action_plan)

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY environment variable"
    )
    def test_plan_english_mission(self, planner_agent):
        """Test planning English mission (requires API key)."""
        mission = MissionCommand(
            command="Move forward 2 meters and scan surroundings",
            language="en",
            priority=5
        )

        action_plan = planner_agent.plan_mission(mission)

        assert len(action_plan) > 0
        assert any(a.action == ActionType.MOVE for a in action_plan)
        assert any(a.action == ActionType.SCAN for a in action_plan)

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY environment variable"
    )
    def test_plan_with_robot_state(self, planner_agent, mock_robot_state):
        """Test planning considers robot state."""
        mission = MissionCommand(
            command="Return to origin position",
            language="en"
        )

        # Set robot at non-origin position
        mock_robot_state.sensors.position_x = 3.0
        mock_robot_state.sensors.position_y = 2.0

        action_plan = planner_agent.plan_mission(mission, mock_robot_state)

        assert len(action_plan) > 0
        # Should have movement action
        move_actions = [a for a in action_plan if a.action == ActionType.MOVE]
        assert len(move_actions) > 0

    def test_plan_invalid_command_fails(self, planner_agent):
        """Test planning with valid command but invalid LLM response."""
        mission = MissionCommand(
            command="Search the area and navigate to safety zone",
            language="en"
        )

        # Mock _parse_action_plan to simulate invalid LLM response
        with patch.object(planner_agent, '_parse_action_plan') as mock_parse:
            mock_parse.side_effect = ValueError("Invalid JSON response from LLM")

            with pytest.raises(ValueError, match="Failed to plan mission"):
                planner_agent.plan_mission(mission)


class TestLanguageInstructions:
    """Test language-specific instructions."""

    def test_korean_instructions(self, planner_agent):
        """Test Korean instruction template."""
        instructions = planner_agent._get_korean_instructions()

        assert "한국어" in instructions
        assert "이동" in instructions
        assert "회전" in instructions
        assert "탐색" in instructions

    def test_english_instructions(self, planner_agent):
        """Test English instruction template."""
        instructions = planner_agent._get_english_instructions()

        assert "move" in instructions.lower()
        assert "rotate" in instructions.lower()
        assert "search" in instructions.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
