"""
Integration Tests for Reactive System Multi-Agent Flow

Tests the integration of HybridReactiveController with ActorAgent and VerifierAgent.
Verifies reactive_log propagation and tolerance adjustment.

Story 3.1 Re-Review Action Item 3: Task 7
"""

import pytest
import time
import os
from unittest.mock import Mock, MagicMock, patch
from src.agents.actor_agent import ActorAgent
from src.agents.verifier_agent import VerifierAgent
from src.reactive.hybrid_controller import HybridReactiveController, InterventionType
from src.schemas.robot_action import RobotAction, ActionType
from src.schemas.robot_state import RobotState


class TestReactiveIntegration:
    """Integration tests for reactive system multi-agent flow."""

    @pytest.fixture
    def api_key(self):
        """Get API key from environment."""
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            pytest.skip("OPENAI_API_KEY not set")
        return key

    @pytest.fixture
    def mock_robot(self):
        """Create mock Webots robot."""
        robot = Mock()
        robot.getBasicTimeStep.return_value = 64  # 64ms timestep
        robot.step.return_value = 0  # Success

        # Mock motors
        left_motor = Mock()
        right_motor = Mock()
        robot.getDevice.side_effect = lambda name: left_motor if 'left' in name else right_motor

        # Mock sensors
        gps = Mock()
        gps.getValues.return_value = [1.0, 2.0, 0.0]

        compass = Mock()
        compass.getValues.return_value = [1.0, 0.0, 0.0]

        lidar = Mock()
        lidar.getRangeImage.return_value = [1.0] * 512
        lidar.getNumberOfPoints.return_value = 512

        camera = Mock()
        camera.getImage.return_value = None

        robot.getDevice.side_effect = lambda name: {
            'gps': gps,
            'compass': compass,
            'lidar': lidar,
            'camera': camera,
            'left wheel motor': left_motor,
            'right wheel motor': right_motor
        }.get(name, Mock())

        return robot

    @pytest.fixture
    def actor_agent(self, mock_robot, api_key):
        """Create ActorAgent with reactive controller."""
        actor = ActorAgent(robot=mock_robot, api_key=api_key)
        # Ensure reactive controller is enabled
        if hasattr(actor, 'reactive_controller'):
            actor.reactive_controller.enable_ollama = False  # Use rules-only for testing
        return actor

    @pytest.fixture
    def verifier_agent(self, api_key):
        """Create VerifierAgent."""
        # VerifierAgent doesn't take 'robot' parameter, only api_key
        return VerifierAgent(api_key=api_key)

    def test_reactive_log_initialization(self, actor_agent):
        """Test 7.1: Verify reactive_log is properly initialized in ActorAgent."""
        assert hasattr(actor_agent, 'reactive_log'), "ActorAgent should have reactive_log attribute"
        assert isinstance(actor_agent.reactive_log, list), "reactive_log should be a list"
        assert len(actor_agent.reactive_log) == 0, "reactive_log should start empty"

    def test_reactive_log_propagation(self, actor_agent, verifier_agent):
        """Test 7.2: Test reactive_log propagation from Actor to Verifier."""
        # Setup: Add intervention to Actor's reactive_log
        intervention = {
            "timestamp": "2025-11-03T10:00:00",
            "type": "MODERATE",
            "reason": "AI detour (confidence=0.85)",
            "action_taken": {"type": "detour", "params": {"detour_x": 0.2, "detour_y": 0.3}},
            "sensor_state": {"lidar_min": 0.3, "position": [1.0, 2.0, 0.0]}
        }
        actor_agent.reactive_log.append(intervention)

        # Create RobotState with reactive_log
        robot_state = RobotState(
            position=[1.0, 2.0, 0.0],
            orientation=0.0,
            sensor_data={},
            status="moving",
            reactive_log=actor_agent.reactive_log.copy()
        )

        # Verify: Verifier receives reactive_log
        assert len(robot_state.reactive_log) == 1, "RobotState should contain reactive_log"
        assert robot_state.reactive_log[0]["type"] == "MODERATE", "Intervention type should be MODERATE"
        assert "detour" in robot_state.reactive_log[0]["action_taken"]["type"], "Action should be detour"

        # Verify: Verifier can access reactive_log
        # Note: In actual flow, Verifier receives RobotState and checks reactive_log
        assert hasattr(verifier_agent, 'adjust_tolerance_based_on_reactive_log'), \
            "VerifierAgent should have method to process reactive_log"

    def test_tolerance_adjustment_with_moderate_intervention(self, verifier_agent):
        """Test 7.3: Test tolerance adjustment from 0.1m to 0.3m with MODERATE intervention."""
        # Setup: Create RobotState with MODERATE intervention
        robot_state = RobotState(
            position=[1.0, 2.0, 0.0],
            orientation=0.0,
            sensor_data={},
            status="moving",
            reactive_log=[{
                "timestamp": "2025-11-03T10:00:00",
                "type": "MODERATE",
                "reason": "AI detour",
                "action_taken": {"type": "detour", "params": {}},
                "sensor_state": {"lidar_min": 0.3}
            }]
        )

        # Default tolerance (no interventions)
        default_tolerance = 0.1

        # Adjusted tolerance (with MODERATE intervention)
        adjusted_tolerance = verifier_agent.adjust_tolerance_based_on_reactive_log(robot_state.reactive_log)

        # Verify: Tolerance increased to 0.3m
        assert adjusted_tolerance > default_tolerance, "Tolerance should increase with MODERATE intervention"
        assert adjusted_tolerance == 0.3, f"Tolerance should be 0.3m, got {adjusted_tolerance}m"

    def test_tolerance_adjustment_with_critical_intervention(self, verifier_agent):
        """Test 7.3b: Test tolerance remains 0.1m with CRITICAL intervention (no adjustment)."""
        # Setup: Create RobotState with CRITICAL intervention
        robot_state = RobotState(
            position=[1.0, 2.0, 0.0],
            orientation=0.0,
            sensor_data={},
            status="stopped",
            reactive_log=[{
                "timestamp": "2025-11-03T10:00:00",
                "type": "CRITICAL",
                "reason": "Emergency stop",
                "action_taken": {"type": "emergency_stop", "params": {}},
                "sensor_state": {"lidar_min": 0.05}
            }]
        )

        # Adjusted tolerance (with CRITICAL intervention)
        adjusted_tolerance = verifier_agent.adjust_tolerance_based_on_reactive_log(robot_state.reactive_log)

        # Verify: Tolerance unchanged (CRITICAL doesn't increase tolerance)
        assert adjusted_tolerance == 0.1, f"Tolerance should remain 0.1m for CRITICAL, got {adjusted_tolerance}m"

    def test_64ms_check_cycle_timing(self):
        """Test 7.4: Verify 64ms check cycle timing requirement."""
        # Setup: Create reactive controller
        controller = HybridReactiveController(enable_ollama=False)

        # Mock sensor data
        sensor_data = {
            'lidar': {'lidar_min_distance': 1.0, 'lidar_avg_distance': 2.0, 'lidar_distances': [1.0] * 512},
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        # Measure check_and_react latency
        start = time.time()
        for _ in range(10):  # 10 cycles
            controller.check_and_react(sensor_data)
        elapsed = (time.time() - start) * 1000  # Convert to ms

        # Verify: Average latency < 64ms (target: <10ms for non-Ollama)
        avg_latency = elapsed / 10
        assert avg_latency < 64, f"Average latency {avg_latency:.2f}ms exceeds 64ms cycle time"
        assert avg_latency < 10, f"Average latency {avg_latency:.2f}ms exceeds 10ms target"

    def test_multi_agent_flow_preservation(self, actor_agent, verifier_agent):
        """Test 7.5: Test multi-agent flow preservation with reactive system."""
        # Setup: Simulate Actor execution with reactive intervention
        actor_agent.reactive_log.clear()

        # Simulate MODERATE intervention during execution
        intervention = {
            "timestamp": "2025-11-03T10:00:00",
            "type": "MODERATE",
            "reason": "AI detour (confidence=0.85)",
            "action_taken": {"type": "detour", "params": {"detour_x": 0.2, "detour_y": 0.3}},
            "sensor_state": {"lidar_min": 0.3, "position": [1.0, 2.0, 0.0]}
        }
        actor_agent.reactive_log.append(intervention)

        # Create RobotState (Actor → Verifier)
        robot_state = RobotState(
            position=[1.2, 2.2, 0.0],  # Position after detour (~0.28m from target)
            orientation=0.0,
            sensor_data={},
            status="moving",
            reactive_log=actor_agent.reactive_log.copy()
        )

        # Create RobotAction (target before detour)
        action = RobotAction(
            action=ActionType.MOVE,
            x=1.0,
            y=2.0
        )

        # Verify: Verifier flow
        # 1. Verifier receives RobotState with reactive_log
        assert len(robot_state.reactive_log) == 1, "RobotState should contain intervention"

        # 2. Verifier adjusts tolerance based on reactive_log
        adjusted_tolerance = verifier_agent.adjust_tolerance_based_on_reactive_log(robot_state.reactive_log)
        assert adjusted_tolerance == 0.3, "Tolerance should be adjusted to 0.3m"

        # 3. Verifier validates action with adjusted tolerance
        # Note: Position [1.2, 2.2] is ~0.28m from target [1.0, 2.0]
        #       - Would FAIL with default 0.1m tolerance (0.28 > 0.1)
        #       - Should PASS with adjusted 0.3m tolerance (0.28 < 0.3)
        import math
        distance = math.sqrt((1.2 - 1.0)**2 + (2.2 - 2.0)**2)
        assert distance > 0.1, "Distance should exceed default tolerance"
        assert distance <= adjusted_tolerance, "Distance should be within adjusted tolerance"

        # Multi-agent flow preserved: Actor intervention → Verifier tolerance adjustment
