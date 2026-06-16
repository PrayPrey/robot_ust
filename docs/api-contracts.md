# API Contracts

**Generated:** 2025-12-16
**API Version:** 1.0.0
**Base URL:** `http://localhost:8000`

---

## Overview

LLM_ROBOT_2 provides a FastAPI-based REST API and WebSocket endpoints for robot control and monitoring.

## REST API Endpoints

### Health Check

```http
GET /health
```

**Response:** `HealthResponse`
```json
{
  "status": "ok",
  "timestamp": "2025-12-16T10:00:00.000Z",
  "details": {
    "uptime_seconds": 3600.5,
    "active_connections": 2,
    "orchestrator_status": "ready",
    "total_connections": 15
  }
}
```

| Status | Description |
|--------|-------------|
| `ok` | System fully operational |
| `degraded` | Orchestrator not initialized |

---

### Get Robot Status

```http
GET /api/status
```

**Response:** `SystemStatus`
```json
{
  "position": [2.5, 0.1, 0.0],
  "sensors": {
    "lidar_min": 0.45,
    "lidar_avg": 1.2,
    "camera_active": true,
    "yaw": 45.0,
    "battery": 85.0
  },
  "mission_state": "executing",
  "reactive_log_summary": {
    "CRITICAL": 0,
    "MODERATE": 2,
    "NORMAL": 10
  },
  "timestamp": "2025-12-16T10:30:45.123Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `position` | `tuple[float, float, float]` | X, Y, Z coordinates |
| `sensors` | `dict` | Sensor readings summary |
| `mission_state` | `string` | idle, executing, failed, complete |
| `reactive_log_summary` | `dict` | Intervention counts by type |

---

### Execute Mission

```http
POST /api/mission
Content-Type: application/json
```

**Request:** `MissionRequest`
```json
{
  "command": "3미터 전진하세요",
  "language": "ko",
  "priority": 5
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `command` | `string` | Yes | - | Natural language command |
| `language` | `string` | No | `"ko"` | Language code (ko/en) |
| `priority` | `int` | No | `5` | Priority 1-10 |

**Response:** `MissionResponse`
```json
{
  "success": true,
  "message": "Mission completed successfully",
  "duration_seconds": 12.5,
  "final_position": [5.0, 0.0, 0.0],
  "reactive_events": [
    {
      "timestamp": "2025-12-16T10:30:45.123Z",
      "intervention_type": "MODERATE",
      "reason": "Obstacle at 0.35m",
      "action_taken": "DETOUR"
    }
  ]
}
```

**Error Responses:**

| Status | Description |
|--------|-------------|
| `503` | Orchestrator not initialized |
| `500` | Mission execution failed |

---

### Emergency Stop

```http
POST /api/stop
```

**Response:**
```json
{
  "success": true,
  "message": "Robot stopped successfully",
  "timestamp": "2025-12-16T10:30:45.123Z"
}
```

---

## WebSocket Endpoints

### Mission Control

```
WebSocket: /ws/control
```

**Client → Server (Command):**
```json
{
  "command": "장애물을 회피하며 5미터 전진하세요",
  "language": "ko",
  "priority": 5
}
```

**Server → Client (Acknowledgment):**
```json
{
  "status": "executing",
  "message": "Mission started: 장애물을 회피하며 5미터 전진하세요"
}
```

**Server → Client (Result):**
```json
{
  "status": "completed",
  "success": true,
  "message": "Mission completed successfully",
  "attempts": 1,
  "duration_seconds": 12.5,
  "final_position": [5.0, 0.0, 0.0],
  "data": { ... }
}
```

---

### Real-time Status

```
WebSocket: /ws/robot-status
```

**Server → Client (10Hz broadcast):**
```json
{
  "type": "status_update",
  "data": {
    "position": [2.5, 0.1, 0.0],
    "sensors": {
      "lidar_min": 0.45,
      "lidar_avg": 1.2,
      "camera_active": true,
      "yaw": 45.0,
      "battery": 85.0
    },
    "mission_state": "executing",
    "reactive_log_summary": {},
    "timestamp": "2025-12-16T10:30:45.123Z"
  }
}
```

**Client → Server (Control):**
```json
{
  "action": "toggle_broadcast",
  "enabled": true
}
```

---

## Data Schemas

### MissionCommand (Internal)

```python
class MissionCommand(BaseModel):
    command: str                    # Natural language command
    language: str = "ko"            # ko or en
    priority: int = 5               # 1-10
    timeout_seconds: float = 60.0   # Mission timeout
    action_plan: List[RobotAction] = []
    status: MissionStatus = MissionStatus.PENDING
    retry_count: int = 0
    starting_position_x: Optional[float] = None
    starting_position_y: Optional[float] = None
    starting_yaw: Optional[float] = None
```

### RobotAction

```python
class RobotAction(BaseModel):
    action: ActionType              # move, rotate, scan, wait, stop
    x: Optional[float] = None       # Target X or forward distance
    y: Optional[float] = None       # Target Y or lateral distance
    angle: Optional[float] = None   # Rotation angle (degrees)
    speed: Optional[float] = 0.2    # Movement speed (m/s)
    duration: Optional[float] = None # Action duration (seconds)
    relative: bool = False          # Relative vs absolute coords
    reason: Optional[str] = None    # Explanation
```

### ActionType

```python
class ActionType(str, Enum):
    MOVE = "move"       # Move to position
    ROTATE = "rotate"   # Rotate by angle
    SCAN = "scan"       # Scan environment
    WAIT = "wait"       # Wait for duration
    STOP = "stop"       # Emergency stop
```

### RobotState

```python
class RobotState(BaseModel):
    status: RobotStatus
    position_x: float
    position_y: float
    position_z: float
    orientation_roll: float
    orientation_pitch: float
    orientation_yaw: float
    sensors: SensorData
    battery_level: float = 100.0
    failure_reason: Optional[FailureReason] = None
    reactive_log: List[Dict] = []
```

---

## Authentication

**Note:** Current implementation does not include authentication. For production:

- Implement OAuth 2.0 or JWT tokens
- Add API key authentication
- Configure CORS for specific origins
- Use HTTPS/WSS

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/api/mission` | 10 req/min |
| `/api/status` | 60 req/min |
| WebSocket | 10 concurrent connections |

---

## Error Handling

All errors return JSON with consistent structure:

```json
{
  "detail": "Error description"
}
```

| HTTP Status | Meaning |
|-------------|---------|
| 400 | Invalid request format |
| 500 | Internal server error |
| 503 | Service unavailable (orchestrator not ready) |

---

*Generated by BMad Document Project Workflow*
