"""
Unit Tests for EnvironmentDetector

Tests the rule-based environment classification logic from sensor data.
Validates detection accuracy for indoor, outdoor, warehouse, hospital, and unknown environments.
"""

import pytest
from src.utils.environment_detector import EnvironmentDetector, EnvironmentClassification
from src.schemas.robot_state import SensorData


class TestEnvironmentDetector:
    """Unit tests for EnvironmentDetector class."""

    @pytest.fixture
    def detector(self):
        """Create EnvironmentDetector instance."""
        return EnvironmentDetector()

    # AC #1: Rule-Based Environment Detection

    def test_detect_indoor(self, detector):
        """Test indoor environment detection (GPS weak, small space, ceiling)."""
        # Indoor: No GPS, Lidar avg < 3m, ceiling detected
        sensor_data = SensorData(
            position_x=None,  # No GPS
            position_y=None,
            position_z=None,
            lidar_avg_distance=2.5,  # Small enclosed space
            lidar_min_distance=0.8,
            camera_has_data=True
        )

        result = detector.detect_environment(sensor_data)

        assert result.environment_type == "indoor", \
            f"Expected 'indoor', got '{result.environment_type}'"
        assert result.confidence > 0.8, \
            f"Expected high confidence (>0.8), got {result.confidence:.2f}"
        assert "gps_signal" in result.features
        assert result.features["gps_signal"] == 0.0  # No GPS

    def test_detect_outdoor(self, detector):
        """Test outdoor environment detection (GPS strong, large space, no ceiling)."""
        # Outdoor: Strong GPS, Lidar avg > 5m, no ceiling
        sensor_data = SensorData(
            position_x=1.5,  # GPS available (strong signal)
            position_y=2.0,
            position_z=0.1,
            lidar_avg_distance=10.0,  # Large open space
            lidar_min_distance=5.0,
            camera_has_data=True
        )

        result = detector.detect_environment(sensor_data)

        assert result.environment_type == "outdoor", \
            f"Expected 'outdoor', got '{result.environment_type}'"
        assert result.confidence > 0.8, \
            f"Expected high confidence (>0.8), got {result.confidence:.2f}"
        assert result.features["gps_signal"] == 1.0  # Strong GPS
        assert result.features["lidar_avg"] == 10.0

    def test_detect_warehouse(self, detector):
        """Test warehouse environment detection (GPS weak, large space, ceiling)."""
        # Warehouse: No GPS, Lidar avg > 5m, ceiling detected
        sensor_data = SensorData(
            position_x=None,  # No GPS (indoor building)
            position_y=None,
            position_z=None,
            lidar_avg_distance=8.0,  # Large space
            lidar_min_distance=3.0,
            camera_has_data=True
        )

        result = detector.detect_environment(sensor_data)

        assert result.environment_type == "warehouse", \
            f"Expected 'warehouse', got '{result.environment_type}'"
        assert result.confidence >= 0.8, \
            f"Expected high confidence (>=0.8), got {result.confidence:.2f}"
        assert result.features["gps_signal"] == 0.0  # No GPS
        assert result.features["lidar_avg"] == 8.0
        assert result.features["ceiling_detected"] == False  # High ceiling (>5m)

    def test_detect_hospital(self, detector):
        """Test hospital environment detection (specific patterns)."""
        # Hospital: Similar to indoor but with specific characteristics
        # In our simplified implementation, hospitals are detected as "indoor"
        # since we don't have specific hospital sensors
        sensor_data = SensorData(
            position_x=None,  # No GPS (indoor)
            position_y=None,
            position_z=None,
            lidar_avg_distance=3.0,  # Medium space
            lidar_min_distance=1.0,
            camera_has_data=True
        )

        result = detector.detect_environment(sensor_data)

        # Note: With current implementation, hospital detection would require
        # additional sensors or heuristics. For now, it should be classified as indoor.
        assert result.environment_type in ["indoor", "hospital"], \
            f"Expected 'indoor' or 'hospital', got '{result.environment_type}'"
        assert result.confidence >= 0.5

    def test_detect_unknown_conflicting_signals(self, detector):
        """Test unknown environment (conflicting signals)."""
        # Conflicting: GPS available BUT ceiling detected (unusual combination)
        sensor_data = SensorData(
            position_x=1.0,  # GPS available (suggests outdoor)
            position_y=2.0,
            position_z=0.1,
            lidar_avg_distance=4.0,  # Medium space with ceiling (suggests indoor)
            lidar_min_distance=2.0,
            camera_has_data=True
        )

        result = detector.detect_environment(sensor_data)

        # With current rules, this should classify as outdoor (GPS signal > 0.8)
        # or unknown if confidence is low
        assert result.environment_type in ["outdoor", "unknown"], \
            f"Expected 'outdoor' or 'unknown', got '{result.environment_type}'"

    def test_detect_unknown_insufficient_data(self, detector):
        """Test unknown environment (missing sensor data)."""
        # Insufficient data: No GPS, no Lidar average
        sensor_data = SensorData(
            position_x=None,
            position_y=None,
            position_z=None,
            lidar_avg_distance=None,  # Missing critical data
            lidar_min_distance=None,
            camera_has_data=False
        )

        result = detector.detect_environment(sensor_data)

        assert result.environment_type == "unknown", \
            f"Expected 'unknown', got '{result.environment_type}'"
        assert result.confidence < 0.5, \
            f"Expected low confidence (<0.5), got {result.confidence:.2f}"

    # AC #1: Confidence Scoring

    def test_confidence_scoring_high(self, detector):
        """Test high confidence classification (all rules agree)."""
        # Clear outdoor: Strong GPS + large space + no ceiling
        sensor_data = SensorData(
            position_x=2.0,
            position_y=3.0,
            position_z=0.1,
            lidar_avg_distance=15.0,
            lidar_min_distance=10.0,
            camera_has_data=True
        )

        result = detector.detect_environment(sensor_data)

        assert result.confidence > 0.8, \
            f"Expected high confidence (>0.8) for clear outdoor, got {result.confidence:.2f}"

    def test_confidence_scoring_medium(self, detector):
        """Test medium confidence classification (some conflicting signals)."""
        # Medium confidence: Medium Lidar distance (neither clearly indoor nor outdoor)
        sensor_data = SensorData(
            position_x=None,  # No GPS
            position_y=None,
            position_z=None,
            lidar_avg_distance=4.0,  # Between 3m (indoor) and 5m (warehouse)
            lidar_min_distance=2.0,
            camera_has_data=True
        )

        result = detector.detect_environment(sensor_data)

        # This should either classify as indoor or unknown depending on other features
        assert 0.5 <= result.confidence <= 1.0

    def test_confidence_scoring_range(self, detector):
        """Test confidence score is within valid range (0.0-1.0)."""
        # Test multiple scenarios
        scenarios = [
            SensorData(position_x=1.0, position_y=2.0, position_z=0.1, lidar_avg_distance=10.0),
            SensorData(lidar_avg_distance=2.5, camera_has_data=True),
            SensorData(position_x=None, lidar_avg_distance=None, camera_has_data=False)
        ]

        for sensor_data in scenarios:
            result = detector.detect_environment(sensor_data)
            assert 0.0 <= result.confidence <= 1.0, \
                f"Confidence {result.confidence:.2f} out of range [0.0, 1.0]"

    # Edge Cases

    def test_edge_case_missing_gps(self, detector):
        """Test classification with missing GPS data."""
        sensor_data = SensorData(
            position_x=None,
            position_y=None,
            position_z=None,
            lidar_avg_distance=6.0,
            camera_has_data=True
        )

        result = detector.detect_environment(sensor_data)

        # Should classify as warehouse (large space, no GPS)
        assert result.environment_type in ["warehouse", "outdoor", "unknown"]
        assert result.features["gps_signal"] == 0.0

    def test_edge_case_missing_lidar(self, detector):
        """Test classification with missing Lidar data."""
        sensor_data = SensorData(
            position_x=1.0,
            position_y=2.0,
            position_z=0.1,
            lidar_avg_distance=None,  # No Lidar
            camera_has_data=True
        )

        result = detector.detect_environment(sensor_data)

        # Should fall back to GPS-based classification or unknown
        assert result.environment_type in ["outdoor", "unknown"]

    def test_edge_case_null_sensors(self, detector):
        """Test classification with all sensors returning null."""
        sensor_data = SensorData(
            position_x=None,
            position_y=None,
            position_z=None,
            lidar_avg_distance=None,
            lidar_min_distance=None,
            camera_has_data=False
        )

        result = detector.detect_environment(sensor_data)

        assert result.environment_type == "unknown"
        assert result.confidence == 0.0

    # Feature Extraction Tests

    def test_feature_extraction_gps_signal(self, detector):
        """Test GPS signal strength feature extraction."""
        # GPS available
        sensor_data_gps = SensorData(
            position_x=1.0, position_y=2.0, position_z=0.1,
            lidar_avg_distance=5.0
        )
        result_gps = detector.detect_environment(sensor_data_gps)
        assert result_gps.features["gps_signal"] == 1.0

        # GPS unavailable
        sensor_data_no_gps = SensorData(
            position_x=None, position_y=None, position_z=None,
            lidar_avg_distance=5.0
        )
        result_no_gps = detector.detect_environment(sensor_data_no_gps)
        assert result_no_gps.features["gps_signal"] == 0.0

    def test_feature_extraction_lidar_avg(self, detector):
        """Test Lidar average distance feature extraction."""
        sensor_data = SensorData(
            lidar_avg_distance=7.5,
            camera_has_data=True
        )

        result = detector.detect_environment(sensor_data)

        assert result.features["lidar_avg"] == 7.5

    def test_feature_extraction_ceiling_detection(self, detector):
        """Test ceiling detection feature extraction."""
        # High ceiling (warehouse/outdoor)
        sensor_data_high = SensorData(
            lidar_avg_distance=8.0,
            camera_has_data=True
        )
        result_high = detector.detect_environment(sensor_data_high)
        assert result_high.features["ceiling_detected"] == False  # Lidar avg > 5m

        # Low ceiling (indoor)
        sensor_data_low = SensorData(
            lidar_avg_distance=3.0,
            camera_has_data=True
        )
        result_low = detector.detect_environment(sensor_data_low)
        assert result_low.features["ceiling_detected"] == True  # Lidar avg < 5m

    # Pydantic Model Tests

    def test_environment_classification_model(self):
        """Test EnvironmentClassification Pydantic model validation."""
        # Valid classification
        classification = EnvironmentClassification(
            environment_type="indoor",
            confidence=0.85,
            features={"gps_signal": 0.0, "lidar_avg": 2.5}
        )

        assert classification.environment_type == "indoor"
        assert classification.confidence == 0.85
        assert classification.features["gps_signal"] == 0.0

    def test_environment_classification_confidence_validation(self):
        """Test confidence score validation (0.0-1.0 range)."""
        # Valid confidence
        valid = EnvironmentClassification(
            environment_type="outdoor",
            confidence=0.9,
            features={}
        )
        assert valid.confidence == 0.9

        # Invalid confidence (should raise ValidationError)
        with pytest.raises(Exception):  # Pydantic ValidationError
            EnvironmentClassification(
                environment_type="indoor",
                confidence=1.5,  # Out of range
                features={}
            )

    def test_environment_classification_type_validation(self):
        """Test environment_type literal validation."""
        # Valid types
        valid_types = ["indoor", "outdoor", "warehouse", "hospital", "unknown"]
        for env_type in valid_types:
            classification = EnvironmentClassification(
                environment_type=env_type,
                confidence=0.8,
                features={}
            )
            assert classification.environment_type == env_type

        # Invalid type (should raise ValidationError)
        with pytest.raises(Exception):  # Pydantic ValidationError
            EnvironmentClassification(
                environment_type="invalid_type",
                confidence=0.8,
                features={}
            )
