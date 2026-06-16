"""
Integration tests for ActorAgent + SafetyValidator.

Tests the complete safety validation flow:
- ActorAgent integrates SafetyValidator
- Actions are validated before execution
- Unsafe actions are rejected with proper logging
- Safe actions are executed normally
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import numpy as np

from src.agents.actor_agent import ActorAgent
from src.schemas.robot_action import RobotAction, ActionType
from src.safety import SafetyConstraints
from src.sensors.exceptions import SafetyViolationException


@pytest.fixture
def mock_robot():
    """Create a mock Webots Robot instance."""
    robot = Mock()

    # Mock motors
    left_motor = Mock()
    right_motor = Mock()
    left_motor.setPosition = Mock()
    right_motor.setPosition = Mock()
    left_motor.setVelocity = Mock()
    right_motor.setVelocity = Mock()

    robot.getDevice = Mock(side_effect=lambda name: {
        'left wheel': left_motor,
        'right wheel': right_motor,
        'gps': create_mock_sensor('gps'),
        'imu': create_mock_sensor('imu'),
        'lidar': create_mock_sensor('lidar'),
        'front_camera': create_mock_sensor('camera')  # Correct device name
    }.get(name))

    robot.step = Mock(return_value=0)  # Simulation continues
    robot.getTime = Mock(return_value=0.0)

    return robot


def create_mock_sensor(sensor_type):
    """Create a mock sensor device."""
    sensor = Mock()
    sensor.enable = Mock()
    sensor.getSamplingPeriod = Mock(return_value=64)

    if sensor_type == 'gps':
        sensor.getValues = Mock(return_value=[0.0, 0.0, 0.0])
    elif sensor_type == 'imu':
        sensor.getRollPitchYaw = Mock(return_value=[0.0, 0.0, 0.0])
    elif sensor_type == 'lidar':
        sensor.getRangeImage = Mock(return_value=[10.0] * 512)
        sensor.getNumberOfPoints = Mock(return_value=512)
    elif sensor_type == 'camera':
        sensor.getImage = Mock(return_value=bytes([128] * (640 * 480 * 4)))
        sensor.getWidth = Mock(return_value=640)
        sensor.getHeight = Mock(return_value=480)

    return sensor


@pytest.fixture
def actor_agent(mock_robot):
    """Create ActorAgent with mocked robot."""
    # Mock both ChatOpenAI and Agent to avoid LLM initialization
    mock_llm = Mock()
    mock_llm.model_name = "gpt-4o-mini"

    with patch('src.agents.actor_agent.ChatOpenAI', return_value=mock_llm), \
         patch('src.agents.actor_agent.Agent') as mock_agent_class:

        mock_agent_instance = Mock()
        mock_agent_class.return_value = mock_agent_instance

        actor = ActorAgent(
            robot=mock_robot,
            api_key="test-key",
            model="gpt-4o-mini",
            verbose=False
        )
    return actor


class TestActorAgentSafetyIntegration:
    """Test ActorAgent integrates SafetyValidator correctly."""

    def test_safety_validator_initialized(self, actor_agent):
        """Test SafetyValidator is initialized in ActorAgent."""
        assert hasattr(actor_agent, 'safety_validator')
        assert actor_agent.safety_validator is not None
        assert hasattr(actor_agent.safety_validator, 'validate_action')

    def test_sensor_manager_initialized(self, actor_agent):
        """Test SensorManager is initialized (required by SafetyValidator)."""
        assert hasattr(actor_agent, 'sensor_manager')
        assert actor_agent.sensor_manager is not None

    def test_safe_action_executes_successfully(self, actor_agent, mock_robot):
        """Test safe action passes validation and executes."""
        # Mock safe conditions
        actor_agent.sensor_manager.is_path_clear_ahead = Mock(return_value=True)
        actor_agent.sensor_manager.get_obstacles_in_range = Mock(return_value=[])
        # Mock sensor data with individual position fields (not tuple)
        mock_sensor_data = Mock()
        mock_sensor_data.position_x = 0.0
        mock_sensor_data.position_y = 0.0
        mock_sensor_data.position_z = 0.0
        actor_agent.sensor_manager.get_sensor_data = Mock(return_value=mock_sensor_data)

        # Safe action
        action = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=0.8)

        result = actor_agent.execute_action(action)

        assert result is True  # Action executed
        actor_agent.sensor_manager.is_path_clear_ahead.assert_called_once()

    def test_obstacle_too_close_action_rejected(self, actor_agent, mock_robot):
        """Test action rejected when obstacle is too close."""
        # Mock unsafe conditions - obstacle at 0.3m (min safe distance: 0.5m)
        actor_agent.sensor_manager.is_path_clear_ahead = Mock(return_value=False)
        actor_agent.sensor_manager.get_obstacles_in_range = Mock(return_value=[250, 255, 260])

        # Unsafe action
        action = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=0.8)

        with patch('src.agents.actor_agent.logger') as mock_logger:
            result = actor_agent.execute_action(action)

            assert result is False  # Action rejected
            # Check warning was logged
            mock_logger.warning.assert_called()
            warning_call = mock_logger.warning.call_args[0][0]
            assert "rejected" in warning_call.lower() or "safety" in warning_call.lower()

    def test_speed_too_high_action_rejected(self, actor_agent, mock_robot):
        """Test action rejected when speed exceeds limit."""
        # Mock safe obstacle conditions
        actor_agent.sensor_manager.is_path_clear_ahead = Mock(return_value=True)
        actor_agent.sensor_manager.get_obstacles_in_range = Mock(return_value=[])

        # Speed 1.5 m/s exceeds max 1.0 m/s
        action = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=1.5)

        result = actor_agent.execute_action(action)

        assert result is False  # Action rejected

    def test_out_of_bounds_action_rejected(self, actor_agent, mock_robot):
        """Test action rejected when target is outside safe zone."""
        # Mock safe obstacle conditions
        actor_agent.sensor_manager.is_path_clear_ahead = Mock(return_value=True)
        actor_agent.sensor_manager.get_obstacles_in_range = Mock(return_value=[])

        # X=5.0 exceeds safe zone bound of 4.8
        action = RobotAction(action=ActionType.MOVE, x=5.0, y=2.0, speed=0.8)

        result = actor_agent.execute_action(action)

        assert result is False  # Action rejected

    def test_safety_bypass_mode(self, actor_agent, mock_robot):
        """Test validation bypassed when safety_check=False (emergency mode)."""
        # Mock unsafe conditions
        actor_agent.sensor_manager.is_path_clear_ahead = Mock(return_value=False)
        actor_agent.sensor_manager.get_obstacles_in_range = Mock(return_value=[100, 200])
        # Mock sensor data with individual position and orientation fields
        mock_sensor_data = Mock()
        mock_sensor_data.position_x = 0.0
        mock_sensor_data.position_y = 0.0
        mock_sensor_data.position_z = 0.0
        mock_sensor_data.yaw = 0.0  # Add IMU yaw
        actor_agent.sensor_manager.get_sensor_data = Mock(return_value=mock_sensor_data)

        # Action with safety_check=False - should bypass safety validation
        action = RobotAction(
            action=ActionType.MOVE,
            x=2.0,
            y=1.5,
            speed=0.8,  # Use safe speed to avoid ActorAgent's speed check (not SafetyValidator)
            safety_check=False  # Bypass SafetyValidator
        )

        result = actor_agent.execute_action(action)

        # Should execute despite unsafe obstacle conditions (because safety_check=False)
        assert result is True

    def test_rotate_action_safety_validation(self, actor_agent, mock_robot):
        """Test ROTATE action also undergoes safety validation."""
        # Mock unsafe conditions
        actor_agent.sensor_manager.is_path_clear_ahead = Mock(return_value=False)
        actor_agent.sensor_manager.get_obstacles_in_range = Mock(return_value=[200])

        action = RobotAction(action=ActionType.ROTATE, angle=90.0)

        result = actor_agent.execute_action(action)

        assert result is False  # Rejected due to obstacle

    def test_scan_action_no_obstacle_check(self, actor_agent, mock_robot):
        """Test SCAN action doesn't check obstacles (stationary)."""
        # Mock unsafe conditions (but SCAN should still pass)
        actor_agent.sensor_manager.is_path_clear_ahead = Mock(return_value=False)
        actor_agent.sensor_manager.get_obstacles_in_range = Mock(return_value=[])

        action = RobotAction(action=ActionType.SCAN, duration=5.0)

        result = actor_agent.execute_action(action)

        assert result is True  # SCAN doesn't check obstacles
        actor_agent.sensor_manager.is_path_clear_ahead.assert_not_called()

    def test_emergency_stop_distance_triggers(self, actor_agent, mock_robot):
        """Test emergency stop triggered at critical distance."""
        # Mock critical emergency distance (0.2m or closer)
        actor_agent.sensor_manager.get_obstacles_in_range = Mock(
            side_effect=lambda dist: [250, 255] if dist <= 0.2 else []
        )

        action = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=0.8)

        with patch('src.agents.actor_agent.logger') as mock_logger:
            result = actor_agent.execute_action(action)

            assert result is False
            # Check for emergency warning in logs
            warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
            assert any("EMERGENCY" in str(call) for call in warning_calls)


