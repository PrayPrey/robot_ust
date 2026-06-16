"""
Test Failure Recovery & Replanning Mechanism

Tests for Story 2.4: VerifierAgent failure analysis and replanning logic.
"""

import pytest
from datetime import datetime

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


class TestFailureReasonAnalysis:
    """Test VerifierAgent.analyze_failure_reason() categorization."""

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
    def mission(self):
        """Sample mission command."""
        return MissionCommand(
            command="Move forward 2 meters",
            language="en",
            priority=5
        )

    def test_obstacle_collision_detection(self, verifier, mission):
        """Test that obstacle collision is detected from Lidar data."""
        # Create state with very close obstacle (< 0.3m)
        final_state = RobotState(
            status=RobotStatus.STOPPED,
            sensors=SensorData(
                position_x=0.5,
                position_y=0.0,
                position_z=0.098,
                lidar_distances=[0.25] * 512,  # All Lidar points show 0.25m
                lidar_min_distance=0.25,
                lidar_avg_distance=0.25
            )
        )

        failure_reason = verifier.analyze_failure_reason(mission, final_state)

        assert failure_reason == FailureReason.OBSTACLE_COLLISION
        print(f"✓ Obstacle collision detected: {failure_reason.value}")

    def test_path_blocked_detection(self, verifier, mission):
        """Test that blocked path is detected."""
        # Create Lidar data with blocked front path
        lidar_distances = [5.0] * 512  # Default: clear
        # Block front 60° arc (indices 226-286)
        for i in range(226, 286):
            lidar_distances[i] = 0.4  # < 0.5m = blocked

        final_state = RobotState(
            status=RobotStatus.STOPPED,
            sensors=SensorData(
                position_x=0.3,
                position_y=0.0,
                position_z=0.098,
                lidar_distances=lidar_distances,
                lidar_min_distance=0.4,
                lidar_avg_distance=4.5
            )
        )

        failure_reason = verifier.analyze_failure_reason(mission, final_state)

        assert failure_reason == FailureReason.PATH_BLOCKED
        print(f"✓ Path blocked detected: {failure_reason.value}")

    def test_goal_unreached_at_origin(self, verifier, mission):
        """Test goal unreached when robot didn't move from origin."""
        final_state = RobotState(
            status=RobotStatus.IDLE,
            sensors=SensorData(
                position_x=0.0,
                position_y=0.0,
                position_z=0.098,
                lidar_distances=[5.0] * 512,
                lidar_min_distance=5.0,
                lidar_avg_distance=5.0
            )
        )

        # Mission requires movement
        mission.command = "Move forward 2 meters"
        failure_reason = verifier.analyze_failure_reason(mission, final_state)

        assert failure_reason == FailureReason.GOAL_UNREACHED
        print(f"✓ Goal unreached detected: {failure_reason.value}")

    def test_sensor_failure_detection(self, verifier, mission):
        """Test sensor failure when GPS and Lidar both unavailable."""
        final_state = RobotState(
            status=RobotStatus.ERROR,
            sensors=SensorData(
                position_x=None,  # GPS failed
                position_y=None,
                position_z=None,
                lidar_distances=None,  # Lidar failed
                lidar_min_distance=None,
                lidar_avg_distance=None
            )
        )

        failure_reason = verifier.analyze_failure_reason(mission, final_state)

        assert failure_reason == FailureReason.SENSOR_FAILURE
        print(f"✓ Sensor failure detected: {failure_reason.value}")

    def test_timeout_detection(self, verifier, monkeypatch):
        """Test timeout detection when mission exceeds time limit."""
        # Create mission with proper validation keywords
        mission = MissionCommand(
            command="Move forward and search",
            language="en",
            priority=5
        )

        final_state = RobotState(
            status=RobotStatus.MOVING,
            sensors=SensorData(
                position_x=1.0,
                position_y=0.5,
                position_z=0.098,
                lidar_distances=[3.0] * 512,
                lidar_min_distance=3.0
            )
        )

        # Use monkeypatch to simulate timeout
        monkeypatch.setattr(mission.__class__, 'get_elapsed_time', lambda self: 350.0)

        failure_reason = verifier.analyze_failure_reason(mission, final_state)

        assert failure_reason == FailureReason.TIMEOUT
        print(f"✓ Timeout detected: {failure_reason.value}")


