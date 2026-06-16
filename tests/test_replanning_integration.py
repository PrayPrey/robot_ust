"""
Integration Tests for Replanning Mechanism

Tests for Story 2.4: Verifier → Planner delegation and replanning integration.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.schemas import (
    MissionCommand,
    RobotState,
    RobotStatus,
    SensorData,
    FailureReason,
    ReplanRequest,
    RobotAction,
    ActionType,
    MissionStatus
)
from src.agents.verifier_agent import VerifierAgent
from src.agents.planner_agent import PlannerAgent


class TestVerifierPlannerDelegation:
    """Test Verifier → Planner delegation flow."""

    @pytest.fixture
    def verifier(self):
        """Mock VerifierAgent for testing (no API calls)."""
        return VerifierAgent(
            api_key="test-key",
            model="gpt-4o-mini",
            temperature=0.1,
            verbose=False
        )

    @pytest.fixture
    def planner(self):
        """Mock PlannerAgent for testing (no API calls)."""
        # Create planner without RAG (knowledge_base=None)
        planner = PlannerAgent(
            api_key="test-key",
            model="gpt-4o-mini",
            temperature=0.3,
            verbose=False,
            knowledge_base=None
        )
        return planner

    @pytest.fixture
    def mission(self):
        """Sample mission command."""
        return MissionCommand(
            command="Move forward 2 meters and scan",
            language="en",
            priority=7,
            action_plan=[
                RobotAction(action=ActionType.MOVE, x=2.0, y=0.0, speed=0.5, reason="Move forward"),
                RobotAction(action=ActionType.SCAN, duration=3.0, reason="Scan surroundings")
            ]
        )

    @pytest.fixture
    def failed_state(self):
        """Robot state after obstacle collision."""
        return RobotState(
            status=RobotStatus.STOPPED,
            sensors=SensorData(
                position_x=0.5,
                position_y=0.0,
                position_z=0.098,
                lidar_distances=[0.25] * 512,  # Obstacle at 0.25m
                lidar_min_distance=0.25,
                lidar_avg_distance=2.0
            )
        )

    def test_delegation_creates_replan_request(self, verifier, planner, mission, failed_state):
        """Test that delegation creates proper ReplanRequest."""
        # Analyze failure
        failure_reason = verifier.analyze_failure_reason(mission, failed_state)
        assert failure_reason == FailureReason.OBSTACLE_COLLISION

        # Build ReplanRequest
        replan_request = ReplanRequest(
            failure_reason=failure_reason,
            sensor_data=failed_state.sensors,
            previous_plan=mission.action_plan,
            retry_count=1,
            original_command=mission.command,
            failure_details="Obstacle detected at 0.25m"
        )

        # Verify ReplanRequest structure
        assert replan_request.failure_reason == FailureReason.OBSTACLE_COLLISION
        assert replan_request.sensor_data.lidar_min_distance == 0.25
        assert len(replan_request.previous_plan) == 2
        assert replan_request.retry_count == 1
        assert replan_request.original_command == mission.command

        print(f"✓ ReplanRequest created successfully with failure: {failure_reason.value}")

    @patch('src.agents.planner_agent.Task')
    def test_delegate_to_planner_calls_replan_mission(self, mock_task_class, verifier, planner, mission, failed_state):
        """Test that delegate_to_planner calls PlannerAgent.replan_mission."""
        # Setup mock Task
        mock_task_instance = Mock()
        mock_task_class.return_value = mock_task_instance

        # Mock Task.execute() to return a mock result with raw attribute
        mock_result = Mock()
        mock_result.raw = '''[
            {"action": "scan", "duration": 2.0, "reason": "Scan for obstacles"},
            {"action": "rotate", "angle": 45, "speed": 0.3, "reason": "Turn to avoid obstacle"},
            {"action": "move", "x": 1.0, "y": 0.0, "speed": 0.3, "reason": "Move cautiously"}
        ]'''
        mock_task_instance.execute.return_value = mock_result

        # Build ReplanRequest
        replan_request = ReplanRequest(
            failure_reason=FailureReason.OBSTACLE_COLLISION,
            sensor_data=failed_state.sensors,
            previous_plan=mission.action_plan,
            retry_count=1,
            original_command=mission.command
        )

        # Call delegate_to_planner
        alternative_plan = verifier.delegate_to_planner(
            planner_agent=planner,
            replan_request=replan_request,
            mission=mission,
            current_state=failed_state
        )

        # Verify alternative plan was returned
        assert isinstance(alternative_plan, list)
        assert len(alternative_plan) > 0
        assert all(isinstance(action, RobotAction) for action in alternative_plan)

        print(f"✓ Delegation returned {len(alternative_plan)} alternative actions")

    @patch('src.agents.planner_agent.Task')
    def test_replan_mission_generates_alternative_plan(self, mock_task_class, planner, mission, failed_state):
        """Test that PlannerAgent.replan_mission generates alternative plan."""
        # Setup mock Task
        mock_task_instance = Mock()
        mock_task_class.return_value = mock_task_instance

        # Mock Task.execute() to return alternative plan
        mock_result = Mock()
        mock_result.raw = '''[
            {"action": "scan", "duration": 3.0, "reason": "Full environment scan"},
            {"action": "rotate", "angle": 90, "speed": 0.3, "reason": "Turn 90 degrees"},
            {"action": "move", "x": 1.0, "y": 0.0, "speed": 0.2, "reason": "Move slowly"},
            {"action": "move", "x": 1.0, "y": 0.0, "speed": 0.3, "reason": "Continue forward"}
        ]'''
        mock_task_instance.execute.return_value = mock_result

        # Build ReplanRequest
        replan_request = ReplanRequest(
            failure_reason=FailureReason.PATH_BLOCKED,
            sensor_data=failed_state.sensors,
            previous_plan=mission.action_plan,
            retry_count=2,
            original_command=mission.command
        )

        # Call replan_mission
        alternative_plan = planner.replan_mission(
            failure_info=replan_request,
            mission=mission,
            current_state=failed_state
        )

        # Verify alternative plan
        assert isinstance(alternative_plan, list)
        assert len(alternative_plan) == 4
        assert alternative_plan[0].action == ActionType.SCAN
        assert alternative_plan[1].action == ActionType.ROTATE
        assert alternative_plan[2].action == ActionType.MOVE
        assert alternative_plan[3].action == ActionType.MOVE

        print(f"✓ Alternative plan generated with {len(alternative_plan)} actions")

    @patch('src.agents.planner_agent.Task')
    def test_replan_request_data_flow(self, mock_task_class, verifier, planner, mission, failed_state):
        """Test complete data flow from Verifier to Planner."""
        # Setup mock Task
        mock_task_instance = Mock()
        mock_task_class.return_value = mock_task_instance

        mock_result = Mock()
        mock_result.raw = '''[
            {"action": "rotate", "angle": 30, "speed": 0.3, "reason": "Avoid obstacle"},
            {"action": "move", "x": 1.5, "y": 0.0, "speed": 0.4, "reason": "Resume movement"}
        ]'''
        mock_task_instance.execute.return_value = mock_result

        # Step 1: Verifier analyzes failure
        failure_reason = verifier.analyze_failure_reason(mission, failed_state)
        assert failure_reason == FailureReason.OBSTACLE_COLLISION

        # Step 2: Verifier builds ReplanRequest
        replan_request = ReplanRequest(
            failure_reason=failure_reason,
            sensor_data=failed_state.sensors,
            previous_plan=mission.action_plan,
            retry_count=1,
            original_command=mission.command,
            failure_details=f"Obstacle at {failed_state.sensors.lidar_min_distance}m"
        )

        # Step 3: Verifier delegates to Planner
        alternative_plan = verifier.delegate_to_planner(
            planner_agent=planner,
            replan_request=replan_request,
            mission=mission,
            current_state=failed_state
        )

        # Step 4: Verify complete flow
        assert isinstance(alternative_plan, list)
        assert len(alternative_plan) > 0
        assert all(isinstance(action, RobotAction) for action in alternative_plan)

        # Verify alternative plan exists (may be same length but different actions)
        # Just verify we got a valid plan back
        assert len(alternative_plan) >= len(mission.action_plan) // 2  # At least half as long

        print(f"✓ Complete data flow verified: Verifier → ReplanRequest → Planner → Alternative Plan")

    def test_delegation_fails_with_invalid_planner(self, verifier, mission, failed_state):
        """Test that delegation fails gracefully with None planner."""
        replan_request = ReplanRequest(
            failure_reason=FailureReason.OBSTACLE_COLLISION,
            sensor_data=failed_state.sensors,
            previous_plan=mission.action_plan,
            retry_count=1
        )

        # Pass None as planner - should raise ValueError (caught and re-raised by delegate_to_planner)
        with pytest.raises(ValueError, match="Replanning delegation failed"):
            verifier.delegate_to_planner(
                planner_agent=None,
                replan_request=replan_request,
                mission=mission,
                current_state=failed_state
            )

        print(f"✓ Delegation fails gracefully with invalid planner")


class TestReplanRequestValidation:
    """Test ReplanRequest schema validation in integration context."""

    def test_replan_request_with_all_failure_types(self):
        """Test ReplanRequest creation with different failure reasons."""
        sensor_data = SensorData(
            position_x=1.0,
            position_y=0.5,
            position_z=0.098,
            lidar_min_distance=0.3
        )

        previous_plan = [
            RobotAction(action=ActionType.MOVE, x=2.0, y=0.0, speed=0.5, reason="Forward")
        ]

        # Test all failure types
        failure_types = [
            FailureReason.OBSTACLE_COLLISION,
            FailureReason.PATH_BLOCKED,
            FailureReason.GOAL_UNREACHED,
            FailureReason.SENSOR_FAILURE,
            FailureReason.TIMEOUT
        ]

        for failure_type in failure_types:
            replan_req = ReplanRequest(
                failure_reason=failure_type,
                sensor_data=sensor_data,
                previous_plan=previous_plan,
                retry_count=1,
                original_command="Test command"
            )

            assert replan_req.failure_reason == failure_type
            assert replan_req.retry_count == 1

        print(f"✓ ReplanRequest validated for all {len(failure_types)} failure types")

    def test_replan_request_retry_count_boundary(self):
        """Test ReplanRequest retry_count validation (0-3)."""
        sensor_data = SensorData(position_x=0.0, position_y=0.0, position_z=0.098)

        # Valid retry counts
        for retry_count in [0, 1, 2, 3]:
            replan_req = ReplanRequest(
                failure_reason=FailureReason.OBSTACLE_COLLISION,
                sensor_data=sensor_data,
                retry_count=retry_count
            )
            assert replan_req.retry_count == retry_count

        # Invalid retry count (> 3)
        with pytest.raises(Exception):  # Pydantic ValidationError
            ReplanRequest(
                failure_reason=FailureReason.OBSTACLE_COLLISION,
                sensor_data=sensor_data,
                retry_count=4  # Invalid: max is 3
            )

        print(f"✓ ReplanRequest retry_count boundary validation working (0-3)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
