"""
Test Pydantic Schemas

Unit tests for RobotAction, RobotState, and MissionCommand schemas.
"""

import pytest
from pydantic import ValidationError
from src.schemas import (
    RobotAction,
    ActionType,
    RobotState,
    RobotStatus,
    SensorData,
    MissionCommand,
    MissionStatus
)


class TestRobotAction:
    """Test RobotAction schema validation."""

    def test_valid_move_action(self):
        """Test valid MOVE action creation."""
        action = RobotAction(
            action=ActionType.MOVE,
            x=2.5,
            y=3.0,
            speed=1.0
        )
        assert action.action == ActionType.MOVE
        assert action.x == 2.5
        assert action.y == 3.0
        assert action.speed == 1.0

    def test_move_without_coordinates_fails(self):
        """Test that MOVE action without coordinates fails."""
        with pytest.raises(ValidationError) as exc_info:
            RobotAction(
                action=ActionType.MOVE,
                speed=1.0
            )
        assert "MOVE action requires both x and y coordinates" in str(exc_info.value)

    def test_rotate_action(self):
        """Test valid ROTATE action."""
        action = RobotAction(
            action=ActionType.ROTATE,
            angle=90.0,
            speed=0.5
        )
        assert action.action == ActionType.ROTATE
        assert action.angle == 90.0

    def test_coordinates_out_of_bounds(self):
        """Test that coordinates beyond environment bounds fail."""
        with pytest.raises(ValidationError):
            RobotAction(
                action=ActionType.MOVE,
                x=10.0,  # Beyond 5.0 limit
                y=2.0
            )

    def test_speed_limit_validation(self):
        """Test speed limit validation."""
        with pytest.raises(ValidationError):
            RobotAction(
                action=ActionType.MOVE,
                x=1.0,
                y=1.0,
                speed=3.0  # Beyond 2.0 limit
            )

    def test_scan_action_requires_duration(self):
        """Test that SCAN action requires duration."""
        with pytest.raises(ValidationError) as exc_info:
            RobotAction(action=ActionType.SCAN)
        assert "requires duration parameter" in str(exc_info.value)

    def test_to_webots_command(self):
        """Test conversion to Webots command format."""
        action = RobotAction(
            action=ActionType.MOVE,
            x=1.5,
            y=2.3,
            speed=1.2
        )
        command = action.to_webots_command()
        assert command["action"] == "move"
        assert command["x"] == 1.5
        assert command["y"] == 2.3
        assert command["speed"] == 1.2


class TestRobotState:
    """Test RobotState schema validation."""

    def test_initial_state(self):
        """Test initial robot state creation."""
        state = RobotState(
            robot_id="test_robot",
            status=RobotStatus.IDLE
        )
        assert state.robot_id == "test_robot"
        assert state.status == RobotStatus.IDLE
        assert state.battery_level == 100.0

    def test_state_with_sensor_data(self):
        """Test robot state with complete sensor data."""
        sensors = SensorData(
            position_x=1.5,
            position_y=2.3,
            position_z=0.098,
            roll=0.0,
            pitch=0.1,
            yaw=90.0,
            lidar_min_distance=1.95,
            camera_has_data=True
        )
        state = RobotState(
            robot_id="rescue_robot",
            status=RobotStatus.MOVING,
            sensors=sensors
        )
        assert state.sensors.position_x == 1.5
        assert state.sensors.yaw == 90.0

    def test_get_position(self):
        """Test position extraction from GPS."""
        state = RobotState(
            sensors=SensorData(
                position_x=1.0,
                position_y=2.0,
                position_z=0.1
            )
        )
        position = state.get_position()
        assert position == (1.0, 2.0, 0.1)

    def test_is_operational(self):
        """Test operational status check."""
        state_idle = RobotState(status=RobotStatus.IDLE)
        state_error = RobotState(status=RobotStatus.ERROR)

        assert state_idle.is_operational() is True
        assert state_error.is_operational() is False

    def test_battery_validation(self):
        """Test battery level constraints."""
        with pytest.raises(ValidationError):
            RobotState(battery_level=150.0)  # Beyond 100%

        with pytest.raises(ValidationError):
            RobotState(battery_level=-10.0)  # Negative


