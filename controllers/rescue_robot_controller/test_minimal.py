"""
Minimal test controller to check if Robot() creation works.
"""
import sys
print("START: Minimal test controller", flush=True)

print("1. Importing Robot...", flush=True)
from controller import Robot
print("2. Robot imported successfully", flush=True)

print("3. Creating Robot instance...", flush=True)
robot = Robot()
print("4. Robot created successfully!", flush=True)

print("5. Getting time step...", flush=True)
TIME_STEP = int(robot.getBasicTimeStep())
print(f"6. Time step: {TIME_STEP}ms", flush=True)

print("7. Starting main loop...", flush=True)
step_count = 0
while robot.step(TIME_STEP) != -1:
    step_count += 1
    if step_count % 100 == 0:
        print(f"Step {step_count}", flush=True)

    if step_count > 1000:
        print("Test successful! Robot() working correctly.", flush=True)
        break

print("END: Test completed", flush=True)
