# Data Models

**Generated:** 2025-12-16
**Framework:** Pydantic v2

---

## Overview

LLM_ROBOT_2 uses Pydantic models for data validation across all components. Models are organized in `/src/schemas/`.

---

## Core Models

### MissionCommand

**Location:** `src/schemas/mission_command.py`

The primary input for mission execution.

```python
class MissionCommand(BaseModel):
    """Natural language mission command with execution state."""

    # Input fields
    command: str                          # Natural language command (Korean/English)
    language: str = "ko"                  # Language code
    priority: int = Field(default=5, ge=1, le=10)  # Mission priority
    timeout_seconds: float = 60.0         # Max execution time

    # Execution state
    action_plan: List[RobotAction] = []   # Generated action sequence
    status: MissionStatus = MissionStatus.PENDING
    retry_count: int = 0                  # Retry attempts
    current_action_index: int = 0         # Current action being executed

    # Position tracking (for relative movement verification)
    starting_position_x: Optional[float] = None
    starting_position_y: Optional[float] = None
    starting_yaw: Optional[float] = None
```

**MissionStatus Enum:**
```python
class MissionStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
```

---

### RobotAction

**Location:** `src/schemas/robot_action.py`

Individual robot action in an action plan.

```python
class RobotAction(BaseModel):
    """Single robot action with parameters."""

    action: ActionType                    # Action type enum

    # Position parameters (for MOVE)
    x: Optional[float] = Field(None, ge=-5.0, le=5.0)
    y: Optional[float] = Field(None, ge=-5.0, le=5.0)
    relative: bool = False                # True: relative to robot, False: world coords

    # Rotation parameters (for ROTATE)
    angle: Optional[float] = Field(None, ge=-180.0, le=180.0)  # Degrees

    # Speed parameters
    speed: Optional[float] = Field(0.2, ge=0.1, le=2.0)  # m/s or rad/s

    # Duration parameters (for SCAN, WAIT)
    duration: Optional[float] = Field(None, ge=0.1, le=10.0)  # Seconds

    # Metadata
    reason: Optional[str] = None          # Explanation for action
```

**ActionType Enum:**
```python
class ActionType(str, Enum):
    MOVE = "move"       # Move to position (absolute or relative)
    ROTATE = "rotate"   # Rotate by angle (always relative)
    SCAN = "scan"       # Scan environment for duration
    WAIT = "wait"       # Wait for duration
    STOP = "stop"       # Emergency stop
```

---

### RobotState

**Location:** `src/schemas/robot_state.py`

Complete robot state including position, sensors, and status.

```python
class RobotState(BaseModel):
    """Current robot state with all sensor data."""

    # Status
    status: RobotStatus = RobotStatus.IDLE

    # Position (world coordinates)
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0

    # Orientation (degrees)
    orientation_roll: float = 0.0
    orientation_pitch: float = 0.0
    orientation_yaw: float = 0.0

    # Sensor data
    sensors: SensorData = Field(default_factory=SensorData)

    # System state
    battery_level: float = Field(100.0, ge=0.0, le=100.0)
    failure_reason: Optional[FailureReason] = None

    # Reactive controller log
    reactive_log: List[Dict[str, Any]] = []

    # Original target (for detour tracking)
    original_target_x: Optional[float] = None
    original_target_y: Optional[float] = None

    # Methods
    def get_position(self) -> Tuple[float, float, float]: ...
    def get_orientation(self) -> Tuple[float, float, float]: ...
    def is_operational(self) -> bool: ...
```

**RobotStatus Enum:**
```python
class RobotStatus(str, Enum):
    IDLE = "idle"
    MOVING = "moving"
    ROTATING = "rotating"
    SCANNING = "scanning"
    STOPPED = "stopped"
    ERROR = "error"
```

---

### SensorData

**Location:** `src/schemas/robot_state.py`

Aggregated sensor readings.

```python
class SensorData(BaseModel):
    """Multi-sensor data aggregation."""

    # Lidar
    lidar_min_distance: Optional[float] = None  # Min obstacle distance (m)
    lidar_avg_distance: Optional[float] = None  # Average distance
    lidar_readings: List[float] = []            # Raw readings

    # Camera
    camera_has_data: bool = False
    camera_frame: Optional[bytes] = None

    # IMU / Orientation
    yaw: Optional[float] = None                 # Current heading (degrees)

    # GPS (simulated)
    gps_position: Optional[Tuple[float, float, float]] = None
```

