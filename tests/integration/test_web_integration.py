"""
Integration Tests for FastAPI Web Control Server
Story 3.2: FastAPI Web Control Server - Task 13

Tests coverage:
- WebSocket → Orchestrator → Response flow (AC #1, #4)
- Status broadcasting during mission execution (AC #2)
- Error propagation from Orchestrator to client (AC #4)
- Concurrent WebSocket connections (AC #2)
- 10Hz status broadcast frequency validation (AC #2)
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock
import time

from src.web.server import app, set_orchestrator


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator for integration testing."""
    orch = Mock()
    orch.execute_mission = Mock(return_value={
        "success": True,
        "message": "Mission completed",
        "execution_log": [],
        "robot_state": MagicMock(
            get_position=Mock(return_value=(3.0, 0.0, 0.0)),
            reactive_log=[]
        )
    })
    orch.actor_agent = MagicMock()
    orch.actor_agent.robot_state = MagicMock(
        get_position=Mock(return_value=(1.0, 0.0, 0.0)),
        sensors={"lidar_min": 0.5, "camera_has_data": True},
        status="IDLE",
        reactive_log=[]
    )
    return orch


@pytest.fixture(autouse=True)
def reset_orchestrator():
    """Reset orchestrator after each test."""
    yield
    set_orchestrator(None)


# ============================================================================
# Test: WebSocket → Orchestrator → Response Flow (AC #1, #4)
# ============================================================================

def test_websocket_mission_execution_flow(client, mock_orchestrator):
    """Test WebSocket command submission → orchestrator execution → response."""
    set_orchestrator(mock_orchestrator)

    with client.websocket_connect("/ws/control") as websocket:
        # Send mission command
        command = {
            "command": "3미터 전진하세요",
            "language": "ko",
            "priority": 5
        }
        websocket.send_json(command)

        # Receive mission response
        response = websocket.receive_json()

        # Validate response structure
        assert "success" in response
        assert "message" in response
        assert response["success"] is True

        # Verify orchestrator was called
        mock_orchestrator.execute_mission.assert_called_once()


def test_websocket_error_propagation(client, mock_orchestrator):
    """Test error propagation from orchestrator to WebSocket client."""
    mock_orchestrator.execute_mission.side_effect = Exception("Orchestrator error")
    set_orchestrator(mock_orchestrator)

    with client.websocket_connect("/ws/control") as websocket:
        command = {"command": "test", "language": "ko", "priority": 5}
        websocket.send_json(command)

        response = websocket.receive_json()

        # Verify error is returned to client
        assert response["success"] is False
        assert "error" in response["message"].lower()


# ============================================================================
# Test: Status Broadcasting (AC #2)
# ============================================================================

def test_status_websocket_broadcasting(client, mock_orchestrator):
    """Test /ws/robot-status broadcasts status updates."""
    set_orchestrator(mock_orchestrator)

    with client.websocket_connect("/ws/robot-status") as websocket:
        # Send start broadcasting message
        websocket.send_json({"action": "start_broadcasting"})

        # Receive first status update
        status = websocket.receive_json(timeout=2)

        # Validate status structure
        assert "position" in status
        assert "sensors" in status
        assert "mission_state" in status
        assert "reactive_log_summary" in status


def test_concurrent_websocket_connections(client, mock_orchestrator):
    """Test server supports concurrent WebSocket connections."""
    set_orchestrator(mock_orchestrator)

    # Open multiple WebSocket connections concurrently
    with client.websocket_connect("/ws/robot-status") as ws1, \
         client.websocket_connect("/ws/robot-status") as ws2:

        # Both connections should receive status updates
        status1 = ws1.receive_json(timeout=2)
        status2 = ws2.receive_json(timeout=2)

        assert "position" in status1
        assert "position" in status2


# ============================================================================
# Test: Broadcast Frequency (AC #2)
# ============================================================================

def test_status_broadcast_frequency_validation(client, mock_orchestrator):
    """Test status broadcast frequency is approximately 10Hz (100ms)."""
    set_orchestrator(mock_orchestrator)

    with client.websocket_connect("/ws/robot-status") as websocket:
        websocket.send_json({"action": "start_broadcasting"})

        # Measure time between 5 status updates
        timestamps = []
        for _ in range(5):
            websocket.receive_json(timeout=2)
            timestamps.append(time.time())

        # Calculate average interval
        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        avg_interval = sum(intervals) / len(intervals)

        # Validate approximately 100ms (10Hz) ± 20ms tolerance
        assert 0.08 < avg_interval < 0.12, f"Expected ~100ms, got {avg_interval*1000:.1f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
