"""
Sensors Module

Multi-sensor integration and noise filtering for rescue robot.

Components:
- SensorManager: Centralized sensor data collection
- Noise Filters: Moving average and Kalman filtering
- Configuration: Pydantic models for type-safe configuration
- Exceptions: Specific error types for better debugging
- FilterFactory: Factory pattern for filter creation
- EnvironmentMap: External environment data loading
"""

from .sensor_manager import SensorManager
from .noise_filter import (
    MovingAverageFilter,
    KalmanFilter1D,
    LidarNoiseFilter,
    CameraNoiseFilter
)
from .config import (
    SensorManagerConfig,
    DEFAULT_SENSOR_CONFIG,
    LidarConfig,
    GPSConfig,
    IMUConfig,
    CameraConfig,
    MovingAverageConfig,
    KalmanFilterConfig
)
from .exceptions import (
    SensorError,
    SensorInitializationError,
    DeviceNotFoundError,
    SensorDataError,
    FilterError,
    FilterConfigurationError
)
from .filter_factory import FilterFactory, FilterManager
from .environment_map import (
    EnvironmentMap,
    EnvironmentMapLoader,
    Obstacle,
    SafeZone,
    DangerZone
)

__all__ = [
    # Sensor Management
    "SensorManager",

    # Noise Filters
    "MovingAverageFilter",
    "KalmanFilter1D",
    "LidarNoiseFilter",
    "CameraNoiseFilter",

    # Configuration
    "SensorManagerConfig",
    "DEFAULT_SENSOR_CONFIG",
    "LidarConfig",
    "GPSConfig",
    "IMUConfig",
    "CameraConfig",
    "MovingAverageConfig",
    "KalmanFilterConfig",

    # Exceptions
    "SensorError",
    "SensorInitializationError",
    "DeviceNotFoundError",
    "SensorDataError",
    "FilterError",
    "FilterConfigurationError",

    # Factory Pattern
    "FilterFactory",
    "FilterManager",

    # Environment Map
    "EnvironmentMap",
    "EnvironmentMapLoader",
    "Obstacle",
    "SafeZone",
    "DangerZone",
]
