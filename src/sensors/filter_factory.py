"""
Filter Factory Pattern for creating sensor filters.

This module implements the Factory Pattern to eliminate code duplication
in filter initialization and provide a centralized way to create filters
based on configuration.
"""

from typing import List, Union
from .noise_filter import MovingAverageFilter, KalmanFilter1D, LidarNoiseFilter
from .config import (
    FilterConfig,
    MovingAverageConfig,
    KalmanFilterConfig,
    LidarConfig,
    GPSConfig,
    IMUConfig
)
from .exceptions import FilterConfigurationError


class FilterFactory:
    """
    Factory for creating sensor filters based on configuration.

    This eliminates duplication in filter initialization code and provides
    a single source of truth for filter creation logic.

    Example:
        >>> from .config import MovingAverageConfig
        >>> config = MovingAverageConfig(window_size=5)
        >>> filter = FilterFactory.create_1d_filter(config)
        >>> filtered_value = filter.update(2.5)
    """

    @staticmethod
    def create_1d_filter(
        config: Union[MovingAverageConfig, KalmanFilterConfig]
    ) -> Union[MovingAverageFilter, KalmanFilter1D]:
        """
        Create a 1D filter (for single-value sensors like GPS coordinates or IMU angles).

        Args:
            config: Filter configuration (MovingAverageConfig or KalmanFilterConfig)

        Returns:
            Initialized filter instance

        Raises:
            FilterConfigurationError: If configuration is invalid
        """
        if isinstance(config, MovingAverageConfig):
            return MovingAverageFilter(window_size=config.window_size)

        elif isinstance(config, KalmanFilterConfig):
            return KalmanFilter1D(
                process_variance=config.process_variance,
                measurement_variance=config.measurement_variance,
                initial_error=config.initial_error
            )

        else:
            raise FilterConfigurationError(
                f"Unsupported filter config type: {type(config).__name__}"
            )

    @staticmethod
    def create_lidar_filter(config: LidarConfig) -> LidarNoiseFilter:
        """
        Create a Lidar filter for multi-point data.

        Args:
            config: Lidar configuration with filter settings

        Returns:
            Initialized LidarNoiseFilter

        Raises:
            FilterConfigurationError: If configuration is invalid
        """
        filter_config = config.filter_config

        if isinstance(filter_config, MovingAverageConfig):
            return LidarNoiseFilter(
                num_points=config.num_points,
                filter_type="moving_average",
                window_size=filter_config.window_size
            )

        elif isinstance(filter_config, KalmanFilterConfig):
            return LidarNoiseFilter(
                num_points=config.num_points,
                filter_type="kalman",
                process_variance=filter_config.process_variance,
                measurement_variance=filter_config.measurement_variance
            )

        else:
            raise FilterConfigurationError(
                f"Unsupported Lidar filter config: {type(filter_config).__name__}"
            )

    @staticmethod
    def create_gps_filters(config: GPSConfig) -> tuple[KalmanFilter1D, KalmanFilter1D, KalmanFilter1D]:
        """
        Create GPS filters for X, Y, Z coordinates.

        Args:
            config: GPS configuration

        Returns:
            Tuple of (x_filter, y_filter, z_filter)
        """
        kalman_config = config.filter_config

        # Create three identical filters for X, Y, Z
        x_filter = KalmanFilter1D(
            process_variance=kalman_config.process_variance,
            measurement_variance=kalman_config.measurement_variance,
            initial_error=kalman_config.initial_error
        )

        y_filter = KalmanFilter1D(
            process_variance=kalman_config.process_variance,
            measurement_variance=kalman_config.measurement_variance,
            initial_error=kalman_config.initial_error
        )

        z_filter = KalmanFilter1D(
            process_variance=kalman_config.process_variance,
            measurement_variance=kalman_config.measurement_variance,
            initial_error=kalman_config.initial_error
        )

        return x_filter, y_filter, z_filter

    @staticmethod
    def create_imu_filters(config: IMUConfig) -> tuple[MovingAverageFilter, MovingAverageFilter, MovingAverageFilter]:
        """
        Create IMU filters for Roll, Pitch, Yaw.

        Args:
            config: IMU configuration

        Returns:
            Tuple of (roll_filter, pitch_filter, yaw_filter)
        """
        ma_config = config.filter_config

        # Create three identical filters for Roll, Pitch, Yaw
        roll_filter = MovingAverageFilter(window_size=ma_config.window_size)
        pitch_filter = MovingAverageFilter(window_size=ma_config.window_size)
        yaw_filter = MovingAverageFilter(window_size=ma_config.window_size)

        return roll_filter, pitch_filter, yaw_filter


class FilterManager:
    """
    Manages all sensor filters for SensorManager.

    This class encapsulates filter creation and management logic,
    making SensorManager cleaner and easier to maintain.
    """

    def __init__(self, config):
        """
        Initialize all filters based on configuration.

        Args:
            config: SensorManagerConfig instance
        """
        self.config = config

        # Initialize filters if filtering is enabled
        if config.enable_filtering:
            self.lidar_filter = FilterFactory.create_lidar_filter(config.lidar)

            self.gps_x_filter, self.gps_y_filter, self.gps_z_filter = \
                FilterFactory.create_gps_filters(config.gps)

            self.roll_filter, self.pitch_filter, self.yaw_filter = \
                FilterFactory.create_imu_filters(config.imu)
        else:
            self.lidar_filter = None
            self.gps_x_filter = None
            self.gps_y_filter = None
            self.gps_z_filter = None
            self.roll_filter = None
            self.pitch_filter = None
            self.yaw_filter = None

    def reset_all(self) -> None:
        """Reset all filters to initial state."""
        if self.config.enable_filtering:
            if self.lidar_filter:
                self.lidar_filter.reset()

            if self.gps_x_filter:
                self.gps_x_filter.reset()
                self.gps_y_filter.reset()
                self.gps_z_filter.reset()

            if self.roll_filter:
                self.roll_filter.reset()
                self.pitch_filter.reset()
                self.yaw_filter.reset()
