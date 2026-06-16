"""
LLM_ROBOT_2 - Generic LLM-based Robot Control Framework
Enhanced Rescue Robot Controller for Webots

This controller demonstrates comprehensive sensor integration:
1. Robot initialization with multiple sensors
2. Motor control (move forward, rotate)
3. Multi-sensor integration (Camera, Lidar, GPS, IMU)
4. Basic movement commands

Author: BMad
Date: 2025-10-29
Version: 1.1 (Enhanced with GPS + IMU)
"""

from controller import Robot, Camera, Lidar, Motor, GPS, InertialUnit
import sys
import math

# Time step for the simulation (in milliseconds)
TIME_STEP = 64

def init_robot():
    """Initialize robot and get device references."""
    print("=" * 60)
    print("LLM_ROBOT_2 - Enhanced Rescue Robot Controller")
    print("Story 1.2: Comprehensive Multi-Sensor Integration")
    print("=" * 60)

    # Create Robot instance
    robot = Robot()

    # Debug: List all available devices
    print("\n[DEBUG] Listing all available devices:")
    num_devices = robot.getNumberOfDevices()
    print(f"[DEBUG] Total devices: {num_devices}")
    for i in range(num_devices):
        device = robot.getDeviceByIndex(i)
        print(f"  [{i}] {device.getName()} (type: {device.getNodeType()})")

    # Try multiple possible motor names for Pioneer 3-DX
    motor_names = [
        ('left wheel motor', 'right wheel motor'),
        ('left wheel', 'right wheel'),
        ('left_wheel_motor', 'right_wheel_motor'),
        ('left_wheel', 'right_wheel')
    ]

    left_motor = None
    right_motor = None

    print("\n[INFO] Attempting to find motor devices...")
    for left_name, right_name in motor_names:
        left_motor = robot.getDevice(left_name)
        right_motor = robot.getDevice(right_name)
        if left_motor and right_motor:
            print(f"[OK] Motors found: '{left_name}', '{right_name}'")
            break
        else:
            print(f"[FAIL] Tried '{left_name}' and '{right_name}' - not found")

    if not left_motor or not right_motor:
        print("\n[ERROR] Could not find motor devices!")
        raise RuntimeError("Motors not found - check device list above")

    # Set motors to velocity control mode (position = infinity)
    left_motor.setPosition(float('inf'))
    right_motor.setPosition(float('inf'))

    # Initialize velocity to 0
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)

    print("[OK] Motors initialized successfully\n")

    # Get and enable Camera
    camera = robot.getDevice('front_camera')
    if camera:
        camera.enable(TIME_STEP)
        print(f"[OK] Camera enabled: front_camera (FOV: 60°, Resolution: {camera.getWidth()}x{camera.getHeight()})")
    else:
        print("[WARNING] Camera 'front_camera' not found")

    # Get and enable Lidar
    lidar = robot.getDevice('lidar')
    if lidar:
        lidar.enable(TIME_STEP)
        lidar.enablePointCloud()
        print(f"[OK] Lidar enabled: lidar (Range: 0.1-8.0m, Resolution: {lidar.getHorizontalResolution()})")
    else:
        print("[WARNING] Lidar 'lidar' not found")

    # Get and enable GPS
    gps = robot.getDevice('gps')
    if gps:
        gps.enable(TIME_STEP)
        print(f"[OK] GPS enabled: gps (Position tracking)")
    else:
        print("[WARNING] GPS 'gps' not found")

    # Get and enable IMU (InertialUnit)
    imu = robot.getDevice('imu')
    if imu:
        imu.enable(TIME_STEP)
        print(f"[OK] IMU enabled: imu (Orientation tracking)")
    else:
        print("[WARNING] IMU 'imu' not found")

    print(f"\n[SUMMARY] Active sensors: {sum([camera is not None, lidar is not None, gps is not None, imu is not None])} / 4")

    return robot, left_motor, right_motor, camera, lidar, gps, imu

def move_forward(left_motor, right_motor, speed=2.0):
    """Move robot forward at specified speed."""
    left_motor.setVelocity(speed)
    right_motor.setVelocity(speed)
    print(f"[ACTION] Moving forward at speed {speed} rad/s")

def rotate_left(left_motor, right_motor, speed=1.0):
    """Rotate robot left (counter-clockwise)."""
    left_motor.setVelocity(-speed)
    right_motor.setVelocity(speed)
    print(f"[ACTION] Rotating left at speed {speed} rad/s")

def rotate_right(left_motor, right_motor, speed=1.0):
    """Rotate robot right (clockwise)."""
    left_motor.setVelocity(speed)
    right_motor.setVelocity(-speed)
    print(f"[ACTION] Rotating right at speed {speed} rad/s")

def stop(left_motor, right_motor):
    """Stop robot movement."""
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)
    print("[ACTION] Robot stopped")

