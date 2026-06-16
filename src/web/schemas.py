"""
Pydantic schemas for FastAPI Web Control Server

Defines request/response models for:
- Mission execution requests and responses
- System status reporting
- WebSocket messages

Story 3.2: FastAPI Web Control Server - Task 2
"""

from pydantic import BaseModel, Field
from typing import Tuple, List, Dict, Any, Optional, Literal
from datetime import datetime


class MissionRequest(BaseModel):
    """
    Request schema for mission execution.

    Used for both REST API and WebSocket endpoints to submit
    natural language commands to the robot.

    Example:
        {
            "command": "앞으로 2미터 이동 후 주변 탐색",
            "language": "ko",
            "priority": 5
        }
    """
    command: str = Field(
        ...,
        max_length=500,
        description="Natural language command for the robot",
        examples=["Move forward 2 meters", "앞으로 5미터 전진"]
    )
    language: str = Field(
        default="ko",
        pattern="^(ko|en)$",
        description="Command language (ko=Korean, en=English)"
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Mission priority level (1=low, 10=high)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "command": "장애물 회피하며 5미터 전진",
                    "language": "ko",
                    "priority": 5
                },
                {
                    "command": "Scan the area for survivors",
                    "language": "en",
                    "priority": 8
                }
            ]
        }
    }


class MissionResponse(BaseModel):
    """
    Response schema for mission execution results.

    Returned after mission completion (or failure) containing
    execution details and reactive events log.

    Example:
        {
            "success": true,
            "message": "Mission completed successfully",
            "duration_seconds": 12.5,
            "final_position": [1.2, 3.4, 0.1],
            "reactive_events": [...]
        }
    """
    success: bool = Field(
        ...,
        description="Whether the mission succeeded"
    )
    message: str = Field(
        ...,
        description="Human-readable mission result message"
    )
    duration_seconds: float = Field(
        ...,
        ge=0,
        description="Total mission execution time in seconds"
    )
    final_position: Tuple[float, float, float] = Field(
        ...,
        description="Final robot position (x, y, z) in meters"
    )
    reactive_events: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of reactive controller interventions during execution"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Mission completed successfully with 2 reactive detours",
                    "duration_seconds": 12.5,
                    "final_position": [2.1, 0.3, 0.098],
                    "reactive_events": [
                        {
                            "timestamp": "2025-11-03T10:30:45.123Z",
                            "intervention_type": "MODERATE",
                            "reason": "Obstacle detected at 0.35m",
                            "action_taken": "DETOUR"
                        }
                    ]
                }
            ]
        }
    }


class SystemStatus(BaseModel):
    """
    Real-time system status for WebSocket broadcasting.

    Broadcast at 10Hz (every 100ms) to connected clients
    containing current robot state and mission progress.

    Example:
        {
            "position": [1.2, 3.4, 0.1],
            "sensors": {"lidar_min": 0.5, "camera_active": true},
            "mission_state": "executing",
            "reactive_log_summary": {"CRITICAL": 0, "MODERATE": 2, "NORMAL": 15}
        }
    """
    position: Tuple[float, float, float] = Field(
        ...,
        description="Current robot position (x, y, z) in meters"
    )
    sensors: Dict[str, Any] = Field(
        ...,
        description="Current sensor readings (lidar_min, camera_active, etc.)"
    )
    mission_state: Literal["idle", "planning", "executing", "verifying", "complete", "failed"] = Field(
        ...,
        description="Current mission execution state"
    )
    reactive_log_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of reactive interventions by type (CRITICAL/MODERATE/NORMAL)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of this status update"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "position": [1.2, 3.4, 0.098],
                    "sensors": {
                        "lidar_min": 0.52,
                        "camera_active": True,
                        "gps_available": False
                    },
                    "mission_state": "executing",
                    "reactive_log_summary": {
                        "CRITICAL": 0,
                        "MODERATE": 2,
                        "NORMAL": 15
                    },
                    "timestamp": "2025-11-03T10:30:45.123456"
                }
            ]
        }
    }


class HealthResponse(BaseModel):
    """
    Health check response schema.

    Simple endpoint to verify server is running.
    """
    status: Literal["ok", "degraded", "error"] = Field(
        ...,
        description="Server health status"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of health check"
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional health check details (uptime, connections, etc.)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "ok",
                    "timestamp": "2025-11-03T10:30:45.123456",
                    "details": {
                        "uptime_seconds": 3600,
                        "active_connections": 3,
                        "orchestrator_status": "ready"
                    }
                }
            ]
        }
    }
