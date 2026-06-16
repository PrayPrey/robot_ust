"""
Sensor Manager

Centralized management of robot sensors:
- Camera (640×480 RGB image)
- Lidar (512-point 360° scan)
- GPS (position)
- IMU (orientation)

Includes noise filtering and data processing.
"""

from typing import Optional, List, Tuple, Dict, Any
import numpy as np
import math
from loguru import logger

from ..schemas import SensorData
from .noise_filter import LidarNoiseFilter, MovingAverageFilter, KalmanFilter1D
from .exceptions import (
    SensorInitializationError,
    DeviceNotFoundError,
    SensorDataError,
    FilterConfigurationError
)
from .config import SensorManagerConfig, DEFAULT_SENSOR_CONFIG
from .filter_factory import FilterManager


class SensorManager:
    """
    Manages all robot sensors with noise filtering.

    Responsibilities:
    1. Collect data from Webots sensors
    2. Apply noise filtering
    3. Process and aggregate sensor data
    4. Return SensorData schema

    Example:
        >>> from controller import Robot
        >>> robot = Robot()
        >>> sensor_mgr = SensorManager(robot, time_step=64)
        >>> sensor_data = sensor_mgr.get_sensor_data()
    """

    def __init__(
        self,
        robot,  # Webots Robot instance
        config: Optional[SensorManagerConfig] = None
    ):
        """
        Initialize sensor manager with configuration.

        Args:
            robot: Webots Robot instance
            config: SensorManagerConfig instance (uses DEFAULT_SENSOR_CONFIG if None)

        Example:
            >>> from controller import Robot
            >>> from .config import SensorManagerConfig
            >>> robot = Robot()
            >>> config = SensorManagerConfig(time_step=64, enable_filtering=True)
            >>> sensor_mgr = SensorManager(robot, config)
        """
        self.robot = robot
        self.config = config or DEFAULT_SENSOR_CONFIG

        # Set convenience properties BEFORE initializing devices
        # (devices need self.time_step during initialization)
        self.time_step = self.config.time_step
        self.enable_filtering = self.config.enable_filtering

        # Initialize devices
        self._init_devices()

        # Initialize filters using FilterManager
        self.filter_manager = FilterManager(self.config)

        # Additional convenience properties for filter access
        self.lidar_filter = self.filter_manager.lidar_filter
        self.gps_x_filter = self.filter_manager.gps_x_filter
        self.gps_y_filter = self.filter_manager.gps_y_filter
        self.gps_z_filter = self.filter_manager.gps_z_filter
        self.roll_filter = self.filter_manager.roll_filter
        self.pitch_filter = self.filter_manager.pitch_filter
        self.yaw_filter = self.filter_manager.yaw_filter

        logger.info(
            f"SensorManager initialized: filtering={'enabled' if self.enable_filtering else 'disabled'}, "
            f"time_step={self.time_step}ms"
        )

    def _init_devices(self) -> None:
        """Initialize Webots sensor devices."""
        try:
            # GPS
            self.gps = self.robot.getDevice('gps')
            if not self.gps:
                raise DeviceNotFoundError('gps')
            self.gps.enable(self.time_step)
            logger.debug("GPS enabled")

            # IMU
            self.imu = self.robot.getDevice('imu')
            if not self.imu:
                raise DeviceNotFoundError('imu')
            self.imu.enable(self.time_step)
            logger.debug("IMU enabled")

            # Lidar
            self.lidar = self.robot.getDevice('lidar')
            if not self.lidar:
                raise DeviceNotFoundError('lidar')
            self.lidar.enable(self.time_step)
            # Enable point cloud for full data access
            self.lidar.enablePointCloud()
            logger.debug("Lidar enabled (512 points)")

            # Camera
            self.camera = self.robot.getDevice('front_camera')
            if not self.camera:
                raise DeviceNotFoundError('front_camera')
            self.camera.enable(self.time_step)
            logger.debug(f"Camera enabled ({self.camera.getWidth()}x{self.camera.getHeight()})")

            logger.info("All sensors initialized")

        except DeviceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during sensor initialization: {e}")
            raise SensorInitializationError("unknown", str(e)) from e

    def get_sensor_data(self) -> SensorData:
        """
        Collect and process data from all sensors.

        Returns:
            SensorData with current readings (filtered if enabled)
        """
        sensor_data = SensorData()

        try:
            # GPS data
            if self.gps:
                gps_values = self.gps.getValues()
                # Check for None first (sensor may not be ready yet)
                if gps_values is not None:
                    # Convert to list to avoid numpy version issues
                    gps_list = list(gps_values) if not isinstance(gps_values, list) else gps_values
                    if len(gps_list) >= 3:
                        # Validate GPS values are not NaN (sensor not initialized yet)
                        if not any(math.isnan(v) for v in gps_list[:3]):
                            if self.enable_filtering:
                                sensor_data.position_x = self.gps_x_filter.update(gps_list[0])
                                sensor_data.position_y = self.gps_y_filter.update(gps_list[1])
                                sensor_data.position_z = self.gps_z_filter.update(gps_list[2])
                            else:
                                sensor_data.position_x = gps_list[0]
                                sensor_data.position_y = gps_list[1]
                                sensor_data.position_z = gps_list[2]
                        else:
                            logger.debug("GPS values are NaN (sensor initializing...)")

            # IMU data
            if self.imu:
                rpy = self.imu.getRollPitchYaw()
                # Check for None first (sensor may not be ready yet)
                if rpy is not None:
                    # Convert to list to avoid numpy version issues
                    rpy_list = list(rpy) if not isinstance(rpy, list) else rpy
                    if len(rpy_list) >= 3:
                        # Validate IMU values are not NaN (sensor not initialized yet)
                        if not any(math.isnan(v) for v in rpy_list[:3]):
                            # Convert radians to degrees
                            roll_deg = np.degrees(rpy_list[0])
                            pitch_deg = np.degrees(rpy_list[1])
                            yaw_deg = np.degrees(rpy_list[2])

                            if self.enable_filtering:
                                sensor_data.roll = self.roll_filter.update(roll_deg)
                                sensor_data.pitch = self.pitch_filter.update(pitch_deg)
                                sensor_data.yaw = self.yaw_filter.update(yaw_deg)
                            else:
                                sensor_data.roll = roll_deg
                                sensor_data.pitch = pitch_deg
                                sensor_data.yaw = yaw_deg
                        else:
                            logger.debug("IMU values are NaN (sensor initializing...)")

            # Lidar data
            if self.lidar:
                lidar_range = self.lidar.getRangeImage()
                # Check for None first (sensor may not be ready yet)
                if lidar_range is not None:
                    try:
                        # Convert to list - handle different data types
                        if hasattr(lidar_range, 'tolist'):
                            # NumPy array
                            lidar_distances = lidar_range.tolist()
                        else:
                            # Plain list or tuple
                            lidar_distances = list(lidar_range)
                    except Exception as e:
                        # During initialization, lidar data may not be ready yet (NULL pointer)
                        # Use DEBUG level to avoid cluttering logs during startup
                        logger.debug(f"Failed to convert Lidar data: {e}")
                        lidar_distances = []

                    # Validate length after conversion
                    if len(lidar_distances) == 512:
                        if self.enable_filtering and self.lidar_filter:
                            lidar_distances = self.lidar_filter.update(lidar_distances)

                        sensor_data.lidar_distances = lidar_distances

                        # Calculate statistics from FRONT-FACING sensors only
                        # 512 readings for 360° → use central 170 readings for ~120° front cone (±60°)
                        # This prevents rear/side obstacles from triggering false detours
                        center_idx = len(lidar_distances) // 2  # 256
                        front_range = 85  # ±85 readings (~±60° from front)
                        front_start = max(0, center_idx - front_range)
                        front_end = min(len(lidar_distances), center_idx + front_range)
                        front_distances = lidar_distances[front_start:front_end]

                        valid_distances = [d for d in front_distances if d > 0.0]
                        if valid_distances:
                            sensor_data.lidar_min_distance = min(valid_distances)

                        # Average distance still uses full 360° for situational awareness
                        all_valid = [d for d in lidar_distances if d > 0.0]
                        if all_valid:
                            sensor_data.lidar_avg_distance = sum(all_valid) / len(all_valid)
                    elif len(lidar_distances) > 0:
                        # Only warn if we got data but wrong length (actual error)
                        logger.warning(f"Unexpected Lidar data length: {len(lidar_distances)} (expected 512)")
                    # else: silently skip if no data yet (sensor still initializing)

            # Camera data
            if self.camera:
                # Check if image is available
                sensor_data.camera_has_data = True
                sensor_data.camera_width = self.camera.getWidth()
                sensor_data.camera_height = self.camera.getHeight()

                # Note: Actual image data (getImage()) is large and not stored in SensorData
                # For image processing, use get_camera_image() method separately

        except Exception as e:
            logger.error(f"Error collecting sensor data: {e}")

        return sensor_data

    def get_camera_image(self, apply_filter: bool = False) -> Optional[np.ndarray]:
        """
        Get camera image data as numpy array.

        Args:
            apply_filter: Apply noise filtering to image

        Returns:
            Image array (H x W x 4) in BGRA format, or None if unavailable
        """
        if not self.camera:
            return None

        try:
            # Get raw image data
            image_data = self.camera.getImage()
            if not image_data:
                return None

            # Convert to numpy array
            width = self.camera.getWidth()
            height = self.camera.getHeight()

            # Webots returns image as flat byte array in BGRA format
            image = np.frombuffer(image_data, dtype=np.uint8)
            image = image.reshape((height, width, 4))

            # Apply filtering if requested
            if apply_filter and self.enable_filtering:
                from .noise_filter import CameraNoiseFilter
                image = CameraNoiseFilter.apply_mean_filter(image, kernel_size=3)

            return image

        except Exception as e:
            logger.error(f"Failed to get camera image: {e}")
            return None

    def get_camera_image_rgb(self, apply_filter: bool = False) -> Optional[np.ndarray]:
        """
        Get camera image in RGB format (without alpha channel).

        Args:
            apply_filter: Apply noise filtering

        Returns:
            Image array (H x W x 3) in RGB format
        """
        bgra_image = self.get_camera_image(apply_filter=apply_filter)
        if bgra_image is None:
            return None

        # Convert BGRA to RGB
        rgb_image = bgra_image[:, :, [2, 1, 0]]  # Swap B and R channels
        return rgb_image

    def get_lidar_point_cloud(self) -> Optional[np.ndarray]:
        """
        Get Lidar point cloud data.

        Returns:
            Point cloud array (N x 3) with XYZ coordinates, or None
        """
        if not self.lidar:
            return None

        try:
            point_cloud = self.lidar.getPointCloud()
            if point_cloud:
                return np.array(point_cloud).reshape(-1, 3)
            return None

        except Exception as e:
            logger.error(f"Failed to get Lidar point cloud: {e}")
            return None

    def get_obstacles_in_range(self, max_distance: float = 2.0) -> List[int]:
        """
        Get indices of Lidar points detecting obstacles within range.

        Args:
            max_distance: Maximum distance threshold in meters

        Returns:
            List of Lidar point indices with obstacles closer than max_distance
        """
        sensor_data = self.get_sensor_data()

        if sensor_data.lidar_distances is None:
            return []

        return [
            i for i, dist in enumerate(sensor_data.lidar_distances)
            if 0.0 < dist < max_distance
        ]

    def is_path_clear_ahead(
        self,
        min_distance: Optional[float] = None,
        angle_range: Optional[float] = None
    ) -> bool:
        """
        Check if path ahead is clear of obstacles.

        Args:
            min_distance: Minimum safe distance in meters (uses config default if None)
            angle_range: Angle range to check in degrees (uses config default if None)

        Returns:
            True if path is clear
        """
        # Use config defaults if not specified
        min_distance = min_distance or self.config.min_safe_distance
        angle_range = angle_range or self.config.forward_check_angle

        sensor_data = self.get_sensor_data()

        if sensor_data.lidar_distances is None:
            return False

        # Forward direction is around index 256 (middle of Lidar scan)
        num_points = self.config.lidar.num_points
        center_idx = num_points // 2
        angle_per_point = 360.0 / num_points
        points_to_check = int(angle_range / angle_per_point)

        start_idx = center_idx - points_to_check
        end_idx = center_idx + points_to_check

        # Check all points in forward arc
        for i in range(start_idx, end_idx + 1):
            idx = i % num_points  # Wrap around
            distance = sensor_data.lidar_distances[idx]

            # If obstacle closer than min_distance, path not clear
            if 0.0 < distance < min_distance:
                return False

        return True

    def reset_filters(self) -> None:
        """Reset all sensor filters."""
        self.filter_manager.reset_all()
        logger.info("All sensor filters reset")
