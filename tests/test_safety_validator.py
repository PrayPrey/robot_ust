"""
Unit tests for SafetyValidator.

Tests safety constraint validation including:
- Obstacle distance checking
- Speed limit enforcement
- Safe zone boundary validation
- Emergency stop triggering
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import numpy as np

from src.safety import SafetyValidator, SafetyConstraints
from src.schemas.robot_action import RobotAction, ActionType
from src.sensors.exceptions import SafetyViolationException


@pytest.fixture
def mock_sensor_manager():
    """Create a mock SensorManager for testing."""
    mock_sm = Mock()
    mock_sm.is_path_clear_ahead = Mock(return_value=True)
    mock_sm.get_obstacles_in_range = Mock(return_value=[])
    return mock_sm


@pytest.fixture
def safety_validator(mock_sensor_manager):
    """Create SafetyValidator with default constraints."""
    constraints = SafetyConstraints()
    return SafetyValidator(mock_sensor_manager, constraints)


@pytest.fixture
def custom_constraints():
    """Create custom safety constraints for testing."""
    return SafetyConstraints(
        min_obstacle_distance=1.0,
        max_speed=0.8,
        safe_zone_bounds=(-3.0, 3.0, -3.0, 3.0),
        emergency_stop_distance=0.3
    )


class TestSafetyConstraints:
    """Test SafetyConstraints Pydantic model."""

    def test_default_constraints(self):
        """Test default constraint values."""
        constraints = SafetyConstraints()

        assert constraints.min_obstacle_distance == 0.5
        assert constraints.max_speed == 1.0
        assert constraints.safe_zone_bounds == (-4.8, 4.8, -4.8, 4.8)
        assert constraints.emergency_stop_distance == 0.2
        assert constraints.forward_check_angle == 30.0

    def test_custom_constraints(self):
        """Test custom constraint values."""
        constraints = SafetyConstraints(
            min_obstacle_distance=1.5,
            max_speed=0.5,
            safe_zone_bounds=(-2.0, 2.0, -2.0, 2.0),
            emergency_stop_distance=0.3,
            forward_check_angle=45.0
        )

        assert constraints.min_obstacle_distance == 1.5
        assert constraints.max_speed == 0.5
        assert constraints.safe_zone_bounds == (-2.0, 2.0, -2.0, 2.0)
        assert constraints.emergency_stop_distance == 0.3
        assert constraints.forward_check_angle == 45.0

    def test_invalid_emergency_distance_too_small(self):
        """Test emergency distance validation - too small."""
        with pytest.raises(ValueError, match="too small"):
            SafetyConstraints(emergency_stop_distance=0.05)

    def test_invalid_safe_zone_x_bounds(self):
        """Test safe zone validation - invalid X bounds."""
        with pytest.raises(ValueError, match="x_min.*must be less than x_max"):
            SafetyConstraints(safe_zone_bounds=(3.0, 2.0, -3.0, 3.0))

    def test_invalid_safe_zone_y_bounds(self):
        """Test safe zone validation - invalid Y bounds."""
        with pytest.raises(ValueError, match="y_min.*must be less than y_max"):
            SafetyConstraints(safe_zone_bounds=(-3.0, 3.0, 3.0, 2.0))

    def test_safe_zone_bounds_too_large(self):
        """Test safe zone validation - bounds too large."""
        with pytest.raises(ValueError, match="too large"):
            SafetyConstraints(safe_zone_bounds=(-15.0, 15.0, -15.0, 15.0))


class TestSafetyValidatorObstacleDetection:
    """Test obstacle distance validation."""

    def test_obstacle_too_close_rejected(self, safety_validator, mock_sensor_manager):
        """Test action rejected when obstacle is too close (AC #5)."""
        # Mock obstacle at 0.3m (min safe distance is 0.5m)
        # Emergency check returns empty (no immediate danger)
        # Normal obstacle check returns obstacles
        mock_sensor_manager.get_obstacles_in_range.side_effect = lambda dist: (
            [] if dist <= 0.2 else [250, 255, 260]  # No emergency, but obstacles in normal range
        )
        mock_sensor_manager.is_path_clear_ahead.return_value = False

        action = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=0.8)
        is_safe, message = safety_validator.validate_action(action)

        assert is_safe is False
        assert "0.5" in message  # Should mention min safe distance
        assert "Obstacle detected" in message
        mock_sensor_manager.is_path_clear_ahead.assert_called_once_with(
            min_distance=0.5,
            angle_range=30.0
        )

    def test_valid_action_approved(self, safety_validator, mock_sensor_manager):
        """Test safe action is approved."""
        # No obstacles detected
        mock_sensor_manager.is_path_clear_ahead.return_value = True
        mock_sensor_manager.get_obstacles_in_range.return_value = []

        action = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=0.8)
        is_safe, message = safety_validator.validate_action(action)

        assert is_safe is True
        assert "passed" in message.lower()

    def test_emergency_stop_triggered(self, safety_validator, mock_sensor_manager):
        """Test emergency stop at critical distance."""
        # Obstacle at emergency distance (0.2m or closer)
        mock_sensor_manager.get_obstacles_in_range.return_value = [255, 256, 257]

        action = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=0.8)
        is_safe, message = safety_validator.validate_action(action)

        assert is_safe is False
        assert "EMERGENCY" in message
        assert "0.2" in message  # Emergency stop distance
        # Should call get_obstacles_in_range with emergency distance FIRST
        calls = mock_sensor_manager.get_obstacles_in_range.call_args_list
        assert calls[0][0][0] == 0.2  # First call with emergency distance

    def test_obstacle_check_for_rotate_action(self, safety_validator, mock_sensor_manager):
        """Test obstacle detection also applies to ROTATE actions."""
        mock_sensor_manager.is_path_clear_ahead.return_value = False
        mock_sensor_manager.get_obstacles_in_range.return_value = [200]

        action = RobotAction(action=ActionType.ROTATE, angle=90.0)
        is_safe, message = safety_validator.validate_action(action)

        assert is_safe is False
        assert "Obstacle detected" in message

    def test_no_obstacle_check_for_scan_action(self, safety_validator, mock_sensor_manager):
        """Test SCAN action doesn't trigger obstacle checks."""
        # Even with obstacles, SCAN should pass (stationary action)
        mock_sensor_manager.is_path_clear_ahead.return_value = False

        action = RobotAction(action=ActionType.SCAN, duration=5.0)
        is_safe, message = safety_validator.validate_action(action)

        assert is_safe is True  # SCAN doesn't check obstacles
        mock_sensor_manager.is_path_clear_ahead.assert_not_called()


