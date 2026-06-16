"""
Test Multi-Sensor Integration (Story 2.2)

Tests sensor data collection, noise filtering, and environment map loading.
"""

import pytest
import numpy as np
from pathlib import Path

from src.sensors import (
    MovingAverageFilter,
    KalmanFilter1D,
    LidarNoiseFilter,
    CameraNoiseFilter,
    EnvironmentMapLoader
)


class TestMovingAverageFilter:
    """Test moving average filter functionality."""

    def test_filter_initialization(self):
        """Test filter initializes correctly."""
        filter = MovingAverageFilter(window_size=5)
        assert filter.window_size == 5
        assert len(filter.buffer) == 0

    def test_filter_single_value(self):
        """Test filter with single value."""
        filter = MovingAverageFilter(window_size=3)
        result = filter.update(10.0)
        assert result == 10.0

    def test_filter_smoothing(self):
        """Test filter smooths noisy data."""
        filter = MovingAverageFilter(window_size=3)

        # Add noisy values
        values = [10.0, 10.5, 9.8, 10.2, 9.9]
        results = [filter.update(v) for v in values]

        # Last result should be average of last 3 values
        expected = sum(values[-3:]) / 3
        assert abs(results[-1] - expected) < 0.001

    def test_filter_reset(self):
        """Test filter reset."""
        filter = MovingAverageFilter(window_size=3)
        filter.update(10.0)
        filter.update(11.0)

        filter.reset()
        assert len(filter.buffer) == 0


class TestKalmanFilter:
    """Test Kalman filter functionality."""

    def test_filter_initialization(self):
        """Test filter initializes correctly."""
        filter = KalmanFilter1D(
            initial_estimate=0.0,
            initial_error=1.0,
            process_variance=1e-5,
            measurement_variance=0.1
        )
        assert filter.estimate == 0.0
        assert filter.error == 1.0

    def test_filter_convergence(self):
        """Test filter converges to true value."""
        filter = KalmanFilter1D(
            initial_estimate=0.0,
            process_variance=1e-5,
            measurement_variance=0.1
        )

        # Add measurements around 10.0 with noise
        np.random.seed(42)
        true_value = 10.0
        measurements = true_value + np.random.normal(0, 0.1, 50)

        estimates = [filter.update(m) for m in measurements]

        # Final estimate should be close to true value
        assert abs(estimates[-1] - true_value) < 0.5

    def test_filter_reset(self):
        """Test filter reset."""
        filter = KalmanFilter1D()
        filter.update(10.0)
        filter.update(11.0)

        filter.reset(initial_estimate=0.0)
        assert filter.estimate == 0.0


class TestLidarNoiseFilter:
    """Test Lidar-specific noise filtering."""

    def test_filter_initialization(self):
        """Test Lidar filter initializes correctly."""
        filter = LidarNoiseFilter(
            num_points=512,
            filter_type="moving_average",
            window_size=5
        )
        assert len(filter.filters) == 512

    def test_filter_lidar_data(self):
        """Test filtering complete Lidar scan."""
        filter = LidarNoiseFilter(
            num_points=512,
            filter_type="moving_average",
            window_size=3
        )

        # Create noisy Lidar data
        np.random.seed(42)
        clean_distances = np.full(512, 2.0)
        noisy_distances = (clean_distances + np.random.normal(0, 0.05, 512)).tolist()

        # Filter data
        filtered = filter.update(noisy_distances)

        assert len(filtered) == 512
        # Filtered data should be closer to clean values
        # (not strictly testable without multiple updates)

    def test_filter_validation(self):
        """Test filter validates input size."""
        filter = LidarNoiseFilter(num_points=512)

        # Wrong number of points should raise error
        with pytest.raises(ValueError, match="Expected 512 points"):
            filter.update([1.0, 2.0, 3.0])

    def test_kalman_filter_type(self):
        """Test Lidar filter with Kalman filter."""
        filter = LidarNoiseFilter(
            num_points=512,
            filter_type="kalman",
            process_variance=1e-5,
            measurement_variance=0.01
        )

        lidar_data = [2.0] * 512
        filtered = filter.update(lidar_data)

        assert len(filtered) == 512


