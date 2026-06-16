"""
Safety constraint definitions using Pydantic models.

This module defines configurable safety constraints for robot operations,
including obstacle avoidance distances, speed limits, and safe zone boundaries.
"""

from typing import Tuple
from pydantic import BaseModel, Field, field_validator


class SafetyConstraints(BaseModel):
    """
    Safety constraint configuration for robot operations.

    Defines limits and thresholds for safe robot behavior including:
    - Minimum obstacle avoidance distance
    - Maximum operating speed
    - Safe operating zone boundaries
    - Emergency stop distance

    Example:
        >>> constraints = SafetyConstraints()
        >>> constraints.min_obstacle_distance
        0.5
        >>> constraints.max_speed
        1.0
    """

    min_obstacle_distance: float = Field(
        default=0.3,
        gt=0,
        le=5.0,
        description="Minimum safe distance from obstacles in meters"
    )

    max_speed: float = Field(
        default=1.0,
        gt=0,
        le=2.0,
        description="Maximum allowed speed in m/s"
    )

    safe_zone_bounds: Tuple[float, float, float, float] = Field(
        default=(-4.9, 4.9, -4.9, 4.9),
        description="Safe zone boundaries (x_min, x_max, y_min, y_max) in meters"
    )

    emergency_stop_distance: float = Field(
        default=0.15,
        gt=0,
        le=1.0,
        description="Critical distance triggering emergency stop in meters (lower than min_obstacle_distance)"
    )

    forward_check_angle: float = Field(
        default=30.0,
        ge=0,
        le=180,
        description="Angle range for forward obstacle detection in degrees"
    )

    @field_validator("emergency_stop_distance")
    @classmethod
    def validate_emergency_distance(cls, v: float, info) -> float:
        """Ensure emergency stop distance is less than min obstacle distance."""
        # Note: 'info' contains validation context including other field values
        # However, during initial validation, min_obstacle_distance might not be set yet
        # This will be checked in model_validator if needed
        if v < 0.1:
            raise ValueError(
                f"Emergency stop distance {v}m is too small. "
                f"Must be at least 0.1m for safety."
            )
        return v

    @field_validator("safe_zone_bounds")
    @classmethod
    def validate_safe_zone(cls, v: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        """Validate safe zone bounds are logical."""
        x_min, x_max, y_min, y_max = v

        if x_min >= x_max:
            raise ValueError(
                f"Invalid safe zone: x_min ({x_min}) must be less than x_max ({x_max})"
            )

        if y_min >= y_max:
            raise ValueError(
                f"Invalid safe zone: y_min ({y_min}) must be less than y_max ({y_max})"
            )

        # Ensure bounds are within reasonable limits
        for bound in v:
            if abs(bound) > 10.0:
                raise ValueError(
                    f"Safe zone bound {bound}m is too large. "
                    f"Must be within [-10, 10] meters."
                )

        return v

    model_config = {
        "validate_assignment": True,
        "extra": "forbid",
        "frozen": False  # Allow updates to constraints during runtime if needed
    }


# Default safety constraints instance
DEFAULT_SAFETY_CONSTRAINTS = SafetyConstraints()