class TestSafetyValidatorSpeedLimits:
    """Test speed limit validation."""

    def test_speed_too_high_rejected(self, safety_validator, mock_sensor_manager):
        """Test action rejected when speed exceeds maximum."""
        mock_sensor_manager.is_path_clear_ahead.return_value = True

        # Speed 1.5 m/s exceeds max 1.0 m/s
        action = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=1.5)
        is_safe, message = safety_validator.validate_action(action)

        assert is_safe is False
        assert "1.5" in message
        assert "1.0" in message
        assert "Speed" in message

    def test_speed_at_limit_accepted(self, safety_validator, mock_sensor_manager):
        """Test action accepted when speed equals maximum."""
        mock_sensor_manager.is_path_clear_ahead.return_value = True

        action = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=1.0)
        is_safe, message = safety_validator.validate_action(action)

        assert is_safe is True

    def test_speed_below_limit_accepted(self, safety_validator, mock_sensor_manager):
        """Test action accepted when speed is below maximum."""
        mock_sensor_manager.is_path_clear_ahead.return_value = True

        action = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=0.5)
        is_safe, message = safety_validator.validate_action(action)

        assert is_safe is True


class TestSafetyValidatorSafeZoneBounds:
    """Test safe zone boundary validation."""

    def test_out_of_safe_zone_x_rejected(self, safety_validator, mock_sensor_manager):
        """Test action rejected when X coordinate outside safe zone."""
        mock_sensor_manager.is_path_clear_ahead.return_value = True
        mock_sensor_manager.get_obstacles_in_range.return_value = []

        # X=4.9 exceeds safe zone bound of 4.8 (but within Pydantic's -5 to 5 range)
        # Update: Use construct to bypass Pydantic validation for testing SafetyValidator
        action = RobotAction.model_construct(
            action=ActionType.MOVE,
            x=4.9,  # Just outside safe zone 4.8 but within Pydantic's 5.0 limit
            y=2.0,
            speed=0.8,
            safety_check=True
        )
        is_safe, message = safety_validator.validate_action(action)

        assert is_safe is False
        assert "outside safe zone" in message
        assert "4.9" in message

    def test_out_of_safe_zone_y_rejected(self, safety_validator, mock_sensor_manager):
        """Test action rejected when Y coordinate outside safe zone."""
        mock_sensor_manager.is_path_clear_ahead.return_value = True
        mock_sensor_manager.get_obstacles_in_range.return_value = []

        # Y=-4.9 exceeds safe zone bound of -4.8 (but within Pydantic's -5 to 5 range)
        # Use construct to bypass Pydantic validation for testing SafetyValidator
        action = RobotAction.model_construct(
            action=ActionType.MOVE,
            x=2.0,
            y=-4.9,  # Just outside safe zone -4.8 but within Pydantic's -5.0 limit
            speed=0.8,
            safety_check=True
        )
        is_safe, message = safety_validator.validate_action(action)

        assert is_safe is False
        assert "outside safe zone" in message
        assert "-4.9" in message

    def test_within_safe_zone_accepted(self, safety_validator, mock_sensor_manager):
        """Test action accepted when coordinates are within safe zone."""
        mock_sensor_manager.is_path_clear_ahead.return_value = True

        action = RobotAction(action=ActionType.MOVE, x=3.0, y=3.0, speed=0.8)
        is_safe, message = safety_validator.validate_action(action)

        assert is_safe is True

    def test_at_safe_zone_boundary_accepted(self, safety_validator, mock_sensor_manager):
        """Test action accepted when coordinates are exactly at boundary."""
        mock_sensor_manager.is_path_clear_ahead.return_value = True

        # Exactly at boundary (4.8, 4.8)
        action = RobotAction(action=ActionType.MOVE, x=4.8, y=4.8, speed=0.8)
        is_safe, message = safety_validator.validate_action(action)

        assert is_safe is True


