"""
Actor Agent

CrewAI agent that executes action plans on Webots robot.
Converts RobotAction objects into Webots API commands.
"""

from typing import List, Optional, Dict, Any
from crewai import Agent, Task
from langchain_openai import ChatOpenAI
from loguru import logger
import time
import math

from ..schemas import RobotAction, ActionType, RobotState, RobotStatus, MissionCommand, MissionStatus
from ..sensors import SensorManager, SensorManagerConfig, DEFAULT_SENSOR_CONFIG
from ..sensors.exceptions import SafetyViolationException
from ..config.robot_config import Pioneer3DXConfig, ROBOT_CONFIG
from ..safety import SafetyValidator, SafetyConstraints
from ..reactive import HybridReactiveController, ReactiveDecision, InterventionType

# Supervisor-based object manipulation callbacks (set by controller)
# These are set via set_object_manipulation_callbacks() method
_attach_object_callback = None
_detach_object_callback = None
_update_object_position_callback = None
_is_object_held_callback = None
_is_mission_success_callback = None
SUPERVISOR_OBJECT_MANIPULATION = False


def attach_object_to_gripper():
    """Wrapper for attach callback."""
    if _attach_object_callback:
        return _attach_object_callback()
    return False


def detach_object():
    """Wrapper for detach callback."""
    if _detach_object_callback:
        return _detach_object_callback()
    return False


def update_held_object_position(robot_x, robot_y, robot_yaw_rad, shoulder_angle_rad):
    """Wrapper for position update callback."""
    if _update_object_position_callback:
        return _update_object_position_callback(robot_x, robot_y, robot_yaw_rad, shoulder_angle_rad)
    return False


def is_object_held():
    """Wrapper for is_held check callback."""
    if _is_object_held_callback:
        return _is_object_held_callback()
    return False


def is_mission_success():
    """Check if mission success condition is met."""
    if _is_mission_success_callback:
        return _is_mission_success_callback()
    return False


# Pickup object position callback for safety relaxation
_get_pickup_position_callback = None


def get_pickup_position():
    """Get pickup object position (x, y) for safety check relaxation."""
    if _get_pickup_position_callback:
        return _get_pickup_position_callback()
    return None


def set_pickup_position_callback(fn):
    """Set the pickup position callback."""
    global _get_pickup_position_callback
    _get_pickup_position_callback = fn


def set_object_manipulation_callbacks(attach_fn, detach_fn, update_fn, is_held_fn, is_success_fn=None):
    """
    Set callbacks for Supervisor-based object manipulation.
    Called by controller after initialization.

    Args:
        attach_fn: Function to attach object to gripper
        detach_fn: Function to detach object from gripper
        update_fn: Function to update held object position (robot_x, robot_y, robot_yaw_rad, shoulder_rad)
        is_held_fn: Function to check if object is held
        is_success_fn: Function to check if mission success condition is met
    """
    global _attach_object_callback, _detach_object_callback
    global _update_object_position_callback, _is_object_held_callback
    global _is_mission_success_callback, SUPERVISOR_OBJECT_MANIPULATION

    _attach_object_callback = attach_fn
    _detach_object_callback = detach_fn
    _update_object_position_callback = update_fn
    _is_object_held_callback = is_held_fn
    _is_mission_success_callback = is_success_fn
    SUPERVISOR_OBJECT_MANIPULATION = True

    logger.info("✓ Supervisor object manipulation callbacks registered")


