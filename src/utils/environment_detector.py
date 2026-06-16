"""
Environment Detector Module

Rule-based environment classification using sensor data patterns.
Classifies robot environment into indoor, outdoor, warehouse, hospital, or unknown.

Used by PlannerAgent to retrieve environment-specific constraints from RAG system.
"""

from typing import Dict, Any, Literal, Optional
from pydantic import BaseModel, Field
import statistics
from loguru import logger

from src.schemas.robot_state import SensorData


class EnvironmentClassification(BaseModel):
    """
    Environment classification result with confidence scoring.

    Attributes:
        environment_type: Detected environment category
        confidence: Classification confidence score (0.0-1.0)
            - High confidence (>0.8): All rules agree
            - Medium confidence (0.5-0.8): Some conflicting signals
            - Low confidence (<0.5): Return "unknown"
        features: Extracted sensor features used for classification
    """

    environment_type: Literal["indoor", "outdoor", "warehouse", "hospital", "unknown"] = Field(
        description="Detected environment category"
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Classification confidence score (0.0-1.0)"
    )

    features: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted sensor features (GPS signal, Lidar avg, ceiling, lighting)"
    )


class EnvironmentDetector:
    """
    Rule-based environment classifier using multi-sensor data.

    Classification Logic:
    - GPS signal > 0.8 + no ceiling → OUTDOOR
    - GPS signal < 0.3 + ceiling detected → INDOOR or WAREHOUSE (based on space size)
    - Lidar avg > 5m + GPS weak → WAREHOUSE
    - Lidar avg < 3m + GPS weak → INDOOR
    - Specific patterns (low noise tolerance) → HOSPITAL
    - Conflicting signals → UNKNOWN (fallback to all constraints)

    Performance: <10ms latency (rule-based, no ML inference)
    """

    def __init__(self):
        """Initialize environment detector."""
        # Story 3.7: Initialize cached state variables
        self._current_environment = None
        self._last_detection_time = None
        self._cached_features = None
        self._last_classification = None
        logger.info("EnvironmentDetector initialized")

    def reset(self):
        """
        Story 3.7: Reset detector state for new mission.

        Clears all cached state so that environment detection
        starts fresh for each mission. This ensures accurate
        environment classification when sensors change between missions.
        """
        self._current_environment = None
        self._last_detection_time = None
        self._cached_features = None
        self._last_classification = None
        logger.debug("EnvironmentDetector state reset for new mission")

    def detect_environment(self, sensor_data: SensorData) -> EnvironmentClassification:
        """
        Detect environment from sensor data patterns.

        Args:
            sensor_data: Multi-sensor data (GPS, Lidar, Camera, IMU)

        Returns:
            EnvironmentClassification with detected type, confidence, and features

        Examples:
            >>> detector = EnvironmentDetector()
            >>> sensor_data = SensorData(
            ...     position_x=1.5, position_y=2.0, position_z=0.1,  # GPS available (outdoor)
            ...     lidar_avg_distance=10.0,  # Large open space
            ...     camera_has_data=True
            ... )
            >>> result = detector.detect_environment(sensor_data)
            >>> assert result.environment_type == "outdoor"
            >>> assert result.confidence > 0.8
        """
        try:
            # Extract sensor features
            features = self._extract_features(sensor_data)

            # Apply classification rules with weighted scoring
            classifications = []

            # Rule 1: GPS signal strength (strong GPS = outdoor)
            gps_score = self._classify_by_gps(features)
            if gps_score:
                classifications.append(gps_score)

            # Rule 2: Lidar space analysis (large space = warehouse, small = indoor)
            lidar_score = self._classify_by_lidar(features)
            if lidar_score:
                classifications.append(lidar_score)

            # Rule 3: Combined GPS + Lidar rules
            combined_score = self._classify_combined(features)
            if combined_score:
                classifications.append(combined_score)

            # Aggregate scores and determine final classification
            if not classifications:
                # Insufficient data for classification
                logger.warning("Insufficient sensor data for environment detection")
                return EnvironmentClassification(
                    environment_type="unknown",
                    confidence=0.0,
                    features=features
                )

            # Majority voting with confidence weighting
            final_classification = self._aggregate_classifications(classifications, features)

            logger.info(
                f"Environment detected: {final_classification.environment_type} "
                f"(confidence: {final_classification.confidence:.2f})"
            )

            return final_classification

        except Exception as e:
            logger.error(f"Error during environment detection: {e}")
            return EnvironmentClassification(
                environment_type="unknown",
                confidence=0.0,
                features={"error": str(e)}
            )

    def _extract_features(self, sensor_data: SensorData) -> Dict[str, Any]:
        """
        Extract relevant features from sensor data.

        Args:
            sensor_data: Raw sensor readings

        Returns:
            Dictionary of extracted features:
                - gps_signal: GPS availability (0.0=unavailable, 1.0=strong)
                - lidar_avg: Average Lidar distance in meters
                - ceiling_detected: Whether ceiling is detected (Lidar upward < 5m)
                - lighting_level: Camera brightness estimation (0.0=dark, 1.0=bright)
        """
        features = {}

        # GPS signal strength (estimate based on position availability)
        if all([
            sensor_data.position_x is not None,
            sensor_data.position_y is not None,
            sensor_data.position_z is not None
        ]):
            # GPS available - assume strong signal
            features["gps_signal"] = 1.0
        else:
            # GPS unavailable - weak/no signal
            features["gps_signal"] = 0.0

        # Lidar average distance
        if sensor_data.lidar_avg_distance is not None:
            features["lidar_avg"] = sensor_data.lidar_avg_distance
        else:
            features["lidar_avg"] = None

        # Ceiling detection (simplified: check if average distance is low)
        # In real implementation, would check upward-facing Lidar points
        if sensor_data.lidar_avg_distance is not None:
            features["ceiling_detected"] = sensor_data.lidar_avg_distance < 5.0
        else:
            features["ceiling_detected"] = None

        # Camera lighting level (simplified: assume has_data implies adequate lighting)
        features["lighting_level"] = 1.0 if sensor_data.camera_has_data else 0.5

        return features

    def _classify_by_gps(self, features: Dict[str, Any]) -> Optional[tuple[str, float]]:
        """
        Classify environment based on GPS signal strength.

        Args:
            features: Extracted sensor features

        Returns:
            Tuple of (environment_type, confidence) or None if inconclusive
        """
        gps_signal = features.get("gps_signal", 0.0)

        if gps_signal > 0.8:
            # Strong GPS = likely outdoor
            return ("outdoor", 0.85)
        elif gps_signal < 0.3:
            # Weak GPS = likely indoor/warehouse/hospital
            # Cannot determine which without Lidar
            return None
        else:
            # Medium GPS signal is inconclusive
            return None

    def _classify_by_lidar(self, features: Dict[str, Any]) -> Optional[tuple[str, float]]:
        """
        Classify environment based on Lidar distance patterns.

        Args:
            features: Extracted sensor features

        Returns:
            Tuple of (environment_type, confidence) or None if inconclusive
        """
        lidar_avg = features.get("lidar_avg")

        if lidar_avg is None:
            return None

        if lidar_avg > 5.0:
            # Large open space = warehouse or outdoor
            # Cannot determine which without GPS
            return None
        elif lidar_avg < 3.0:
            # Small enclosed space = indoor or hospital
            return ("indoor", 0.75)
        else:
            # Medium space is inconclusive
            return None

    def _classify_combined(self, features: Dict[str, Any]) -> Optional[tuple[str, float]]:
        """
        Classify environment using combined GPS + Lidar rules.

        This is where the primary classification logic lives.

        Args:
            features: Extracted sensor features

        Returns:
            Tuple of (environment_type, confidence) or None if inconclusive
        """
        gps_signal = features.get("gps_signal", 0.0)
        lidar_avg = features.get("lidar_avg")
        ceiling_detected = features.get("ceiling_detected")

        if lidar_avg is None:
            return None

        # Rule: Strong GPS + no ceiling → OUTDOOR
        if gps_signal > 0.8 and not ceiling_detected:
            return ("outdoor", 0.9)

        # Rule: Weak GPS + ceiling detected
        if gps_signal < 0.3 and ceiling_detected:
            if lidar_avg > 5.0:
                # Large indoor space = WAREHOUSE
                return ("warehouse", 0.85)
            else:
                # Small indoor space = INDOOR
                return ("indoor", 0.9)

        # Rule: Weak GPS + large open space (no ceiling constraint)
        if gps_signal < 0.3 and lidar_avg > 5.0:
            return ("warehouse", 0.8)

        # Rule: Weak GPS + small space
        if gps_signal < 0.3 and lidar_avg < 3.0:
            return ("indoor", 0.85)

        # No clear match
        return None

    def _aggregate_classifications(
        self,
        classifications: list[tuple[str, float]],
        features: Dict[str, Any]
    ) -> EnvironmentClassification:
        """
        Aggregate multiple classification results using weighted voting.

        Args:
            classifications: List of (environment_type, confidence) tuples
            features: Extracted sensor features

        Returns:
            Final EnvironmentClassification with aggregated result
        """
        if not classifications:
            return EnvironmentClassification(
                environment_type="unknown",
                confidence=0.0,
                features=features
            )

        # Weighted voting: sum confidence scores for each environment type
        votes: Dict[str, list[float]] = {}
        for env_type, confidence in classifications:
            if env_type not in votes:
                votes[env_type] = []
            votes[env_type].append(confidence)

        # Calculate average confidence for each environment type
        avg_confidences = {
            env_type: statistics.mean(confidences)
            for env_type, confidences in votes.items()
        }

        # Select environment with highest average confidence
        best_env = max(avg_confidences, key=avg_confidences.get)
        best_confidence = avg_confidences[best_env]

        # Check if confidence is sufficient
        if best_confidence < 0.5:
            # Low confidence - return unknown
            return EnvironmentClassification(
                environment_type="unknown",
                confidence=best_confidence,
                features=features
            )

        return EnvironmentClassification(
            environment_type=best_env,
            confidence=best_confidence,
            features=features
        )
