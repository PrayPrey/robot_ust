"""Debug OpenCV filter performance."""

import numpy as np
import time
import cv2

# Create test images
img_3ch = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
img_4ch = np.random.randint(0, 256, (480, 640, 4), dtype=np.uint8)

print("=== Testing cv2.blur performance ===")

# Test 3-channel image (direct)
start = time.perf_counter()
result_3ch = cv2.blur(img_3ch, (3, 3))
time_3ch = time.perf_counter() - start
print(f"3-channel direct: {time_3ch*1000:.2f}ms")

# Test 4-channel image (direct)
start = time.perf_counter()
result_4ch = cv2.blur(img_4ch, (3, 3))
time_4ch = time.perf_counter() - start
print(f"4-channel direct: {time_4ch*1000:.2f}ms")

# Test 4-channel with split/merge
start = time.perf_counter()
rgb = img_4ch[:, :, :3]
alpha = img_4ch[:, :, 3:4]
rgb_blurred = cv2.blur(rgb, (3, 3))
result_split = np.concatenate([rgb_blurred, alpha], axis=2)
time_split = time.perf_counter() - start
print(f"4-channel split/merge: {time_split*1000:.2f}ms")

print("\n=== Testing cv2.medianBlur performance ===")

# Test 3-channel median
start = time.perf_counter()
result_median_3ch = cv2.medianBlur(img_3ch, 3)
time_median_3ch = time.perf_counter() - start
print(f"3-channel direct: {time_median_3ch*1000:.2f}ms")

# Test 4-channel median (direct)
start = time.perf_counter()
try:
    result_median_4ch = cv2.medianBlur(img_4ch, 3)
    time_median_4ch = time.perf_counter() - start
    print(f"4-channel direct: {time_median_4ch*1000:.2f}ms")
except Exception as e:
    print(f"4-channel direct failed: {e}")

# Test 4-channel median with split/merge
start = time.perf_counter()
rgb = img_4ch[:, :, :3]
alpha = img_4ch[:, :, 3:4]
rgb_median = cv2.medianBlur(rgb, 3)
result_median_split = np.concatenate([rgb_median, alpha], axis=2)
time_median_split = time.perf_counter() - start
print(f"4-channel split/merge: {time_median_split*1000:.2f}ms")