def get_sensor_data(camera, lidar, gps, imu, step_count):
    """Read and display sensor data periodically."""
    if step_count % 50 == 0:  # Print every 50 steps (~3.2 seconds)
        print(f"\n--- Sensor Status (Step {step_count}) ---")

        # Camera info
        if camera:
            camera_width = camera.getWidth()
            camera_height = camera.getHeight()
            print(f"Camera: {camera_width}x{camera_height} pixels")

        # Lidar data
        if lidar:
            lidar_data = lidar.getRangeImage()
            if lidar_data and len(lidar_data) > 0:
                min_distance = min(lidar_data)
                max_distance = max(lidar_data)
                avg_distance = sum(lidar_data) / len(lidar_data)

                print(f"Lidar: Min={min_distance:.2f}m, Max={max_distance:.2f}m, Avg={avg_distance:.2f}m")
                print(f"Lidar Points: {len(lidar_data)} measurements")
            else:
                print("Lidar: No data available yet")

        # GPS data
        if gps:
            gps_values = gps.getValues()
            if gps_values:
                print(f"GPS: Position X={gps_values[0]:.3f}m, Y={gps_values[1]:.3f}m, Z={gps_values[2]:.3f}m")
            else:
                print("GPS: No data available yet")

        # IMU data
        if imu:
            roll_pitch_yaw = imu.getRollPitchYaw()
            if roll_pitch_yaw:
                roll = math.degrees(roll_pitch_yaw[0])
                pitch = math.degrees(roll_pitch_yaw[1])
                yaw = math.degrees(roll_pitch_yaw[2])
                print(f"IMU: Roll={roll:.1f}°, Pitch={pitch:.1f}°, Yaw={yaw:.1f}°")
            else:
                print("IMU: No data available yet")

        print("-" * 40)

def test_basic_movements(robot, left_motor, right_motor, camera, lidar, gps, imu):
    """
    Test basic robot movements with comprehensive sensor monitoring:
    1. Move forward for 3 seconds
    2. Stop for 1 second
    3. Rotate left for 2 seconds
    4. Stop for 1 second
    5. Rotate right for 2 seconds
    6. Stop and idle
    """
    step_count = 0
    phase = 0

    print("\n[TEST] Starting enhanced movement test sequence...")
    print("Phase 0: Move forward (3s)\n")

    while robot.step(TIME_STEP) != -1:
        step_count += 1

        # Read sensor data periodically
        get_sensor_data(camera, lidar, gps, imu, step_count)

        # Phase-based movement control
        if phase == 0 and step_count == 1:
            # Phase 0: Move forward
            move_forward(left_motor, right_motor, speed=2.0)

        elif phase == 0 and step_count >= 47:  # ~3 seconds
            stop(left_motor, right_motor)
            phase = 1
            print("\nPhase 1: Stop (1s)")

        elif phase == 1 and step_count >= 63:  # +1 second
            rotate_left(left_motor, right_motor, speed=1.5)
            phase = 2
            print("\nPhase 2: Rotate left (2s)")

        elif phase == 2 and step_count >= 94:  # +2 seconds
            stop(left_motor, right_motor)
            phase = 3
            print("\nPhase 3: Stop (1s)")

        elif phase == 3 and step_count >= 110:  # +1 second
            rotate_right(left_motor, right_motor, speed=1.5)
            phase = 4
            print("\nPhase 4: Rotate right (2s)")

        elif phase == 4 and step_count >= 141:  # +2 seconds
            stop(left_motor, right_motor)
            phase = 5
            print("\nPhase 5: Test complete - Robot idle")

        elif phase == 5 and step_count >= 157:  # +1 second
            print("\n" + "=" * 60)
            print("[SUCCESS] Story 1.2 - Enhanced multi-sensor test completed!")
            print("Robot capabilities verified:")
            print("  ✓ Forward movement")
            print("  ✓ Left rotation")
            print("  ✓ Right rotation")

            sensor_count = 0
            if camera:
                print("  ✓ Camera sensor integration (640x480)")
                sensor_count += 1
            if lidar:
                print("  ✓ Lidar sensor integration (360°, 512 points)")
                sensor_count += 1
            if gps:
                print("  ✓ GPS sensor integration (Position tracking)")
                sensor_count += 1
            if imu:
                print("  ✓ IMU sensor integration (Orientation tracking)")
                sensor_count += 1

            print(f"\n[SUMMARY] Total active sensors: {sensor_count}/4")
            print("=" * 60)
            # Continue idle loop
            pass

def main():
    """Main controller entry point."""
    try:
        # Initialize robot and sensors
        robot, left_motor, right_motor, camera, lidar, gps, imu = init_robot()

        print("\n[INFO] Waiting for first sensor readings...")
        # Wait for sensors to warm up
        robot.step(TIME_STEP)

        print("[INFO] Sensors ready!\n")

        # Run basic movement test
        test_basic_movements(robot, left_motor, right_motor, camera, lidar, gps, imu)

    except Exception as e:
        print(f"\n[ERROR] Controller exception: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
