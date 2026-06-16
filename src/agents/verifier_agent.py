"""
Verifier Agent

CrewAI agent that verifies mission execution results and triggers replanning.
"""

from typing import Optional, Dict, Any, List
from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI
from loguru import logger
import math

from ..schemas import MissionCommand, RobotState, RobotStatus, MissionStatus, FailureReason, SensorData, ReplanRequest, RobotAction
from ..rag import RobotKnowledgeBase


class VerifierAgent:
    """
    Verifier Agent for mission success/failure verification.

    Responsibilities:
    1. Analyze final robot state after mission
    2. Determine success/failure based on criteria
    3. Trigger replanning if needed (max 3 retries)
    4. Generate verification report

    Example:
        >>> verifier = VerifierAgent(api_key="sk-...")
        >>> mission = MissionCommand(command="Search area", language="en")
        >>> final_state = RobotState(...)
        >>> success, message = verifier.verify_mission(mission, final_state)
    """

    def __init__(
        self,
        api_key: str,
        knowledge_base: Optional[RobotKnowledgeBase] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        verbose: bool = True
    ):
        """
        Initialize Verifier Agent.

        Args:
            api_key: OpenAI API key
            knowledge_base: RobotKnowledgeBase for RAG (optional)
            model: LLM model to use
            temperature: LLM temperature (lower = more consistent)
            verbose: Enable verbose logging
        """
        self.api_key = api_key
        self.knowledge_base = knowledge_base
        self.model = model
        self.temperature = temperature
        self.verbose = verbose

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=api_key
        )

        # Create CrewAI Agent
        self.agent = Agent(
            role="Mission Verifier",
            goal="Verify mission success by analyzing robot state and sensor data",
            backstory=(
                "You are an expert mission verification specialist. "
                "You analyze robot sensor data, final positions, and mission objectives "
                "to determine if missions were completed successfully. "
                "You provide clear reasoning for your decisions."
            ),
            llm=self.llm,
            verbose=verbose,
            allow_delegation=False
        )

        logger.info(f"VerifierAgent initialized with model={model}")

    def verify_mission(
        self,
        mission: MissionCommand,
        final_state: RobotState,
        execution_success: bool
    ) -> tuple[bool, str]:
        """
        Verify if mission was completed successfully.

        Args:
            mission: Original mission command
            final_state: Robot state after execution
            execution_success: Whether all actions executed without errors

        Returns:
            (success: bool, message: str) - Verification result and explanation
        """
        logger.info(f"Verifying mission: {mission.command}")

        # Quick failure checks
        if not execution_success:
            return False, "Mission failed during execution"

        if mission.status == MissionStatus.FAILED:
            return False, mission.failure_reason or "Mission marked as failed"

        # Build verification prompt
        prompt = self._build_verification_prompt(mission, final_state)

        # Create verification task
        task = Task(
            description=prompt,
            agent=self.agent,
            expected_output="Clear YES or NO decision with reasoning"
        )

        try:
            # Execute verification using Crew
            crew = Crew(
                agents=[self.agent],
                tasks=[task],
                verbose=self.verbose
            )

            result = crew.kickoff()

            # Convert CrewOutput to string
            result_str = str(result.raw) if hasattr(result, 'raw') else str(result)

            # Parse result
            success = self._parse_verification_result(result_str)

            if success:
                message = f"Mission verified successful: {result}"
                logger.info(message)
            else:
                message = f"Mission verification failed: {result}"
                logger.warning(message)

            return success, message

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False, f"Verification error: {e}"

    def adjust_tolerance_based_on_reactive_log(self, reactive_log: List[Dict[str, Any]]) -> float:
        """
        Adjust tolerance based on reactive interventions.

        Helper method for testing and explicit tolerance calculation.

        Only MODERATE (AI detour) interventions trigger tolerance expansion.
        CRITICAL (emergency stop) interventions do NOT increase tolerance.

        Args:
            reactive_log: List of reactive interventions from RobotState

        Returns:
            Fixed tolerance of 0.1m
        """
        return 0.1  # Fixed tolerance

    def _build_verification_prompt(
        self,
        mission: MissionCommand,
        final_state: RobotState
    ) -> str:
        """
        Build verification analysis prompt with fixed tolerance.

        Uses fixed 0.1m tolerance regardless of detours.
        """

        # Get position info
        position = final_state.get_position()
        position_str = f"X={position[0]:.2f}m, Y={position[1]:.2f}m, Z={position[2]:.2f}m" if position else "Unknown"

        # Starting position info for relative movement verification
        starting_position_info = ""
        if mission.starting_position_x is not None and mission.starting_position_y is not None:
            starting_position_info = f"""
**Starting Position (at mission start):**
- Start: X={mission.starting_position_x:.2f}m, Y={mission.starting_position_y:.2f}m
- Starting Heading: {mission.starting_yaw:.1f}° (direction robot was facing)
"""
            # Calculate target position and distance for verification
            if position and mission.action_plan:
                # Find the move action and calculate absolute target position
                # IMPORTANT: Track cumulative heading changes from rotate actions
                target_x = None
                target_y = None
                action_desc = ""

                # Start with initial heading and position
                current_heading = mission.starting_yaw
                current_x = mission.starting_position_x
                current_y = mission.starting_position_y

                for action in mission.action_plan:
                    if action.action.value == "rotate":
                        # Update heading for subsequent move calculations
                        rotate_angle = action.angle or 0
                        current_heading += rotate_angle
                        # Normalize to -180 to 180
                        while current_heading > 180:
                            current_heading -= 360
                        while current_heading < -180:
                            current_heading += 360
                    elif action.action.value == "move":
                        action_x = action.x or 0
                        action_y = action.y or 0

                        if action.relative:
                            # Convert relative to absolute coordinates
                            # Use CURRENT heading (after any rotations), not starting heading
                            # Math convention: 0°=East(+X), 90°=North(+Y)
                            # Forward (action_x): cos(yaw) for X, sin(yaw) for Y
                            # Left (action_y): -sin(yaw) for X, cos(yaw) for Y
                            yaw_rad = math.radians(current_heading)
                            target_x = current_x + action_x * math.cos(yaw_rad) - action_y * math.sin(yaw_rad)
                            target_y = current_y + action_x * math.sin(yaw_rad) + action_y * math.cos(yaw_rad)

                            # Describe the action type with heading info
                            direction = "forward" if action_x > 0 and action_y == 0 else \
                                        "backward" if action_x < 0 and action_y == 0 else \
                                        "left" if action_y > 0 and action_x == 0 else \
                                        "right" if action_y < 0 and action_x == 0 else \
                                        "diagonal"
                            heading_note = f", heading={current_heading:.1f}°" if current_heading != mission.starting_yaw else ""
                            action_desc = f"{direction} (relative: x={action_x:.1f}, y={action_y:.1f}{heading_note})"
                        else:
                            # Already absolute coordinates
                            target_x = action_x
                            target_y = action_y
                            action_desc = f"absolute target ({action_x:.1f}, {action_y:.1f})"

                        # Update current position for next move action (multi-step paths)
                        current_x = target_x
                        current_y = target_y
                        # Don't break - continue to process all actions for multi-step missions

                if target_x is not None and target_y is not None:
                    # Calculate EUCLIDEAN distance from current position to target
                    dx_to_target = target_x - position[0]
                    dy_to_target = target_y - position[1]
                    distance_to_target = math.sqrt(dx_to_target**2 + dy_to_target**2)

                    # Also calculate distance moved from start (for reference)
                    dx_from_start = position[0] - mission.starting_position_x
                    dy_from_start = position[1] - mission.starting_position_y
                    distance_moved = math.sqrt(dx_from_start**2 + dy_from_start**2)

                    # Tolerance: 0.1m normally, progressive with detours (0.1m × detour_count, max 1.0m)
                    # (reactive_log is checked later in the prompt building)
                    base_tolerance = 0.1  # meters
                    distance_ok = distance_to_target <= base_tolerance

                    starting_position_info += f"""- End: X={position[0]:.2f}m, Y={position[1]:.2f}m
- Target: X={target_x:.2f}m, Y={target_y:.2f}m ({action_desc})
- **Distance to Target: {distance_to_target:.2f}m**
- Distance Moved from Start: {distance_moved:.2f}m
- Tolerance: {base_tolerance}m (fixed)
- **Distance Check: {"✓ PASS" if distance_ok else "❌ FAIL"}** ({distance_to_target:.2f}m {"<=" if distance_ok else ">"} {base_tolerance}m)

**PRE-CALCULATED VERIFICATION RESULT:**
- Tolerance = 0.1m (fixed)
- Distance to target: {distance_to_target:.2f}m
- **{"PASS - Distance within tolerance" if distance_ok else "FAIL - Distance exceeds tolerance"}**
"""
                else:
                    starting_position_info += f"""- End: X={position[0]:.2f}m, Y={position[1]:.2f}m
- (No move action found in plan)
"""

        # CRITICAL: Check for goal location in RAG (entrance, exit, 입구, 출구, 도착지점, 목적지)
        goal_location_info = ""
        if self.knowledge_base:
            location_keywords = ["entrance", "exit", "입구", "출구", "도착지점", "도착점", "목적지", "destination"]
            command_lower = mission.command.lower()

            # Check if command contains location keywords
            for keyword in location_keywords:
                if keyword in command_lower:
                    logger.info(f"Verifier: Location keyword '{keyword}' detected, querying RAG for coordinates")

                    # Search for location coordinates
                    rag_results = self.knowledge_base.search_capabilities(keyword, n_results=3)

                    if rag_results:
                        # Extract location info from RAG
                        for result in rag_results:
                            doc = result.get('document', '')
                            metadata = result.get('metadata', {})

                            # Look for position coordinates
                            if 'position_x' in metadata and 'position_y' in metadata:
                                goal_x = float(metadata['position_x'])
                                goal_y = float(metadata['position_y'])

                                # Calculate distance to goal
                                if position:
                                    dx = goal_x - position[0]
                                    dy = goal_y - position[1]
                                    distance_to_goal = math.sqrt(dx**2 + dy**2)

                                    goal_location_info = f"""
**Goal Location Verification:**
- Target: {keyword.upper()} at X={goal_x:.2f}m, Y={goal_y:.2f}m
- Current Position: X={position[0]:.2f}m, Y={position[1]:.2f}m
- **Distance to Goal: {distance_to_goal:.2f}m**
- Required Tolerance: {"✓ PASS" if distance_to_goal <= 0.3 else "✗ FAIL (too far)"}

"""
                                    logger.info(
                                        f"Verifier: Goal location {keyword} at ({goal_x:.2f}, {goal_y:.2f}), "
                                        f"distance={distance_to_goal:.2f}m"
                                    )
                                    break
                    break

        # Get orientation info
        orientation = final_state.get_orientation()
        orientation_str = f"Yaw={orientation[2]:.1f}°" if orientation else "Unknown"

        # Get sensor info
        sensors = final_state.sensors
        lidar_info = f"Min distance: {sensors.lidar_min_distance:.2f}m" if sensors.lidar_min_distance else "No data"

        # Fixed tolerance for distance check (0.1m)
        tolerance = 0.1  # meters (fixed)
        reactive_info = ""

        if final_state.reactive_log and len(final_state.reactive_log) > 0:
            # Count MODERATE interventions (actual detours, not POST_DETOUR stabilization)
            detour_count = sum(1 for log in final_state.reactive_log if log.get('type') == 'MODERATE')
            reactive_count = len(final_state.reactive_log)
            reactive_types = {log.get('type', 'UNKNOWN') for log in final_state.reactive_log}

            reactive_info = f"""
**Reactive Interventions Detected (Obstacle Avoidance):**
- Count: {reactive_count} interventions ({detour_count} detours)
- Types: {', '.join(reactive_types)}
- **Tolerance: {tolerance:.1f}m** (fixed)
- Reason: Robot had to deviate from planned path to avoid obstacles

**IMPORTANT:** When obstacles were avoided, robot may not reach exact target position.
Use {tolerance:.1f}m tolerance for distance check!
"""
            logger.info(
                f"Verifier: Reactive adjustment detected ({detour_count} detours, {reactive_count} total interventions), "
                f"tolerance: {tolerance}m (fixed)"
            )
        else:
            reactive_info = f"""
**Reactive Interventions:**
- None detected (no obstacle avoidance)
- Standard tolerance: {tolerance}m
"""

        prompt = f"""
Verify if this robot mission was completed successfully.

**Mission Command:** "{mission.command}"
**Language:** {mission.language}
**Priority:** {mission.priority}/10

**Robot Final State:**
- Status: {final_state.status}
- Position: {position_str}
- Orientation: {orientation_str}
- Lidar: {lidar_info}
- Operational: {final_state.is_operational()}

{goal_location_info}

{starting_position_info}

{reactive_info}

**Verification Tolerance:**
- Position tolerance: {tolerance}m (fixed)
- Orientation tolerance: 5 degrees

**Action Plan Executed:**
{len(mission.action_plan) if mission.action_plan else 0} actions completed
{self._format_action_plan_details(mission.action_plan) if mission.action_plan else ""}

**Mission Objectives:**
Analyze the mission command and determine if the robot achieved the stated goal.

For movement missions:
- Did the robot reach the target location?
- Is the final position reasonable for the command?

For scanning missions:
- Did the robot complete the scan duration?
- Were obstacles detected if expected?

For general missions:
- Did all planned actions execute?
- Is the robot in a safe, operational state?

**Your Decision:**
Answer with CLEAR reasoning:
1. State YES or NO as the first word
2. Explain why based on the evidence above

**CRITICAL RULE:**
- If **Distance to Target <= Tolerance**, you MUST answer **YES** (mission successful)
- The tolerance already accounts for obstacle avoidance deviations
- Do NOT fail the mission if distance is within tolerance

Format: "YES/NO: [reasoning]"
"""
        return prompt

    def _format_action_plan_details(self, action_plan: List) -> str:
        """
        Format action plan details for verification prompt.

        Provides detailed information about each action, especially for
        MOVE actions with relative coordinates so the Verifier can
        properly understand what movement was intended.

        Args:
            action_plan: List of RobotAction objects

        Returns:
            Formatted string with action details
        """
        if not action_plan:
            return ""

        details = []
        for i, action in enumerate(action_plan):
            if action.action.value == "move":
                if action.relative:
                    # Relative movement - explain clearly
                    direction = "forward" if action.x and action.x > 0 else "backward" if action.x and action.x < 0 else ""
                    lateral = "left" if action.y and action.y > 0 else "right" if action.y and action.y < 0 else ""
                    details.append(
                        f"  {i+1}. MOVE (relative): x={action.x}m ({direction}), y={action.y}m ({lateral}), speed={action.speed}m/s\n"
                        f"     **Note: This is RELATIVE movement from robot's heading direction, NOT absolute coordinates**"
                    )
                else:
                    # Absolute movement
                    details.append(
                        f"  {i+1}. MOVE (absolute): target=({action.x}, {action.y}), speed={action.speed}m/s"
                    )
            elif action.action.value == "rotate":
                direction = "left (CCW)" if action.angle and action.angle > 0 else "right (CW)"
                details.append(
                    f"  {i+1}. ROTATE: {action.angle}° {direction}, speed={action.speed}"
                )
            elif action.action.value == "scan":
                details.append(f"  {i+1}. SCAN: duration={action.duration}s")
            elif action.action.value == "wait":
                details.append(f"  {i+1}. WAIT: duration={action.duration}s")
            elif action.action.value == "stop":
                details.append(f"  {i+1}. STOP")

        return "\n" + "\n".join(details) if details else ""

    def _parse_verification_result(self, result: str) -> bool:
        """
        Parse verification result from LLM.

        Args:
            result: Raw LLM output

        Returns:
            True if verified successful, False otherwise
        """
        result_lower = result.lower().strip()

        # Check for explicit YES/NO
        if result_lower.startswith('yes'):
            return True
        elif result_lower.startswith('no'):
            return False

        # Check for success indicators
        success_keywords = ['success', 'achieved', 'completed', 'accomplished']
        failure_keywords = ['fail', 'incomplete', 'not achieved', 'unsuccessful']

        success_count = sum(1 for keyword in success_keywords if keyword in result_lower)
        failure_count = sum(1 for keyword in failure_keywords if keyword in result_lower)

        if success_count > failure_count:
            return True
        elif failure_count > success_count:
            return False

        # Default to failure if ambiguous
        logger.warning(f"Ambiguous verification result: {result}")
        return False

    def should_retry(
        self,
        mission: MissionCommand
    ) -> bool:
        """
        Check if mission should be retried.

        Args:
            mission: Mission command

        Returns:
            True if retry is allowed, False otherwise
        """
        can_retry = mission.can_retry()

        if can_retry:
            logger.info(f"Mission can be retried (attempt {mission.retry_count + 1}/3)")
        else:
            logger.warning(f"Mission cannot be retried (max attempts reached)")

        return can_retry

    def prepare_retry(
        self,
        mission: MissionCommand,
        failure_reason: str
    ) -> None:
        """
        Prepare mission for retry.

        Args:
            mission: Mission to retry
            failure_reason: Reason for failure
        """
        logger.info(f"Preparing retry for mission: {failure_reason}")

        # Increment retry count
        mission.increment_retry()

        # Clear previous execution state
        mission.current_action_index = 0
        mission.action_plan = None  # Will be regenerated by Planner

        logger.info(f"Mission prepared for retry {mission.retry_count}/3")

    def analyze_failure_reason(
        self,
        mission: MissionCommand,
        final_state: RobotState
    ) -> FailureReason:
        """
        Analyze mission failure and categorize the reason.

        Uses sensor data and mission context to determine why the mission failed.
        Checks for: obstacle collision, path blocked, goal unreached, sensor failure, timeout.

        Args:
            mission: Failed mission command
            final_state: Robot state when mission failed

        Returns:
            FailureReason enum indicating categorized failure type
        """
        logger.info(f"Analyzing failure for mission: {mission.command}")

        # Check for obstacle collision (highest priority - immediate danger)
        if self._check_obstacle_collision(final_state.sensors):
            logger.warning("Failure reason: OBSTACLE_COLLISION detected")
            return FailureReason.OBSTACLE_COLLISION

        # Check for sensor failure
        if self._check_sensor_failure(final_state.sensors):
            logger.error("Failure reason: SENSOR_FAILURE detected")
            return FailureReason.SENSOR_FAILURE

        # Check for path blocked
        if self._check_path_blocked(final_state.sensors):
            logger.warning("Failure reason: PATH_BLOCKED detected")
            return FailureReason.PATH_BLOCKED

        # Check for goal unreached (based on GPS/position)
        if self._check_goal_unreached(mission, final_state):
            logger.warning("Failure reason: GOAL_UNREACHED detected")
            return FailureReason.GOAL_UNREACHED

        # Check for timeout
        if mission.get_elapsed_time() > 300:  # 5 minutes default timeout
            logger.warning("Failure reason: TIMEOUT detected")
            return FailureReason.TIMEOUT

        # Default to goal unreached if no specific cause found
        logger.warning("Failure reason unclear, defaulting to GOAL_UNREACHED")
        return FailureReason.GOAL_UNREACHED

    def _check_obstacle_collision(self, sensors: SensorData) -> bool:
        """
        Check if robot collided with an obstacle.

        Uses Lidar data to detect very close obstacles indicating collision.

        Args:
            sensors: Current sensor data

        Returns:
            True if collision detected, False otherwise
        """
        if sensors.lidar_distances is None:
            return False

        # Check minimum distance - collision if < 0.3m
        if sensors.lidar_min_distance is not None and sensors.lidar_min_distance < 0.3:
            logger.warning(f"Obstacle collision: min distance {sensors.lidar_min_distance:.2f}m < 0.3m")
            return True

        # Count very close obstacles (< 0.3m)
        close_obstacles = [d for d in sensors.lidar_distances if d < 0.3]
        if len(close_obstacles) > 10:  # More than 10 points detect collision
            logger.warning(f"Obstacle collision: {len(close_obstacles)} lidar points < 0.3m")
            return True

        return False

    def _check_path_blocked(self, sensors: SensorData) -> bool:
        """
        Check if path ahead is blocked by obstacles.

        Uses Lidar data to check if forward path is clear.

        Args:
            sensors: Current sensor data

        Returns:
            True if path blocked, False otherwise
        """
        if sensors.lidar_distances is None:
            return False

        # Check forward path (±30° from front)
        # Front is at index 256 (512 points / 2)
        front_start_idx = 226  # -30°
        front_end_idx = 286    # +30°

        front_distances = sensors.lidar_distances[front_start_idx:front_end_idx]

        # Path blocked if most front distances < 0.5m
        blocked_count = sum(1 for d in front_distances if d < 0.5)
        if blocked_count > len(front_distances) * 0.7:  # >70% blocked
            logger.warning(f"Path blocked: {blocked_count}/{len(front_distances)} points < 0.5m")
            return True

        return False

    def _check_goal_unreached(self, mission: MissionCommand, final_state: RobotState) -> bool:
        """
        Check if robot failed to reach goal position.

        Compares current position with mission target (if available).

        Args:
            mission: Mission command
            final_state: Final robot state

        Returns:
            True if goal not reached, False otherwise
        """
        # Get current position
        current_pos = final_state.get_position()
        if current_pos is None:
            logger.warning("Cannot check goal: no GPS position available")
            return True  # Assume unreached if no position

        # Try to extract target position from mission
        # (For now, we check if robot moved significantly - full implementation would parse mission.command)
        # Simple heuristic: if robot is at origin (0,0,0), likely didn't move
        x, y, z = current_pos
        distance_from_origin = math.sqrt(x**2 + y**2)

        # If mission involves movement and robot is still at origin
        movement_keywords = ['move', 'go', 'navigate', 'search', '이동', '탐색']
        if any(keyword in mission.command.lower() for keyword in movement_keywords):
            if distance_from_origin < 0.1:  # Very close to origin
                logger.warning(f"Goal unreached: robot at origin ({x:.2f}, {y:.2f}), mission requires movement")
                return True

        # If action plan wasn't completed
        if mission.action_plan and mission.current_action_index < len(mission.action_plan) - 1:
            logger.warning(f"Goal unreached: only {mission.current_action_index + 1}/{len(mission.action_plan)} actions completed")
            return True

        return False

    def _check_sensor_failure(self, sensors: SensorData) -> bool:
        """
        Check if critical sensors have failed.

        Args:
            sensors: Current sensor data

        Returns:
            True if sensor failure detected, False otherwise
        """
        # Check if critical sensors are missing data
        gps_failed = all([
            sensors.position_x is None,
            sensors.position_y is None,
            sensors.position_z is None
        ])

        lidar_failed = sensors.lidar_distances is None

        # If both GPS and Lidar failed, it's a sensor failure
        if gps_failed and lidar_failed:
            logger.error("Sensor failure: both GPS and Lidar unavailable")
            return True

        return False

    def should_replan(
        self,
        failure_reason: FailureReason,
        mission: MissionCommand
    ) -> bool:
        """
        Determine if mission failure is recoverable via replanning.

        Some failures (obstacle collision, path blocked) can be solved by
        finding alternative routes. Others (sensor failure) require hardware fix.

        Args:
            failure_reason: Categorized failure reason
            mission: Failed mission command

        Returns:
            True if replanning is possible and allowed, False otherwise
        """
        # Check if retries are still available
        if not mission.can_retry():
            logger.warning("Cannot replan: max retries reached")
            return False

        # Determine if failure type is replan-able
        replanable_failures = {
            FailureReason.OBSTACLE_COLLISION,
            FailureReason.PATH_BLOCKED,
            FailureReason.GOAL_UNREACHED
        }

        non_replanable_failures = {
            FailureReason.SENSOR_FAILURE,
            FailureReason.TIMEOUT
        }

        if failure_reason in replanable_failures:
            logger.info(f"Replanning possible for {failure_reason.value}")
            return True
        elif failure_reason in non_replanable_failures:
            logger.warning(f"Replanning NOT possible for {failure_reason.value} (requires hardware/system fix)")
            return False
        else:
            # Unknown failure type - default to no replan for safety
            logger.warning(f"Unknown failure type {failure_reason}, defaulting to no replan")
            return False

    def generate_report(
        self,
        mission: MissionCommand,
        verification_success: bool,
        message: str
    ) -> Dict[str, Any]:
        """
        Generate verification report.

        Args:
            mission: Verified mission
            verification_success: Verification result
            message: Verification message

        Returns:
            Report dictionary
        """
        report = {
            "mission_id": mission.mission_id,
            "command": mission.command,
            "status": mission.status.value,
            "verification_success": verification_success,
            "verification_message": message,
            "retry_count": mission.retry_count,
            "can_retry": mission.can_retry(),
            "execution_time_seconds": mission.get_elapsed_time(),
            "actions_executed": mission.current_action_index + 1 if mission.action_plan else 0,
            "total_actions": len(mission.action_plan) if mission.action_plan else 0
        }

        logger.info(f"Verification report: {report}")
        return report

    def delegate_to_planner(
        self,
        planner_agent,
        replan_request: ReplanRequest,
        mission: MissionCommand,
        current_state: RobotState
    ) -> List[RobotAction]:
        """
        Delegate replanning to PlannerAgent via CrewAI.

        This method implements the delegation pattern where Verifier
        requests PlannerAgent to generate an alternative action plan.

        Args:
            planner_agent: PlannerAgent instance to delegate to
            replan_request: Replanning request with failure context
            mission: Original mission command
            current_state: Current robot state

        Returns:
            Alternative action plan from PlannerAgent

        Raises:
            ValueError: If delegation or replanning fails
        """
        logger.info(
            f"Delegating replanning to PlannerAgent "
            f"(failure: {replan_request.failure_reason.value}, retry: {replan_request.retry_count}/3)"
        )

        try:
            # Call PlannerAgent's replan_mission method
            alternative_plan = planner_agent.replan_mission(
                failure_info=replan_request,
                mission=mission,
                current_state=current_state
            )

            logger.info(f"PlannerAgent generated {len(alternative_plan)} alternative actions")
            return alternative_plan

        except Exception as e:
            logger.error(f"Delegation to PlannerAgent failed: {e}")
            raise ValueError(f"Replanning delegation failed: {e}")


class VerifierAgentFactory:
    """Factory for creating VerifierAgent instances."""

    _instance: Optional[VerifierAgent] = None

    @classmethod
    def create(
        cls,
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        verbose: bool = True
    ) -> VerifierAgent:
        """
        Create or return singleton VerifierAgent instance.

        Args:
            api_key: OpenAI API key
            model: LLM model name
            temperature: LLM temperature
            verbose: Enable verbose logging

        Returns:
            VerifierAgent instance
        """
        if cls._instance is None:
            cls._instance = VerifierAgent(
                api_key=api_key,
                model=model,
                temperature=temperature,
                verbose=verbose
            )
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None
