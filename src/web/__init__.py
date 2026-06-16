"""
FastAPI Web Control Server

Provides web-based control interface for LLM_ROBOT_2 with:
- REST API endpoints for mission execution
- WebSocket endpoints for real-time status updates
- Natural language command processing

Story 3.2: FastAPI Web Control Server
"""

__version__ = "1.0.0"

# Export main components for external use
from .server import (
    app,
    set_orchestrator,
    start_status_broadcasting,
    stop_status_broadcasting,
    toggle_status_broadcasting,
    get_current_system_status
)

__all__ = [
    "app",
    "set_orchestrator",
    "start_status_broadcasting",
    "stop_status_broadcasting",
    "toggle_status_broadcasting",
    "get_current_system_status"
]
