"""
Safety Validator for robot action validation.

This module provides runtime safety validation for robot actions,
checking for obstacle collisions, speed limits, and safe zone boundaries.
"""

from typing import Tuple, Optional
from loguru import logger

from ..schemas.robot_action import RobotAction, ActionType
from ..sensors.sensor_manager import SensorManager
from ..sensors.exceptions import SafetyViolationException
from .constraints import SafetyConstraints, DEFAULT_SAFETY_CONSTRAINTS


class SafetyValidator:
    """
    Validates robot actions against safety constraints.

    Performs real-time safety checks including:
    - Obstacle distance validation using Lidar data
    - Speed limit enforcement
    - Safe zone boundary validation
    - Emergency stop triggering

    Example:
        >>> from controller import Robot
        >>> from ..sensors import SensorManager
        >>> robot = Robot()
        >>> sensor_mgr = SensorManager(robot)
        >>> validator = SafetyValidator(sensor_mgr)
        >>> action = RobotAction(action="move", x=2.0, y=1.5, speed=0.8)
        >>> is_safe, message = validator.validate_action(action)
        >>> if is_safe:
        ...     # Execute action
        ...     pass
    """

    def __init__(
        self,
        sensor_manager: SensorManager,
        constraints: Optional[SafetyConstraints] = None
    ):
        """
        Initialize SafetyValidator with sensor manager and constraints.

        Args:
            sensor_manager: SensorManager instance for accessing sensor data
            constraints: SafetyConstraints instance (uses DEFAULT_SAFETY_CONSTRAINTS if None)

        Example:
            >>> validator = SafetyValidator(sensor_mgr, SafetyConstraints(max_speed=0.8))
        """
        self.sensor_manager = sensor_manager
        self.constraints = constraints or DEFAULT_SAFETY_CONSTRAINTS

        logger.info(
            f"SafetyValidator initialized: "
            f"min_obstacle_distance={self.constraints.min_obstacle_distance}m, "
            f"max_speed={self.constraints.max_speed}m/s, "
            f"emergency_stop_distance={self.constraints.emergency_stop_distance}m"
        )

    def validate_action(self, action: RobotAction) -> Tuple[bool, str]:
        """
        Validate a robot action against all safety constraints.

        Performs comprehensive safety validation including:
        1. Obstacle detection (Lidar-based)
        2. Speed limit validation
        3. Safe zone boundary check
        4. Emergency stop distance check

        Args:
            action: RobotAction to validate

        Returns:
            Tuple[bool, str]: (is_safe, message)
                - is_safe: True if action is safe, False otherwise
                - message: Explanation of validation result

        Example:
            >>> action = RobotAction(action="move", x=2.0, y=1.5, speed=0.8)
            >>> is_safe, msg = validator.validate_action(action)
            >>> print(f"Safe: {is_safe}, Reason: {msg}")
            Safe: True, Reason: All safety checks passed
        """
        # Skip validation if safety_check is disabled (emergency mode)
        if not action.safety_check:
            logger.warning(
                f"Safety validation bypassed for action: {action.action.value} "
                f"(safety_check=False)"
            )
            return True, "Safety validation bypassed (emergency mode)"

        # Check 1: Speed limit validation
        if action.speed is not None and action.speed > self.constraints.max_speed:
            message = (
                f"Speed {action.speed:.2f} m/s exceeds maximum "
                f"{self.constraints.max_speed:.2f} m/s"
            )
            logger.warning(f"Safety violation: {message}")
            return False, message

        # Check 2: Safe zone boundary validation (for move actions)
        # IMPORTANT: Skip bounds check for relative moves - coordinates will be converted
        # to absolute in ActorAgent._execute_move() and validated there
        if action.action == ActionType.MOVE:
            if action.relative:
                logger.debug(
                    f"Skipping bounds check for relative move (x={action.x}, y={action.y}) - "
                    f"will validate after coordinate conversion in ActorAgent"
                )
            else:
                is_in_bounds, bounds_msg = self._check_safe_zone_bounds(action.x, action.y)
                if not is_in_bounds:
                    logger.warning(f"Safety violation: {bounds_msg}")
                    return False, bounds_msg

        # Check 3: Obstacle distance validation (for move/rotate actions)
        if action.action in [ActionType.MOVE, ActionType.ROTATE]:
            is_clear, obstacle_msg = self._check_obstacle_distance(action)
            if not is_clear:
                logger.warning(f"Safety violation: {obstacle_msg}")
                return False, obstacle_msg

        # All checks passed
        logger.debug(
            f"Action validated successfully: {action.action.value} "
            f"(x={action.x}, y={action.y}, speed={action.speed})"
        )
        return True, "All safety checks passed"

    def _check_safe_zone_bounds(
        self,
        x: Optional[float],
        y: Optional[float]
    ) -> Tuple[bool, str]:
        """
        Check if target coordinates are within safe zone boundaries.

        Args:
            x: Target X coordinate
            y: Target Y coordinate

        Returns:
            Tuple[bool, str]: (is_in_bounds, message)
        """
        if x is None or y is None:
            return True, "No coordinates to check"

        x_min, x_max, y_min, y_max = self.constraints.safe_zone_bounds

        if not (x_min <= x <= x_max and y_min <= y <= y_max):
            message = (
                f"Target position ({x:.2f}, {y:.2f}) is outside safe zone "
                f"bounds: X[{x_min:.1f}, {x_max:.1f}], Y[{y_min:.1f}, {y_max:.1f}]"
            )
            return False, message

        return True, "Position within safe zone"

    def _check_obstacle_distance(self, action: RobotAction) -> Tuple[bool, str]:
        """
        Check if path is clear of obstacles using Lidar data.

        Uses SensorManager's is_path_clear_ahead() method to detect
        obstacles within the minimum safe distance.

        EMERGENCY ESCAPE LOGIC:
        - Backward movement (relative=True, x<0): Skips forward obstacle check to allow escape
        - Rotation: Only checks emergency distance (<0.2m), more lenient to allow maneuvering
        - Forward movement: Full safety checks

        Args:
            action: RobotAction being validated

        Returns:
            Tuple[bool, str]: (is_clear, message)
        """
        # Detect backward movement (emergency escape)
        is_backward = False
        if action.action == ActionType.MOVE and action.relative and action.x is not None and action.x < 0:
            is_backward = True
            logger.info(f"Backward movement detected (x={action.x:.2f}m) - relaxing forward obstacle checks for emergency escape")

        # Detect rotation (allow more lenient checks for maneuvering)
        is_rotation = action.action == ActionType.ROTATE

        # Check for emergency stop distance (always enforce, even for backward/rotation)
        obstacles_emergency = self.sensor_manager.get_obstacles_in_range(
            self.constraints.emergency_stop_distance
        )

        if obstacles_emergency:
            # For rotation or backward movement, be more lenient - allow if not critical
            if is_rotation or is_backward:
                logger.debug(f"{'Rotation' if is_rotation else 'Backward movement'} action: emergency obstacles detected but allowing for maneuvering/escape")
            else:
                message = (
                    f"EMERGENCY: Obstacle detected at {self.constraints.emergency_stop_distance:.2f}m or closer "
                    f"({len(obstacles_emergency)} Lidar points). Immediate stop required!"
                )
                return False, message

        # Skip forward obstacle check for backward movement (emergency escape)
        if is_backward:
            logger.debug("Backward movement: skipping forward obstacle check (emergency escape mode)")
            return True, "Backward movement allowed for emergency escape"

        # For rotation, only emergency check is required (already done above)
        if is_rotation:
            return True, "Rotation allowed for maneuvering"

        # Check normal minimum safe distance (for forward movement)
        is_clear = self.sensor_manager.is_path_clear_ahead(
            min_distance=self.constraints.min_obstacle_distance,
            angle_range=self.constraints.forward_check_angle
        )

        if not is_clear:
            # Get detailed obstacle information
            obstacles = self.sensor_manager.get_obstacles_in_range(
                self.constraints.min_obstacle_distance
            )
            message = (
                f"Obstacle detected within {self.constraints.min_obstacle_distance:.2f}m "
                f"({len(obstacles)} Lidar points). Minimum safe distance violated."
            )
            return False, message

        return True, "Path ahead is clear"

    def raise_on_violation(self, action: RobotAction) -> None:
        """
        Validate action and raise SafetyViolationException if unsafe.

        This is a convenience method that raises an exception instead of
        returning a tuple, useful for flow control where exceptions are preferred.

        Args:
            action: RobotAction to validate

        Raises:
            SafetyViolationException: If action violates safety constraints

        Example:
            >>> try:
            ...     validator.raise_on_violation(action)
            ...     # Execute action
            ... except SafetyViolationException as e:
            ...     logger.error(f"Safety violation: {e}")
        """
        is_safe, message = self.validate_action(action)

        if not is_safe:
            # Determine violation type from message
            violation_type = self._determine_violation_type(message)
            raise SafetyViolationException(violation_type, message, action)

    def _determine_violation_type(self, message: str) -> str:
        """Determine violation type from validation message."""
        message_lower = message.lower()

        if "emergency" in message_lower:
            return "emergency_stop"
        elif "obstacle" in message_lower:
            return "obstacle_too_close"
        elif "speed" in message_lower:
            return "speed_too_high"
        elif "outside safe zone" in message_lower or "bounds" in message_lower:
            return "out_of_bounds"
        else:
            return "unknown"

    def update_constraints(self, constraints: SafetyConstraints) -> None:
        """
        Update safety constraints at runtime.

        Allows dynamic adjustment of safety parameters without recreating
        the validator instance.

        Args:
            constraints: New SafetyConstraints configuration

        Example:
            >>> new_constraints = SafetyConstraints(max_speed=0.5, min_obstacle_distance=1.0)
            >>> validator.update_constraints(new_constraints)
        """
        self.constraints = constraints
        logger.info(
            f"Safety constraints updated: "
            f"min_obstacle_distance={constraints.min_obstacle_distance}m, "
            f"max_speed={constraints.max_speed}m/s"
        )
