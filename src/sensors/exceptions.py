"""
Sensor-specific exceptions for better error handling and debugging.

This module defines custom exception classes for sensor-related errors,
making it easier to catch and handle specific failure scenarios.
"""


class SensorError(Exception):
    """Base exception for all sensor-related errors."""
    pass


class SensorInitializationError(SensorError):
    """
    Raised when a sensor fails to initialize properly.

    Examples:
        - Sensor device not found in Webots
        - Failed to enable sensor
        - Invalid sensor configuration
    """
    def __init__(self, sensor_name: str, message: str = ""):
        self.sensor_name = sensor_name
        full_message = f"Failed to initialize sensor '{sensor_name}'"
        if message:
            full_message += f": {message}"
        super().__init__(full_message)


class DeviceNotFoundError(SensorInitializationError):
    """
    Raised when a required sensor device is not found in the robot.

    This typically indicates:
        - Incorrect device name in configuration
        - Device not present in Webots world file
        - Robot model mismatch
    """
    def __init__(self, device_name: str):
        super().__init__(
            device_name,
            f"Device '{device_name}' not found in robot"
        )
        self.device_name = device_name


class SensorDataError(SensorError):
    """
    Raised when sensor data is invalid or corrupted.

    Examples:
        - Invalid data format
        - Data out of expected range
        - Missing required data fields
    """
    def __init__(self, sensor_name: str, message: str):
        self.sensor_name = sensor_name
        super().__init__(f"Invalid data from sensor '{sensor_name}': {message}")


class FilterError(SensorError):
    """
    Raised when a noise filter encounters an error.

    Examples:
        - Filter configuration error
        - Filter state inconsistency
        - Invalid input data dimensions
    """
    pass


class FilterConfigurationError(FilterError):
    """
    Raised when filter configuration is invalid.

    Examples:
        - Invalid filter type
        - Invalid filter parameters
        - Missing required configuration
    """
    pass


class SafetyViolationException(SensorError):
    """
    Raised when a safety constraint is violated.

    This exception is raised when the SafetyValidator detects that
    a proposed robot action would violate safety constraints.

    Attributes:
        violation_type: Type of violation (obstacle_too_close, speed_too_high,
                       out_of_bounds, emergency_stop)
        message: Detailed description of the violation
        action: The action that triggered the violation (optional)

    Examples:
        - Obstacle detected at 0.3m (min safe distance: 0.5m)
        - Speed 1.5 m/s exceeds maximum 1.0 m/s
        - Target position outside safe zone boundaries
        - Emergency stop triggered at 0.15m
    """

    def __init__(self, violation_type: str, message: str, action=None):
        self.violation_type = violation_type
        self.action = action
        full_message = f"Safety violation ({violation_type}): {message}"
        super().__init__(full_message)
