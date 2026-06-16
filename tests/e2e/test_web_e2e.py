"""
End-to-End Tests for FastAPI Web Control Server
Story 3.2: FastAPI Web Control Server - Task 14

Note: These tests require full system integration.
For local testing, use mocked orchestrator.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock

from src.web.server import app, set_orchestrator


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_full_orchestrator():
    """Mock orchestrator with complete mission execution simulation."""
    orch = Mock()

    # Simulate full mission execution
    def execute_mission_mock(mission):
        return {
            "success": True,
            "message": "Mission completed successfully",
            "execution_log": [
                "Planning: Generated 3-step plan",
                "Execution: Moved forward 3m",
                "Verification: Goal reached"
            ],
            "robot_state": MagicMock(
                get_position=Mock(return_value=(3.0, 0.0, 0.0)),
                reactive_log=[
                    {
                        "timestamp": "2025-11-03T10:30:45Z",
                        "intervention_type": "MODERATE",
                        "reason": "Obstacle at 0.4m",
                        "action_taken": "DETOUR"
                    }
                ]
            )
        }

    orch.execute_mission = Mock(side_effect=execute_mission_mock)
    orch.actor_agent = MagicMock()
    orch.actor_agent.robot_state = MagicMock(
        get_position=Mock(return_value=(0.0, 0.0, 0.0)),
        sensors={"lidar_min": 0.8, "camera_has_data": True, "battery": 85.0},
        status="IDLE",
        reactive_log=[]
    )
    return orch


@pytest.fixture(autouse=True)
def reset_orchestrator():
    """Reset orchestrator after each test."""
    yield
    set_orchestrator(None)


def test_e2e_web_ui_to_mission_execution(client, mock_full_orchestrator):
    """Test complete flow: Web UI → WebSocket → Orchestrator → Response."""
    set_orchestrator(mock_full_orchestrator)

    # 1. Check health
    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json()["orchestrator_initialized"] is True

    # 2. Submit mission via WebSocket
    with client.websocket_connect("/ws/control") as websocket:
        command = {
            "command": "장애물을 회피하며 5미터 전진하세요",
            "language": "ko",
            "priority": 5
        }
        websocket.send_json(command)

        # 3. Receive mission response
        response = websocket.receive_json()

        # 4. Validate complete response
        assert response["success"] is True
        assert "completed" in response["message"].lower()
        assert len(response["reactive_events"]) > 0


def test_e2e_status_updates_during_execution(client, mock_full_orchestrator):
    """Test status broadcasting provides updates during mission execution."""
    set_orchestrator(mock_full_orchestrator)

    with client.websocket_connect("/ws/robot-status") as websocket:
        # Start broadcasting
        websocket.send_json({"action": "start_broadcasting"})

        # Receive multiple status updates
        for _ in range(3):
            status = websocket.receive_json(timeout=2)
            assert "position" in status
            assert "mission_state" in status


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