class TestCameraNoiseFilter:
    """Test camera image noise filtering."""

    def test_mean_filter(self):
        """Test mean filter on image."""
        # Create simple test image
        image = np.array([
            [[100, 100, 100, 255], [150, 150, 150, 255], [200, 200, 200, 255]],
            [[110, 110, 110, 255], [160, 160, 160, 255], [210, 210, 210, 255]],
            [[120, 120, 120, 255], [170, 170, 170, 255], [220, 220, 220, 255]]
        ], dtype=np.uint8)

        filtered = CameraNoiseFilter.apply_mean_filter(image, kernel_size=3)

        assert filtered.shape == image.shape
        assert filtered.dtype == image.dtype

    def test_mean_filter_odd_kernel_only(self):
        """Test mean filter rejects even kernel sizes."""
        image = np.zeros((10, 10, 4), dtype=np.uint8)

        with pytest.raises(ValueError, match="Kernel size must be odd"):
            CameraNoiseFilter.apply_mean_filter(image, kernel_size=4)

    def test_median_filter(self):
        """Test median filter on image."""
        # Create image with salt-and-pepper noise
        image = np.full((5, 5, 4), 100, dtype=np.uint8)
        image[2, 2] = [255, 255, 255, 255]  # Salt noise

        filtered = CameraNoiseFilter.apply_median_filter(image, kernel_size=3)

        assert filtered.shape == image.shape
        # Center pixel should be filtered
        assert np.all(filtered[2, 2] < 200)


class TestEnvironmentMap:
    """Test environment map loading and querying."""

    @pytest.fixture
    def sample_map_path(self, tmp_path):
        """Create temporary sample environment map."""
        map_file = tmp_path / "test_env_map.json"
        EnvironmentMapLoader.create_sample_map(str(map_file))
        return map_file

    def test_load_environment_map(self, sample_map_path):
        """Test loading environment map from file."""
        env_map = EnvironmentMapLoader.load_from_file(str(sample_map_path))

        assert env_map.map_id == "rescue_environment_001"
        assert env_map.map_name == "Rescue Robot Test Environment"
        assert len(env_map.obstacles) == 3
        assert len(env_map.safe_zones) == 2
        assert len(env_map.danger_zones) == 2

    def test_map_dimensions_validation(self, sample_map_path):
        """Test environment map dimensions are validated."""
        env_map = EnvironmentMapLoader.load_from_file(str(sample_map_path))

        assert env_map.dimensions == (10.0, 10.0, 3.0)
        assert all(d > 0 for d in env_map.dimensions)

    def test_get_obstacles_near(self, sample_map_path):
        """Test finding nearby obstacles."""
        env_map = EnvironmentMapLoader.load_from_file(str(sample_map_path))

        # Position near "debris_1" at (2.0, 2.0)
        position = (2.5, 2.5)
        nearby = env_map.get_obstacles_near(position, radius=2.0)

        assert len(nearby) > 0
        # Should find debris_1
        assert any(obs.id == "debris_1" for obs in nearby)

    def test_is_in_safe_zone(self, sample_map_path):
        """Test safe zone detection."""
        env_map = EnvironmentMapLoader.load_from_file(str(sample_map_path))

        # Start zone is at (0.0, 0.0) with radius 1.5
        assert env_map.is_in_safe_zone((0.0, 0.0)) is True
        assert env_map.is_in_safe_zone((1.0, 0.0)) is True
        assert env_map.is_in_safe_zone((5.0, 5.0)) is False

    def test_is_in_danger_zone(self, sample_map_path):
        """Test danger zone detection."""
        env_map = EnvironmentMapLoader.load_from_file(str(sample_map_path))

        # Collapse risk at (-3.0, 3.0) with radius 1.5
        danger = env_map.is_in_danger_zone((-3.0, 3.0))
        assert danger is not None
        assert danger.id == "collapse_risk_1"
        assert danger.severity == "high"

        # Safe position
        assert env_map.is_in_danger_zone((0.0, 0.0)) is None

    def test_get_nearest_obstacle(self, sample_map_path):
        """Test finding nearest obstacle."""
        env_map = EnvironmentMapLoader.load_from_file(str(sample_map_path))

        position = (2.5, 2.5)
        result = env_map.get_nearest_obstacle(position)

        assert result is not None
        nearest_obstacle, distance = result
        assert nearest_obstacle is not None
        assert distance >= 0.0

    def test_load_nonexistent_file(self):
        """Test loading nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            EnvironmentMapLoader.load_from_file("nonexistent.json")


class TestProjectEnvironmentMap:
    """Test project's actual environment map."""

    def test_project_environment_map_exists(self):
        """Test project environment map file exists."""
        project_root = Path(__file__).parent.parent
        map_file = project_root / "data" / "environment_map.json"

        assert map_file.exists(), "Environment map JSON file should exist"

    def test_load_project_environment_map(self):
        """Test loading project environment map."""
        project_root = Path(__file__).parent.parent
        map_file = project_root / "data" / "environment_map.json"

        env_map = EnvironmentMapLoader.load_from_file(str(map_file))

        # Verify map structure
        assert env_map.map_id is not None
        assert env_map.map_name is not None
        assert len(env_map.obstacles) > 0
        assert isinstance(env_map.dimensions, tuple)
        assert len(env_map.dimensions) == 3

        # Verify at least some zones exist
        assert len(env_map.safe_zones) > 0 or len(env_map.danger_zones) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
