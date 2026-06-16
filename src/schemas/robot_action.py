"""
Robot Action Schema

Pydantic schema for robot actions with validation and safety constraints.
Used for LLM Function Calling to control Webots robot.
"""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator
from typing_extensions import Self


class ActionType(str, Enum):
    """Available robot action types."""
    # Mobile base actions
    MOVE = "move"
    ROTATE = "rotate"
    SCAN = "scan"
    STOP = "stop"
    WAIT = "wait"
    # Arm manipulation actions
    ARM_MOVE = "arm_move"  # Move arm to specific joint positions
    GRIP = "grip"          # Close gripper to grasp object
    RELEASE = "release"    # Open gripper to release object


class RobotAction(BaseModel):
    """
    Robot action schema for LLM Function Calling.

    Validates robot actions with safety constraints:
    - Position limits: -5m to 5m (10m×10m environment)
    - Speed limits: 0.1 to 2.0 m/s
    - Rotation limits: -180° to 180°
    - Safety distance: minimum 0.5m from obstacles

    Example:
        >>> action = RobotAction(
        ...     action="move",
        ...     x=2.5,
        ...     y=3.0,
        ...     speed=1.0
        ... )
    """

    action: ActionType = Field(
        description="Type of action to perform (move, rotate, scan, stop, wait)"
    )

    x: Optional[float] = Field(
        default=None,
        ge=-5.0,
        le=5.0,
        description="X coordinate or distance in meters (for move action). Absolute if relative=False, relative if relative=True"
    )

    y: Optional[float] = Field(
        default=None,
        ge=-5.0,
        le=5.0,
        description="Y coordinate or distance in meters (for move action). Absolute if relative=False, relative if relative=True"
    )

    relative: bool = Field(
        default=False,
        description="If True, x/y are relative to current position and orientation. If False, x/y are absolute world coordinates"
    )

    angle: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Rotation angle in degrees (for rotate action)"
    )

    speed: Optional[float] = Field(
        default=1.0,
        gt=0.0,
        le=2.0,
        description="Movement speed in m/s (default: 1.0)"
    )

    duration: Optional[float] = Field(
        default=None,
        gt=0.0,
        le=10.0,
        description="Action duration in seconds (for wait/scan)"
    )

    safety_check: bool = Field(
        default=True,
        description="Enable safety validation (collision avoidance)"
    )

    reason: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Reason for this action (for logging/debugging)"
    )

    # ========== ARM MANIPULATION PARAMETERS ==========
    shoulder_angle: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Shoulder joint angle in degrees (for arm_move action)"
    )

    elbow_angle: Optional[float] = Field(
        default=None,
        ge=-115.0,
        le=115.0,
        description="Elbow joint angle in degrees (for arm_move action)"
    )

    gripper_force: Optional[float] = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Gripper force ratio 0.0-1.0 (for grip action)"
    )

    # NOTE: Coordinate safety validation moved to SafetyValidator
    # This allows separation of concerns:
    # - Pydantic validates data format/range (-5.0 to 5.0)
    # - SafetyValidator validates safety logic at runtime (safe_zone_bounds)
    # Removed @field_validator to allow SafetyValidator to handle boundary checks

    @field_validator("speed")
    @classmethod
    def validate_speed(cls, v: Optional[float]) -> Optional[float]:
        """Validate speed is within safe limits."""
        if v is not None and v > 1.5:
            # Warn for high speed (still valid but cautious)
            import warnings
            warnings.warn(
                f"Speed {v} m/s is high. Consider reducing for safety.",
                UserWarning
            )
        return v

    @model_validator(mode="after")
    def validate_action_parameters(self) -> Self:
        """Validate that required parameters are present for each action type."""
        if self.action == ActionType.MOVE:
            if self.x is None or self.y is None:
                raise ValueError(
                    f"MOVE action requires both x and y coordinates. "
                    f"Got x={self.x}, y={self.y}"
                )

        elif self.action == ActionType.ROTATE:
            if self.angle is None:
                raise ValueError(
                    "ROTATE action requires angle parameter"
                )

        elif self.action == ActionType.SCAN or self.action == ActionType.WAIT:
            if self.duration is None:
                raise ValueError(
                    f"{self.action.value.upper()} action requires duration parameter"
                )

        # ARM_MOVE action requires at least one arm joint angle
        elif self.action == ActionType.ARM_MOVE:
            if self.shoulder_angle is None and self.elbow_angle is None:
                raise ValueError(
                    "ARM_MOVE action requires at least one of: shoulder_angle, elbow_angle"
                )

        # GRIP and RELEASE actions require no additional parameters (use defaults)
        # STOP action requires no additional parameters

        return self

    def to_webots_command(self) -> dict:
        """
        Convert to Webots API command format.

        Returns:
            dict: Command dictionary for Webots Python API
        """
        return {
            "action": self.action.value,
            "x": self.x,
            "y": self.y,
            "angle": self.angle,
            "speed": self.speed,
            "duration": self.duration,
            "safety_check": self.safety_check,
            # Arm parameters
            "shoulder_angle": self.shoulder_angle,
            "elbow_angle": self.elbow_angle,
            "gripper_force": self.gripper_force,
        }

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "examples": [
                {
                    "action": "move",
                    "x": 2.5,
                    "y": 3.0,
                    "speed": 1.0,
                    "safety_check": True,
                    "reason": "Navigate to search area"
                },
                {
                    "action": "rotate",
                    "angle": 90.0,
                    "speed": 0.5,
                    "reason": "Orient camera towards target"
                },
                {
                    "action": "scan",
                    "duration": 5.0,
                    "reason": "Search for survivors"
                },
                # Arm manipulation examples
                {
                    "action": "arm_move",
                    "shoulder_angle": 45.0,
                    "elbow_angle": -30.0,
                    "reason": "Position arm to reach object"
                },
                {
                    "action": "grip",
                    "gripper_force": 0.7,
                    "reason": "Grasp the target object"
                },
                {
                    "action": "release",
                    "reason": "Release object at destination"
                }
            ]
        }