class TestActorAgentMultipleActions:
    """Test multiple action sequence with safety validation."""

    def test_mixed_safe_and_unsafe_actions(self, actor_agent, mock_robot):
        """Test sequence of safe and unsafe actions."""
        # Setup mocks - mock sensor data with individual position fields
        mock_sensor_data = Mock()
        mock_sensor_data.position_x = 0.0
        mock_sensor_data.position_y = 0.0
        mock_sensor_data.position_z = 0.0
        mock_sensor_data.yaw = 0.0
        actor_agent.sensor_manager.get_sensor_data = Mock(return_value=mock_sensor_data)

        actions_and_expected = [
            # (action, should_pass, obstacle_clear)
            (RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=0.8), True, True),
            (RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=1.5), False, True),  # Speed too high
            (RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=0.8), False, False),  # Obstacle
            (RobotAction(action=ActionType.MOVE, x=5.0, y=2.0, speed=0.8), False, True),  # Out of bounds
        ]

        results = []
        for action, should_pass, obstacle_clear in actions_and_expected:
            actor_agent.sensor_manager.is_path_clear_ahead = Mock(return_value=obstacle_clear)
            actor_agent.sensor_manager.get_obstacles_in_range = Mock(
                return_value=[] if obstacle_clear else [200]
            )

            result = actor_agent.execute_action(action)
            results.append(result)

        assert results == [True, False, False, False]


