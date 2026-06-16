"""
Planner Agent

CrewAI agent that converts natural language mission commands (Korean/English)
into structured action plans using LLM Function Calling.
"""

from typing import List, Optional, Dict, Any
from crewai import Agent, Task
from langchain_openai import ChatOpenAI
from loguru import logger
import json

from ..schemas import MissionCommand, RobotAction, ActionType, RobotState, ReplanRequest
from ..rag import RobotKnowledgeBase
from ..rag.tools import format_rag_context
from ..utils.environment_detector import EnvironmentDetector


class PlannerAgent:
    """
    Planner Agent for converting natural language to action plans.

    Responsibilities:
    1. Parse Korean/English mission commands
    2. Generate sequential action plans
    3. Validate action safety and feasibility
    4. Consider current robot state in planning

    Example:
        >>> planner = PlannerAgent(api_key="sk-...")
        >>> mission = MissionCommand(
        ...     command="3층 동쪽 구역에서 생존자 탐색",
        ...     language="ko"
        ... )
        >>> action_plan = planner.plan_mission(mission)
    """

    def __init__(
        self,
        api_key: str,
        knowledge_base: Optional[RobotKnowledgeBase] = None,
        model: str = "gpt-4o",
        temperature: float = 0.3,
        verbose: bool = True,
        dynamic_objects: Optional[Dict[str, Dict[str, float]]] = None
    ):
        """
        Initialize Planner Agent.

        Args:
            api_key: OpenAI API key
            knowledge_base: RobotKnowledgeBase for RAG (optional)
            model: LLM model to use (default: gpt-4o)
            temperature: LLM temperature (0.0-1.0, lower = more deterministic)
            verbose: Enable verbose logging
            dynamic_objects: Dictionary of dynamic object positions (e.g., pickup_object)
        """
        self.api_key = api_key
        self.knowledge_base = knowledge_base
        self.model = model
        self.temperature = temperature
        self.verbose = verbose
        self.dynamic_objects = dynamic_objects or {}

        # Initialize Environment Detector (Story 3.3)
        self.environment_detector = EnvironmentDetector()

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=api_key
        )

        # Create CrewAI Agent
        self.agent = Agent(
            role="Mission Planner",
            goal="Convert natural language mission commands into safe, executable action plans",
            backstory=(
                "You are an expert mission planner for rescue robots. "
                "You understand Korean and English commands and can break them down "
                "into precise movement, rotation, and scanning actions. "
                "You prioritize safety and consider the robot's current state and environment."
                + (" You have access to a knowledge base of robot capabilities and environment constraints "
                   "that you MUST consult before planning." if knowledge_base else "")
            ),
            llm=self.llm,
            verbose=verbose,
            allow_delegation=False
        )

        rag_status = "enabled" if knowledge_base else "disabled"
        logger.info(f"PlannerAgent initialized with model={model}, temperature={temperature}, RAG={rag_status}")

    def plan_mission(
        self,
        mission: MissionCommand,
        current_state: Optional[RobotState] = None
    ) -> List[RobotAction]:
        """
        Generate action plan from natural language mission command.

        Args:
            mission: Mission command with natural language instruction
            current_state: Current robot state (optional, for context-aware planning)

        Returns:
            List of RobotAction objects forming the action plan

        Raises:
            ValueError: If command cannot be parsed or plan is unsafe
        """
        logger.info(f"Planning mission: {mission.command} (language={mission.language})")

        # RAG: Retrieve relevant knowledge (with environment detection in Story 3.3)
        rag_context = ""
        if self.knowledge_base:
            logger.info("Retrieving relevant knowledge from RAG...")
            rag_context = self._retrieve_rag_context(mission.command, current_state)
            logger.debug(f"RAG context retrieved: {len(rag_context)} characters")

        # Build planning prompt (with RAG context)
        prompt = self._build_planning_prompt(mission, current_state, rag_context)

        # Create planning task
        task = Task(
            description=prompt,
            agent=self.agent,
            expected_output="JSON array of robot actions with valid parameters"
        )

        # Execute planning using Crew.kickoff() (CrewAI latest API)
        try:
            # Create a temporary crew to execute the task
            from crewai import Crew

            crew = Crew(
                agents=[self.agent],
                tasks=[task],
                verbose=self.verbose
            )

            # Execute and get result
            crew_output = crew.kickoff()

            # Extract raw output from CrewOutput
            result = crew_output.raw if hasattr(crew_output, 'raw') else str(crew_output)

            # Parse result into RobotAction list
            action_plan = self._parse_action_plan(result)

            # DEBUG: Log detailed action plan for troubleshooting
            logger.debug(f"LLM raw response: {result[:500]}...")  # First 500 chars
            for i, action in enumerate(action_plan):
                logger.info(f"  Action {i+1}: {action.action.value} | x={action.x}, y={action.y}, relative={action.relative}, speed={action.speed}")

            # Validate plan
            self._validate_action_plan(action_plan, mission)

            logger.info(f"Generated action plan with {len(action_plan)} actions")
            return action_plan

        except Exception as e:
            logger.error(f"Mission planning failed: {e}")
            raise ValueError(f"Failed to plan mission: {e}")

    def _retrieve_rag_context(
        self,
        query: str,
        current_state: Optional[RobotState] = None
    ) -> str:
        """
        Retrieve relevant knowledge from ChromaDB with environment-based filtering.

        New in Story 3.3: Environment-aware RAG filtering
        - Detects environment from sensor data
        - Filters constraints by environment_type metadata
        - Falls back to unfiltered search if environment is "unknown"

        Args:
            query: User's mission command (used as search query)
            current_state: Current robot state for environment detection (optional)

        Returns:
            Formatted RAG context string
        """
        if not self.knowledge_base:
            return ""

        # Story 3.3: Detect environment from sensor data
        environment_type = "unknown"
        confidence = 0.0

        if current_state and current_state.sensors:
            try:
                env_classification = self.environment_detector.detect_environment(
                    current_state.sensors
                )
                environment_type = env_classification.environment_type
                confidence = env_classification.confidence

                logger.info(
                    f"Environment detected: {environment_type} (confidence: {confidence:.2f})"
                )
            except Exception as e:
                logger.warning(f"Environment detection failed: {e}. Using unfiltered RAG.")

        # Check if query contains location keywords (entrance, exit, 입구, 출구)
        location_keywords = ["entrance", "exit", "입구", "출구"]
        is_location_query = any(keyword in query.lower() for keyword in location_keywords)

        # Check if obstacles are nearby - add obstacle avoidance context
        obstacle_nearby = False
        if current_state and current_state.sensors and current_state.sensors.lidar_min_distance is not None:
            if current_state.sensors.lidar_min_distance < 1.0:
                obstacle_nearby = True
                # Append obstacle avoidance keywords to query
                query = f"{query} obstacle avoidance collision prevention"
                logger.info(f"Obstacle detected at {current_state.sensors.lidar_min_distance:.2f}m - including obstacle avoidance strategies in RAG")

        # Search capabilities (prioritize location info or obstacle avoidance if needed)
        if is_location_query or obstacle_nearby:
            # Get more results to ensure location info or obstacle strategies are included
            capabilities = self.knowledge_base.search_capabilities(query, n_results=5)
        else:
            capabilities = self.knowledge_base.search_capabilities(query, n_results=3)

        # Search constraints with environment filter (Story 3.3)
        if environment_type != "unknown" and confidence > 0.5:
            # Use environment-specific constraints
            logger.debug(f"Applying environment filter: {environment_type}")
            constraints = self.knowledge_base.search_constraints(
                query,
                n_results=5,  # Get more results when filtering by environment
                where={"environment_type": environment_type}
            )
        else:
            # Fallback to all constraints (backward compatible)
            logger.debug("Using unfiltered constraint search (environment unknown or low confidence)")
            constraints = self.knowledge_base.search_constraints(query, n_results=3)

        # Format using helper function
        context = format_rag_context(capabilities, constraints)

        return context

    def _build_planning_prompt(
        self,
        mission: MissionCommand,
        current_state: Optional[RobotState],
        rag_context: str = ""
    ) -> str:
        """Build planning prompt with context and RAG knowledge."""

        # Korean or English instructions
        if mission.language == "ko":
            instructions = self._get_korean_instructions()
        else:
            instructions = self._get_english_instructions()

        # RAG context section
        rag_section = ""
        if rag_context:
            rag_section = f"\n{rag_context}\n"

        # Add current state context (including sensors for obstacle awareness)
        state_context = ""
        if current_state:
            position = current_state.get_position()
            if position:
                state_context = f"\n\nCurrent robot position: X={position[0]:.2f}m, Y={position[1]:.2f}m"

                orientation = current_state.get_orientation()
                if orientation:
                    state_context += f", Yaw={orientation[2]:.1f}deg"

                # Add sensor data for obstacle awareness (Story 3.x: Multi-agent obstacle avoidance)
                sensors = current_state.sensors
                if sensors and sensors.lidar_min_distance is not None:
                    state_context += f"\n- Lidar: Min distance to obstacle: {sensors.lidar_min_distance:.2f}m"

                    # Warn if obstacles are nearby
                    if sensors.lidar_min_distance < 0.5:
                        state_context += f" ⚠️ **OBSTACLE NEARBY**"
                    if sensors.lidar_min_distance < 0.3:
                        state_context += f"\n- **WARNING: Very close to obstacle! Consider slower speeds or alternative paths**"

        # Add dynamic objects context (e.g., pickup object position)
        dynamic_objects_context = ""
        if self.dynamic_objects:
            dynamic_objects_context = "\n\n**DYNAMIC OBJECTS IN ENVIRONMENT:**"
            for obj_name, obj_info in self.dynamic_objects.items():
                if obj_name == "pickup_object" and isinstance(obj_info, dict) and "position" in obj_info:
                    # New format with approach position
                    pos = obj_info["position"]
                    approach = obj_info["approach"]
                    dynamic_objects_context += f"\n\n🚨 **CRITICAL - PICKUP OBJECT HANDLING:**"
                    dynamic_objects_context += f"\n- Object location (DO NOT GO HERE): X={pos['x']:.2f}m, Y={pos['y']:.2f}m, Z={pos['z']:.2f}m"
                    dynamic_objects_context += f"\n- **APPROACH POSITION (GO HERE FIRST)**: X={approach['x']:.2f}m, Y={approach['y']:.2f}m"
                    dynamic_objects_context += f"\n"
                    dynamic_objects_context += f"\n⚠️ **MANDATORY PICKUP SEQUENCE:**"
                    dynamic_objects_context += f"\n1. MOVE to APPROACH POSITION ({approach['x']:.2f}, {approach['y']:.2f}) - NOT object position!"
                    dynamic_objects_context += f"\n2. ARM_MOVE (shoulder_angle=70, elbow_angle=0) - arm extends forward to z=0.31m"
                    dynamic_objects_context += f"\n3. GRIP"
                    dynamic_objects_context += f"\n4. ARM_MOVE (lift: shoulder_angle=0, elbow_angle=0)"
                    dynamic_objects_context += f"\n5. MOVE (x=-0.5, relative=true) - BACKUP before turning"
                    dynamic_objects_context += f"\n6. Then proceed to destination"
                else:
                    # Fallback for simple format
                    dynamic_objects_context += f"\n- {obj_name}: X={obj_info.get('x', 0):.2f}m, Y={obj_info.get('y', 0):.2f}m"

        prompt = f"""
{instructions}
{rag_section}{dynamic_objects_context}
Mission Command: "{mission.command}"
Language: {mission.language}
Priority: {mission.priority}/10
Timeout: {mission.timeout_seconds}s{state_context}

Generate a JSON array of actions to complete this mission. Each action must follow this schema:

Actions available:
1. MOVE: Move to target coordinates (absolute or relative)
   {{"action": "move", "x": float (-5.0 to 5.0), "y": float (-5.0 to 5.0), "speed": float (0.1 to 2.0), "relative": bool (default: false), "reason": string}}
   - If relative=false (default): x/y are absolute world coordinates
   - If relative=true: x=forward/backward distance, y=left/right distance from current position and orientation

2. ROTATE: Rotate by angle (ALWAYS RELATIVE - how much to turn from current heading)
   {{"action": "rotate", "angle": float (-180 to 180), "speed": float (0.1 to 2.0), "reason": string}}
   - **CRITICAL**: angle is how many degrees to TURN from current heading, NOT target direction
   - "turn left 45 degrees" = angle=+45 (add 45° to current heading)
   - "turn right 30 degrees" = angle=-30 (subtract 30° from current heading)
   - Positive = counter-clockwise (left), Negative = clockwise (right)
   - **DO NOT** factor in current heading value - if user says "turn 45 degrees", angle=45!

3. SCAN: Scan area for duration (keep scans SHORT - sensors are fast)
   {{"action": "scan", "duration": float (0.1 to 2.0), "reason": string}}

4. WAIT: Wait for duration
   {{"action": "wait", "duration": float (0.1 to 5.0), "reason": string}}

5. STOP: Stop immediately
   {{"action": "stop", "reason": string}}

6. ARM_MOVE: Move robotic arm to specified joint positions
   {{"action": "arm_move", "shoulder_angle": float (-90 to 90), "elbow_angle": float (-115 to 115), "reason": string}}
   - shoulder_angle: shoulder joint angle in degrees (positive = forward/down, negative = backward/up)
   - elbow_angle: elbow joint angle in degrees (positive = bend down relative to upper arm)

   **ARM PHYSICAL SPECS & KINEMATICS:**
   - Arm mounted at z=0.22m height, x=0.05m forward on robot (on top of robot body)
   - Upper arm: 12cm, Forearm: 15cm (total reach ~27cm from arm base, 32cm from robot center)
   - Gripper can reach objects at z=0.22m to z=0.45m height
   - **CRITICAL FOR PICKUP (z=0.30m pedestal): shoulder_angle=70, elbow_angle=0**
     - This positions gripper at z≈0.31m, x≈0.30m from robot center

7. GRIP: Close gripper to grasp object
   {{"action": "grip", "gripper_force": float (0.0 to 1.0, default 0.5), "reason": string}}

8. RELEASE: Open gripper to release object
   {{"action": "release", "reason": string}}

Safety constraints:
- Position limits: -5m to 5m (10mx10m environment)
- Keep 0.3m safety margin from boundaries (-4.7m to 4.7m recommended)
- Speed limits: 0.1 to 0.2 m/s (CRITICAL: Use 0.15-0.2 m/s for safe obstacle avoidance with tinyllama reaction time)
- Rotation speed: 0.1 to 0.2 rad/s (approximately 6-11 deg/s)
- Duration limits: SCAN (0.1 to 2.0s), WAIT (0.1 to 5.0s) - keep scans SHORT

Return ONLY a valid JSON array, no additional text or markdown formatting.
"""
        return prompt

    def _get_korean_instructions(self) -> str:
        """Get instructions for Korean language input (written in English for LLM consistency)."""
        return """
You are an expert mission planner for rescue robots.
Convert Korean language commands into precise robot action sequences.

**Korean Keyword Mapping:**
- "이동" / "가다" / "향하다" (move/go/head) → MOVE action
- "회전" / "돌다" / "방향전환" (rotate/turn) → ROTATE action
- "탐색" / "스캔" / "찾다" (search/scan/find) → SCAN action
- "대기" / "기다리다" (wait) → WAIT action
- "정지" / "멈추다" (stop) → STOP action
- "팔 이동" / "팔 움직여" / "팔 위치" (move arm) → ARM_MOVE action
- "집다" / "잡다" / "그립" / "픽업" (grip/pick up/grasp) → GRIP action
- "놓다" / "놓아줘" / "릴리즈" / "내려놓다" (release/drop/let go) → RELEASE action

**IMPORTANT: MOVE Action Modes**
- MOVE supports **absolute coordinates (relative=false)** or **relative coordinates (relative=true)**
- relative=false (default): x/y are **absolute world coordinates**
- relative=true: x/y are **distances relative to current position and orientation**
  - x = forward(+) / backward(-) distance
  - y = left(+) / right(-) distance

**Command Processing Guide:**

1. **Location Keywords**: "입구" (entrance), "출구" (exit)
   - Look up absolute coordinates from Robot Knowledge Base
   - Example: "출구까지" (to exit) → Find exit (x, y) from Knowledge Base
   - Use MOVE x=exit_x, y=exit_y, relative=false
   - **Important**: For long distances, split into multiple waypoints (3m recommended)

2. **Absolute Position**: "X좌표 A, Y좌표 B로 이동" (move to X=A, Y=B)
   → MOVE x=A, y=B, relative=false

3. **Cardinal Direction Movement**: "동쪽/서쪽/남쪽/북쪽으로 N미터" (N meters east/west/south/north)
   - East "동쪽" (+X) → MOVE x=(current_x + N), y=current_y, relative=false
   - West "서쪽" (-X) → MOVE x=(current_x - N), y=current_y, relative=false
   - North "북쪽" (+Y) → MOVE x=current_x, y=(current_y + N), relative=false
   - South "남쪽" (-Y) → MOVE x=current_x, y=(current_y - N), relative=false

4. **Relative Movement**: "N미터 전진/후진" (N meters forward/backward)
   - "전진" (forward) → MOVE x=N, y=0, relative=true
   - "후진" (backward) → MOVE x=-N, y=0, relative=true
   - "좌측" (left) → MOVE x=0, y=N, relative=true
   - "우측" (right) → MOVE x=0, y=-N, relative=true

5. **Rotation**: "N도 회전" / "왼쪽으로 N도" / "오른쪽으로 N도"
   → ROTATE angle=N (ALWAYS relative to current heading)
   - **CRITICAL**: angle is ALWAYS how many degrees to TURN from current heading
   - "왼쪽으로 45도" (45 degrees left) = angle=+45
   - "오른쪽으로 30도" (30 degrees right) = angle=-30
   - Positive (+) = turn left (CCW), Negative (-) = turn right (CW)
   - **DO NOT factor in current heading value** - if user says "45도 회전", use angle=45!

**"Turn then Move" Commands:**
- "왼쪽으로 X도 방향으로 Y미터" → ROTATE angle=+X, MOVE x=Y, y=0, relative=true
- "오른쪽으로 X도 방향으로 Y미터" → ROTATE angle=-X, MOVE x=Y, y=0, relative=true
- "180도 회전 후 2미터 전진" → ROTATE angle=180, MOVE x=2, y=0, relative=true

**Obstacle Avoidance Guidelines:**
- When **obstacle detected (Lidar < 0.3m)**: Use slower speeds (0.15 m/s), add SCAN, rotate to find clear path
- When **very close (<0.3m)**: First action MUST be backward (MOVE x=-0.5, relative=true) for safety
- When **path blocked**: Try rotation (±45° to 90°) to find alternative path
- Use obstacle avoidance strategies from Robot Knowledge Base

**Examples:**
- "출구까지 가주세요" → Look up exit (4.85, 4.85) → MOVE x=4.85, y=4.85, relative=false
- "입구로 돌아가" → Look up entrance (0.0, 0.0) → MOVE x=0.0, y=0.0, relative=false
- "동쪽으로 3미터" → MOVE x=(current_x + 3), y=current_y, relative=false
- "3미터 전진" → MOVE x=3, y=0, relative=true
- "2미터 후진" → MOVE x=-2, y=0, relative=true
- "90도 회전" → ROTATE angle=90.0
- "왼쪽으로 45도 방향으로 2미터" → ROTATE angle=45, MOVE x=2, y=0, relative=true

**팔 물리적 사양:**
- 팔 장착 위치: z=0.22m, 로봇 중심에서 5cm 앞
- 상완: 12cm, 전완: 15cm (총 reach ~32cm from robot center)
- 그리퍼 도달 가능 높이: z=0.22m ~ z=0.45m
- 물체는 높은 받침대(z=0.30m) 위에 있음

**Arm Manipulation Examples:**
- "물체를 집어" / "그거 잡아" → GRIP (gripper_force=0.5 default)
- "물체를 놓아줘" / "내려놓아" → RELEASE
- "팔을 앞으로 뻗어" → ARM_MOVE (shoulder_angle=70, elbow_angle=0)  # 받침대 높이 (z=0.30m)
- "팔을 위로 올려" → ARM_MOVE (shoulder_angle=0, elbow_angle=0)
- "팔을 내려서 집어" → ARM_MOVE (shoulder_angle=70, elbow_angle=0)

**Pick and Place Sequence Example:**
"물체를 집어서 앞으로 1미터 가서 놓아줘" →
1. ARM_MOVE (position arm for pickup: shoulder_angle=70, elbow_angle=0) - reaches z=0.31m
2. GRIP (gripper_force=0.5)
3. ARM_MOVE (lift arm: shoulder_angle=0, elbow_angle=0)
4. **MOVE (x=-0.5, y=0, relative=true) - CRITICAL: Backup to clear pedestal before turning!**
5. MOVE (to destination)
6. ARM_MOVE (position for release: shoulder_angle=70, elbow_angle=0)
7. RELEASE

**IMPORTANT PICKUP RULE:**
After GRIP, you MUST add a BACKUP move (MOVE x=-0.5, relative=true) before any other movement!
This prevents collision with the pedestal when rotating toward the next destination.
"""

    def _get_english_instructions(self) -> str:
        """Get English language instructions."""
        return """
You are an expert mission planner for rescue robots.
Convert English commands into precise robot action sequences.

**Keyword Mapping:**
- "move" / "go" / "navigate" → MOVE action
- "rotate" / "turn" → ROTATE action
- "search" / "scan" / "find" → SCAN action
- "wait" → WAIT action
- "stop" → STOP action
- "move arm" / "arm position" / "extend arm" → ARM_MOVE action
- "pick up" / "grab" / "grasp" / "grip" → GRIP action
- "release" / "drop" / "let go" / "put down" → RELEASE action

**IMPORTANT: MOVE Action Modes**
- MOVE supports **absolute coordinates (relative=false)** or **relative coordinates (relative=true)**
- relative=false (default): x/y are **absolute world coordinates**
- relative=true: x/y are **distances relative to current position and orientation**
  - x = forward(+) / backward(-) distance
  - y = left(+) / right(-) distance

**Command Processing Guide:**

1. **Location Keywords**: "entrance", "exit"
   - Look up absolute coordinates from Robot Knowledge Base
   - Use MOVE x=location_x, y=location_y, relative=false
   - **Important**: For long distances, split into multiple waypoints (3m recommended)

2. **Absolute Position**: "move to X=A, Y=B"
   → MOVE x=A, y=B, relative=false

3. **Cardinal Direction Movement**: "N meters east/west/south/north"
   - East (+X) → MOVE x=(current_x + N), y=current_y, relative=false
   - West (-X) → MOVE x=(current_x - N), y=current_y, relative=false
   - North (+Y) → MOVE x=current_x, y=(current_y + N), relative=false
   - South (-Y) → MOVE x=current_x, y=(current_y - N), relative=false

4. **Relative Movement**: "N meters forward/backward/left/right"
   - "forward" → MOVE x=N, y=0, relative=true
   - "backward" → MOVE x=-N, y=0, relative=true
   - "left" → MOVE x=0, y=N, relative=true
   - "right" → MOVE x=0, y=-N, relative=true

5. **Rotation**: "turn left/right N degrees"
   → ROTATE angle=N (ALWAYS relative to current heading)
   - **CRITICAL**: angle is ALWAYS how many degrees to TURN from current heading
   - "turn left 45 degrees" = angle=+45
   - "turn right 30 degrees" = angle=-30
   - Positive (+) = turn left (CCW), Negative (-) = turn right (CW)
   - **DO NOT factor in current heading value** - if user says "turn 45 degrees", use angle=45!

**"Turn then Move" Commands:**
- "turn left X degrees then move Y meters" → ROTATE angle=+X, MOVE x=Y, y=0, relative=true
- "turn right X degrees then move Y meters" → ROTATE angle=-X, MOVE x=Y, y=0, relative=true
- "move Y meters in X degrees left direction" → ROTATE angle=+X, MOVE x=Y, y=0, relative=true

**Obstacle Avoidance Guidelines:**
- When **obstacle detected (Lidar < 0.3m)**: Use slower speeds (0.15 m/s), add SCAN, rotate to find clear path
- When **very close (<0.3m)**: First action MUST be backward (MOVE x=-0.5, relative=true) for safety
- When **path blocked**: Try rotation (±45° to 90°) to find alternative path
- Use obstacle avoidance strategies from Robot Knowledge Base

**Examples:**
- "go to exit" → Look up exit coordinates → MOVE x=exit_x, y=exit_y, relative=false
- "move 3 meters east" → MOVE x=(current_x + 3), y=current_y, relative=false
- "move forward 3 meters" → MOVE x=3, y=0, relative=true
- "back up 2 meters" → MOVE x=-2, y=0, relative=true
- "turn left 90 degrees" → ROTATE angle=90
- "turn left 45 degrees and move 2 meters" → ROTATE angle=45, MOVE x=2, y=0, relative=true

**Arm Physical Specifications:**
- Arm mounted at z=0.22m height, 5cm forward from robot center (on top of robot body)
- Upper arm: 12cm, Forearm: 15cm (total reach ~32cm from robot center)
- Gripper can reach objects at z=0.22m to z=0.45m height
- Objects are on taller pedestals at z=0.30m for comfortable pickup

**Arm Manipulation Examples:**
- "pick up the object" / "grab it" → GRIP (gripper_force=0.5 default)
- "release the object" / "put it down" → RELEASE
- "extend arm forward" → ARM_MOVE (shoulder_angle=70, elbow_angle=0)  # For pedestal pickup (z=0.30m)
- "raise arm up" → ARM_MOVE (shoulder_angle=0, elbow_angle=0)
- "lower arm for pickup" → ARM_MOVE (shoulder_angle=70, elbow_angle=0)

**Pick and Place Sequence Example:**
"pick up object and move 1 meter forward then drop it" →
1. ARM_MOVE (position arm for pickup: shoulder_angle=70, elbow_angle=0) - reaches z=0.31m
2. GRIP (gripper_force=0.5)
3. ARM_MOVE (lift arm: shoulder_angle=0, elbow_angle=0)
4. **MOVE (x=-0.5, y=0, relative=true) - CRITICAL: Backup to clear pedestal before turning!**
5. MOVE (to destination)
6. ARM_MOVE (position for release: shoulder_angle=70, elbow_angle=0)
7. RELEASE

**IMPORTANT PICKUP RULE:**
After GRIP, you MUST add a BACKUP move (MOVE x=-0.5, relative=true) before any other movement!
This prevents collision with the pedestal when rotating toward the next destination.
"""

    def _parse_action_plan(self, result: str) -> List[RobotAction]:
        """
        Parse planning result into RobotAction list.

        Args:
            result: Raw result string from LLM (expected JSON array)

        Returns:
            List of validated RobotAction objects
        """
        # Clean result (remove markdown formatting if present)
        result = result.strip()
        if result.startswith("```json"):
            result = result[7:]
        if result.startswith("```"):
            result = result[3:]
        if result.endswith("```"):
            result = result[:-3]
        result = result.strip()

        # Extract JSON array only (ignore trailing explanation text)
        # Find the first '[' and last ']' to extract just the JSON array
        json_start = result.find('[')
        json_end = result.rfind(']')

        if json_start == -1 or json_end == -1 or json_end < json_start:
            logger.error(f"No valid JSON array found in response: {result}")
            raise ValueError(f"Response does not contain a valid JSON array")

        # Extract only the JSON array part
        json_str = result[json_start:json_end+1]

        # Parse JSON
        try:
            actions_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {json_str}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")

        # Convert to RobotAction objects
        if not isinstance(actions_data, list):
            raise ValueError("Expected JSON array of actions")

        actions = []
        for i, action_data in enumerate(actions_data):
            try:
                # Convert action string to ActionType enum
                action_type = ActionType(action_data["action"])
                action_data["action"] = action_type

                # Create RobotAction (Pydantic validates automatically)
                action = RobotAction(**action_data)
                actions.append(action)

            except Exception as e:
                logger.error(f"Failed to parse action {i}: {action_data}, error: {e}")
                raise ValueError(f"Invalid action at index {i}: {e}")

        return actions

    def _validate_action_plan(
        self,
        actions: List[RobotAction],
        mission: MissionCommand
    ) -> None:
        """
        Validate action plan for safety and feasibility.

        Args:
            actions: List of actions to validate
            mission: Original mission command

        Raises:
            ValueError: If plan is invalid or unsafe
        """
        if len(actions) == 0:
            raise ValueError("Action plan is empty")

        if len(actions) > 20:
            logger.warning(f"Action plan has {len(actions)} actions (>20), may be too complex")

        # Estimate total execution time
        total_time = 0.0
        for action in actions:
            if action.action == ActionType.MOVE:
                # Estimate move time from distance and speed
                if action.x is not None and action.y is not None and action.speed:
                    distance = (action.x**2 + action.y**2) ** 0.5
                    total_time += distance / action.speed
            elif action.action in [ActionType.SCAN, ActionType.WAIT]:
                if action.duration:
                    total_time += action.duration
            elif action.action == ActionType.ROTATE:
                # Estimate rotation time (assume 45°/sec at default speed)
                if action.angle and action.speed:
                    total_time += abs(action.angle) / (45.0 * action.speed)

        # Check timeout
        if total_time > mission.timeout_seconds:
            logger.warning(
                f"Estimated execution time {total_time:.1f}s exceeds "
                f"mission timeout {mission.timeout_seconds}s"
            )

        logger.debug(f"Action plan validated: {len(actions)} actions, ~{total_time:.1f}s estimated")

    def replan_mission(
        self,
        failure_info: ReplanRequest,
        mission: MissionCommand,
        current_state: RobotState
    ) -> List[RobotAction]:
        """
        Generate alternative action plan after mission failure.

        Uses failure analysis to create a new plan that avoids the previous failure.
        Leverages RAG to search for obstacle avoidance and alternative strategies.

        Args:
            failure_info: Failure analysis from Verifier Agent
            mission: Original mission command
            current_state: Current robot state

        Returns:
            List of alternative actions to retry the mission

        Raises:
            ValueError: If alternative plan cannot be generated
        """
        logger.info(
            f"Replanning mission (retry {failure_info.retry_count}/3) "
            f"due to {failure_info.failure_reason.value}"
        )

        # Build replanning prompt with failure context
        prompt = self._build_replan_prompt(failure_info, mission, current_state)

        # Create replanning task
        task = Task(
            description=prompt,
            agent=self.agent,
            expected_output="JSON array of alternative actions"
        )

        try:
            # Execute planning via Crew (CrewAI requires Crew to execute tasks)
            from crewai import Crew
            crew = Crew(
                agents=[self.agent],
                tasks=[task],
                verbose=False
            )
            result = crew.kickoff()

            # Convert CrewOutput to string
            result_str = str(result.raw) if hasattr(result, 'raw') else str(result)

            # Parse actions from result
            actions = self._parse_action_plan(result_str)

            # Validate alternative plan
            self._validate_action_plan(actions, mission)

            logger.info(f"Alternative plan generated: {len(actions)} actions")
            return actions

        except Exception as e:
            logger.error(f"Replanning failed: {e}")
            raise ValueError(f"Failed to generate alternative plan: {e}")

    def _build_replan_prompt(
        self,
        failure_info: ReplanRequest,
        mission: MissionCommand,
        current_state: RobotState
    ) -> str:
        """
        Build replanning prompt with failure context and RAG strategies.

        Args:
            failure_info: Failure analysis data
            mission: Original mission command
            current_state: Current robot state

        Returns:
            Formatted prompt for replanning
        """
        # Use RAG to get alternative strategies based on failure type
        rag_context = ""
        if self.knowledge_base:
            # Search for strategies based on failure reason
            # Include mission command to capture location keywords (entrance, exit, 입구, 출구)
            if failure_info.failure_reason.value == "obstacle_collision":
                rag_query = f"{mission.command} obstacle avoidance strategies collision recovery"
            elif failure_info.failure_reason.value == "path_blocked":
                rag_query = f"{mission.command} alternative path planning blocked route navigation"
            elif failure_info.failure_reason.value == "goal_unreached":
                rag_query = f"{mission.command} goal reaching strategies navigation retry"
            else:
                rag_query = f"{mission.command} {failure_info.failure_reason.value} recovery strategies"

            # Check if mission command contains location keywords - get more results if so
            location_keywords = ["entrance", "exit", "입구", "출구"]
            is_location_query = any(keyword in mission.command.lower() for keyword in location_keywords)
            k_results = 5 if is_location_query else 3

            logger.debug(f"RAG query for replanning: {rag_query} (k={k_results})")
            rag_results = self.knowledge_base.search(rag_query, k=k_results)
            # Story 3.6: Extract capabilities and constraints from search results
            rag_context = format_rag_context(
                rag_results.get('capabilities', []),
                rag_results.get('constraints', [])
            )

        # Get current position and orientation
        position = current_state.get_position()
        position_str = f"X={position[0]:.2f}m, Y={position[1]:.2f}m, Z={position[2]:.2f}m" if position else "Unknown"

        # Get current heading (orientation) - CRITICAL for rotate angle calculation
        orientation = current_state.get_orientation()
        if orientation:
            position_str += f", Heading={orientation[2]:.1f}° (current facing direction)"

        # Get original target (if detour occurred)
        original_target_str = ""
        if failure_info.original_target_x is not None and failure_info.original_target_y is not None:
            original_target_str = f"\n- **ORIGINAL TARGET (before detour)**: X={failure_info.original_target_x:.2f}m, Y={failure_info.original_target_y:.2f}m"
            # Calculate remaining distance
            if position:
                import math
                dx = failure_info.original_target_x - position[0]
                dy = failure_info.original_target_y - position[1]
                remaining_dist = math.sqrt(dx**2 + dy**2)
                original_target_str += f"\n- **REMAINING DISTANCE to original target**: {remaining_dist:.2f}m"

        # Get sensor info
        sensors = failure_info.sensor_data
        lidar_info = f"Min distance: {sensors.lidar_min_distance:.2f}m" if sensors.lidar_min_distance else "No data"

        # Check if robot is too close to obstacle
        too_close_warning = ""
        if sensors.lidar_min_distance and sensors.lidar_min_distance < 0.3:
            too_close_warning = f"\n- ⚠️ **WARNING: Robot is TOO CLOSE to obstacle ({sensors.lidar_min_distance:.2f}m < 0.3m)**\n- **FIRST ACTION MUST BE BACKWARD MOVEMENT** to create safe distance"

        # Previous plan summary
        previous_actions = ", ".join([
            action.action.value for action in failure_info.previous_plan
        ]) if failure_info.previous_plan else "None"

        # Add dynamic objects context (same as plan_mission)
        dynamic_objects_context = ""
        if self.dynamic_objects:
            for obj_name, obj_info in self.dynamic_objects.items():
                if obj_name == "pickup_object" and isinstance(obj_info, dict) and "position" in obj_info:
                    pos = obj_info["position"]
                    approach = obj_info["approach"]
                    dynamic_objects_context += f"\n\n🚨 **PICKUP OBJECT INFO (for ARM operations):**"
                    dynamic_objects_context += f"\n- Object: X={pos['x']:.2f}m, Y={pos['y']:.2f}m, Z={pos['z']:.2f}m"
                    dynamic_objects_context += f"\n- Approach position: X={approach['x']:.2f}m, Y={approach['y']:.2f}m"
                    dynamic_objects_context += f"\n- **ARM ANGLES FOR PICKUP: shoulder_angle=70, elbow_angle=0** (reaches z=0.31m)"
                    dynamic_objects_context += f"\n- **ARM ANGLES FOR LIFT: shoulder_angle=0, elbow_angle=0**"

        prompt = f"""
**MISSION REPLANNING REQUEST**

**Original Command:** "{mission.command}"
**Language:** {mission.language}
**Retry Attempt:** {failure_info.retry_count}/3

**FAILURE ANALYSIS:**
- Reason: {failure_info.failure_reason.value}
- Details: {failure_info.failure_details or "Not provided"}

**CURRENT ROBOT STATE:**
- Position: {position_str}{original_target_str}
- Lidar: {lidar_info}{too_close_warning}
- Status: {current_state.status.value}

**PREVIOUS PLAN (FAILED):**
{previous_actions}

**ALTERNATIVE STRATEGIES (from knowledge base):**
{rag_context if rag_context else "No specific strategies found - use general replanning approach"}
{dynamic_objects_context}

**YOUR TASK:**
Generate an ALTERNATIVE action plan that:
1. Avoids the previous failure (e.g., different route if path blocked, slower speed if collision)
2. Still achieves the original mission goal
3. Considers current sensor data (obstacles detected)
4. Is safer and more conservative than the first attempt
5. **IMPORTANT**:
   - If command mentions "출구" or "exit": Use knowledge base to find exit coordinates (4.85, 4.85)
   - If command is relative movement (e.g., "앞으로 Xm", "forward"): Use ORIGINAL TARGET coordinates provided above
   - ORIGINAL TARGET is the absolute position the robot was trying to reach - use it directly!

**REPLANNING GUIDELINES:**
- If OBSTACLE_COLLISION and robot is TOO CLOSE to obstacle (<0.3m):
  **CRITICAL - EMERGENCY ESCAPE MODE**: First action MUST be backward movement (MOVE x=-0.5, y=0, relative=true, speed=0.15)
  Safety system allows backward movement even when obstacle < 0.3m (emergency escape exception)
  Then scan, rotate to find clear path, and proceed with alternative route
- If OBSTACLE_COLLISION but robot has clearance (>0.3m): Use slower speeds (0.15 m/s), add scan actions before movement, consider rotation to find clear path
- If PATH_BLOCKED: Find alternative route (use rotation ±45°~90° to explore, then move), add obstacle detection scans
- **If GOAL_UNREACHED after detour (ORIGINAL TARGET provided)**:
  **CRITICAL**: The obstacle was ALREADY avoided by reactive control. Generate ONLY 1-2 actions maximum.
  Use the ORIGINAL TARGET coordinates (NOT exit coordinates unless command mentions "출구" or "exit").
  Return a direct move to ORIGINAL TARGET with absolute coordinates and speed 0.25 m/s.
  Optional: Add ONE scan before the move if sensors show obstacles nearby.
  DO NOT add rotations. DO NOT add multiple scans. DO NOT use relative moves. DO NOT use intermediate waypoints.
- If GOAL_UNREACHED without detour: Break down movement into smaller steps, add verification scans

**SAFETY SYSTEM BEHAVIOR:**
- Backward movement (relative=true, x<0): Forward obstacle checks are SKIPPED to allow emergency escape from tight spaces
- Rotation: More lenient checks to allow maneuvering when trapped
- Forward movement: Full safety validation (0.3m minimum clearance required)

**OUTPUT FORMAT:**
Return ONLY a JSON array of actions. Each action must have:
- "action": one of [move, rotate, scan, wait, stop, arm_move, grip, release]
- Required parameters based on action type

**ARM ACTIONS (for pickup/manipulation tasks):**
- arm_move: {{"action": "arm_move", "shoulder_angle": 70, "elbow_angle": 0}} for pickup position (reaches z=0.31m)
- arm_move: {{"action": "arm_move", "shoulder_angle": 0, "elbow_angle": 0}} for lift/home position
- grip: {{"action": "grip", "gripper_force": 0.5}}
- release: {{"action": "release"}}

**IMPORTANT - MOVE action format:**
- MOVE supports both absolute and relative coordinates
- For "forward/backward" commands: {{"action": "move", "x": distance, "y": 0.0, "relative": true}}
- For absolute positions: {{"action": "move", "x": target_x, "y": target_y, "relative": false}}
- relative=true: x=forward(+)/backward(-), y=left(+)/right(-)
- relative=false: x/y are world coordinates

**IMPORTANT - ROTATE action format:**
- ROTATE angle is RELATIVE to robot's current heading
- Example: If robot heading=90° and target direction=135°, use angle=45 (turn left 45°)
- Positive angle = turn left (CCW), Negative angle = turn right (CW)
- Use current heading provided above to calculate relative rotation needed

Example 1 - When TOO CLOSE to obstacle (<0.3m):
[
  {{"action": "move", "x": -0.5, "y": 0.0, "relative": true, "speed": 0.15}},
  {{"action": "scan", "duration": 0.5}},
  {{"action": "rotate", "angle": 45, "speed": 0.15}},
  {{"action": "scan", "duration": 0.5}},
  {{"action": "move", "x": 1.0, "y": 0.0, "relative": true, "speed": 0.2}}
]

Example 2 - Normal obstacle avoidance (clearance >0.3m):
[
  {{"action": "scan", "duration": 0.5}},
  {{"action": "rotate", "angle": 45, "speed": 0.15}},
  {{"action": "move", "x": 1.0, "y": 0.0, "relative": true, "speed": 0.2}},
  {{"action": "scan", "duration": 0.5}}
]

Example 3 - Backward movement (후진):
[
  {{"action": "scan", "duration": 0.5}},
  {{"action": "move", "x": -2.0, "y": 0.0, "relative": true, "speed": 0.2}},
  {{"action": "scan", "duration": 0.5}}
]

Generate the alternative action plan now:
"""
        return prompt


class PlannerAgentFactory:
    """Factory for creating PlannerAgent instances."""

    _instance: Optional[PlannerAgent] = None

    @classmethod
    def create(
        cls,
        api_key: str,
        knowledge_base: Optional[RobotKnowledgeBase] = None,
        model: str = "gpt-4o",
        temperature: float = 0.3,
        verbose: bool = True
    ) -> PlannerAgent:
        """
        Create or return singleton PlannerAgent instance.

        Args:
            api_key: OpenAI API key
            knowledge_base: RobotKnowledgeBase for RAG (optional)
            model: LLM model name
            temperature: LLM temperature
            verbose: Enable verbose logging

        Returns:
            PlannerAgent instance
        """
        if cls._instance is None:
            cls._instance = PlannerAgent(
                api_key=api_key,
                knowledge_base=knowledge_base,
                model=model,
                temperature=temperature,
                verbose=verbose
            )
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None