class TestReplanDecisionLogic:
    """Test VerifierAgent.should_replan() decision logic."""

    @pytest.fixture
    def verifier(self):
        return VerifierAgent(
            api_key="test-key",
            model="gpt-4o-mini",
            temperature=0.1,
            verbose=False
        )

    @pytest.fixture
    def mission(self):
        return MissionCommand(
            command="Navigate to checkpoint",
            language="en",
            priority=7
        )

    def test_replan_allowed_for_obstacle_collision(self, verifier):
        """Obstacle collision should allow replanning."""
        # Create mission with valid command
        mission = MissionCommand(
            command="Navigate to checkpoint",
            language="en",
            priority=7
        )
        mission.status = MissionStatus.FAILED  # Required for can_retry()
        mission.retry_count = 0  # Still has retries

        failure_reason = FailureReason.OBSTACLE_COLLISION
        should_replan = verifier.should_replan(failure_reason, mission)

        assert should_replan is True
        print(f"✓ Replanning allowed for {failure_reason.value}")

    def test_replan_allowed_for_path_blocked(self, verifier):
        """Path blocked should allow replanning."""
        mission = MissionCommand(
            command="Navigate to checkpoint",
            language="en",
            priority=7
        )
        mission.status = MissionStatus.FAILED
        mission.retry_count = 1  # Still has retries (< 3)

        failure_reason = FailureReason.PATH_BLOCKED
        should_replan = verifier.should_replan(failure_reason, mission)

        assert should_replan is True
        print(f"✓ Replanning allowed for {failure_reason.value}")

    def test_replan_not_allowed_for_sensor_failure(self, verifier, mission):
        """Sensor failure should NOT allow replanning (hardware issue)."""
        failure_reason = FailureReason.SENSOR_FAILURE
        mission.retry_count = 0

        should_replan = verifier.should_replan(failure_reason, mission)

        assert should_replan is False
        print(f"✓ Replanning blocked for {failure_reason.value} (hardware issue)")

    def test_replan_not_allowed_when_max_retries_reached(self, verifier, mission):
        """Should not replan if max retries (3) reached."""
        failure_reason = FailureReason.PATH_BLOCKED
        mission.retry_count = 3  # Max retries

        should_replan = verifier.should_replan(failure_reason, mission)

        assert should_replan is False
        print(f"✓ Replanning blocked: max retries reached ({mission.retry_count}/3)")


class TestReplanRequest:
    """Test ReplanRequest schema construction."""

    def test_replan_request_creation(self):
        """Test creating ReplanRequest with all fields."""
        sensor_data = SensorData(
            position_x=1.2,
            position_y=0.8,
            position_z=0.098,
            lidar_min_distance=0.35,
            lidar_avg_distance=2.1,
            lidar_distances=[0.5] * 512
        )

        previous_plan = [
            RobotAction(action=ActionType.MOVE, x=2.0, y=0.0, speed=0.5, reason="Move forward"),
            RobotAction(action=ActionType.ROTATE, angle=90, speed=0.3, reason="Turn right")
        ]

        replan_request = ReplanRequest(
            failure_reason=FailureReason.OBSTACLE_COLLISION,
            sensor_data=sensor_data,
            previous_plan=previous_plan,
            retry_count=1,
            original_command="Move forward 2 meters and turn right",
            failure_details="Obstacle detected at 0.35m distance"
        )

        assert replan_request.failure_reason == FailureReason.OBSTACLE_COLLISION
        assert replan_request.retry_count == 1
        assert len(replan_request.previous_plan) == 2
        assert replan_request.sensor_data.lidar_min_distance == 0.35
        print(f"✓ ReplanRequest created successfully")

    def test_replan_request_validation(self):
        """Test ReplanRequest validation (retry_count range)."""
        sensor_data = SensorData(
            position_x=0.0,
            position_y=0.0,
            position_z=0.098
        )

        # Invalid retry_count (> 3)
        with pytest.raises(Exception):  # Pydantic ValidationError
            ReplanRequest(
                failure_reason=FailureReason.GOAL_UNREACHED,
                sensor_data=sensor_data,
                retry_count=5  # Invalid: max is 3
            )

        print(f"✓ ReplanRequest validation working (retry_count must be 0-3)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