class TestSafetyValidatorConstraintsIntegration:
    """Test custom safety constraints integration."""

    def test_custom_constraints_applied(self, mock_robot):
        """Test ActorAgent respects custom safety constraints."""
        # Mock both ChatOpenAI and Agent
        mock_llm = Mock()
        mock_llm.model_name = "gpt-4o-mini"

        with patch('src.agents.actor_agent.ChatOpenAI', return_value=mock_llm), \
             patch('src.agents.actor_agent.Agent'):

            actor = ActorAgent(
                robot=mock_robot,
                api_key="test-key",
                verbose=False
            )

        # Update to more restrictive constraints
        custom_constraints = SafetyConstraints(
            max_speed=0.5,
            min_obstacle_distance=1.0,
            safe_zone_bounds=(-2.0, 2.0, -2.0, 2.0)
        )
        actor.safety_validator.update_constraints(custom_constraints)

        # Mock safe conditions
        actor.sensor_manager.is_path_clear_ahead = Mock(return_value=True)
        actor.sensor_manager.get_obstacles_in_range = Mock(return_value=[])

        # Test speed limit
        action_fast = RobotAction(action=ActionType.MOVE, x=1.0, y=1.0, speed=0.6)
        result = actor.execute_action(action_fast)
        assert result is False  # 0.6 > 0.5 max_speed

        # Test safe zone
        action_far = RobotAction(action=ActionType.MOVE, x=3.0, y=1.0, speed=0.4)
        result = actor.execute_action(action_far)
        assert result is False  # 3.0 > 2.0 safe_zone bound


class TestActorAgentLogging:
    """Test safety validation logging."""

    def test_safety_pass_logged(self, actor_agent, mock_robot):
        """Test successful validation is logged."""
        actor_agent.sensor_manager.is_path_clear_ahead = Mock(return_value=True)
        actor_agent.sensor_manager.get_obstacles_in_range = Mock(return_value=[])
        actor_agent.sensor_manager.get_sensor_data = Mock()
        actor_agent.sensor_manager.get_sensor_data.return_value.position = (0.0, 0.0, 0.0)

        action = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=0.8)

        with patch('src.agents.actor_agent.logger') as mock_logger:
            actor_agent.execute_action(action)

            # Check debug log was called
            mock_logger.debug.assert_called()

    def test_safety_fail_logged(self, actor_agent, mock_robot):
        """Test failed validation is logged with warning."""
        actor_agent.sensor_manager.is_path_clear_ahead = Mock(return_value=False)
        actor_agent.sensor_manager.get_obstacles_in_range = Mock(return_value=[200])

        action = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=0.8)

        with patch('src.agents.actor_agent.logger') as mock_logger:
            actor_agent.execute_action(action)

            # Check warning log was called
            mock_logger.warning.assert_called()
            warning_message = mock_logger.warning.call_args[0][0]
            assert "rejected" in warning_message.lower() or "safety" in warning_message.lower()