class TestSafetyValidatorBypassMode:
    """Test safety check bypass functionality."""

    def test_safety_check_bypass(self, safety_validator, mock_sensor_manager):
        """Test validation bypassed when safety_check=False."""
        # Set up conditions that would normally fail validation
        mock_sensor_manager.is_path_clear_ahead.return_value = False
        mock_sensor_manager.get_obstacles_in_range.return_value = [100, 200, 300]

        # But with safety_check=False, should bypass
        action = RobotAction(
            action=ActionType.MOVE,
            x=2.0,
            y=1.5,
            speed=1.5,  # Over speed limit
            safety_check=False  # Bypass validation
        )
        is_safe, message = safety_validator.validate_action(action)

        assert is_safe is True
        assert "bypass" in message.lower() or "emergency" in message.lower()


class TestSafetyValidatorRaiseOnViolation:
    """Test raise_on_violation method."""

    def test_raises_exception_on_violation(self, safety_validator, mock_sensor_manager):
        """Test raise_on_violation raises SafetyViolationException."""
        # Set up mocks: no emergency obstacle, but normal obstacle detected
        mock_sensor_manager.get_obstacles_in_range.side_effect = lambda dist: (
            [] if dist <= 0.2 else [250]  # No emergency distance obstacle, but obstacle in normal range
        )
        mock_sensor_manager.is_path_clear_ahead.return_value = False

        action = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=0.8)

        with pytest.raises(SafetyViolationException) as exc_info:
            safety_validator.raise_on_violation(action)

        assert exc_info.value.violation_type == "obstacle_too_close"

    def test_no_exception_when_safe(self, safety_validator, mock_sensor_manager):
        """Test raise_on_violation doesn't raise when action is safe."""
        mock_sensor_manager.is_path_clear_ahead.return_value = True

        action = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=0.8)

        # Should not raise
        safety_validator.raise_on_violation(action)


class TestSafetyValidatorUpdateConstraints:
    """Test dynamic constraint updates."""

    def test_update_constraints(self, safety_validator, mock_sensor_manager, custom_constraints):
        """Test updating constraints at runtime."""
        # Initial constraints: max_speed=1.0
        action_fast = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=0.9)
        mock_sensor_manager.is_path_clear_ahead.return_value = True

        is_safe, _ = safety_validator.validate_action(action_fast)
        assert is_safe is True  # 0.9 < 1.0

        # Update to more restrictive constraints: max_speed=0.8
        safety_validator.update_constraints(custom_constraints)

        is_safe, message = safety_validator.validate_action(action_fast)
        assert is_safe is False  # 0.9 > 0.8
        assert "0.9" in message
        assert "0.8" in message


class TestSafetyViolationException:
    """Test SafetyViolationException class."""

    def test_exception_creation(self):
        """Test creating SafetyViolationException."""
        action = RobotAction(action=ActionType.MOVE, x=2.0, y=1.5, speed=1.5)
        exc = SafetyViolationException(
            "speed_too_high",
            "Speed 1.5 m/s exceeds maximum 1.0 m/s",
            action
        )

        assert exc.violation_type == "speed_too_high"
        assert exc.action == action
        assert "speed_too_high" in str(exc)
        assert "1.5" in str(exc)

    def test_exception_without_action(self):
        """Test creating exception without action."""
        exc = SafetyViolationException(
            "obstacle_too_close",
            "Obstacle at 0.3m"
        )

        assert exc.violation_type == "obstacle_too_close"
        assert exc.action is None