class TestSensorData:
    """Test SensorData schema validation."""

    def test_lidar_data_validation(self):
        """Test Lidar data format validation."""
        # Valid: 512 points
        sensors = SensorData(
            lidar_distances=[1.5] * 512
        )
        assert len(sensors.lidar_distances) == 512

        # Invalid: wrong number of points
        with pytest.raises(ValidationError) as exc_info:
            SensorData(lidar_distances=[1.5] * 100)
        assert "512 points" in str(exc_info.value)

    def test_get_obstacles_nearby(self):
        """Test nearby obstacle detection."""
        sensors = SensorData(
            lidar_distances=[0.5, 1.5, 0.8, 2.0] + [5.0] * 508
        )
        obstacles = sensors.get_obstacles_nearby(threshold=1.0)
        assert 0 in obstacles  # 0.5m
        assert 2 in obstacles  # 0.8m
        assert 1 not in obstacles  # 1.5m > threshold

    def test_is_path_clear(self):
        """Test path clearance check."""
        # All distances > 1m
        sensors = SensorData(
            lidar_distances=[2.0] * 512
        )
        assert sensors.is_path_clear((0, 45), min_distance=1.0) is True

        # Some distances < 1m in the checked range
        # Angle range (0, 45) maps to indices around 256-320
        sensors.lidar_distances[280] = 0.3
        assert sensors.is_path_clear((0, 45), min_distance=1.0) is False


class TestMissionCommand:
    """Test MissionCommand schema validation."""

    def test_valid_korean_command(self):
        """Test valid Korean mission command."""
        mission = MissionCommand(
            command="3층 동쪽 구역에서 생존자 탐색",
            language="ko",
            priority=8
        )
        assert mission.language == "ko"
        assert mission.priority == 8
        assert mission.status == MissionStatus.PENDING

    def test_valid_english_command(self):
        """Test valid English mission command."""
        mission = MissionCommand(
            command="Search for survivors in the east wing",
            language="en"
        )
        assert mission.language == "en"

    def test_command_too_short(self):
        """Test that short commands are rejected."""
        with pytest.raises(ValidationError):
            MissionCommand(command="Go")  # Too short (< 10 chars)

    def test_command_without_keywords(self):
        """Test that commands without actionable keywords fail."""
        with pytest.raises(ValidationError) as exc_info:
            MissionCommand(command="This is just a random sentence")
        assert "actionable keywords" in str(exc_info.value)

    def test_mission_lifecycle(self):
        """Test mission status lifecycle."""
        mission = MissionCommand(
            command="Navigate to safe zone and search",
            language="en"
        )

        # Start execution
        mission.start_execution()
        assert mission.status == MissionStatus.EXECUTING
        assert mission.started_at is not None

        # Mark completed
        mission.mark_completed(success=True, message="Mission successful")
        assert mission.status == MissionStatus.COMPLETED
        assert mission.success is True
        assert mission.completed_at is not None

    def test_retry_mechanism(self):
        """Test retry count and limits."""
        mission = MissionCommand(
            command="Search and rescue mission",
            language="en"
        )

        # Mark as failed
        mission.mark_failed("Obstacle blocked path")
        assert mission.can_retry() is True

        # Increment retries
        mission.increment_retry()
        assert mission.retry_count == 1

        mission.mark_failed("Path still blocked")
        mission.increment_retry()
        assert mission.retry_count == 2

        mission.mark_failed("Third failure")
        mission.increment_retry()
        assert mission.retry_count == 3

        # Cannot retry beyond 3
        assert mission.can_retry() is False
        with pytest.raises(ValueError) as exc_info:
            mission.increment_retry()
        assert "Maximum retry attempts" in str(exc_info.value)

    def test_progress_calculation(self):
        """Test mission progress calculation."""
        mission = MissionCommand(
            command="Multi-step rescue operation",
            language="en",
            action_plan=[
                RobotAction(action=ActionType.MOVE, x=1.0, y=1.0),
                RobotAction(action=ActionType.SCAN, duration=5.0),
                RobotAction(action=ActionType.MOVE, x=2.0, y=2.0),
            ],
            current_action_index=1
        )

        progress = mission.get_progress()
        assert progress == pytest.approx(33.33, rel=0.1)  # 1/3 complete


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
