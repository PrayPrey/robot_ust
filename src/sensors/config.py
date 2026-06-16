"""
Sensor configuration using Pydantic models for validation and type safety.

This module defines configuration classes for sensors and filters,
eliminating magic numbers and providing centralized configuration management.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class FilterConfig(BaseModel):
    """Base configuration for sensor filters."""

    filter_type: Literal["moving_average", "kalman"] = Field(
        default="moving_average",
        description="Type of filter to use"
    )


class MovingAverageConfig(FilterConfig):
    """Configuration for Moving Average filter."""

    filter_type: Literal["moving_average"] = "moving_average"
    window_size: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of samples to average (1-100)"
    )


class KalmanFilterConfig(FilterConfig):
    """Configuration for Kalman filter."""

    filter_type: Literal["kalman"] = "kalman"
    process_variance: float = Field(
        default=1e-5,
        gt=0,
        description="Process noise variance (Q)"
    )
    measurement_variance: float = Field(
        default=0.01,
        gt=0,
        description="Measurement noise variance (R)"
    )
    initial_error: float = Field(
        default=1.0,
        gt=0,
        description="Initial estimation error"
    )


class LidarConfig(BaseModel):
    """Configuration for Lidar sensor."""

    num_points: int = Field(
        default=512,
        ge=1,
        description="Number of Lidar scan points"
    )
    max_detection_distance: float = Field(
        default=10.0,
        gt=0,
        description="Maximum detection distance in meters"
    )
    filter_config: FilterConfig = Field(
        default_factory=lambda: MovingAverageConfig(window_size=5),
        description="Filter configuration for Lidar"
    )


class GPSConfig(BaseModel):
    """Configuration for GPS sensor."""

    filter_config: KalmanFilterConfig = Field(
        default_factory=lambda: KalmanFilterConfig(
            process_variance=1e-5,
            measurement_variance=0.01
        ),
        description="Kalman filter configuration for GPS"
    )


class IMUConfig(BaseModel):
    """Configuration for IMU sensor."""

    filter_config: MovingAverageConfig = Field(
        default_factory=lambda: MovingAverageConfig(window_size=5),
        description="Moving average filter configuration for IMU"
    )
    convert_to_degrees: bool = Field(
        default=True,
        description="Convert orientation from radians to degrees"
    )


class CameraConfig(BaseModel):
    """Configuration for Camera sensor."""

    width: int = Field(default=640, ge=1, description="Image width in pixels")
    height: int = Field(default=480, ge=1, description="Image height in pixels")
    enable_filtering: bool = Field(
        default=True,
        description="Enable noise filtering for camera images"
    )
    filter_kernel_size: int = Field(
        default=3,
        ge=1,
        description="Kernel size for image filtering (must be odd)"
    )

    @field_validator('filter_kernel_size')
    @classmethod
    def validate_kernel_size(cls, v: int) -> int:
        """Ensure kernel size is odd."""
        if v % 2 == 0:
            raise ValueError("Kernel size must be odd")
        return v


class SensorManagerConfig(BaseModel):
    """
    Centralized configuration for SensorManager.

    This replaces magic numbers and provides type-safe configuration
    with validation.

    Example:
        >>> config = SensorManagerConfig()
        >>> config.time_step
        64
        >>> config.lidar.num_points
        512
    """

    time_step: int = Field(
        default=64,
        ge=1,
        le=1000,
        description="Simulation time step in milliseconds"
    )

    enable_filtering: bool = Field(
        default=True,
        description="Enable noise filtering for all sensors"
    )

    lidar: LidarConfig = Field(
        default_factory=LidarConfig,
        description="Lidar sensor configuration"
    )

    gps: GPSConfig = Field(
        default_factory=GPSConfig,
        description="GPS sensor configuration"
    )

    imu: IMUConfig = Field(
        default_factory=IMUConfig,
        description="IMU sensor configuration"
    )

    camera: CameraConfig = Field(
        default_factory=CameraConfig,
        description="Camera sensor configuration"
    )

    # Safety thresholds
    min_safe_distance: float = Field(
        default=0.5,
        ge=0,
        description="Minimum safe distance from obstacles in meters"
    )

    forward_check_angle: float = Field(
        default=30.0,
        ge=0,
        le=180,
        description="Forward path check angle range in degrees"
    )

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }


# Default configuration instance
DEFAULT_SENSOR_CONFIG = SensorManagerConfig()
