"""
End-to-End Tests for Failure Recovery & Replanning

Tests for Story 2.4: Complete mission retry cycle with obstacle recovery.
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
from src.agents.actor_agent import ActorAgent


class TestObstacleRecoveryCycle:
    """Test complete obstacle detection → failure → replan → retry → success cycle."""

    @pytest.fixture
    def agents(self):
        """Create all agents for E2E testing (mocked, no API calls)."""
        verifier = VerifierAgent(
            api_key="test-key",
            model="gpt-4o-mini",
            temperature=0.1,
            verbose=False
        )

        planner = PlannerAgent(
            api_key="test-key",
            model="gpt-4o-mini",
            temperature=0.3,
            verbose=False,
            knowledge_base=None
        )

        # Note: ActorAgent tests are covered in other test files
        # For E2E tests, we focus on Verifier → Planner flow

        return {"verifier": verifier, "planner": planner}

    @pytest.fixture
    def mission_with_obstacle(self):
        """Mission that will encounter an obstacle."""
        return MissionCommand(
            command="Move forward 3 meters and scan area",
            language="en",
            priority=8,
            action_plan=[
                RobotAction(action=ActionType.MOVE, x=3.0, y=0.0, speed=0.5, reason="Move forward"),
                RobotAction(action=ActionType.SCAN, duration=5.0, reason="Scan environment")
            ]
        )

    def test_single_retry_success_cycle(self, agents, mission_with_obstacle):
        """Test obstacle → failure → replan → retry → success (1 retry)."""
        verifier = agents["verifier"]
        planner = agents["planner"]
        mission = mission_with_obstacle

        # Simulate: Mission failed with obstacle collision
        failed_state = RobotState(
            status=RobotStatus.STOPPED,
            sensors=SensorData(
                position_x=1.5,  # Robot moved 1.5m before hitting obstacle
                position_y=0.0,
                position_z=0.098,
                lidar_distances=[0.28] * 512,  # Obstacle at 0.28m (collision)
                lidar_min_distance=0.28,
                lidar_avg_distance=1.5
            )
        )

        # Step 1: Verifier analyzes failure
        failure_reason = verifier.analyze_failure_reason(mission, failed_state)
        assert failure_reason == FailureReason.OBSTACLE_COLLISION

        # Step 2: Check if replanning is possible
        mission.status = MissionStatus.FAILED  # Mark as failed
        mission.retry_count = 0
        should_replan = verifier.should_replan(failure_reason, mission)
        assert should_replan is True  # Obstacle collision is replan-able

        # Step 3: Prepare retry
        verifier.prepare_retry(mission, "Obstacle collision at 1.5m")
        assert mission.retry_count == 1
        # After prepare_retry, status is PENDING, need to set FAILED to check can_retry
        mission.status = MissionStatus.FAILED
        assert mission.can_retry() is True  # Still has retries (1/3)

        # Step 4: Build ReplanRequest
        replan_request = ReplanRequest(
            failure_reason=failure_reason,
            sensor_data=failed_state.sensors,
            previous_plan=mission.action_plan if mission.action_plan else [],
            retry_count=mission.retry_count,
            original_command=mission.command,
            failure_details="Obstacle collision at 0.28m distance"
        )

        # Step 5: Mock Planner to generate alternative plan
        with patch('src.agents.planner_agent.Task') as mock_task_class:
            mock_task_instance = Mock()
            mock_task_class.return_value = mock_task_instance

            # Alternative plan: scan first, then rotate and move
            mock_result = Mock()
            mock_result.raw = '''[
                {"action": "scan", "duration": 3.0, "reason": "Scan for obstacles"},
                {"action": "rotate", "angle": 45, "speed": 0.3, "reason": "Turn to avoid obstacle"},
                {"action": "move", "x": 1.5, "y": 0.0, "speed": 0.3, "reason": "Move around obstacle"},
                {"action": "rotate", "angle": -45, "speed": 0.3, "reason": "Realign to target"},
                {"action": "move", "x": 1.5, "y": 0.0, "speed": 0.4, "reason": "Complete movement"},
                {"action": "scan", "duration": 5.0, "reason": "Final scan"}
            ]'''
            mock_task_instance.execute.return_value = mock_result

            # Delegate to planner
            alternative_plan = verifier.delegate_to_planner(
                planner_agent=planner,
                replan_request=replan_request,
                mission=mission,
                current_state=failed_state
            )

        # Verify alternative plan generated
        assert isinstance(alternative_plan, list)
        assert len(alternative_plan) == 6  # More cautious plan
        assert alternative_plan[0].action == ActionType.SCAN  # Safety first
        assert alternative_plan[1].action == ActionType.ROTATE  # Avoid obstacle

        print(f"✓ E2E cycle completed: Obstacle → Analysis → Replan → Alternative Plan ({len(alternative_plan)} actions)")

    def test_max_retries_boundary(self, agents, mission_with_obstacle):
        """Test that 3 failures → final FAILED status (max_retries=3)."""
        verifier = agents["verifier"]
        mission = mission_with_obstacle

        failed_state = RobotState(
            status=RobotStatus.STOPPED,
            sensors=SensorData(
                position_x=0.5,
                position_y=0.0,
                position_z=0.098,
                lidar_distances=[0.25] * 512,
                lidar_min_distance=0.25
            )
        )

        # Simulate 3 consecutive failures
        mission.status = MissionStatus.FAILED
        for attempt in range(1, 4):
            # Analyze failure
            failure_reason = verifier.analyze_failure_reason(mission, failed_state)
            assert failure_reason == FailureReason.OBSTACLE_COLLISION

            # Check if can retry
            should_replan = verifier.should_replan(failure_reason, mission)

            if attempt < 3:
                assert should_replan is True
                verifier.prepare_retry(mission, f"Retry attempt {attempt}")
                assert mission.retry_count == attempt
                mission.status = MissionStatus.FAILED  # Mark failed again
            else:
                # On 3rd attempt (retry_count=3), can_retry() returns False
                verifier.prepare_retry(mission, f"Retry attempt {attempt}")
                assert mission.retry_count == 3
                mission.status = MissionStatus.FAILED
                should_replan = verifier.should_replan(failure_reason, mission)
                assert should_replan is False  # Max retries reached

        # Verify final state
        assert mission.retry_count == 3
        mission.status = MissionStatus.FAILED
        assert mission.can_retry() is False

        print(f"✓ Max retries boundary verified: 3 attempts → Final FAILED")

    def test_non_recoverable_failure_immediate_stop(self, agents):
        """Test that SENSOR_FAILURE and TIMEOUT stop immediately (no retry)."""
        verifier = agents["verifier"]

        # Test SENSOR_FAILURE
        mission_sensor_fail = MissionCommand(
            command="Move forward",
            language="en",
            priority=5
        )

        sensor_failed_state = RobotState(
            status=RobotStatus.ERROR,
            sensors=SensorData(
                position_x=None,  # GPS failed
                position_y=None,
                position_z=None,
                lidar_distances=None,  # Lidar failed
                lidar_min_distance=None
            )
        )

        failure_reason = verifier.analyze_failure_reason(mission_sensor_fail, sensor_failed_state)
        assert failure_reason == FailureReason.SENSOR_FAILURE

        should_replan = verifier.should_replan(failure_reason, mission_sensor_fail)
        assert should_replan is False  # Cannot replan hardware failures

        # Test TIMEOUT
        mission_timeout = MissionCommand(
            command="Search area",
            language="en",
            priority=7
        )

        timeout_state = RobotState(
            status=RobotStatus.MOVING,
            sensors=SensorData(
                position_x=1.0,
                position_y=0.5,
                position_z=0.098,
                lidar_distances=[3.0] * 512,
                lidar_min_distance=3.0
            )
        )

        # Mock get_elapsed_time() on the MissionCommand class
        with patch.object(MissionCommand, 'get_elapsed_time', return_value=350.0):
            failure_reason_timeout = verifier.analyze_failure_reason(mission_timeout, timeout_state)

        assert failure_reason_timeout == FailureReason.TIMEOUT

        should_replan_timeout = verifier.should_replan(failure_reason_timeout, mission_timeout)
        assert should_replan_timeout is False  # Cannot replan timeouts

        print(f"✓ Non-recoverable failures (SENSOR_FAILURE, TIMEOUT) stop immediately")

    @patch('src.agents.planner_agent.Task')
    def test_path_blocked_recovery(self, mock_task_class, agents):
        """Test PATH_BLOCKED detection and recovery."""
        verifier = agents["verifier"]
        planner = agents["planner"]

        mission = MissionCommand(
            command="Navigate to waypoint",
            language="en",
            priority=8,
            action_plan=[
                RobotAction(action=ActionType.MOVE, x=4.0, y=0.0, speed=0.5, reason="Navigate")
            ]
        )

        # Create PATH_BLOCKED scenario (front 60° arc blocked)
        lidar_distances = [5.0] * 512
        for i in range(226, 286):  # Front arc
            lidar_distances[i] = 0.45  # < 0.5m = blocked

        blocked_state = RobotState(
            status=RobotStatus.STOPPED,
            sensors=SensorData(
                position_x=0.8,
                position_y=0.0,
                position_z=0.098,
                lidar_distances=lidar_distances,
                lidar_min_distance=0.45,
                lidar_avg_distance=4.2
            )
        )

        # Analyze failure
        failure_reason = verifier.analyze_failure_reason(mission, blocked_state)
        assert failure_reason == FailureReason.PATH_BLOCKED

        # Verify replanning is possible
        mission.status = MissionStatus.FAILED
        mission.retry_count = 0
        should_replan = verifier.should_replan(failure_reason, mission)
        assert should_replan is True

        # Mock alternative plan for blocked path
        mock_task_instance = Mock()
        mock_task_class.return_value = mock_task_instance

        mock_result = Mock()
        mock_result.raw = '''[
            {"action": "scan", "duration": 4.0, "reason": "Assess blockage"},
            {"action": "rotate", "angle": 90, "speed": 0.3, "reason": "Turn 90 degrees"},
            {"action": "move", "x": 2.0, "y": 0.0, "speed": 0.4, "reason": "Move around blockage"},
            {"action": "rotate", "angle": -90, "speed": 0.3, "reason": "Realign"},
            {"action": "move", "x": 2.0, "y": 0.0, "speed": 0.4, "reason": "Continue to goal"}
        ]'''
        mock_task_instance.execute.return_value = mock_result

        # Generate alternative plan
        replan_request = ReplanRequest(
            failure_reason=failure_reason,
            sensor_data=blocked_state.sensors,
            previous_plan=mission.action_plan,
            retry_count=1
        )

        alternative_plan = planner.replan_mission(
            failure_info=replan_request,
            mission=mission,
            current_state=blocked_state
        )

        # Verify alternative plan avoids blockage
        assert len(alternative_plan) > len(mission.action_plan)  # More steps to navigate around
        assert alternative_plan[0].action == ActionType.SCAN  # Assess first
        assert alternative_plan[1].action == ActionType.ROTATE  # Turn to avoid

        print(f"✓ PATH_BLOCKED recovery: Alternative plan generated with {len(alternative_plan)} actions")

    @patch('src.agents.planner_agent.Task')
    def test_goal_unreached_recovery(self, mock_task_class, agents):
        """Test GOAL_UNREACHED detection and recovery."""
        verifier = agents["verifier"]
        planner = agents["planner"]

        mission = MissionCommand(
            command="Move forward 3 meters",
            language="en",
            priority=6,
            action_plan=[
                RobotAction(action=ActionType.MOVE, x=3.0, y=0.0, speed=0.5, reason="Move to goal")
            ]
        )
        mission.current_action_index = 0  # Only completed 1/1 actions, but didn't reach goal

        # Robot stopped at origin (goal unreached)
        unreached_state = RobotState(
            status=RobotStatus.IDLE,
            sensors=SensorData(
                position_x=0.0,  # Still at origin
                position_y=0.0,
                position_z=0.098,
                lidar_distances=[4.0] * 512,
                lidar_min_distance=4.0
            )
        )

        # Analyze failure
        failure_reason = verifier.analyze_failure_reason(mission, unreached_state)
        assert failure_reason == FailureReason.GOAL_UNREACHED

        # Verify replanning is possible
        mission.status = MissionStatus.FAILED  # Required for should_replan
        should_replan = verifier.should_replan(failure_reason, mission)
        assert should_replan is True

        # Mock alternative plan (break into smaller steps)
        mock_task_instance = Mock()
        mock_task_class.return_value = mock_task_instance

        mock_result = Mock()
        mock_result.raw = '''[
            {"action": "move", "x": 1.0, "y": 0.0, "speed": 0.3, "reason": "Move 1m slowly"},
            {"action": "scan", "duration": 2.0, "reason": "Check progress"},
            {"action": "move", "x": 1.0, "y": 0.0, "speed": 0.3, "reason": "Move another 1m"},
            {"action": "scan", "duration": 2.0, "reason": "Check progress"},
            {"action": "move", "x": 1.0, "y": 0.0, "speed": 0.3, "reason": "Final 1m to goal"}
        ]'''
        mock_task_instance.execute.return_value = mock_result

        replan_request = ReplanRequest(
            failure_reason=failure_reason,
            sensor_data=unreached_state.sensors,
            previous_plan=mission.action_plan,
            retry_count=1
        )

        alternative_plan = planner.replan_mission(
            failure_info=replan_request,
            mission=mission,
            current_state=unreached_state
        )

        # Verify alternative plan breaks goal into smaller steps
        assert len(alternative_plan) > len(mission.action_plan)  # More granular
        move_actions = [a for a in alternative_plan if a.action == ActionType.MOVE]
        assert all(a.x <= 1.0 for a in move_actions)  # Smaller increments

        print(f"✓ GOAL_UNREACHED recovery: Broken into {len(alternative_plan)} smaller steps")


class TestRetryMechanismIntegration:
    """Test retry mechanism integration with MissionCommand."""

    def test_retry_count_increment(self):
        """Test retry_count increments correctly through multiple failures."""
        mission = MissionCommand(
            command="Move forward",
            language="en",
            priority=5
        )

        assert mission.retry_count == 0

        # Mark as FAILED to allow retries
        mission.status = MissionStatus.FAILED
        assert mission.can_retry() is True  # 0/3

        # Increment through retries
        for expected_count in [1, 2, 3]:
            mission.increment_retry()
            assert mission.retry_count == expected_count
            if expected_count < 3:
                mission.status = MissionStatus.FAILED  # Mark failed again for next retry

        # After 3 retries, can_retry() should return False
        mission.status = MissionStatus.FAILED
        assert mission.can_retry() is False  # 3/3 - max reached

        print(f"✓ Retry count increments correctly: 0 → 1 → 2 → 3 → max_retries")

    def test_prepare_retry_workflow(self):
        """Test VerifierAgent.prepare_retry() workflow."""
        verifier = VerifierAgent(
            api_key="test-key",
            model="gpt-4o-mini",
            temperature=0.1,
            verbose=False
        )

        mission = MissionCommand(
            command="Navigate forward",
            language="en",
            priority=7
        )

        mission.status = MissionStatus.FAILED
        assert mission.retry_count == 0

        # Prepare first retry
        verifier.prepare_retry(mission, "First failure - obstacle collision")
        assert mission.retry_count == 1
        assert mission.status == MissionStatus.PENDING

        # Prepare second retry
        mission.status = MissionStatus.FAILED
        verifier.prepare_retry(mission, "Second failure - path blocked")
        assert mission.retry_count == 2
        assert mission.status == MissionStatus.PENDING

        # Prepare third retry
        mission.status = MissionStatus.FAILED
        verifier.prepare_retry(mission, "Third failure - goal unreached")
        assert mission.retry_count == 3
        assert mission.status == MissionStatus.PENDING

        print(f"✓ prepare_retry() workflow verified through 3 retries")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
