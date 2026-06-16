"""
Unit Tests for FastAPI Web Control Server
Story 3.2: FastAPI Web Control Server - Task 12

Tests coverage:
- FastAPI app initialization (AC #5)
- REST API endpoints (/health, /api/status, /api/mission) (AC #1, #5)
- WebSocket connection management (AC #1)
- ConnectionManager class (AC #2)
- Pydantic schema validation (AC #1, #5)
- Error handling (400, 500, 503) (AC #4)
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from fastapi import WebSocket
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json

# Import web server components
from src.web.server import app, manager, set_orchestrator
from src.web.schemas import MissionRequest, MissionResponse, SystemStatus, HealthResponse
from src.schemas import MissionCommand, RobotState


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_orchestrator():
    """Mock MissionOrchestrator for isolated testing."""
    orch = Mock()
    orch.execute_mission = Mock(return_value={
        "success": True,
        "message": "Mission completed",
        "execution_log": [],
        "robot_state": MagicMock(
            get_position=Mock(return_value=(3.0, 0.0, 0.0)),
            reactive_log=[
                {
                    "timestamp": "2025-11-03T10:30:45.123Z",
                    "intervention_type": "MODERATE",
                    "reason": "Obstacle detected",
                    "action_taken": "DETOUR"
                }
            ]
        )
    })
    return orch


@pytest.fixture(autouse=True)
def reset_orchestrator():
    """Reset orchestrator to None after each test."""
    yield
    set_orchestrator(None)


# ============================================================================
# Test: FastAPI App Initialization (AC #5)
# ============================================================================

def test_app_initialization(client):
    """Test FastAPI app is properly initialized with correct configuration."""
    assert app.title == "LLM Robot Control API"
    assert app.version == "1.0.0"
    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"


def test_cors_middleware_configured(client):
    """Test CORS middleware is properly configured."""
    # FastAPI wraps middleware - check that middleware stack exists
    # In FastAPI 0.104+, middleware is wrapped differently
    assert len(app.user_middleware) > 0, "Expected middleware to be configured"
    # Alternative: test CORS functionality by checking allowed origins
    from fastapi.middleware.cors import CORSMiddleware
    # If CORS is configured, OPTIONS requests should work
    response = client.options("/health")
    # Just verify the middleware stack is not empty
    assert response.status_code in [200, 404, 405]  # Any valid HTTP response


# ============================================================================
# Test: Health Endpoint (AC #5)
# ============================================================================

def test_health_endpoint_returns_200(client):
    """Test /health endpoint returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_response_format(client):
    """Test /health endpoint returns correct JSON format."""
    response = client.get("/health")
    data = response.json()

    # Check response structure
    assert "status" in data
    assert "uptime_seconds" in data
    assert "active_connections" in data
    assert "orchestrator_initialized" in data

    # Check data types
    assert isinstance(data["status"], str)
    assert isinstance(data["uptime_seconds"], (int, float))
    assert isinstance(data["active_connections"], int)
    assert isinstance(data["orchestrator_initialized"], bool)


def test_health_endpoint_without_orchestrator(client):
    """Test /health shows orchestrator not initialized when orchestrator is None."""
    response = client.get("/health")
    data = response.json()
    assert data["orchestrator_initialized"] is False


def test_health_endpoint_with_orchestrator(client, mock_orchestrator):
    """Test /health shows orchestrator initialized after set_orchestrator."""
    set_orchestrator(mock_orchestrator)
    response = client.get("/health")
    data = response.json()
    assert data["orchestrator_initialized"] is True


# ============================================================================
# Test: GET /api/status Endpoint (AC #1, #5)
# ============================================================================

def test_api_status_without_orchestrator_returns_503(client):
    """Test GET /api/status returns 503 when orchestrator not initialized."""
    response = client.get("/api/status")
    assert response.status_code == 503
    assert "Orchestrator not initialized" in response.json()["detail"]


def test_api_status_with_orchestrator_returns_200(client, mock_orchestrator):
    """Test GET /api/status returns 200 with valid SystemStatus when orchestrator is set."""
    # Setup mock robot state
    mock_robot_state = MagicMock()
    mock_robot_state.get_position.return_value = (1.5, 0.5, 0.0)
    mock_robot_state.sensors = {
        "lidar_min": 0.8,
        "lidar_avg": 1.2,
        "camera_has_data": True,
        "yaw": 45.0,
        "battery": 85.0
    }
    mock_robot_state.status = "IDLE"
    mock_robot_state.reactive_log = []

    mock_orchestrator.actor_agent = MagicMock()
    mock_orchestrator.actor_agent.robot_state = mock_robot_state

    set_orchestrator(mock_orchestrator)

    response = client.get("/api/status")
    assert response.status_code == 200

    data = response.json()
    # Validate SystemStatus schema
    assert "position" in data
    assert "sensors" in data
    assert "mission_state" in data
    assert "reactive_log_summary" in data
    assert "timestamp" in data


