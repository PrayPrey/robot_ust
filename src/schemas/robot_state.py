"""
Robot State Schema

Pydantic schema for robot state and sensor data.
Represents current robot status, position, and sensor readings.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class RobotStatus(str, Enum):
    """Robot operational status."""
    IDLE = "idle"
    MOVING = "moving"
    ROTATING = "rotating"
    SCANNING = "scanning"
    ERROR = "error"
    STOPPED = "stopped"


class FailureReason(str, Enum):
    """
    Mission failure reason categories.

    Used by Verifier Agent to categorize mission failures
    and determine if replanning is possible.
    """
    OBSTACLE_COLLISION = "obstacle_collision"  # Hit an obstacle
    PATH_BLOCKED = "path_blocked"  # Path to goal is blocked
    GOAL_UNREACHED = "goal_unreached"  # Failed to reach target position
    SENSOR_FAILURE = "sensor_failure"  # Hardware/sensor malfunction
    TIMEOUT = "timeout"  # Execution timeout exceeded


class SensorData(BaseModel):
    """
    Multi-sensor data from robot.

    Aggregates data from:
    - Camera (640×480 image)
    - Lidar (360° scan, 512 points)
    - GPS (XYZ position)
    - IMU (Roll/Pitch/Yaw orientation)
    """

    # GPS data
    position_x: Optional[float] = Field(
        default=None,
        description="Current X position in meters (from GPS)"
    )

    position_y: Optional[float] = Field(
        default=None,
        description="Current Y position in meters (from GPS)"
    )

    position_z: Optional[float] = Field(
        default=None,
        description="Current Z position in meters (from GPS)"
    )

    # IMU data
    roll: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Roll angle in degrees (from IMU)"
    )

    pitch: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Pitch angle in degrees (from IMU)"
    )

    yaw: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Yaw angle in degrees (from IMU)"
    )

    # Lidar data
    lidar_distances: Optional[List[float]] = Field(
        default=None,
        description="Lidar distance measurements (512 points, 360°)"
    )

    lidar_min_distance: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Minimum detected distance in meters"
    )

    lidar_avg_distance: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Average detected distance in meters"
    )

    # Camera data
    camera_width: Optional[int] = Field(
        default=640,
        description="Camera image width in pixels"
    )

    camera_height: Optional[int] = Field(
        default=480,
        description="Camera image height in pixels"
    )

    camera_has_data: bool = Field(
        default=False,
        description="Whether camera image data is available"
    )

    # Timestamp
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Sensor data capture timestamp"
    )

    @field_validator("lidar_distances")
    @classmethod
    def validate_lidar_data(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        """Validate Lidar data format."""
        if v is not None:
            if len(v) != 512:
                raise ValueError(
                    f"Lidar should have 512 points, got {len(v)}"
                )
            # Check for invalid readings
            if any(d < 0 for d in v):
                raise ValueError("Lidar distances cannot be negative")
        return v

    def get_obstacles_nearby(self, threshold: float = 1.0) -> List[int]:
        """
        Get indices of Lidar points detecting nearby obstacles.

        Args:
            threshold: Distance threshold in meters

        Returns:
            List of indices where distance < threshold
        """
        if self.lidar_distances is None:
            return []

        return [
            i for i, dist in enumerate(self.lidar_distances)
            if dist < threshold
        ]

    def is_path_clear(self, angle_range: tuple[float, float], min_distance: float = 0.5) -> bool:
        """
        Check if path is clear in given angle range.

        Args:
            angle_range: (start_angle, end_angle) in degrees
            min_distance: Minimum safe distance in meters

        Returns:
            True if path is clear, False otherwise
        """
        if self.lidar_distances is None:
            return False

        # Convert angle range to lidar indices
        start_idx = int((angle_range[0] + 180) / 360 * 512) % 512
        end_idx = int((angle_range[1] + 180) / 360 * 512) % 512

        # Check distances in range
        if start_idx < end_idx:
            range_distances = self.lidar_distances[start_idx:end_idx]
        else:
            range_distances = self.lidar_distances[start_idx:] + self.lidar_distances[:end_idx]

        return all(d >= min_distance for d in range_distances)


class RobotState(BaseModel):
    """
    Complete robot state including position, status, and sensors.

    Used by:
    - Actor Agent: Read current state before action
    - Verifier Agent: Validate mission success/failure
    - Planner Agent: Consider current state in planning
    """

    # Robot identification
    robot_id: str = Field(
        default="rescue_robot",
        description="Unique robot identifier"
    )

    # Operational status
    status: RobotStatus = Field(
        default=RobotStatus.IDLE,
        description="Current robot operational status"
    )

    # Current action being executed
    current_action: Optional[str] = Field(
        default=None,
        description="Currently executing action (if any)"
    )

    # Sensor data
    sensors: SensorData = Field(
        default_factory=SensorData,
        description="Multi-sensor data (GPS, IMU, Lidar, Camera)"
    )

    # Battery/Energy (simulation)
    battery_level: float = Field(
        default=100.0,
        ge=0.0,
        le=100.0,
        description="Battery level percentage (0-100)"
    )

    # Error information
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if status is ERROR"
    )

    # Failure analysis (Story 2.4)
    failure_reason: Optional[FailureReason] = Field(
        default=None,
        description="Categorized failure reason (set by Verifier Agent)"
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

    # Reactive control log (Story 3.1)
    reactive_log: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Reactive intervention log from HybridReactiveController. "
            "Each entry records real-time obstacle avoidance decisions. "
            "Used by Verifier to expand tolerance (0.1m -> 0.3m) for reactive adjustments. "
            "Entry structure: {"
            "  'timestamp': ISO format datetime, "
            "  'type': 'CRITICAL'|'MODERATE'|'NORMAL', "
            "  'reason': str, "
            "  'action_taken': {'type': str, 'params': dict}, "
            "  'sensor_state': {'lidar_min': float, 'position': [x, y, z]} "
            "}"
        )
    )

    # Metadata
    last_updated: datetime = Field(
        default_factory=datetime.now,
        description="Last state update timestamp"
    )

    @field_validator("battery_level")
    @classmethod
    def warn_low_battery(cls, v: float) -> float:
        """Warn if battery is low."""
        if v < 20.0:
            import warnings
            warnings.warn(
                f"Low battery: {v}%. Consider returning to base.",
                UserWarning
            )
        return v

    def is_operational(self) -> bool:
        """Check if robot is operational (not in error or stopped state)."""
        return self.status not in [RobotStatus.ERROR, RobotStatus.STOPPED]

    def get_position(self) -> Optional[tuple[float, float, float]]:
        """Get current 3D position from GPS."""
        if all([
            self.sensors.position_x is not None,
            self.sensors.position_y is not None,
            self.sensors.position_z is not None
        ]):
            return (
                self.sensors.position_x,
                self.sensors.position_y,
                self.sensors.position_z
            )
        return None

    def get_orientation(self) -> Optional[tuple[float, float, float]]:
        """Get current orientation (Roll, Pitch, Yaw) from IMU."""
        if all([
            self.sensors.roll is not None,
            self.sensors.pitch is not None,
            self.sensors.yaw is not None
        ]):
            return (
                self.sensors.roll,
                self.sensors.pitch,
                self.sensors.yaw
            )
        return None

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "examples": [
                {
                    "robot_id": "rescue_robot",
                    "status": "moving",
                    "current_action": "move",
                    "sensors": {
                        "position_x": 1.5,
                        "position_y": 2.3,
                        "position_z": 0.098,
                        "roll": 0.0,
                        "pitch": 0.1,
                        "yaw": 90.0,
                        "lidar_min_distance": 1.95,
                        "lidar_avg_distance": 4.92,
                        "camera_has_data": True
                    },
                    "battery_level": 85.0
                }
            ]
        }
