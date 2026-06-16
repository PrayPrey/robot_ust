"""
Replan Request Schema

Pydantic schema for replanning requests from Verifier to Planner.
Contains all information needed for Planner to generate alternative action plan.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from .robot_action import RobotAction
from .robot_state import FailureReason, SensorData


class ReplanRequest(BaseModel):
    """
    Replanning request data passed from Verifier to Planner.

    Contains failure analysis and context needed for generating
    alternative action plan.

    Example:
        >>> replan_req = ReplanRequest(
        ...     failure_reason=FailureReason.OBSTACLE_COLLISION,
        ...     sensor_data=current_sensors,
        ...     previous_plan=[action1, action2],
        ...     retry_count=1
        ... )
    """

    # Failure analysis
    failure_reason: FailureReason = Field(
        ...,
        description="Categorized failure reason (from Verifier analysis)"
    )

    # Current sensor context
    sensor_data: SensorData = Field(
        ...,
        description="Current sensor data (Lidar, GPS, IMU) for replanning"
    )

    # Previous plan that failed
    previous_plan: List[RobotAction] = Field(
        default_factory=list,
        description="Previous action plan that failed"
    )

    # Retry context
    retry_count: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Current retry attempt (0-3)"
    )

    # Original mission command (for context)
    original_command: Optional[str] = Field(
        default=None,
        description="Original mission command text"
    )

    # Additional context
    failure_details: Optional[str] = Field(
        default=None,
        description="Human-readable failure details from Verifier"
    )

    # Original target coordinates (for detour recovery)
    original_target_x: Optional[float] = Field(
        default=None,
        description="Original target X coordinate before detour (world coordinates)"
    )

    original_target_y: Optional[float] = Field(
        default=None,
        description="Original target Y coordinate before detour (world coordinates)"
    )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "examples": [
                {
                    "failure_reason": "obstacle_collision",
                    "sensor_data": {
                        "position_x": 1.2,
                        "position_y": 0.8,
                        "position_z": 0.098,
                        "lidar_min_distance": 0.25,
                        "lidar_avg_distance": 1.5
                    },
                    "previous_plan": [
                        {"action_type": "move", "parameters": {"distance": 2.0, "speed": 0.5}},
                        {"action_type": "rotate", "parameters": {"angle": 90, "speed": 0.3}}
                    ],
                    "retry_count": 1,
                    "original_command": "Move forward 2 meters and turn right",
                    "failure_details": "Obstacle collision detected at 0.25m distance"
                }
            ]
        }