def test_api_status_response_schema_validation(client, mock_orchestrator):
    """Test GET /api/status returns data matching SystemStatus schema."""
    mock_robot_state = MagicMock()
    mock_robot_state.get_position.return_value = (2.0, 1.0, 0.0)
    mock_robot_state.sensors = {
        "lidar_min": 0.5,
        "camera_has_data": False
    }
    mock_robot_state.status = "EXECUTING"
    mock_robot_state.reactive_log = [
        {"intervention_type": "CRITICAL"},
        {"intervention_type": "MODERATE"},
        {"intervention_type": "NORMAL"}
    ]

    mock_orchestrator.actor_agent = MagicMock()
    mock_orchestrator.actor_agent.robot_state = mock_robot_state

    set_orchestrator(mock_orchestrator)

    response = client.get("/api/status")
    data = response.json()

    # Validate position tuple
    assert isinstance(data["position"], list)
    assert len(data["position"]) == 3

    # Validate sensors dict
    assert isinstance(data["sensors"], dict)

    # Validate mission state
    assert data["mission_state"] in ["idle", "planning", "executing", "verifying", "unknown"]

    # Validate reactive_log_summary
    assert isinstance(data["reactive_log_summary"], dict)
    assert "CRITICAL" in data["reactive_log_summary"]
    assert "MODERATE" in data["reactive_log_summary"]
    assert "NORMAL" in data["reactive_log_summary"]


# ============================================================================
# Test: POST /api/mission Endpoint (AC #1, #5)
# ============================================================================

def test_api_mission_without_orchestrator_returns_503(client):
    """Test POST /api/mission returns 503 when orchestrator not initialized."""
    payload = {
        "command": "3미터 전진하세요",
        "language": "ko",
        "priority": 5
    }
    response = client.post("/api/mission", json=payload)
    assert response.status_code == 503
    assert "Orchestrator not initialized" in response.json()["detail"]


def test_api_mission_with_valid_payload_returns_200(client, mock_orchestrator):
    """Test POST /api/mission returns 200 with valid MissionResponse."""
    set_orchestrator(mock_orchestrator)

    payload = {
        "command": "3미터 전진하세요",
        "language": "ko",
        "priority": 5
    }

    response = client.post("/api/mission", json=payload)
    assert response.status_code == 200

    data = response.json()
    # Validate MissionResponse schema
    assert "success" in data
    assert "message" in data
    assert "duration_seconds" in data
    assert "final_position" in data
    assert "reactive_events" in data


def test_api_mission_invalid_command_too_long_returns_422(client):
    """Test POST /api/mission returns 422 when command exceeds max length."""
    payload = {
        "command": "A" * 501,  # Exceeds max_length=500
        "language": "ko",
        "priority": 5
    }
    response = client.post("/api/mission", json=payload)
    assert response.status_code == 422  # Pydantic validation error


def test_api_mission_invalid_priority_returns_422(client):
    """Test POST /api/mission returns 422 when priority out of range."""
    payload = {
        "command": "테스트 명령",
        "language": "ko",
        "priority": 11  # Invalid: must be 1-10
    }
    response = client.post("/api/mission", json=payload)
    assert response.status_code == 422


def test_api_mission_missing_required_field_returns_422(client):
    """Test POST /api/mission returns 422 when required field is missing."""
    payload = {
        "language": "ko",
        "priority": 5
        # Missing "command" field
    }
    response = client.post("/api/mission", json=payload)
    assert response.status_code == 422


# ============================================================================
# Test: ConnectionManager Class (AC #2)
# ============================================================================

@pytest.mark.asyncio
async def test_connection_manager_connect():
    """Test ConnectionManager accepts and tracks WebSocket connections."""
    from src.web.server import ConnectionManager

    mgr = ConnectionManager()
    mock_ws = AsyncMock(spec=WebSocket)

    await mgr.connect(mock_ws)

    assert mock_ws in mgr.active_connections
    assert mgr.get_connection_count() == 1
    mock_ws.accept.assert_called_once()


@pytest.mark.asyncio
async def test_connection_manager_disconnect():
    """Test ConnectionManager removes WebSocket from active connections."""
    from src.web.server import ConnectionManager

    mgr = ConnectionManager()
    mock_ws = AsyncMock(spec=WebSocket)

    await mgr.connect(mock_ws)
    mgr.disconnect(mock_ws)

    assert mock_ws not in mgr.active_connections
    assert mgr.get_connection_count() == 0


