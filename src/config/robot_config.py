"""
Robot Configuration

Physical specifications for different robot models.
Currently supports Pioneer 3-DX.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class RobotConfig:
    """Base robot configuration."""

    name: str
    wheel_radius: float  # meters
    wheel_distance: float  # meters (distance between wheels)
    max_speed: float  # m/s
    max_angular_speed: float  # rad/s
    position_tolerance: float  # meters
    angle_tolerance: float  # radians


class Pioneer3DXConfig(RobotConfig):
    """Pioneer 3-DX robot specifications.

    Based on official Pioneer 3-DX documentation:
    - Wheel radius: 97.5mm (0.0975m)
    - Wheel distance: 330mm (0.33m)
    - Max speed: ~1.2 m/s
    - Weight: 9kg
    """

    def __init__(self):
        super().__init__(
            name="Pioneer 3-DX",
            wheel_radius=0.0975,  # 97.5mm
            wheel_distance=0.33,  # 330mm between wheels
            max_speed=1.2,  # m/s
            max_angular_speed=2.0,  # rad/s (~114 deg/s)
            position_tolerance=0.05,  # 5cm
            angle_tolerance=0.0349  # 2 degrees in radians
        )

    def speed_to_wheel_velocity(self, linear_speed: float) -> float:
        """
        Convert linear speed (m/s) to wheel angular velocity (rad/s).

        Formula: ω = v / r
        where:
            ω = angular velocity (rad/s)
            v = linear speed (m/s)
            r = wheel radius (m)

        Args:
            linear_speed: Desired linear speed in m/s

        Returns:
            Wheel angular velocity in rad/s

        Example:
            >>> config = Pioneer3DXConfig()
            >>> config.speed_to_wheel_velocity(1.0)
            10.256410256410257  # rad/s
        """
        if linear_speed > self.max_speed:
            raise ValueError(
                f"Speed {linear_speed} exceeds max speed {self.max_speed} m/s"
            )

        return linear_speed / self.wheel_radius

    def angular_speed_to_wheel_velocities(
        self,
        angular_speed: float
    ) -> tuple[float, float]:
        """
        Convert angular speed (rad/s) to left/right wheel velocities.

        For differential drive robots in Webots:
        - positive angular_speed = CW (right turn)
        - negative angular_speed = CCW (left turn)

        Args:
            angular_speed: Desired angular speed in rad/s (positive = CW/right turn)

        Returns:
            Tuple of (left_wheel_velocity, right_wheel_velocity) in rad/s

        Example:
            >>> config = Pioneer3DXConfig()
            >>> config.angular_speed_to_wheel_velocities(1.57)  # CW 90 deg/s
            (2.66, -2.66)  # left forward, right backward = CW turn
        """
        if abs(angular_speed) > self.max_angular_speed:
            raise ValueError(
                f"Angular speed {angular_speed} exceeds max {self.max_angular_speed} rad/s"
            )

        # For differential drive with Webots simulator:
        # positive angular_speed = CW (clockwise/right turn) = left wheel forward, right wheel backward
        # negative angular_speed = CCW (counter-clockwise/left turn) = left wheel backward, right wheel forward
        half_distance = self.wheel_distance / 2.0

        # Webots wheel velocity convention
        left_velocity = angular_speed * half_distance / self.wheel_radius
        right_velocity = -angular_speed * half_distance / self.wheel_radius

        return left_velocity, right_velocity


# Global robot configuration instance
ROBOT_CONFIG = Pioneer3DXConfig()


def get_robot_config(robot_type: Literal["pioneer3dx"] = "pioneer3dx") -> RobotConfig:
    """
    Get robot configuration for specified robot type.

    Args:
        robot_type: Type of robot (currently only "pioneer3dx" supported)

    Returns:
        Robot configuration instance

    Raises:
        ValueError: If robot type is not supported
    """
    if robot_type == "pioneer3dx":
        return Pioneer3DXConfig()
    else:
        raise ValueError(f"Unsupported robot type: {robot_type}")