---

### ReplanRequest

**Location:** `src/schemas/replan_request.py`

Failure context for replanning.

```python
class ReplanRequest(BaseModel):
    """Request for alternative action plan after failure."""

    failure_reason: FailureReason             # Why previous plan failed
    sensor_data: SensorData                   # Current sensor readings
    previous_plan: List[RobotAction]          # Failed action sequence
    retry_count: int                          # Current retry number
    original_command: str                     # Original mission command
    failure_details: Optional[str] = None     # Detailed failure description

    # Original target (for detour recovery)
    original_target_x: Optional[float] = None
    original_target_y: Optional[float] = None
```

**FailureReason Enum:**
```python
class FailureReason(str, Enum):
    OBSTACLE_COLLISION = "obstacle_collision"
    PATH_BLOCKED = "path_blocked"
    GOAL_UNREACHED = "goal_unreached"
    TIMEOUT = "timeout"
    SENSOR_FAILURE = "sensor_failure"
    SAFETY_VIOLATION = "safety_violation"
    UNKNOWN = "unknown"
```

---

## Web API Models

**Location:** `src/web/schemas.py`

### MissionRequest

```python
class MissionRequest(BaseModel):
    """Web API mission request."""

    command: str                              # Natural language command
    language: str = "ko"                      # ko or en
    priority: int = Field(default=5, ge=1, le=10)
```

### MissionResponse

```python
class MissionResponse(BaseModel):
    """Web API mission response."""

    success: bool
    message: str
    duration_seconds: float
    final_position: Tuple[float, float, float]
    reactive_events: List[Dict[str, Any]] = []
```

### SystemStatus

```python
class SystemStatus(BaseModel):
    """Real-time system status for WebSocket broadcast."""

    position: Tuple[float, float, float]
    sensors: Dict[str, Any]
    mission_state: str                        # idle, executing, failed, complete
    reactive_log_summary: Dict[str, int]
    timestamp: datetime
```

### HealthResponse

```python
class HealthResponse(BaseModel):
    """Health check response."""

    status: str                               # ok or degraded
    timestamp: datetime
    details: Dict[str, Any]
```

---

## Safety Models

**Location:** `src/safety/constraints.py`

### SafetyConstraints

```python
class SafetyConstraints(BaseModel):
    """Robot safety limits."""

    # Position limits (m)
    min_x: float = -5.0
    max_x: float = 5.0
    min_y: float = -5.0
    max_y: float = 5.0

    # Speed limits (m/s)
    max_speed: float = 2.0
    min_speed: float = 0.1

    # Obstacle clearance (m)
    min_obstacle_distance: float = 0.3

    # Battery threshold (%)
    min_battery_level: float = 20.0

    # Timeout (s)
    max_mission_duration: float = 60.0
```

---

## RAG Models

**Location:** `src/rag/knowledge_base.py`

### CapabilityDocument

```python
class CapabilityDocument(TypedDict):
    """Robot capability entry in ChromaDB."""

    id: str
    content: str                              # Capability description
    metadata: Dict[str, Any]                  # Tags, categories
    embedding: List[float]                    # Vector embedding
```

### ConstraintDocument

```python
class ConstraintDocument(TypedDict):
    """Environment constraint entry in ChromaDB."""

    id: str
    content: str                              # Constraint description
    metadata: Dict[str, Any]                  # environment_type, severity
    embedding: List[float]                    # Vector embedding
```

---

## Model Relationships

```
MissionCommand
    ├── action_plan: List[RobotAction]
    └── status: MissionStatus

RobotState
    ├── sensors: SensorData
    ├── status: RobotStatus
    └── failure_reason: FailureReason

ReplanRequest
    ├── failure_reason: FailureReason
    ├── sensor_data: SensorData
    └── previous_plan: List[RobotAction]

MissionRequest → MissionCommand (conversion)
SystemStatus ← RobotState (extraction)
```

---

*Generated by BMad Document Project Workflow*