class ActorAgent:
    """
    Actor Agent for executing action plans on Webots robot.

    Responsibilities:
    1. Execute RobotAction sequences
    2. Monitor execution status
    3. Handle execution errors
    4. Update mission state

    Example:
        >>> from controller import Robot
        >>> robot = Robot()
        >>> actor = ActorAgent(robot, api_key="sk-...")
        >>> mission = MissionCommand(command="Move forward", language="en")
        >>> mission.action_plan = [
        ...     RobotAction(action=ActionType.MOVE, x=2.0, y=0.0, speed=1.0)
        ... ]
        >>> result = actor.execute_mission(mission)
    """

    def __init__(
        self,
        robot,  # Webots Robot instance
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        verbose: bool = True,
        time_step: int = 64,
        sensor_config: Optional[SensorManagerConfig] = None,
        step_callback: Optional[callable] = None  # External step control
    ):
        """
        Initialize Actor Agent with integrated SensorManager.

        Args:
            robot: Webots Robot instance
            api_key: OpenAI API key
            model: LLM model to use
            temperature: LLM temperature
            verbose: Enable verbose logging
            time_step: Webots simulation time step in ms
            sensor_config: SensorManagerConfig for sensor filtering (uses default if None)
            step_callback: Optional callback for step control (for Web mode coordination)
        """
        self.robot = robot
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.verbose = verbose
        self.time_step = time_step
        self.step_callback = step_callback  # Use this instead of direct robot.step()

        # Robot configuration
        self.robot_config = ROBOT_CONFIG

        # Initialize LLM (for error recovery)
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=api_key
        )

        # Create CrewAI Agent
        self.agent = Agent(
            role="Robot Action Executor",
            goal="Execute robot actions safely and accurately on Webots simulator",
            backstory=(
                "You are an expert robot controller. "
                "You execute movement, rotation, and scanning actions precisely. "
                "You monitor sensor data and handle errors during execution."
            ),
            llm=self.llm,
            verbose=verbose,
            allow_delegation=False
        )

        # Initialize Webots devices (motors + SensorManager)
        self._init_devices(sensor_config)

        # Initialize HybridReactiveController (Story 3.1)
        self.reactive_controller = HybridReactiveController(
            ollama_host="http://localhost:11434",
            model_name="tinyllama",
            enable_ollama=True,  # ENABLED with OpenAI provider (gpt-4o-mini, ~1-2s response)
            emergency_threshold=0.3,  # meters (30cm - emergency stop, aligned with safety validator)
            detour_threshold=0.5,  # meters (50cm - AI detour decision)
            llm_provider="openai",  # Use OpenAI instead of Ollama
            api_key=api_key  # Pass API key for OpenAI
        )
        self.reactive_log: List[Dict[str, Any]] = []  # Store reactive interventions
        self._current_status = RobotStatus.IDLE  # Track actual robot status

        logger.info(
            f"ActorAgent initialized with model={model}, time_step={time_step}ms, "
            f"sensor_filtering={'enabled' if (sensor_config or DEFAULT_SENSOR_CONFIG).enable_filtering else 'disabled'}, "
            f"reactive_control={'enabled' if self.reactive_controller.enable_ollama else 'rules-only'}, "
            f"step_mode={'callback' if step_callback else 'direct'}"
        )

    def _do_step(self) -> int:
        """
        Execute one simulation step.

        Uses step_callback if provided (Web mode), otherwise calls robot.step() directly.

        Returns:
            0 if successful, -1 if simulation stopped
        """
        if self.step_callback:
            # step_callback handles object position update with Supervisor API (no GPS delay)
            result = self.step_callback(self.time_step)
        else:
            result = self.robot.step(self.time_step)

        # Object position update is done in step_callback using Supervisor API
        # This avoids GPS sensor delay for smoother object following

        # Check for early mission success (robot at EXIT with object)
        if is_mission_success():
            logger.info("🎉 Mission success detected - robot at EXIT with object!")
            return -2  # Special code for mission success

        return result

    def _init_devices(self, sensor_config: Optional[SensorManagerConfig] = None) -> None:
        """
        Initialize Webots robot devices.

        Args:
            sensor_config: Optional sensor configuration for SensorManager
        """
        try:
            # Initialize motors
            self.left_motor = self.robot.getDevice('left wheel')
            self.right_motor = self.robot.getDevice('right wheel')

            if not self.left_motor or not self.right_motor:
                raise ValueError("Motors not found")

            self.left_motor.setPosition(float('inf'))
            self.right_motor.setPosition(float('inf'))
            self.left_motor.setVelocity(0.0)
            self.right_motor.setVelocity(0.0)

            logger.debug("Wheel motors initialized")

            # ========== ARM MOTORS INITIALIZATION ==========
            # Initialize arm motors (optional - may not exist in all worlds)
            try:
                self.arm_shoulder = self.robot.getDevice('arm_shoulder')
                self.arm_elbow = self.robot.getDevice('arm_elbow')
                self.gripper_left = self.robot.getDevice('gripper_left')
                self.gripper_right = self.robot.getDevice('gripper_right')

                # Initialize arm position sensors
                self.arm_shoulder_sensor = self.robot.getDevice('arm_shoulder_sensor')
                self.arm_elbow_sensor = self.robot.getDevice('arm_elbow_sensor')

                if self.arm_shoulder and self.arm_elbow:
                    # Enable position sensors
                    if self.arm_shoulder_sensor:
                        self.arm_shoulder_sensor.enable(self.time_step)
                    if self.arm_elbow_sensor:
                        self.arm_elbow_sensor.enable(self.time_step)

                    # Set initial arm position (home position - arm up)
                    self.arm_shoulder.setPosition(0.0)
                    self.arm_elbow.setPosition(0.0)

                    # Set gripper to open position
                    if self.gripper_left and self.gripper_right:
                        self.gripper_left.setPosition(0.3)  # Open
                        self.gripper_right.setPosition(-0.3)  # Open (mirror)

                    self.arm_available = True
                    logger.info("Arm motors initialized: shoulder, elbow, gripper")
                else:
                    self.arm_available = False
                    logger.warning("Arm motors not found - arm control disabled")

            except Exception as e:
                self.arm_available = False
                logger.warning(f"Arm initialization skipped: {e}")

            # Initialize SensorManager with noise filtering
            if sensor_config is None:
                # Use default config with time_step matching ActorAgent
                sensor_config = SensorManagerConfig(time_step=self.time_step)

            self.sensor_manager = SensorManager(
                robot=self.robot,
                config=sensor_config
            )

            # Keep references to raw sensors for backward compatibility (if needed)
            # But prefer using sensor_manager for filtered data
            self.gps = self.sensor_manager.gps
            self.imu = self.sensor_manager.imu
            self.lidar = self.sensor_manager.lidar
            self.camera = self.sensor_manager.camera

            # Initialize SafetyValidator for action validation
            self.safety_validator = SafetyValidator(
                sensor_manager=self.sensor_manager,
                constraints=SafetyConstraints()  # Uses default safety constraints
            )

            logger.info(
                f"Webots devices initialized: motors + SensorManager + SafetyValidator "
                f"(filtering={'enabled' if sensor_config.enable_filtering else 'disabled'})"
            )

        except Exception as e:
            logger.error(f"Failed to initialize devices: {e}")
            raise

    def execute_mission(
        self,
        mission: MissionCommand
    ) -> bool:
        """
        Execute complete mission with action plan.

        Args:
            mission: Mission command with action_plan

        Returns:
            True if mission completed successfully, False otherwise
        """
        if not mission.action_plan or len(mission.action_plan) == 0:
            logger.error("Mission has no action plan")
            mission.mark_failed("No action plan provided")
            return False

        logger.info(f"Executing mission: {mission.command}")
        mission.start_execution()

        # Reset detour history for new mission (keep history within mission, reset between missions)
        self.reactive_controller.detour_history = []

        try:
            for i, action in enumerate(mission.action_plan):
                mission.current_action_index = i

                logger.info(f"Executing action {i+1}/{len(mission.action_plan)}: {action.action}")

                success = self.execute_action(action)

                if not success:
                    logger.error(f"Action {i+1} failed")
                    mission.mark_failed(f"Action {i+1} ({action.action}) failed")
                    return False

                # Step simulation
                if self._do_step() == -1:
                    logger.error("Simulation stopped")
                    mission.mark_failed("Simulation stopped unexpectedly")
                    return False

            # Mission completed
            mission.mark_completed(True, f"All {len(mission.action_plan)} actions executed successfully")
            logger.info("Mission completed successfully")
            return True

        except Exception as e:
            logger.error(f"Mission execution failed: {e}")
            mission.mark_failed(str(e))
            return False

    def execute_action(
        self,
        action: RobotAction
    ) -> bool:
        """
        Execute single robot action with safety validation.

        Performs safety validation before executing the action.
        If validation fails, the action is skipped and a warning is logged.

        Args:
            action: RobotAction to execute

        Returns:
            True if action executed successfully, False if validation failed or execution error
        """
        try:
            # Check if near pickup object - relax safety for approach
            near_pickup = False
            pickup_pos = get_pickup_position()
            if pickup_pos:
                current_pos = self.get_current_position()
                if current_pos:
                    dx = pickup_pos[0] - current_pos[0]
                    dy = pickup_pos[1] - current_pos[1]
                    dist_to_pickup = math.sqrt(dx**2 + dy**2)
                    if dist_to_pickup < 1.0:  # Within 1m of pickup object
                        near_pickup = True
                        logger.info(f"🎯 Near pickup object ({dist_to_pickup:.2f}m) - relaxing safety checks")

            # Safety validation (unless safety_check is disabled or near pickup)
            if action.safety_check and not near_pickup:
                is_safe, message = self.safety_validator.validate_action(action)

                if not is_safe:
                    logger.warning(
                        f"Action rejected by safety validator: {action.action.value} "
                        f"- Reason: {message}"
                    )
                    return False

                logger.debug(f"Safety validation passed: {message}")

            # Execute action based on type
            if action.action == ActionType.MOVE:
                return self._execute_move(action)

            elif action.action == ActionType.ROTATE:
                return self._execute_rotate(action)

            elif action.action == ActionType.SCAN:
                return self._execute_scan(action)

            elif action.action == ActionType.WAIT:
                return self._execute_wait(action)

            elif action.action == ActionType.STOP:
                return self._execute_stop(action)

            # ========== ARM MANIPULATION ACTIONS ==========
            elif action.action == ActionType.ARM_MOVE:
                return self._execute_arm_move(action)

            elif action.action == ActionType.GRIP:
                return self._execute_grip(action)

            elif action.action == ActionType.RELEASE:
                return self._execute_release(action)

            else:
                logger.error(f"Unknown action type: {action.action}")
                return False

        except SafetyViolationException as e:
            logger.error(
                f"Safety violation detected: {e.violation_type} - {e}"
            )
            return False

        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return False

    def _execute_move(self, action: RobotAction) -> bool:
        """
        Execute MOVE action with support for both absolute and relative coordinates.

        Args:
            action: MOVE action with x, y, speed, and relative flag

        Returns:
            True if successful
        """
        if action.x is None or action.y is None:
            logger.error("MOVE action missing coordinates")
            return False

        # Set status to MOVING
        self._current_status = RobotStatus.MOVING

        # Get current position
        current_pos = self.get_current_position()
        if not current_pos:
            logger.error("Cannot get current position")
            return False

        # Initialize backward movement flag
        is_backward = False

        # Handle relative vs absolute coordinates
        if action.relative:
            # Relative mode: x/y are relative to current position and orientation
            current_yaw = self.get_current_yaw()
            if current_yaw is None:
                logger.error("Cannot get current yaw for relative movement")
                return False

            # Convert relative coordinates to absolute
            # x = forward/backward (along current heading)
            # y = left/right (perpendicular to current heading)
            #
            # IMPORTANT: Webots uses Math convention (NOT IMU convention)
            # Math convention: 0° = East (+X), 90° = North (+Y), 180° = West (-X), -90° = South (-Y)
            #
            # Forward (action.x) along heading: cos(yaw) for X, sin(yaw) for Y
            # Left (action.y) perpendicular: -sin(yaw) for X, cos(yaw) for Y
            target_x = current_pos[0] + action.x * math.cos(current_yaw) - action.y * math.sin(current_yaw)
            target_y = current_pos[1] + action.x * math.sin(current_yaw) + action.y * math.cos(current_yaw)

            logger.info(f"Relative move: ({action.x}, {action.y}) from current heading {math.degrees(current_yaw):.1f}°")
            logger.info(f"Converted to absolute: ({target_x:.2f}, {target_y:.2f})")

            # Check if this is backward movement BEFORE coordinate conversion
            is_backward = (action.x is not None and action.x < 0)

            if is_backward:
                # Backward movement - skip safety validation (emergency escape)
                logger.info("Backward movement: skipping safety validation for emergency escape")
            elif action.safety_check:
                # IMPORTANT: Create a new action with absolute coordinates for safety validation
                # This ensures SafetyValidator checks the actual target position, not relative offsets
                action_for_validation = RobotAction(
                    action=ActionType.MOVE,
                    x=target_x,
                    y=target_y,
                    speed=action.speed,
                    relative=False,  # Now it's absolute
                    safety_check=action.safety_check,
                    reason=action.reason
                )

                # Validate the converted absolute coordinates
                is_safe, message = self.safety_validator.validate_action(action_for_validation)
                if not is_safe:
                    logger.warning(
                        f"Action rejected by safety validator (after coordinate conversion): move "
                        f"- Reason: {message}"
                    )
                    return False
                logger.debug(f"Safety validation passed for converted coordinates: {message}")
        else:
            # Absolute mode: x/y are world coordinates
            target_x = action.x
            target_y = action.y

        # Store original target (for detour recovery)
        original_target_x = target_x
        original_target_y = target_y

        # Store starting position for logging
        is_relative_move = action.relative
        starting_pos_x = current_pos[0]
        starting_pos_y = current_pos[1]

        # Log movement info (target_x, target_y are absolute target coordinates)
        if is_relative_move:
            logger.debug(
                f"Relative move: start=({starting_pos_x:.2f}, {starting_pos_y:.2f}), "
                f"target=({target_x:.2f}, {target_y:.2f})"
            )
        else:
            logger.debug(
                f"Absolute move: start=({starting_pos_x:.2f}, {starting_pos_y:.2f}), "
                f"target=({target_x:.2f}, {target_y:.2f})"
            )

        # Track if detour occurred (for returning control to Planner)
        detour_occurred = False
        # Track if returning from detour (to enable heading correction for relative moves)
        returning_from_detour = False
        # Count detours to progressively expand tolerance (avoid infinite loop near obstacles)
        detour_count = 0

        # === INFINITE LOOP PREVENTION ===
        # Maximum allowed detours before giving up (avoid endless obstacle loop)
        MAX_DETOUR_COUNT = 3
        # Minimum position change between detours to consider "progress" (meters)
        MIN_POSITION_CHANGE = 0.3
        # Track position at last detour for progress detection
        last_detour_position = None

        # Determine if this is backward movement (for reactive controller)
        # For relative movements, this was already checked above
        # For absolute movements, check if target is behind current position
        if not action.relative:
            # Absolute movement: check if target is behind robot's current heading
            # BUG FIX: Use get_current_yaw() instead of current_pos[2] (which is Z coordinate, not yaw!)
            current_yaw = self.get_current_yaw()
            if current_yaw is not None:
                dx_to_target = target_x - current_pos[0]
                dy_to_target = target_y - current_pos[1]
                # Project target onto robot's heading vector
                # Math convention (Webots): 0°=East(+X), forward direction = (cos(yaw), sin(yaw))
                forward_component = dx_to_target * math.cos(current_yaw) + dy_to_target * math.sin(current_yaw)
                is_backward = (forward_component < 0)
        # else: is_backward already determined in relative block above

        # Calculate distance and angle to target
        dx = target_x - current_pos[0]
        dy = target_y - current_pos[1]
        distance = math.sqrt(dx**2 + dy**2)
        target_angle_math = math.atan2(dy, dx)  # Math convention: 0° = East (+X), 90° = North (+Y)

        logger.info(f"Moving to ({target_x:.2f}, {target_y:.2f}), distance={distance:.2f}m")

        # IMPORTANT: For relative movement, we should NOT rotate to face the target
        # because the target was calculated based on the current heading.
        # Only rotate for absolute coordinate movement.
        if not action.relative:
            # First, rotate to face target (only for absolute coordinates)
            current_yaw = self.get_current_yaw()
            if current_yaw is not None:
                # CRITICAL FIX: Webots IMU uses Math convention directly
                # Math convention: 0° = East (+X), 90° = North (+Y)
                # Webots IMU: Same as Math convention (NOT North-based!)
                # NO conversion needed - use Math angle directly
                target_angle = target_angle_math

                angle_diff = target_angle - current_yaw
                # Normalize to [-pi, pi]
                angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi

                logger.debug(
                    f"Angle calculation: Target={math.degrees(target_angle):.1f}°, "
                    f"Current={math.degrees(current_yaw):.1f}°, Diff={math.degrees(angle_diff):.1f}°"
                )

                if abs(angle_diff) > 0.1:  # 5.7 degrees threshold
                    rotate_action = RobotAction(
                        action=ActionType.ROTATE,
                        angle=math.degrees(angle_diff),
                        speed=action.speed if action.speed else 1.0
                    )
                    logger.info(f"Rotating to face target: {math.degrees(angle_diff):.1f}°")
                    if not self._execute_rotate(rotate_action):
                        return False
        else:
            logger.info("Relative movement: skipping rotation, moving in current heading direction")

        # Then, move forward/backward with feedback control
        speed = action.speed if action.speed else 1.0

        # Convert linear speed to wheel angular velocity using robot configuration
        wheel_speed = self.robot_config.speed_to_wheel_velocity(speed)

        # Set motor velocity based on direction (forward vs backward)
        if is_backward:
            # Backward movement: negative velocity to reverse
            self.left_motor.setVelocity(-wheel_speed)
            self.right_motor.setVelocity(-wheel_speed)
            logger.info(f"🔙 Reversing: wheel_velocity={-wheel_speed:.2f} rad/s")
        else:
            # Forward movement: positive velocity
            self.left_motor.setVelocity(wheel_speed)
            self.right_motor.setVelocity(wheel_speed)

        # Move with feedback loop - check position until target reached
        distance_threshold = 0.05  # Stop when within 5cm of target
        max_duration = distance / speed * 2.0  # Max 2x expected time (safety)
        max_steps = int((max_duration * 1000) / self.time_step)

        for step in range(max_steps):
            step_result = self._do_step()
            if step_result == -1:
                return False
            elif step_result == -2:
                # Mission success - robot reached EXIT with object
                logger.info("🎉 Mission complete! Stopping movement.")
                self.left_motor.setVelocity(0.0)
                self.right_motor.setVelocity(0.0)
                return True

            # Reactive control check every cycle (32ms) - Story 3.1
            sensor_data = self.get_reactive_sensor_data()
            lidar_min = sensor_data.get('lidar', {}).get('lidar_min_distance', float('inf'))

            # === CALCULATE DISTANCE TO ORIGINAL TARGET (every step for bypass checks) ===
            gps = sensor_data.get('gps', {})
            imu = sensor_data.get('imu', {})
            curr_x = gps.get('position_x', 0.0)
            curr_y = gps.get('position_y', 0.0)
            curr_yaw = imu.get('yaw', 0.0)
            # Use ORIGINAL target for near-target bypass (not detour waypoint)
            dist_to_target = math.sqrt((original_target_x - curr_x)**2 + (original_target_y - curr_y)**2)

            # === DETAILED DEBUG LOGGING (every 10 steps) ===
            if step % 10 == 0:
                logger.info(
                    f"📊 [Step {step}] pos=({curr_x:.2f}, {curr_y:.2f}) yaw={curr_yaw:.1f}° | "
                    f"target=({target_x:.2f}, {target_y:.2f}) dist_to_orig={dist_to_target:.2f}m | "
                    f"lidar_min={lidar_min:.2f}m"
                )

            # BACKWARD ESCAPE: Check if we've reversed far enough from obstacle
            # Stop when forward obstacle is at safe distance (0.6m+)
            if is_backward:
                if lidar_min >= 0.6:  # Safe distance reached
                    self.left_motor.setVelocity(0.0)
                    self.right_motor.setVelocity(0.0)
                    logger.info(f"✅ Backward escape complete: obstacle now at {lidar_min:.2f}m (safe distance reached)")
                    break
                else:
                    # Still too close, continue reversing
                    logger.debug(f"🔙 Continuing backward escape: obstacle at {lidar_min:.2f}m (target: 0.6m)")

            # Pre-emptive stop for AI detour decision
            # Stop robot when obstacle detected in MODERATE zone (0.1m-0.5m)
            # Gives LLM time to generate detour plan safely
            # SKIP this check during backward movement OR when near target (pickup approach)
            PREEMPTIVE_NEAR_TARGET_THRESHOLD = 2.0  # meters - skip pre-emptive stop when near target
            if not is_backward and 0.1 <= lidar_min < 0.5 and self.reactive_controller.enable_ollama:
                if dist_to_target >= PREEMPTIVE_NEAR_TARGET_THRESHOLD:
                    self.left_motor.setVelocity(0.0)
                    self.right_motor.setVelocity(0.0)
                    logger.info(f"⏸ Pre-emptive stop: obstacle at {lidar_min:.2f}m, waiting for AI decision...")
                else:
                    logger.debug(f"⏩ Skipping pre-emptive stop: near target ({dist_to_target:.2f}m < {PREEMPTIVE_NEAR_TARGET_THRESHOLD}m)")

            # Build target_info for smart detour decisions (Option B: LLM with target + history)
            # Use sensor_data GPS for current position (updated every cycle, not initial position)
            # Note: get_reactive_sensor_data() uses "or 0.0" so values are always present
            gps_data = sensor_data.get('gps', {})
            target_info = {
                'target_x': original_target_x,
                'target_y': original_target_y,
                'current_x': gps_data.get('position_x', 0.0),
                'current_y': gps_data.get('position_y', 0.0),
                'current_yaw': sensor_data.get('imu', {}).get('yaw', 0.0)  # degrees
            }

            # Pass backward movement flag and target_info to reactive controller
            # During backward movement, forward obstacle checks should be skipped
            reactive_decision = self.reactive_controller.check_and_react(
                sensor_data, is_backward=is_backward, target_info=target_info
            )

            # Handle reactive interventions
            if reactive_decision.intervention_type == InterventionType.CRITICAL:
                # === NEAR TARGET CHECK FOR CRITICAL ===
                # Bypass CRITICAL intervention ONLY if robot is near its MOVE target
                # (not just near pickup object - that was causing issues when going to EXIT)
                NEAR_TARGET_CRITICAL_THRESHOLD = 2.0  # meters

                # Check if MOVE target is near pickup object (i.e., we're approaching to grip)
                target_is_near_pickup = False
                pickup_pos = get_pickup_position()
                if pickup_pos:
                    dist_target_to_pickup = math.sqrt((target_x - pickup_pos[0])**2 + (target_y - pickup_pos[1])**2)
                    dist_robot_to_pickup = math.sqrt((curr_x - pickup_pos[0])**2 + (curr_y - pickup_pos[1])**2)
                    # Target must be near pickup AND robot must be near pickup
                    if dist_target_to_pickup < 1.0 and dist_robot_to_pickup < 1.5:
                        target_is_near_pickup = True
                        logger.info(f"🎯 Approaching pickup object (target={dist_target_to_pickup:.2f}m, robot={dist_robot_to_pickup:.2f}m)")

                if dist_to_target < NEAR_TARGET_CRITICAL_THRESHOLD or target_is_near_pickup:
                    lidar_min = reactive_decision.metadata.get('lidar_min', 0.0)
                    logger.info(
                        f"🎯 CRITICAL bypass: Near target ({dist_to_target:.2f}m < {NEAR_TARGET_CRITICAL_THRESHOLD}m) - "
                        f"Continuing slow approach (lidar={lidar_min:.2f}m)"
                    )
                    # Continue at very slow speed for final approach
                    slow_speed = wheel_speed * 0.3
                    self.left_motor.setVelocity(slow_speed)
                    self.right_motor.setVelocity(slow_speed)
                    continue  # Skip emergency stop, keep approaching

                # Emergency stop - halt immediately (only if not near target)
                self.left_motor.setVelocity(0.0)
                self.right_motor.setVelocity(0.0)

                # Log intervention
                intervention = {
                    "timestamp": reactive_decision.timestamp,
                    "type": reactive_decision.intervention_type.value,
                    "reason": reactive_decision.metadata.get("reason", "Emergency stop"),
                    "action_taken": {"type": "emergency_stop", "params": {}},
                    "sensor_state": {
                        "lidar_min": reactive_decision.metadata.get("lidar_min", 0.0),
                        "position": list(current_pos) if current_pos else [0.0, 0.0, 0.0]
                    }
                }
                self.reactive_log.append(intervention)

                logger.warning(
                    f"CRITICAL intervention triggered - emergency stop "
                    f"(lidar_min={reactive_decision.metadata.get('lidar_min', 0.0):.2f}m)"
                )
                return False  # Action failed - Verifier will trigger replanning

            elif reactive_decision.intervention_type == InterventionType.MODERATE:
                # === NEAR TARGET CHECK ===
                # Skip detour logic ONLY if robot is near its MOVE target
                NEAR_TARGET_THRESHOLD = 2.0  # meters

                # Check if MOVE target is near pickup object (i.e., we're approaching to grip)
                target_near_pickup_moderate = False
                pickup_pos_mod = get_pickup_position()
                if pickup_pos_mod:
                    dist_target_to_pickup_mod = math.sqrt((target_x - pickup_pos_mod[0])**2 + (target_y - pickup_pos_mod[1])**2)
                    dist_robot_to_pickup_mod = math.sqrt((curr_x - pickup_pos_mod[0])**2 + (curr_y - pickup_pos_mod[1])**2)
                    # Target must be near pickup AND robot must be near pickup
                    if dist_target_to_pickup_mod < 1.0 and dist_robot_to_pickup_mod < 1.5:
                        target_near_pickup_moderate = True

                if dist_to_target < NEAR_TARGET_THRESHOLD or target_near_pickup_moderate:
                    logger.info(
                        f"🎯 Near target ({dist_to_target:.2f}m < {NEAR_TARGET_THRESHOLD}m) - "
                        f"Bypassing detour logic, continuing approach"
                    )
                    # Continue movement at reduced speed for safety
                    slow_speed = wheel_speed * 0.5
                    self.left_motor.setVelocity(slow_speed)
                    self.right_motor.setVelocity(slow_speed)
                    continue  # Skip detour, keep moving toward target

                # AI-powered detour - adjust target and reduce speed
                detour_plan = reactive_decision.metadata.get("detour_plan", {})
                speed_modifier = detour_plan.get('speed_modifier', 0.5)  # Default 50% speed
                detour_x = detour_plan.get('detour_x', 0.0)
                detour_y = detour_plan.get('detour_y', 0.0)

                # Apply detour adjustment to target position (if significant deviation)
                if abs(detour_x) > 0.1 or abs(detour_y) > 0.1:
                    # Mark that detour occurred (will return control to Planner after clearing obstacle)
                    detour_occurred = True
                    detour_count += 1  # Track detour count for progressive tolerance

                    # === INFINITE LOOP CHECK ===
                    # Check 1: Maximum detour count exceeded
                    if detour_count > MAX_DETOUR_COUNT:
                        logger.error(
                            f"❌ MISSION FAILED: Maximum detour count ({MAX_DETOUR_COUNT}) exceeded! "
                            f"Target ({original_target_x:.2f}, {original_target_y:.2f}) appears unreachable."
                        )
                        self.left_motor.setVelocity(0.0)
                        self.right_motor.setVelocity(0.0)
                        return False  # Give up - Verifier will trigger replanning

                    # Check 2: No progress between detours (stuck in loop)
                    if last_detour_position is not None:
                        position_change = math.sqrt(
                            (current_pos[0] - last_detour_position[0])**2 +
                            (current_pos[1] - last_detour_position[1])**2
                        )
                        if position_change < MIN_POSITION_CHANGE:
                            logger.error(
                                f"❌ MISSION FAILED: No progress between detours! "
                                f"Position change: {position_change:.2f}m (min: {MIN_POSITION_CHANGE}m). "
                                f"Robot appears stuck in obstacle loop."
                            )
                            self.left_motor.setVelocity(0.0)
                            self.right_motor.setVelocity(0.0)
                            return False  # Give up - Verifier will trigger replanning

                    # Update last detour position for next check
                    last_detour_position = (current_pos[0], current_pos[1])
                    logger.info(f"🔄 Detour #{detour_count}: Position ({current_pos[0]:.2f}, {current_pos[1]:.2f})")

                    # Store original target for Planner replanning
                    # This allows Planner to know where we were originally trying to go
                    self._original_target_x = original_target_x
                    self._original_target_y = original_target_y

                    # Calculate detour target (temporary waypoint to avoid obstacle)
                    # CRITICAL FIX: Convert robot-frame detour to world coordinates
                    # LLM returns detour in robot frame: detour_x=forward, detour_y=left(+)/right(-)
                    # Must transform using current heading (Webots yaw = Math convention)
                    # BUG FIX: sensor_data yaw is in DEGREES, must convert to radians!
                    current_yaw_for_detour = math.radians(sensor_data.get('imu', {}).get('yaw', 0.0))
                    # Math convention (Webots): 0°=East(+X), 90°=North(+Y)
                    # Transform:
                    #   world_x = robot_forward * cos(yaw) - robot_left * sin(yaw)
                    #   world_y = robot_forward * sin(yaw) + robot_left * cos(yaw)
                    detour_target_x = current_pos[0] + detour_x * math.cos(current_yaw_for_detour) - detour_y * math.sin(current_yaw_for_detour)
                    detour_target_y = current_pos[1] + detour_x * math.sin(current_yaw_for_detour) + detour_y * math.cos(current_yaw_for_detour)

                    # BUG FIX: DON'T modify original action - use temporary variables for detour
                    # This preserves the original action_plan for Verifier verification
                    # (Previously action.x/y were modified, corrupting the action_plan)
                    temp_target_x = detour_target_x
                    temp_target_y = detour_target_y

                    # Recalculate distance and direction with new target
                    dx = temp_target_x - current_pos[0]
                    dy = temp_target_y - current_pos[1]
                    distance = math.sqrt(dx**2 + dy**2)
                    target_direction_math = math.atan2(dy, dx)  # Math convention: 0°=East(+X)

                    logger.info(
                        f"MODERATE intervention: Detouring to avoid obstacle "
                        f"(robot-frame: forward={detour_x:.2f}m, left={detour_y:.2f}m, heading={math.degrees(current_yaw_for_detour):.1f}°) "
                        f"→ world target=({temp_target_x:.2f}, {temp_target_y:.2f})"
                    )

                    # CRITICAL: Rotate to new target direction before moving
                    # BUG FIX: Convert Math convention to IMU convention for angle comparison
                    # Webots IMU uses Math convention directly
                    # Math: 0°=East(+X), 90°=North(+Y)
                    # Webots IMU: Same as Math (NO conversion needed)
                    target_direction = target_direction_math
                    current_yaw_rad = current_yaw_for_detour  # Already in radians from above
                    angle_diff = target_direction - current_yaw_rad

                    # Normalize angle to [-pi, pi]
                    angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi

                    # Rotate to new direction if needed (threshold: 5 degrees)
                    if abs(angle_diff) > 0.087:  # ~5 degrees
                        logger.info(f"🔄 Detour rotation: turning {math.degrees(angle_diff):.1f}° to new target")

                        # Perform rotation
                        # angle_diff > 0 → target > current → CW needed → negative speed
                        # angle_diff < 0 → target < current → CCW needed → positive speed
                        rotation_speed = -0.3 if angle_diff > 0 else 0.3  # rad/s
                        left_velocity, right_velocity = self.robot_config.angular_speed_to_wheel_velocities(rotation_speed)

                        self.left_motor.setVelocity(left_velocity)
                        self.right_motor.setVelocity(right_velocity)

                        # Rotate until target angle reached
                        start_time = time.time()
                        while time.time() - start_time < abs(angle_diff) / abs(rotation_speed) * 1.2:
                            self.step_callback(self.time_step)
                            current_yaw = self.get_current_yaw()  # Returns radian (Math convention)
                            if current_yaw is None:
                                continue
                            current_diff = target_direction - current_yaw

                            # Normalize
                            current_diff = (current_diff + math.pi) % (2 * math.pi) - math.pi

                            if abs(current_diff) < 0.05:  # Within ~3 degrees
                                break

                        # Stop rotation
                        self.left_motor.setVelocity(0.0)
                        self.right_motor.setVelocity(0.0)
                        for _ in range(3):
                            self.step_callback(self.time_step)

                        logger.info("✓ Detour rotation complete, resuming movement")

                    # Recalculate wheel speed with new distance and speed modifier
                    speed = speed * speed_modifier
                    wheel_speed = self.robot_config.speed_to_wheel_velocity(speed)

                # Log intervention
                intervention = {
                    "timestamp": reactive_decision.timestamp,
                    "type": reactive_decision.intervention_type.value,
                    "reason": f"Obstacle detected - detour applied (confidence={detour_plan.get('confidence', 0.0):.2f})",
                    "action_taken": {
                        "type": "detour",
                        "speed_modifier": speed_modifier,
                        "detour_x": detour_x,
                        "detour_y": detour_y
                    },
                    "sensor_state": {
                        "lidar_min": reactive_decision.metadata.get("lidar_min", 0.0),
                        "position": list(current_pos) if current_pos else [0.0, 0.0, 0.0]
                    }
                }
                self.reactive_log.append(intervention)

                # Apply speed modifier to motor velocities
                adjusted_wheel_speed = wheel_speed * speed_modifier
                self.left_motor.setVelocity(adjusted_wheel_speed)
                self.right_motor.setVelocity(adjusted_wheel_speed)

                logger.info(
                    f"MODERATE intervention: Speed reduced to {speed_modifier:.0%} "
                    f"(lidar_min={reactive_decision.metadata.get('lidar_min', 0.0):.2f}m)"
                )

            elif reactive_decision.intervention_type == InterventionType.POST_DETOUR:
                # Post-detour stabilization - LLM continues control
                stabilization_plan = reactive_decision.metadata.get("stabilization_plan", {})
                speed_modifier = stabilization_plan.get('speed_modifier', 0.7)  # Default 70% speed
                steps_remaining = reactive_decision.metadata.get('steps_remaining', 0)

                # Mark that we're still in detour mode (for multi-agent handoff)
                detour_occurred = True

                # Log intervention
                intervention = {
                    "timestamp": reactive_decision.timestamp,
                    "type": reactive_decision.intervention_type.value,
                    "reason": f"Post-detour stabilization ({steps_remaining} steps remaining)",
                    "action_taken": {
                        "type": "stabilize",
                        "speed_modifier": speed_modifier,
                        "steps_remaining": steps_remaining
                    },
                    "sensor_state": {
                        "lidar_min": reactive_decision.metadata.get("lidar_min", 0.0),
                        "position": list(current_pos) if current_pos else [0.0, 0.0, 0.0]
                    }
                }
                self.reactive_log.append(intervention)

                # Apply speed modifier to motor velocities
                adjusted_wheel_speed = wheel_speed * speed_modifier
                self.left_motor.setVelocity(adjusted_wheel_speed)
                self.right_motor.setVelocity(adjusted_wheel_speed)

                logger.info(
                    f"🔧 POST_DETOUR stabilization: Speed at {speed_modifier:.0%}, "
                    f"{steps_remaining} steps remaining "
                    f"(lidar_min={reactive_decision.metadata.get('lidar_min', 0.0):.2f}m)"
                )

            # CRITICAL: Check if detour+stabilization was completed (POST_DETOUR → NONE transition)
            # Must check AFTER all intervention blocks to catch transition immediately
            if detour_occurred and reactive_decision.intervention_type == InterventionType.NONE:
                # Detour completed! Check distance to target using EUCLIDEAN distance
                current_pos = self.get_current_position()
                if current_pos:
                    # Calculate Euclidean distance to target (works for both relative and absolute moves)
                    dx = original_target_x - current_pos[0]
                    dy = original_target_y - current_pos[1]
                    remaining_distance = math.sqrt(dx**2 + dy**2)

                    # Fixed tolerance: 0.1m regardless of detour count
                    detour_tolerance = 0.1

                    logger.info(
                        f"✅ Detour completed - Checking target distance: "
                        f"Current: ({current_pos[0]:.2f}, {current_pos[1]:.2f}), "
                        f"Target: ({original_target_x:.2f}, {original_target_y:.2f}), "
                        f"Distance: {remaining_distance:.2f}m, Tolerance: {detour_tolerance}m (fixed)"
                    )

                    # SUCCESS: If close enough to target after detour
                    if remaining_distance <= detour_tolerance:
                        logger.info(
                            f"🎉 Target reached after detour! Distance: {remaining_distance:.2f}m "
                            f"(<= {detour_tolerance}m tolerance)"
                        )
                        returning_from_detour = False  # Reset flag
                        break  # Exit loop - mission success!

                    # Not close enough yet - continue to original target
                    logger.info(f"🔄 Need to move {remaining_distance:.2f}m more to reach target")

                    # Continue to original target - rotate to face it and resume movement
                    # Stop motors temporarily
                    self.left_motor.setVelocity(0.0)
                    self.right_motor.setVelocity(0.0)
                    for _ in range(3):
                        self._do_step()

                    # Rotate to face original target
                    current_yaw = self.get_current_yaw()
                    if current_yaw is not None:
                        target_angle_math = math.atan2(dy, dx)
                        # Webots IMU uses Math convention - no conversion needed
                        target_angle = target_angle_math
                        heading_error = target_angle - current_yaw
                        heading_error = (heading_error + math.pi) % (2 * math.pi) - math.pi
                        heading_error_deg = math.degrees(heading_error)

                        if abs(heading_error_deg) > 5.0:
                            logger.info(f"🔄 Rotating {heading_error_deg:.1f}° to face original target")
                            rotate_action = RobotAction(
                                action=ActionType.ROTATE,
                                angle=heading_error_deg,
                                speed=action.speed if action.speed else 1.0
                            )
                            self._execute_rotate(rotate_action)

                    # Resume forward movement to original target
                    logger.info(f"🚀 Resuming movement to original target ({original_target_x:.2f}, {original_target_y:.2f})")
                    self.left_motor.setVelocity(wheel_speed)
                    self.right_motor.setVelocity(wheel_speed)

                    # Reset detour flag so we can handle new obstacles
                    detour_occurred = False
                    # Enable heading correction for relative moves (since we're returning to absolute target)
                    returning_from_detour = True
                    continue  # Continue the movement loop

            # Check if we've reached the target using EUCLIDEAN distance
            # Works for both relative and absolute moves (target_x, target_y are always absolute)
            current_pos = self.get_current_position()
            if current_pos:
                dx = target_x - current_pos[0]
                dy = target_y - current_pos[1]
                remaining_distance = math.sqrt(dx**2 + dy**2)

                if remaining_distance < distance_threshold:
                    logger.info(f"Target reached (within {distance_threshold}m)")
                    returning_from_detour = False  # Reset flag
                    break

                # HEADING CORRECTION: Check and correct heading every 10 steps
                # Enabled for: absolute coords OR returning from detour (to reach original target)
                # This prevents accumulated drift during long-distance movement
                # Skip heading correction during reactive interventions (MODERATE/POST_DETOUR)
                if ((not action.relative or returning_from_detour) and step % 10 == 0 and remaining_distance > 0.2 and
                    reactive_decision.intervention_type == InterventionType.NONE):
                    current_yaw = self.get_current_yaw()
                    if current_yaw is not None:
                        # Calculate desired heading to target
                        target_angle_math = math.atan2(dy, dx)
                        # Webots IMU uses Math convention - no conversion needed
                        target_angle = target_angle_math

                        heading_error = target_angle - current_yaw
                        # Normalize to [-pi, pi]
                        heading_error = (heading_error + math.pi) % (2 * math.pi) - math.pi

                        # DEBUG: Log heading correction calculation
                        logger.info(
                            f"🔧 Heading check: pos=({current_pos[0]:.2f}, {current_pos[1]:.2f}), "
                            f"target=({target_x:.2f}, {target_y:.2f}), dx={dx:.2f}, dy={dy:.2f}, "
                            f"target_angle={math.degrees(target_angle):.1f}°, "
                            f"current_yaw={math.degrees(current_yaw):.1f}°, error={math.degrees(heading_error):.1f}°"
                        )

                        # Detect overshoot: if heading error > 90 degrees, we've passed the target
                        if abs(heading_error) > math.pi / 2:  # 90 degrees
                            logger.info(
                                f"🎯 Overshoot detected! Heading error={math.degrees(heading_error):.1f}° > 90°"
                            )
                            logger.info(f"🎯 Stopping at current position (close enough to target)")
                            break  # Stop here, we've effectively reached the target

                        # Correct if error > 5 degrees (0.087 rad) but < 90 degrees
                        if abs(heading_error) > 0.087:
                            logger.info(
                                f"🔧 Heading correction needed: error={math.degrees(heading_error):.1f}°"
                            )

                            # Stop motors temporarily
                            self.left_motor.setVelocity(0.0)
                            self.right_motor.setVelocity(0.0)
                            for _ in range(2):
                                self._do_step()

                            # Perform small correction rotation
                            rotate_correction = RobotAction(
                                action=ActionType.ROTATE,
                                angle=math.degrees(heading_error),
                                speed=action.speed if action.speed else 1.0
                            )
                            self._execute_rotate(rotate_correction)

                            # Resume forward movement
                            self.left_motor.setVelocity(wheel_speed)
                            self.right_motor.setVelocity(wheel_speed)
                            logger.debug("Heading corrected, resuming movement")

                # Track previous distance to detect if moving away from target
                # (Removed broken overshooting logic that caused false positives)

        # Stop
        self.left_motor.setVelocity(0.0)
        self.right_motor.setVelocity(0.0)

        # Final position check
        # Use target_x, target_y (absolute coordinates) NOT action.x, action.y (might be relative)
        final_pos = self.get_current_position()
        if final_pos:
            dx = target_x - final_pos[0]
            dy = target_y - final_pos[1]
            final_distance = math.sqrt(dx**2 + dy**2)
            logger.info(f"Move completed - final distance from target: {final_distance:.3f}m")

        # Set status to IDLE after move completion
        self._current_status = RobotStatus.IDLE

        return True

    def _execute_rotate(self, action: RobotAction) -> bool:
        """
        Execute ROTATE action with feedback control.

        Args:
            action: ROTATE action with angle, speed

        Returns:
            True if successful
        """
        if action.angle is None:
            logger.error("ROTATE action missing angle")
            return False

        logger.info(f"Rotating {action.angle}°")

        # Get initial orientation
        initial_yaw = self.get_current_yaw()
        if initial_yaw is None:
            logger.error("Cannot get current yaw")
            return False

        # Calculate target yaw
        target_yaw = initial_yaw + math.radians(action.angle)
        # Normalize to [-pi, pi]
        target_yaw = (target_yaw + math.pi) % (2 * math.pi) - math.pi

        # Convert degrees to radians
        angle_rad = math.radians(action.angle)

        # Calculate angular speed (rad/s) - action.speed represents angular velocity
        # Default to 0.3 rad/s (~17 deg/s) for precise rotation (reduced from 1.0)
        angular_speed = (action.speed if action.speed else 1.0) * 0.3  # rad/s, scaled down for precision

        # Determine rotation direction based on angle
        # Math convention (Webots): angle increase = CCW (counter-clockwise)
        # angular_speed_to_wheel_velocities: positive angular_speed = CW rotation
        # So: positive angle (CCW needed) → negative angular_speed → CCW
        #     negative angle (CW needed) → positive angular_speed → CW
        if angle_rad > 0:
            # CCW turn (counter-clockwise) - negate angular speed
            angular_speed = -angular_speed

        # Convert angular speed to wheel velocities using robot configuration
        left_velocity, right_velocity = self.robot_config.angular_speed_to_wheel_velocities(angular_speed)

        self.left_motor.setVelocity(left_velocity)
        self.right_motor.setVelocity(right_velocity)

        # Rotate with feedback loop - check orientation until target reached
        angle_threshold = math.radians(2.0)  # Stop when within 2 degrees
        # Calculate max_duration based on ACTUAL angular speed (not assumed 45°/sec)
        # angular_speed is in rad/s, angle_rad is the angle to rotate
        # Safety factor increased from 2.0x to 4.0x to ensure we have enough time
        actual_angular_speed = abs(angular_speed)  # rad/s
        if actual_angular_speed > 0:
            max_duration = abs(angle_rad) / actual_angular_speed * 4.0  # 4x safety margin
        else:
            max_duration = 10.0  # Fallback: 10 seconds
        max_steps = int((max_duration * 1000) / self.time_step)

        logger.info(f"🎯 Rotation target: {math.degrees(target_yaw):.1f}° (from initial: {math.degrees(initial_yaw):.1f}°)")
        logger.info(f"🎯 Angle to rotate: {action.angle}°, Max steps: {max_steps}")
        logger.info(f"🎯 Left motor velocity: {left_velocity:.2f}, Right motor velocity: {right_velocity:.2f}")

        reached_target = False
        for step in range(max_steps):
            if self._do_step() == -1:
                return False

            # Safety check: abort rotation if EXTREMELY close obstacle detected
            # Note: Use 0.15m threshold (same as reactive controller CRITICAL level)
            sensor_data = self.sensor_manager.get_sensor_data()
            if sensor_data.lidar_min_distance is not None and sensor_data.lidar_min_distance < 0.15:
                logger.error(
                    f"ROTATE aborted: Critical obstacle at {sensor_data.lidar_min_distance:.2f}m. "
                    f"Cannot rotate safely."
                )
                self.left_motor.setVelocity(0.0)
                self.right_motor.setVelocity(0.0)
                return False

            # Check if we've reached the target orientation
            current_yaw = self.get_current_yaw()
            if current_yaw is not None:
                angle_diff = target_yaw - current_yaw
                # Normalize to [-pi, pi]
                angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi

                # Log every 5 steps for debugging (changed from 10)
                if step % 5 == 0 or step < 5:
                    logger.info(f"🔄 Step {step}: Current={math.degrees(current_yaw):.1f}°, Target={math.degrees(target_yaw):.1f}°, Diff={math.degrees(angle_diff):.1f}°")

                if abs(angle_diff) < angle_threshold:
                    logger.info(f"✅ Target orientation reached (within {math.degrees(angle_threshold):.1f}°)")
                    logger.info(f"✅ Final: Current={math.degrees(current_yaw):.1f}°, Target={math.degrees(target_yaw):.1f}°, Diff={math.degrees(angle_diff):.1f}°")
                    reached_target = True
                    break
            else:
                logger.warning(f"⚠️ Step {step}: Cannot get current yaw!")

        # Check if we exited loop due to max_steps without reaching target
        if not reached_target:
            current_yaw = self.get_current_yaw()
            if current_yaw is not None:
                angle_diff = target_yaw - current_yaw
                angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi
                logger.warning(
                    f"⚠️  Max steps ({max_steps}) reached. "
                    f"Remaining error: {math.degrees(angle_diff):.2f}°"
                )

        # Active braking: briefly apply reverse torque to eliminate inertia
        logger.info("⏸️  Active braking...")

        # Check current rotation direction and apply counter-torque
        current_yaw_before_brake = self.get_current_yaw()

        # Apply weak reverse velocity for 3 steps (~192ms)
        reverse_brake_velocity = 0.1  # Very weak counter-torque
        self.left_motor.setVelocity(left_velocity * -0.1)  # Reverse at 10% of original
        self.right_motor.setVelocity(right_velocity * -0.1)

        for _ in range(3):
            if self._do_step() == -1:
                return False

        # Now fully stop
        self.left_motor.setVelocity(0.0)
        self.right_motor.setVelocity(0.0)

        # Wait for complete stop (passive brake)
        for _ in range(5):  # ~320ms settle time
            if self._do_step() == -1:
                return False

        # Final orientation check after braking
        final_yaw = self.get_current_yaw()
        if final_yaw is not None:
            final_diff = target_yaw - final_yaw
            final_diff = (final_diff + math.pi) % (2 * math.pi) - math.pi
            logger.info(f"✅ Rotation completed - final angle error: {math.degrees(final_diff):.2f}°")

        return True

    def _execute_scan(self, action: RobotAction) -> bool:
        """
        Execute SCAN action with filtered sensor data and safety checks.

        Args:
            action: SCAN action with duration

        Returns:
            True if successful, False if critical obstacle detected
        """
        if action.duration is None:
            logger.error("SCAN action missing duration")
            return False

        logger.info(f"Scanning for {action.duration}s")

        # Stop motors
        self.left_motor.setVelocity(0.0)
        self.right_motor.setVelocity(0.0)

        # Scan for duration
        steps = int((action.duration * 1000) / self.time_step)

        for _ in range(steps):
            # Read filtered sensor data from SensorManager
            sensor_data = self.sensor_manager.get_sensor_data()

            # Check for close obstacles using filtered lidar data
            if sensor_data.lidar_min_distance is not None:
                if sensor_data.lidar_min_distance < 0.3:
                    logger.warning(f"Object detected at {sensor_data.lidar_min_distance:.2f}m")

                # CRITICAL: Abort scan if extremely close obstacle detected
                # Note: Use 0.15m threshold (same as reactive controller CRITICAL level)
                if sensor_data.lidar_min_distance < 0.15:
                    logger.error(
                        f"SCAN aborted: Critical obstacle at {sensor_data.lidar_min_distance:.2f}m. "
                        f"Robot is too close to obstacle to continue scanning safely."
                    )
                    return False

            if self._do_step() == -1:
                return False

        logger.info(f"Scan completed")
        return True

    def _execute_wait(self, action: RobotAction) -> bool:
        """
        Execute WAIT action.

        Args:
            action: WAIT action with duration

        Returns:
            True if successful
        """
        if action.duration is None:
            logger.error("WAIT action missing duration")
            return False

        logger.info(f"Waiting for {action.duration}s")

        # Stop motors
        self.left_motor.setVelocity(0.0)
        self.right_motor.setVelocity(0.0)

        # Wait for duration
        steps = int((action.duration * 1000) / self.time_step)

        for _ in range(steps):
            if self._do_step() == -1:
                return False

        logger.info(f"Wait completed")
        return True

    def _execute_stop(self, action: RobotAction) -> bool:
        """
        Execute STOP action.

        Args:
            action: STOP action

        Returns:
            True if successful
        """
        logger.info("Stopping robot")

        self.left_motor.setVelocity(0.0)
        self.right_motor.setVelocity(0.0)

        return True

    # ========== ARM MANIPULATION METHODS ==========

    def _execute_arm_move(self, action: RobotAction) -> bool:
        """
        Execute ARM_MOVE action - move arm to specified joint positions.

        Args:
            action: ARM_MOVE action with shoulder_angle and/or elbow_angle (in degrees)

        Returns:
            True if successful
        """
        if not getattr(self, 'arm_available', False):
            logger.error("ARM_MOVE failed: Arm not available")
            return False

        # Calculate arm reach for debugging
        L1, L2 = 0.12, 0.15  # upper arm, forearm lengths
        shoulder_deg = action.shoulder_angle or 0
        elbow_deg = action.elbow_angle or 0
        shoulder_rad = math.radians(shoulder_deg)
        elbow_rad = math.radians(elbow_deg)
        # Forward reach from arm base
        forward_reach = L1 * math.sin(shoulder_rad) + L2 * math.sin(shoulder_rad + elbow_rad)
        # Height from arm base (0.22m above ground)
        height_from_base = L1 * math.cos(shoulder_rad) + L2 * math.cos(shoulder_rad + elbow_rad)
        gripper_height = 0.22 + height_from_base

        logger.info(
            f"🦾 ARM_MOVE: shoulder={shoulder_deg}°, elbow={elbow_deg}° | "
            f"forward_reach={forward_reach:.3f}m, gripper_height={gripper_height:.3f}m"
        )

        try:
            # Convert degrees to radians and set motor positions
            if action.shoulder_angle is not None and self.arm_shoulder:
                shoulder_rad = math.radians(action.shoulder_angle)
                self.arm_shoulder.setPosition(shoulder_rad)
                logger.debug(f"Shoulder set to {action.shoulder_angle}° ({shoulder_rad:.3f} rad)")

            if action.elbow_angle is not None and self.arm_elbow:
                elbow_rad = math.radians(action.elbow_angle)
                self.arm_elbow.setPosition(elbow_rad)
                logger.debug(f"Elbow set to {action.elbow_angle}° ({elbow_rad:.3f} rad)")

            # Wait for arm to reach target position
            # Estimate time based on max angle change (~1 rad/s motor speed)
            max_angle_change = max(
                abs(action.shoulder_angle or 0),
                abs(action.elbow_angle or 0)
            )
            wait_time = max(0.5, max_angle_change / 60.0)  # At least 0.5s
            wait_steps = int((wait_time * 1000) / self.time_step)

            for _ in range(wait_steps):
                if self._do_step() == -1:
                    return False

                # Update held object position to follow gripper during arm movement
                if SUPERVISOR_OBJECT_MANIPULATION and is_object_held():
                    gps = self.gps.getValues() if self.gps else [0, 0, 0]
                    imu_values = self.imu.getRollPitchYaw() if self.imu else [0, 0, 0]
                    robot_yaw = imu_values[2]  # yaw in radians
                    # Get current shoulder angle from position sensor
                    current_shoulder = self.arm_shoulder_sensor.getValue() if self.arm_shoulder_sensor else shoulder_rad
                    update_held_object_position(gps[0], gps[1], robot_yaw, current_shoulder)

            logger.info("Arm movement completed")
            return True

        except Exception as e:
            logger.error(f"ARM_MOVE failed: {e}")
            return False

    def _execute_grip(self, action: RobotAction) -> bool:
        """
        Execute GRIP action - close gripper to grasp object.

        Args:
            action: GRIP action with optional gripper_force (0.0-1.0)

        Returns:
            True if successful
        """
        if not getattr(self, 'arm_available', False):
            logger.error("GRIP failed: Arm not available")
            return False

        if not self.gripper_left or not self.gripper_right:
            logger.error("GRIP failed: Gripper motors not found")
            return False

        force = action.gripper_force if action.gripper_force is not None else 0.5
        logger.info(f"Closing gripper (force={force:.1f})")

        try:
            # Close gripper - fingers move towards center
            # Position correlates to grip tightness
            grip_position = 0.05 * (1.0 - force)  # Tighter grip = smaller position
            self.gripper_left.setPosition(-grip_position)  # Left moves right (negative)
            self.gripper_right.setPosition(grip_position)  # Right moves left (positive)

            # Wait for gripper to close
            wait_steps = int((500) / self.time_step)  # 500ms
            for _ in range(wait_steps):
                if self._do_step() == -1:
                    return False

            logger.info("Gripper closed - attempting to grasp object")

            # Supervisor-based object attachment (makes object visually follow gripper)
            if SUPERVISOR_OBJECT_MANIPULATION:
                if not attach_object_to_gripper():
                    logger.error("❌ GRIP FAILED: Object is not in front of robot arm - cannot attach!")
                    # Open gripper back since grip failed
                    self.gripper_left.setPosition(-0.1)
                    self.gripper_right.setPosition(0.1)
                    return False
                logger.info("✅ Object successfully attached to gripper")

            return True

        except Exception as e:
            logger.error(f"GRIP failed: {e}")
            return False

    def _execute_release(self, action: RobotAction) -> bool:
        """
        Execute RELEASE action - open gripper to release object.

        Args:
            action: RELEASE action

        Returns:
            True if successful
        """
        if not getattr(self, 'arm_available', False):
            logger.error("RELEASE failed: Arm not available")
            return False

        if not self.gripper_left or not self.gripper_right:
            logger.error("RELEASE failed: Gripper motors not found")
            return False

        logger.info("Opening gripper")

        try:
            # Open gripper - fingers move outward
            self.gripper_left.setPosition(0.3)   # Left moves left (positive)
            self.gripper_right.setPosition(-0.3)  # Right moves right (negative)

            # Wait for gripper to open
            wait_steps = int((500) / self.time_step)  # 500ms
            for _ in range(wait_steps):
                if self._do_step() == -1:
                    return False

            logger.info("Gripper opened - object released")

            # Supervisor-based object detachment
            if SUPERVISOR_OBJECT_MANIPULATION:
                detach_object()

            return True

        except Exception as e:
            logger.error(f"RELEASE failed: {e}")
            return False

    def get_arm_position(self) -> Optional[Dict[str, float]]:
        """
        Get current arm joint positions.

        Returns:
            Dictionary with shoulder_angle and elbow_angle in degrees, or None
        """
        if not getattr(self, 'arm_available', False):
            return None

        try:
            result = {}
            if self.arm_shoulder_sensor:
                shoulder_rad = self.arm_shoulder_sensor.getValue()
                result['shoulder_angle'] = math.degrees(shoulder_rad)
            if self.arm_elbow_sensor:
                elbow_rad = self.arm_elbow_sensor.getValue()
                result['elbow_angle'] = math.degrees(elbow_rad)
            return result
        except Exception as e:
            logger.warning(f"Failed to get arm position: {e}")
            return None

    def get_current_position(self) -> Optional[tuple[float, float, float]]:
        """
        Get current robot position from SensorManager (filtered GPS data).

        Returns:
            (x, y, z) position or None if unavailable
        """
        try:
            sensor_data = self.sensor_manager.get_sensor_data()
            if sensor_data.position_x is not None and sensor_data.position_y is not None:
                # Validate values are not NaN (sensor not initialized yet)
                if not math.isnan(sensor_data.position_x) and not math.isnan(sensor_data.position_y):
                    z_pos = sensor_data.position_z or 0.0
                    # Also check Z position if it exists
                    if sensor_data.position_z is not None and math.isnan(sensor_data.position_z):
                        z_pos = 0.0
                    return (
                        sensor_data.position_x,
                        sensor_data.position_y,
                        z_pos
                    )
            return None
        except Exception as e:
            logger.error(f"Failed to get GPS position: {e}")
            return None

    def get_current_yaw(self) -> Optional[float]:
        """
        Get current robot yaw angle from SensorManager (filtered IMU data).

        Returns:
            Yaw angle in radians or None if unavailable
        """
        try:
            sensor_data = self.sensor_manager.get_sensor_data()
            if sensor_data.yaw is not None:
                # Validate value is not NaN (sensor not initialized yet)
                if not math.isnan(sensor_data.yaw):
                    # SensorManager returns degrees, convert to radians
                    return math.radians(sensor_data.yaw)
            return None
        except Exception as e:
            logger.error(f"Failed to get IMU yaw: {e}")
            return None

    def get_robot_state(self) -> RobotState:
        """
        Get current complete robot state with filtered sensor data.

        Uses SensorManager to get noise-filtered sensor readings.
        Includes reactive_log from Story 3.1 reactive controller.

        Returns:
            RobotState with current sensor data (filtered if enabled) and reactive_log
        """
        # Get filtered sensor data from SensorManager
        sensors = self.sensor_manager.get_sensor_data()

        # Create robot state with reactive_log and original target (if detour occurred)
        state = RobotState(
            robot_id="rescue_robot",
            status=self._current_status,  # Use actual tracked status
            sensors=sensors,
            reactive_log=self.reactive_log,  # Include reactive interventions
            original_target_x=getattr(self, '_original_target_x', None),
            original_target_y=getattr(self, '_original_target_y', None)
        )

        return state

    def get_reactive_sensor_data(self) -> Dict[str, Any]:
        """
        Get sensor data formatted for HybridReactiveController.

        Returns:
            Dictionary with lidar, gps, imu, camera data
        """
        sensor_data_obj = self.sensor_manager.get_sensor_data()

        return {
            'lidar': {
                'lidar_distances': sensor_data_obj.lidar_distances or [],
                'lidar_min_distance': sensor_data_obj.lidar_min_distance or float('inf'),
                'lidar_avg_distance': sensor_data_obj.lidar_avg_distance or 0.0
            },
            'gps': {
                'position_x': sensor_data_obj.position_x or 0.0,
                'position_y': sensor_data_obj.position_y or 0.0,
                'position_z': sensor_data_obj.position_z or 0.0
            },
            'imu': {
                'roll': sensor_data_obj.roll or 0.0,
                'pitch': sensor_data_obj.pitch or 0.0,
                'yaw': sensor_data_obj.yaw or 0.0
            },
            'camera': {
                'has_data': sensor_data_obj.camera_has_data,
                'width': sensor_data_obj.camera_width or 640,
                'height': sensor_data_obj.camera_height or 480
            }
        }

    def get_reactive_log(self) -> List[Dict[str, Any]]:
        """
        Get reactive intervention log.

        Returns:
            List of reactive intervention records
        """
        return self.reactive_log

    def clear_reactive_log(self):
        """Clear reactive intervention log (e.g., at start of new mission)."""
        self.reactive_log = []


class ActorAgentFactory:
    """Factory for creating ActorAgent instances."""

    _instance: Optional[ActorAgent] = None

    @classmethod
    def create(
        cls,
        robot,
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        verbose: bool = True,
        time_step: int = 64,
        sensor_config: Optional[SensorManagerConfig] = None
    ) -> ActorAgent:
        """
        Create or return singleton ActorAgent instance with SensorManager.

        Args:
            robot: Webots Robot instance
            api_key: OpenAI API key
            model: LLM model name
            temperature: LLM temperature
            verbose: Enable verbose logging
            time_step: Webots time step in ms
            sensor_config: Optional SensorManagerConfig for sensor filtering

        Returns:
            ActorAgent instance
        """
        if cls._instance is None:
            cls._instance = ActorAgent(
                robot=robot,
                api_key=api_key,
                model=model,
                temperature=temperature,
                verbose=verbose,
                time_step=time_step,
                sensor_config=sensor_config
            )
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None
