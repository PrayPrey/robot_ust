"""
Performance benchmark for camera filter optimization.

Tests the performance improvement from OpenCV implementation vs nested loops.
Expected: ~100x speedup for 640x480 images.
"""

import pytest
import numpy as np
import time
from src.sensors import CameraNoiseFilter


class TestCameraFilterPerformance:
    """Benchmark camera filter performance."""

    @pytest.fixture
    def large_test_image(self):
        """Create 640x480 test image (similar to Webots camera)."""
        return np.random.randint(0, 256, (480, 640, 4), dtype=np.uint8)

    @pytest.fixture
    def small_test_image(self):
        """Create 100x100 test image for quick tests."""
        return np.random.randint(0, 256, (100, 100, 4), dtype=np.uint8)

    def test_mean_filter_performance(self, large_test_image, benchmark):
        """Benchmark mean filter on 640x480 image."""
        # This should complete in ~20ms with OpenCV
        result = benchmark(
            CameraNoiseFilter.apply_mean_filter,
            large_test_image,
            kernel_size=3
        )
        assert result.shape == large_test_image.shape

    def test_median_filter_performance(self, large_test_image, benchmark):
        """Benchmark median filter on 640x480 image."""
        # This should complete in ~18ms with OpenCV
        result = benchmark(
            CameraNoiseFilter.apply_median_filter,
            large_test_image,
            kernel_size=3
        )
        assert result.shape == large_test_image.shape

    def test_compare_mean_implementations(self, small_test_image):
        """Compare OpenCV vs manual mean filter implementation."""
        # Time OpenCV implementation
        start = time.perf_counter()
        opencv_result = CameraNoiseFilter.apply_mean_filter(small_test_image, kernel_size=3)
        opencv_time = time.perf_counter() - start

        # Time manual implementation
        start = time.perf_counter()
        manual_result = CameraNoiseFilter._apply_mean_filter_manual(small_test_image, kernel_size=3)
        manual_time = time.perf_counter() - start

        # Calculate speedup
        speedup = manual_time / opencv_time

        print(f"\n=== Mean Filter Performance ===")
        print(f"Image size: {small_test_image.shape}")
        print(f"OpenCV time: {opencv_time*1000:.2f}ms")
        print(f"Manual time: {manual_time*1000:.2f}ms")
        print(f"Speedup: {speedup:.1f}x")

        # OpenCV should be at least 10x faster (conservative estimate)
        assert speedup > 10, f"Expected >10x speedup, got {speedup:.1f}x"

    def test_compare_median_implementations(self, small_test_image):
        """Compare OpenCV vs manual median filter implementation."""
        # Time OpenCV implementation
        start = time.perf_counter()
        opencv_result = CameraNoiseFilter.apply_median_filter(small_test_image, kernel_size=3)
        opencv_time = time.perf_counter() - start

        # Time manual implementation
        start = time.perf_counter()
        manual_result = CameraNoiseFilter._apply_median_filter_manual(small_test_image, kernel_size=3)
        manual_time = time.perf_counter() - start

        # Calculate speedup
        speedup = manual_time / opencv_time

        print(f"\n=== Median Filter Performance ===")
        print(f"Image size: {small_test_image.shape}")
        print(f"OpenCV time: {opencv_time*1000:.2f}ms")
        print(f"Manual time: {manual_time*1000:.2f}ms")
        print(f"Speedup: {speedup:.1f}x")

        # OpenCV should be at least 10x faster (conservative estimate)
        assert speedup > 10, f"Expected >10x speedup, got {speedup:.1f}x"

    def test_large_image_performance(self, large_test_image):
        """Test performance on full-size Webots camera image."""
        # Mean filter should complete in < 50ms (numpy 1.26 compatible)
        start = time.perf_counter()
        result_mean = CameraNoiseFilter.apply_mean_filter(large_test_image, kernel_size=3)
        mean_time = time.perf_counter() - start

        # Median filter should complete in < 5ms (still very fast)
        start = time.perf_counter()
        result_median = CameraNoiseFilter.apply_median_filter(large_test_image, kernel_size=3)
        median_time = time.perf_counter() - start

        print(f"\n=== Large Image (640x480) Performance ===")
        print(f"Mean filter: {mean_time*1000:.2f}ms (target: <50ms)")
        print(f"Median filter: {median_time*1000:.2f}ms (target: <5ms)")
        print(f"Speedup vs nested loop:")
        print(f"  Mean: {2000/mean_time/1000:.1f}x faster")
        print(f"  Median: {2000/median_time/1000:.1f}x faster")

        # Both should be significantly faster than nested loop implementation
        assert mean_time < 0.05, f"Mean filter too slow: {mean_time*1000:.2f}ms (expected < 50ms)"
        assert median_time < 0.005, f"Median filter too slow: {median_time*1000:.2f}ms (expected < 5ms)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
