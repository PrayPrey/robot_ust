"""
Loguru logging configuration for LLM_robot_2.

This module provides structured logging using Loguru with JSON serialization
for all agent actions, LLM calls, sensor data, and mission events.

Story: 2.5 - Monitoring, Logging, and Evaluation
AC #1: Log all actions, LLM calls, and sensor data in JSON format
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger


class LoggerConfig:
    """
    Centralized logging configuration using Loguru.

    Features:
    - JSON structured logging for evaluation
    - Multiple output sinks (console, file, JSON file)
    - Level-based filtering
    - Mission-specific log files with timestamps

    Usage:
        >>> from src.utils.logger_config import setup_logger
        >>> setup_logger(mission_name="search_rescue_001")
        >>> logger.info("Mission started", mission_id="search_rescue_001", status="started")
    """

    _initialized: bool = False
    _log_dir: Path = Path("logs")
    _current_mission: Optional[str] = None

    @classmethod
    def setup(
        cls,
        mission_name: Optional[str] = None,
        log_dir: str = "logs",
        console_level: str = "INFO",
        file_level: str = "DEBUG"
    ) -> None:
        """
        Initialize Loguru logger with structured logging configuration.

        Args:
            mission_name: Optional mission identifier for log file naming
            log_dir: Directory for log files (default: "logs")
            console_level: Minimum level for console output (default: "INFO")
            file_level: Minimum level for file output (default: "DEBUG")

        Creates:
            - logs/mission_{timestamp}.log - Human-readable logs (all levels)
            - logs/mission_{timestamp}.json - JSON structured logs (for evaluation)
        """
        if cls._initialized:
            logger.warning("Logger already initialized. Skipping re-initialization.")
            return

        # Remove default handler
        logger.remove()

        # Setup log directory
        cls._log_dir = Path(log_dir)
        cls._log_dir.mkdir(exist_ok=True)

        # Set current mission
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cls._current_mission = mission_name or f"mission_{timestamp}"

        # Console handler - INFO level and above, colorized
        logger.add(
            sys.stdout,
            level=console_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
            colorize=True,
            enqueue=True  # Thread-safe
        )

        # File handler - All levels, human-readable
        log_file = cls._log_dir / f"{cls._current_mission}.log"
        logger.add(
            log_file,
            level=file_level,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",  # Rotate when file reaches 10 MB
            retention="30 days",  # Keep logs for 30 days
            compression="zip",  # Compress rotated logs
            enqueue=True  # Thread-safe
        )

        # JSON handler - All levels, structured format for evaluation
        json_file = cls._log_dir / f"{cls._current_mission}.json"
        logger.add(
            json_file,
            level=file_level,
            format="{message}",
            serialize=True,  # JSON serialization
            enqueue=True  # Thread-safe
        )

        cls._initialized = True

        logger.info(
            "Logger initialized",
            mission=cls._current_mission,
            log_dir=str(cls._log_dir),
            console_level=console_level,
            file_level=file_level
        )

    @classmethod
    def get_mission_name(cls) -> Optional[str]:
        """Get current mission name."""
        return cls._current_mission

    @classmethod
    def log_agent_action(
        cls,
        agent_name: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        level: str = "INFO"
    ) -> None:
        """
        Log agent action with structured data.

        Args:
            agent_name: Name of the agent (Planner, Actor, Verifier)
            action: Action being performed
            details: Additional structured data
            level: Log level (DEBUG, INFO, WARNING, ERROR)
        """
        log_data = {
            "event_type": "agent_action",
            "agent": agent_name,
            "action": action,
            "timestamp": datetime.now().isoformat(),
            **(details or {})
        }

        log_method = getattr(logger, level.lower(), logger.info)
        log_method(f"[{agent_name}] {action}", **log_data)

    @classmethod
    def log_llm_call(
        cls,
        agent_name: str,
        prompt: str,
        response: Optional[str] = None,
        tokens: Optional[Dict[str, int]] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Log LLM API call with metrics.

        Args:
            agent_name: Agent making the LLM call
            prompt: LLM prompt text
            response: LLM response text (if successful)
            tokens: Token usage dict {"prompt": int, "completion": int, "total": int}
            duration_ms: Call duration in milliseconds
            error: Error message (if failed)
        """
        log_data = {
            "event_type": "llm_call",
            "agent": agent_name,
            "prompt_preview": prompt[:200] if prompt else None,  # First 200 chars
            "response_preview": response[:200] if response else None,
            "tokens": tokens,
            "duration_ms": duration_ms,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }

        if error:
            logger.error(f"[{agent_name}] LLM call failed", **log_data)
        else:
            logger.debug(f"[{agent_name}] LLM call completed", **log_data)

    @classmethod
    def log_sensor_data(
        cls,
        sensor_type: str,
        data: Dict[str, Any],
        agent_name: str = "Actor"
    ) -> None:
        """
        Log sensor data reading.

        Args:
            sensor_type: Type of sensor (GPS, Lidar, Camera, IMU)
            data: Sensor data dictionary
            agent_name: Agent reading the sensor
        """
        log_data = {
            "event_type": "sensor_data",
            "agent": agent_name,
            "sensor": sensor_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }

        logger.debug(f"[{agent_name}] {sensor_type} reading", **log_data)

    @classmethod
    def log_mission_event(
        cls,
        event: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
        level: str = "INFO"
    ) -> None:
        """
        Log mission lifecycle event.

        Args:
            event: Event name (mission_start, mission_end, phase_transition)
            status: Event status (started, completed, failed)
            details: Additional event data
            level: Log level
        """
        log_data = {
            "event_type": "mission_event",
            "event": event,
            "status": status,
            "mission": cls._current_mission,
            "timestamp": datetime.now().isoformat(),
            **(details or {})
        }

        log_method = getattr(logger, level.lower(), logger.info)
        log_method(f"Mission {event}: {status}", **log_data)

    @classmethod
    def log_safety_event(
        cls,
        violation_type: str,
        severity: str,
        details: Dict[str, Any]
    ) -> None:
        """
        Log safety constraint violation.

        Args:
            violation_type: Type of violation
            severity: Severity level (LOW, MEDIUM, HIGH, CRITICAL)
            details: Violation details
        """
        log_data = {
            "event_type": "safety_violation",
            "violation_type": violation_type,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            **details
        }

        logger.warning(f"Safety violation: {violation_type} ({severity})", **log_data)

    @classmethod
    def log_failure_event(
        cls,
        failure_type: str,
        agent_name: str,
        details: Dict[str, Any],
        replan_triggered: bool = False
    ) -> None:
        """
        Log mission failure and recovery events.

        Args:
            failure_type: Type of failure (FailureReason enum value)
            agent_name: Agent detecting the failure
            details: Failure details
            replan_triggered: Whether replanning was triggered
        """
        log_data = {
            "event_type": "failure_event",
            "failure_type": failure_type,
            "agent": agent_name,
            "replan_triggered": replan_triggered,
            "timestamp": datetime.now().isoformat(),
            **details
        }

        logger.warning(f"[{agent_name}] Failure detected: {failure_type}", **log_data)


def setup_logger(
    mission_name: Optional[str] = None,
    log_dir: str = "logs",
    console_level: str = "INFO",
    file_level: str = "DEBUG"
) -> None:
    """
    Convenience function to setup logger.

    Args:
        mission_name: Optional mission identifier
        log_dir: Directory for log files
        console_level: Console output level
        file_level: File output level
    """
    LoggerConfig.setup(
        mission_name=mission_name,
        log_dir=log_dir,
        console_level=console_level,
        file_level=file_level
    )


def get_logger():
    """
    Get the configured logger instance.

    Returns:
        Loguru logger instance
    """
    return logger