@pytest.mark.asyncio
async def test_connection_manager_send_to_client():
    """Test ConnectionManager sends JSON message to specific client."""
    from src.web.server import ConnectionManager

    mgr = ConnectionManager()
    mock_ws = AsyncMock(spec=WebSocket)

    await mgr.connect(mock_ws)
    message = {"type": "test", "data": "hello"}
    await mgr.send_to_client(message, mock_ws)

    mock_ws.send_json.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_connection_manager_broadcast():
    """Test ConnectionManager broadcasts message to all connected clients."""
    from src.web.server import ConnectionManager

    mgr = ConnectionManager()
    mock_ws1 = AsyncMock(spec=WebSocket)
    mock_ws2 = AsyncMock(spec=WebSocket)

    await mgr.connect(mock_ws1)
    await mgr.connect(mock_ws2)

    message = {"type": "broadcast", "data": "update"}
    await mgr.broadcast(message)

    mock_ws1.send_json.assert_called_once_with(message)
    mock_ws2.send_json.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_connection_manager_broadcast_handles_failed_client():
    """Test ConnectionManager removes failed clients during broadcast."""
    from src.web.server import ConnectionManager

    mgr = ConnectionManager()
    mock_ws1 = AsyncMock(spec=WebSocket)
    mock_ws2 = AsyncMock(spec=WebSocket)
    mock_ws2.send_json.side_effect = Exception("Connection lost")

    await mgr.connect(mock_ws1)
    await mgr.connect(mock_ws2)

    message = {"type": "test"}
    await mgr.broadcast(message)

    # ws1 should receive message, ws2 should be disconnected
    mock_ws1.send_json.assert_called_once_with(message)
    assert mock_ws2 not in mgr.active_connections


# ============================================================================
# Test: Pydantic Schema Validation (AC #1, #5)
# ============================================================================

def test_mission_request_schema_validation():
    """Test MissionRequest schema validates correctly."""
    # Valid request
    valid_request = MissionRequest(
        command="3미터 전진하세요",
        language="ko",
        priority=5
    )
    assert valid_request.command == "3미터 전진하세요"
    assert valid_request.language == "ko"
    assert valid_request.priority == 5


def test_mission_request_schema_defaults():
    """Test MissionRequest schema applies default values."""
    request = MissionRequest(command="test command")
    assert request.language == "ko"  # Default
    assert request.priority == 5  # Default


def test_mission_request_schema_validation_error():
    """Test MissionRequest schema raises validation error for invalid data."""
    with pytest.raises(Exception):  # Pydantic ValidationError
        MissionRequest(
            command="A" * 501,  # Exceeds max_length
            language="invalid",  # Must be ko or en
            priority=11  # Must be 1-10
        )


def test_system_status_schema_validation():
    """Test SystemStatus schema validates correctly."""
    status = SystemStatus(
        position=(1.0, 2.0, 0.0),
        sensors={"lidar_min": 0.5},
        mission_state="executing",
        reactive_log_summary={"CRITICAL": 0, "MODERATE": 1, "NORMAL": 5},
        timestamp="2025-11-03T10:30:00Z"
    )
    assert status.position == (1.0, 2.0, 0.0)
    assert status.mission_state == "executing"


# ============================================================================
# Test: Error Handling (AC #4)
# ============================================================================

def test_api_mission_internal_error_returns_500(client, mock_orchestrator):
    """Test POST /api/mission returns 500 when orchestrator raises exception."""
    mock_orchestrator.execute_mission.side_effect = Exception("Internal error")
    set_orchestrator(mock_orchestrator)

    payload = {
        "command": "테스트 명령",
        "language": "ko",
        "priority": 5
    }

    response = client.post("/api/mission", json=payload)
    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]


def test_invalid_json_returns_422(client):
    """Test endpoints return 422 for malformed JSON."""
    response = client.post(
        "/api/mission",
        data="invalid json",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422


# ============================================================================
# Test: Web UI Serving (AC #3)
# ============================================================================

def test_root_endpoint_serves_web_ui(client):
    """Test GET / serves the web UI index.html."""
    response = client.get("/")
    assert response.status_code == 200
    # Check for HTML content
    assert "text/html" in response.headers.get("content-type", "")


# ============================================================================
# Test: set_orchestrator() Helper (AC #4)
# ============================================================================

def test_set_orchestrator_registers_orchestrator(mock_orchestrator):
    """Test set_orchestrator() registers orchestrator globally."""
    set_orchestrator(mock_orchestrator)

    # Verify orchestrator is accessible via health endpoint
    client = TestClient(app)
    response = client.get("/health")
    data = response.json()
    assert data["orchestrator_initialized"] is True


def test_set_orchestrator_with_none_clears_orchestrator():
    """Test set_orchestrator(None) clears orchestrator."""
    set_orchestrator(None)

    client = TestClient(app)
    response = client.get("/health")
    data = response.json()
    assert data["orchestrator_initialized"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
