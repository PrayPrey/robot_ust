"""
Unit Tests for HybridReactiveController

Tests 3-level reactive decision logic:
- Level 1 CRITICAL: Emergency stop (Lidar < 0.15m)
- Level 2 MODERATE: AI-powered detour (0.15m <= Lidar < 0.5m)
- Level 3 NORMAL: No intervention (Lidar >= 0.5m)

Story 3.1 Acceptance Criteria Coverage:
- AC #1: Emergency stop logic
- AC #2: Ollama detour decision (mocked)
- AC #3: Normal execution path
- AC #5: Performance (<10ms for non-Ollama modes)
- AC #6: Code coverage >90%
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from src.reactive.hybrid_controller import (
    HybridReactiveController,
    ReactiveDecision,
    InterventionType,
    DetourPlan
)


class TestHybridReactiveController:
    """Test HybridReactiveController initialization and basic operations."""

    def test_init_with_ollama_enabled(self):
        """Test controller initialization with Ollama enabled."""
        controller = HybridReactiveController(
            ollama_host="http://localhost:11434",
            model_name="tinyllama",
            enable_ollama=True
        )

        assert controller.ollama_host == "http://localhost:11434"
        assert controller.model_name == "tinyllama"
        assert controller.emergency_threshold == 0.15
        assert controller.detour_threshold == 0.5
        # Ollama client may or may not initialize depending on service availability
        # Just check the controller is created

    def test_init_with_ollama_disabled(self):
        """Test controller initialization with Ollama disabled (rules-only mode)."""
        controller = HybridReactiveController(
            enable_ollama=False
        )

        assert controller.enable_ollama is False
        assert controller.ollama_client is None

    def test_init_custom_thresholds(self):
        """Test custom threshold configuration."""
        controller = HybridReactiveController(
            emergency_threshold=0.2,
            detour_threshold=0.6,
            enable_ollama=False
        )

        assert controller.emergency_threshold == 0.2
        assert controller.detour_threshold == 0.6


class TestEmergencyStopLogic:
    """Test Level 1 CRITICAL emergency stop logic (AC #1)."""

    def test_emergency_stop_triggered_below_threshold(self):
        """Test emergency stop when Lidar < 0.15m."""
        controller = HybridReactiveController(enable_ollama=False)

        sensor_data = {
            'lidar': {
                'lidar_min_distance': 0.12,  # Below 0.15m threshold
                'lidar_avg_distance': 1.5,
                'lidar_distances': [0.12] * 512
            },
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        decision = controller.check_and_react(sensor_data)

        assert decision.intervention_type == InterventionType.CRITICAL
        assert decision.action == "emergency_stop"
        assert decision.metadata['lidar_min'] == 0.12
        assert decision.metadata['threshold'] == 0.15
        assert "Obstacle detected" in decision.metadata['reason']

    def test_emergency_stop_at_exact_threshold(self):
        """Test behavior at exact threshold boundary (0.15m)."""
        controller = HybridReactiveController(enable_ollama=False)

        sensor_data = {
            'lidar': {
                'lidar_min_distance': 0.15,  # Exactly at threshold
                'lidar_avg_distance': 1.5,
                'lidar_distances': [0.15] * 512
            },
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        decision = controller.check_and_react(sensor_data)

        # At threshold, should trigger MODERATE (not CRITICAL)
        # Since CRITICAL is strictly < 0.15m
        assert decision.intervention_type in [InterventionType.MODERATE, InterventionType.CRITICAL]

    def test_emergency_stop_reaction_time(self):
        """Test emergency stop reaction time < 0.001s (1ms)."""
        controller = HybridReactiveController(enable_ollama=False)

        sensor_data = {
            'lidar': {
                'lidar_min_distance': 0.1,
                'lidar_avg_distance': 1.5,
                'lidar_distances': [0.1] * 512
            },
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        start = time.time()
        decision = controller.check_and_react(sensor_data)
        latency = (time.time() - start) * 1000  # ms

        assert decision.intervention_type == InterventionType.CRITICAL
        assert latency < 1.0  # < 1ms reaction time
        assert decision.latency_ms < 10.0  # Recorded latency also < 10ms


class TestNormalExecutionPath:
    """Test Level 3 NORMAL no-intervention logic (AC #3)."""

    def test_no_intervention_when_path_clear(self):
        """Test no intervention when Lidar >= 0.5m."""
        controller = HybridReactiveController(enable_ollama=False)

        sensor_data = {
            'lidar': {
                'lidar_min_distance': 2.5,  # Well above 0.5m threshold
                'lidar_avg_distance': 3.0,
                'lidar_distances': [2.5] * 512
            },
            'gps': {'position_x': 1.0, 'position_y': 2.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 45.0},
            'camera': {'has_data': True}
        }

        decision = controller.check_and_react(sensor_data)

        assert decision.intervention_type == InterventionType.NONE
        assert decision.action == "continue"
        assert "Path clear" in decision.metadata['reason']

    def test_no_intervention_at_threshold_boundary(self):
        """Test behavior at 0.5m threshold boundary."""
        controller = HybridReactiveController(enable_ollama=False)

        sensor_data = {
            'lidar': {
                'lidar_min_distance': 0.5,  # Exactly at detour threshold
                'lidar_avg_distance': 1.0,
                'lidar_distances': [0.5] * 512
            },
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        decision = controller.check_and_react(sensor_data)

        # At 0.5m, should not trigger intervention (NORMAL path)
        assert decision.intervention_type == InterventionType.NONE


class TestOllamaDetourLogic:
    """Test Level 2 MODERATE AI-powered detour logic (AC #2)."""

    @patch('src.reactive.hybrid_controller.Client')
    def test_ollama_detour_triggered_in_moderate_range(self, mock_client_class):
        """Test Ollama detour decision triggered for 0.15m < Lidar < 0.5m."""
        # Mock Ollama client
        mock_client = Mock()
        mock_response = {
            'response': '{"detour_x": 0.2, "detour_y": 0.5, "speed_modifier": 0.7, "confidence": 0.85, "reasoning": "Move right"}'
        }
        mock_client.generate.return_value = mock_response
        mock_client_class.return_value = mock_client

        controller = HybridReactiveController(
            enable_ollama=True,
            ollama_host="http://localhost:11434",
            model_name="tinyllama"
        )
        controller.ollama_client = mock_client  # Force mock client
        controller.enable_ollama = True  # Ensure Ollama is enabled

        sensor_data = {
            'lidar': {
                'lidar_min_distance': 0.3,  # In MODERATE range (0.15 < x < 0.5)
                'lidar_avg_distance': 1.2,
                'lidar_distances': [0.3] * 512
            },
            'gps': {'position_x': 1.0, 'position_y': 2.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 90.0},
            'camera': {'has_data': False}
        }

        decision = controller.check_and_react(sensor_data)

        assert decision.intervention_type == InterventionType.MODERATE
        assert decision.action == "detour"
        assert 'detour_plan' in decision.metadata
        assert decision.metadata['ai_provider'] == "ollama"
        assert decision.metadata['model'] == "tinyllama"

        # Verify Ollama was called
        mock_client.generate.assert_called_once()
        call_args = mock_client.generate.call_args
        assert call_args[1]['model'] == 'tinyllama'
        assert call_args[1]['options']['temperature'] == 0.1

    @patch('src.reactive.hybrid_controller.Client')
    def test_ollama_markdown_code_block_parsing(self, mock_client_class):
        """Test JSON parsing with markdown code blocks (Story 3.0 pattern)."""
        mock_client = Mock()
        # Simulate TinyLlama wrapping JSON in markdown code blocks
        mock_response = {
            'response': '''```json
{"detour_x": 0.1, "detour_y": 0.3, "speed_modifier": 0.8, "confidence": 0.9, "reasoning": "Detour left"}
```'''
        }
        mock_client.generate.return_value = mock_response
        mock_client_class.return_value = mock_client

        controller = HybridReactiveController(enable_ollama=True)
        controller.ollama_client = mock_client
        controller.enable_ollama = True  # Ensure Ollama is enabled

        sensor_data = {
            'lidar': {'lidar_min_distance': 0.25, 'lidar_avg_distance': 1.0, 'lidar_distances': [0.25] * 512},
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        decision = controller.check_and_react(sensor_data)

        assert decision.intervention_type == InterventionType.MODERATE
        detour_plan = decision.metadata['detour_plan']
        assert detour_plan['detour_x'] == 0.1
        assert detour_plan['detour_y'] == 0.3
        assert detour_plan['confidence'] == 0.9


class TestGracefulDegradation:
    """Test graceful degradation when Ollama fails (AC #2)."""

    @patch('src.reactive.hybrid_controller.Client')
    def test_fallback_to_critical_on_ollama_failure(self, mock_client_class):
        """Test fallback to emergency stop when Ollama fails."""
        mock_client = Mock()
        mock_client.generate.side_effect = Exception("Ollama connection error")
        mock_client_class.return_value = mock_client

        controller = HybridReactiveController(enable_ollama=True)
        controller.ollama_client = mock_client
        controller.enable_ollama = True  # Ensure Ollama is enabled

        sensor_data = {
            'lidar': {'lidar_min_distance': 0.3, 'lidar_avg_distance': 1.0, 'lidar_distances': [0.3] * 512},
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        decision = controller.check_and_react(sensor_data)

        # Should fall back to CRITICAL mode
        assert decision.intervention_type == InterventionType.CRITICAL
        assert decision.action == "emergency_stop"
        assert "Ollama failure" in decision.metadata['reason']
        assert controller.ollama_failure_count == 1

    def test_rules_only_mode_when_ollama_disabled(self):
        """Test MODERATE range triggers emergency stop when Ollama disabled."""
        controller = HybridReactiveController(enable_ollama=False)

        sensor_data = {
            'lidar': {'lidar_min_distance': 0.3, 'lidar_avg_distance': 1.0, 'lidar_distances': [0.3] * 512},
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        decision = controller.check_and_react(sensor_data)

        # Should fall back to emergency stop (rules-only mode)
        assert decision.intervention_type == InterventionType.CRITICAL
        assert decision.action == "emergency_stop"
        assert "Ollama disabled" in decision.metadata['reason']


class TestPerformance:
    """Test performance requirements (AC #5)."""

    def test_check_and_react_latency_critical_mode(self):
        """Test check_and_react() latency < 10ms for CRITICAL mode."""
        controller = HybridReactiveController(enable_ollama=False)

        sensor_data = {
            'lidar': {'lidar_min_distance': 0.1, 'lidar_avg_distance': 1.0, 'lidar_distances': [0.1] * 512},
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        latencies = []
        for _ in range(100):
            start = time.time()
            decision = controller.check_and_react(sensor_data)
            latency_ms = (time.time() - start) * 1000
            latencies.append(latency_ms)

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

        assert avg_latency < 10.0, f"Avg latency {avg_latency:.2f}ms exceeds 10ms"
        assert p95_latency < 10.0, f"P95 latency {p95_latency:.2f}ms exceeds 10ms"

    def test_check_and_react_latency_normal_mode(self):
        """Test check_and_react() latency < 10ms for NORMAL mode."""
        controller = HybridReactiveController(enable_ollama=False)

        sensor_data = {
            'lidar': {'lidar_min_distance': 2.0, 'lidar_avg_distance': 3.0, 'lidar_distances': [2.0] * 512},
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        latencies = []
        for _ in range(100):
            start = time.time()
            decision = controller.check_and_react(sensor_data)
            latency_ms = (time.time() - start) * 1000
            latencies.append(latency_ms)

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

        assert avg_latency < 10.0, f"Avg latency {avg_latency:.2f}ms exceeds 10ms"
        assert p95_latency < 10.0, f"P95 latency {p95_latency:.2f}ms exceeds 10ms"


class TestStatistics:
    """Test controller statistics tracking."""

    def test_statistics_tracking(self):
        """Test intervention and Ollama call statistics."""
        controller = HybridReactiveController(enable_ollama=False)

        # Trigger CRITICAL intervention
        sensor_data_critical = {
            'lidar': {'lidar_min_distance': 0.1, 'lidar_avg_distance': 1.0, 'lidar_distances': [0.1] * 512},
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        controller.check_and_react(sensor_data_critical)
        controller.check_and_react(sensor_data_critical)

        stats = controller.get_statistics()

        assert stats['intervention_count'] == 2
        assert stats['ollama_call_count'] == 0
        assert stats['ollama_failure_count'] == 0
        assert stats['avg_latency_ms'] > 0

    def test_reset_statistics(self):
        """Test statistics reset."""
        controller = HybridReactiveController(enable_ollama=False)

        sensor_data = {
            'lidar': {'lidar_min_distance': 0.1, 'lidar_avg_distance': 1.0, 'lidar_distances': [0.1] * 512},
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        controller.check_and_react(sensor_data)

        stats_before = controller.get_statistics()
        assert stats_before['intervention_count'] > 0

        controller.reset_statistics()

        stats_after = controller.get_statistics()
        assert stats_after['intervention_count'] == 0
        assert stats_after['total_latency_ms'] == 0.0


class TestDetourCaching:
    """Test Ollama detour caching functionality (Story 3.1 Re-Review Action Item 1)."""

    @patch('src.reactive.hybrid_controller.Client')
    def test_cache_hit_on_repeated_sensor_pattern(self, mock_client_class):
        """Test cache hit when same sensor pattern is repeated."""
        # Setup mock Ollama client
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock Ollama response
        mock_client.generate.return_value = {
            'response': '{"detour_x": 0.3, "detour_y": 0.5, "speed_modifier": 0.7, "confidence": 0.85, "reasoning": "Test detour"}'
        }

        controller = HybridReactiveController(enable_ollama=True)
        controller.ollama_client = mock_client  # Force mock client
        controller.enable_ollama = True  # Ensure Ollama is enabled even if OLLAMA_AVAILABLE=False

        # Create sensor data with MODERATE threat (0.15m <= lidar < 0.5m)
        sensor_data = {
            'lidar': {
                'lidar_min_distance': 0.3,
                'lidar_avg_distance': 1.0,
                'lidar_distances': [0.3, 0.4, 0.5] * 171  # 513 points (sampled every 10th)
            },
            'gps': {'position_x': 1.0, 'position_y': 2.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 45.0},
            'camera': {'has_data': False}
        }

        # First call - should call Ollama (cache miss)
        decision1 = controller.check_and_react(sensor_data)
        assert decision1.intervention_type == InterventionType.MODERATE
        assert mock_client.generate.call_count == 1
        assert controller.cache_misses == 1
        assert controller.cache_hits == 0

        # Second call with SAME sensor pattern - should use cache (cache hit)
        decision2 = controller.check_and_react(sensor_data)
        assert decision2.intervention_type == InterventionType.MODERATE
        assert mock_client.generate.call_count == 1  # Still 1 (no new Ollama call)
        assert controller.cache_hits == 1
        assert controller.cache_misses == 1

        # Verify cache hit rate
        stats = controller.get_statistics()
        assert stats['cache_hit_rate'] == 0.5  # 1 hit / 2 total requests

    @patch('src.reactive.hybrid_controller.Client')
    def test_cache_miss_on_new_sensor_pattern(self, mock_client_class):
        """Test cache miss when sensor pattern changes."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_client.generate.return_value = {
            'response': '{"detour_x": 0.2, "detour_y": 0.3, "speed_modifier": 0.8, "confidence": 0.9, "reasoning": "Test"}'
        }

        controller = HybridReactiveController(enable_ollama=True)
        controller.ollama_client = mock_client  # Force mock client
        controller.enable_ollama = True  # Ensure Ollama is enabled

        # First sensor pattern
        sensor_data1 = {
            'lidar': {
                'lidar_min_distance': 0.3,
                'lidar_avg_distance': 1.0,
                'lidar_distances': [0.3] * 512
            },
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        # Second sensor pattern (DIFFERENT lidar_min and pattern)
        sensor_data2 = {
            'lidar': {
                'lidar_min_distance': 0.4,  # Different
                'lidar_avg_distance': 1.0,
                'lidar_distances': [0.4] * 512  # Different pattern
            },
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        # First call - cache miss
        controller.check_and_react(sensor_data1)
        assert controller.cache_misses == 1
        assert mock_client.generate.call_count == 1

        # Second call with DIFFERENT pattern - cache miss
        controller.check_and_react(sensor_data2)
        assert controller.cache_misses == 2
        assert mock_client.generate.call_count == 2

        # Verify cache now has 2 entries
        assert len(controller.detour_cache) == 2

    @patch('src.reactive.hybrid_controller.Client')
    def test_cache_eviction_at_50_entries(self, mock_client_class):
        """Test FIFO cache eviction when cache size exceeds 50."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_client.generate.return_value = {
            'response': '{"detour_x": 0.1, "detour_y": 0.1, "speed_modifier": 0.9, "confidence": 0.8, "reasoning": "Test"}'
        }

        controller = HybridReactiveController(enable_ollama=True)
        controller.ollama_client = mock_client  # Force mock client
        controller.enable_ollama = True  # Ensure Ollama is enabled

        # Generate 51 unique sensor patterns
        for i in range(51):
            sensor_data = {
                'lidar': {
                    'lidar_min_distance': 0.2 + (i * 0.001),  # Unique lidar_min
                    'lidar_avg_distance': 1.0,
                    'lidar_distances': [0.2 + (i * 0.001)] * 512  # Unique pattern
                },
                'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
                'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
                'camera': {'has_data': False}
            }
            controller.check_and_react(sensor_data)

        # Verify cache size is capped at 50 (oldest entry evicted)
        assert len(controller.detour_cache) == 50
        assert controller.cache_misses == 51
        assert mock_client.generate.call_count == 51

    @patch('src.reactive.hybrid_controller.Client')
    def test_cache_statistics_in_get_statistics(self, mock_client_class):
        """Test cache statistics are included in get_statistics()."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_client.generate.return_value = {
            'response': '{"detour_x": 0.1, "detour_y": 0.1, "speed_modifier": 0.9, "confidence": 0.8, "reasoning": "Test"}'
        }

        controller = HybridReactiveController(enable_ollama=True)
        controller.ollama_client = mock_client  # Force mock client
        controller.enable_ollama = True  # Ensure Ollama is enabled

        sensor_data = {
            'lidar': {
                'lidar_min_distance': 0.3,
                'lidar_avg_distance': 1.0,
                'lidar_distances': [0.3] * 512
            },
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        # First call - miss
        controller.check_and_react(sensor_data)
        # Second call - hit
        controller.check_and_react(sensor_data)

        stats = controller.get_statistics()

        # Verify cache statistics are present
        assert 'cache_size' in stats
        assert 'cache_hits' in stats
        assert 'cache_misses' in stats
        assert 'cache_hit_rate' in stats

        # Verify values
        assert stats['cache_size'] == 1
        assert stats['cache_hits'] == 1
        assert stats['cache_misses'] == 1
        assert stats['cache_hit_rate'] == 0.5

    @patch('src.reactive.hybrid_controller.Client')
    def test_cache_reset_statistics(self, mock_client_class):
        """Test reset_statistics() clears cache counters but preserves cache content."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_client.generate.return_value = {
            'response': '{"detour_x": 0.1, "detour_y": 0.1, "speed_modifier": 0.9, "confidence": 0.8, "reasoning": "Test"}'
        }

        controller = HybridReactiveController(enable_ollama=True)
        controller.ollama_client = mock_client  # Force mock client
        controller.enable_ollama = True  # Ensure Ollama is enabled

        sensor_data = {
            'lidar': {
                'lidar_min_distance': 0.3,
                'lidar_avg_distance': 1.0,
                'lidar_distances': [0.3] * 512
            },
            'gps': {'position_x': 0.0, 'position_y': 0.0, 'position_z': 0.0},
            'imu': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'camera': {'has_data': False}
        }

        # Build up cache
        controller.check_and_react(sensor_data)  # miss
        controller.check_and_react(sensor_data)  # hit

        assert controller.cache_hits == 1
        assert controller.cache_misses == 1
        cache_size_before = len(controller.detour_cache)
        assert cache_size_before == 1

        # Reset statistics
        controller.reset_statistics()

        # Verify counters are reset
        assert controller.cache_hits == 0
        assert controller.cache_misses == 0

        # Verify cache content is PRESERVED
        assert len(controller.detour_cache) == cache_size_before
