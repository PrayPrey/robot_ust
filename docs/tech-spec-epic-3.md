# Epic Technical Specification: Advanced Real-time Control & Web Interface

Date: 2025-11-02
Author: BMad (Scrum Master - Bob)
Epic ID: 3
Status: Approved
Version: 1.0

---

## Overview

Epic 3 transforms the LLM_ROBOT_2 multi-agent system from a simulation-based proof-of-concept into a **production-ready platform** capable of real-time reactive control and remote web-based operation. Building upon the successfully completed Epic 1 (Foundation) and Epic 2 (Advanced Features), this epic introduces three major capabilities: (1) **Hybrid Reactive Controller** that combines rule-based emergency responses with local LLM-powered decision-making for obstacle avoidance during mission execution, (2) **FastAPI Web Control Server** with WebSocket support for natural language commands from anywhere, and (3) **Environment-Aware Planning** that automatically adapts mission strategies based on detected environmental conditions (indoor/outdoor/warehouse/hospital).

The epic maintains strict backward compatibility with the existing Planner/Actor/Verifier multi-agent workflow, layering reactive capabilities on top without replacing core components. This approach reduces riskwhile extending the system's practical utility from controlled simulation scenarios to dynamic real-world deployment contexts.

## Objectives and Scope

**In-Scope:**
- Ollama tinyllama (1.1B param) installation, validation, and integration for reactive decisions
- 3-level hybrid reactive controller (CRITICAL/MODERATE/NORMAL) with <1200ms P90 latency for AI decisions
- Real-time sensor monitoring during action execution (64ms polling interval)
- FastAPI server with WebSocket endpoints for bidirectional communication
- Basic HTML/JavaScript web UI for natural language robot control
- Environment detection using rule-based sensor analysis (GPS, Lidar, Camera)
- RAG extension with environment-specific metadata filtering (ChromaDB)
- Integration testing framework covering reactive + web + environment components
- Performance benchmarking against Epic 2 baseline (collision rate, success rate, replanning frequency)

**Out-of-Scope (Deferred):**
- Production-grade React UI dashboard (Story 3.4 - optional enhancement)
- Multi-robot coordination or fleet management
- Physical robot deployment (remains Webots simulation-based)
- Advanced computer vision for obstacle classification
- Real-time video streaming to web UI
- SSL/TLS encryption for web server (development-only deployment)
- User authentication and authorization

## System Architecture Alignment

Epic 3 extends the **layered architecture** established in Epics 1-2:

**Preserved Components (No Changes):**
- CrewAI Planner/Actor/Verifier agents (Epic 1) - remain the core mission execution flow
- Pydantic schemas for RobotAction, RobotState, MissionCommand (Epic 1)
- ChromaDB RAG system for robot capabilities and constraints (Epic 2)
- Safety Validator with collision prevention rules (Epic 2.3)
- Failure recovery and replanning mechanisms (Epic 2.4)
- Loguru + OpenLit monitoring infrastructure (Epic 2.5)

**New Components (Epic 3 Additions):**
- `src/reactive/hybrid_controller.py` - HybridReactiveController class (Story 3.1)
- `src/utils/environment_detector.py` - EnvironmentDetector for sensor-based classification (Story 3.3)
- `api/server.py` - FastAPI application with WebSocket handlers (Story 3.2)
- `api/templates/index.html` - Basic web UI (Story 3.2)
- `ui/` directory - Optional React application (Story 3.4, deferred)

**Architectural Constraints Met:**
- **Latency Requirements:** CRITICAL decisions <1ms (rules), MODERATE decisions <1200ms P90 (Ollama tinyllama), NORMAL <10ms (passthrough)
- **Non-Blocking Execution:** Reactive controller operates asynchronously without blocking Planner/Actor workflow
- **Backward Compatibility:** All 270+ Epic 1-2 tests must continue passing (regression requirement)
- **Technology Stack Consistency:** Python 3.11+, existing dependency set extended with FastAPI, Ollama client, optional React

**Integration Points:**
- ActorAgent.\_execute\_move\_with\_reactive() - injects reactive checks during action execution
- VerifierAgent adjusts tolerance ranges based on reactive\_log context
- PlannerAgent.\_retrieve\_rag\_context() - extended with environment-based filtering
- WebSocket → Orchestrator.execute\_mission() - enables remote control

## Detailed Design

### Services and Modules

| Module | Responsibility | Inputs | Outputs | Owner |
|--------|---------------|--------|---------|-------|
| **HybridReactiveController** (`src/reactive/hybrid_controller.py`) | Real-time obstacle avoidance during action execution using 3-level decision system (CRITICAL/MODERATE/NORMAL) | SensorData, current RobotAction | ReactiveDecision (action: STOP/DETOUR/CONTINUE, detour_plan, execution_time) | Story 3.1 |
| **FastAPI Server** (`api/server.py`) | HTTP/WebSocket server for remote mission control and status broadcasting | MissionRequest (natural language command) via WebSocket | MissionResult, real-time robot status updates (10Hz) | Story 3.2 |
| **EnvironmentDetector** (`src/utils/environment_detector.py`) | Rule-based environment classification from sensor patterns | SensorData (GPS, Lidar, Camera) | Environment type: "indoor", "outdoor", "warehouse", "hospital", "unknown" | Story 3.3 |
| **ConnectionManager** (`api/server.py`) | Manage WebSocket connections for real-time client updates | WebSocket connections | Broadcast messages to all connected clients | Story 3.2 |
| **React Dashboard** (`ui/src/App.tsx`, optional) | Production-grade web UI for robot control and monitoring | WebSocket messages from FastAPI | User commands, visual status displays | Story 3.4 (deferred) |
| **Integration Test Suite** (`tests/integration/test_epic3_e2e.py`) | End-to-end validation of reactive + web + environment components | Test scenarios (10+) | Pass/fail results, performance metrics | Story 3.5 |

### Data Models and Contracts

**New Pydantic Models (Story 3.1):**

```python
class ReactiveDecision(BaseModel):
    """Output from HybridReactiveController.check_and_react()"""
    level: Literal["CRITICAL", "MODERATE", "NORMAL"]
    action: Literal["EMERGENCY_STOP", "DETOUR", "CONTINUE"]
    detour_plan: Optional[List[str]]  # e.g., ["rotate_left", "move_forward", "rotate_right"]
    execution_time_ms: float
```

**Extended Pydantic Models (Story 3.1):**

```python
class RobotState(BaseModel):
    # Existing fields from Epic 1...
    sensors: SensorData
    status: RobotStatus
    position: Tuple[float, float, float]

    # NEW: Reactive log for Verifier context
    reactive_log: List[Dict[str, Any]] = []  # [{timestamp, trigger, detour}, ...]
```

**FastAPI Request/Response Models (Story 3.2):**

```python
class MissionRequest(BaseModel):
    """WebSocket/REST request to execute mission"""
    command: str  # Natural language command
    language: str = "ko"  # Korean by default
    priority: int = 5  # 1-10 scale

class MissionResponse(BaseModel):
    """WebSocket/REST response after mission execution"""
    success: bool
    message: str
    duration_seconds: float
    final_position: Tuple[float, float, float]
    reactive_events: List[Dict[str, Any]]  # Summary of reactive interventions
```

**Environment Detection Output (Story 3.3):**

```python
class EnvironmentClassification(BaseModel):
    """Output from EnvironmentDetector.detect_environment()"""
    environment_type: Literal["indoor", "outdoor", "warehouse", "hospital", "unknown"]
    confidence: float  # 0.0-1.0
    features: Dict[str, Any]  # {has_gps_signal, ceiling_detected, lighting_level, ...}
```

**Data Relationships:**
- RobotState.reactive_log → stores all ReactiveDecision events during mission execution
- MissionResponse.reactive_events → summarizes RobotState.reactive_log for client display
- EnvironmentClassification.environment_type → filters ChromaDB RAG queries (Story 3.3)

### APIs and Interfaces

**FastAPI REST Endpoints (Story 3.2):**

| Method | Path | Request | Response | Description |
|--------|------|---------|----------|-------------|
| POST | `/api/mission` | MissionRequest | MissionResponse | Execute mission command (async) |
| GET | `/api/status` | None | SystemStatus | Get current robot status |
| GET | `/health` | None | {"status": "ok"} | Health check endpoint |

**WebSocket Endpoints (Story 3.2):**

| Path | Direction | Message Format | Description |
|------|-----------|----------------|-------------|
| `/ws/robot-status` | Server → Client | `{"position": [x,y,z], "status": "...", "sensors": {...}}` | Real-time robot status broadcast (10Hz) |
| `/ws/control` | Client → Server | MissionRequest JSON | Submit mission command |
| `/ws/control` | Server → Client | MissionResponse JSON | Mission execution result |

**HybridReactiveController API (Story 3.1):**

```python
class HybridReactiveController:
    def check_and_react(
        self,
        sensor_data: SensorData,
        current_action: RobotAction
    ) -> ReactiveDecision:
        """
        Real-time reactive check (called every 64ms).

        Returns: ReactiveDecision with level, action, detour_plan, execution_time
        """

    def get_reactive_log(self) -> List[Dict[str, Any]]:
        """Retrieve log of all reactive interventions for Verifier context."""
```

**EnvironmentDetector API (Story 3.3):**

```python
class EnvironmentDetector:
    def detect_environment(
        self,
        sensor_data: SensorData
    ) -> EnvironmentClassification:
        """
        Classify environment using rule-based sensor analysis.

        Returns: EnvironmentClassification with type, confidence, features
        """
```

**Ollama Integration (Story 3.1):**

```python
# External API call to local Ollama service
response = ollama_client.generate(
    model="tinyllama",
    prompt="...",
    options={"temperature": 0.1}
)
# Expected latency: ~680ms avg, ~1027ms P90 (90th percentile < 1200ms)
```

**Error Codes:**

| Code | Meaning | Scenario |
|------|---------|----------|
| 400 | Bad Request | Invalid mission command format |
| 500 | Internal Server Error | Orchestrator execution failed |
| 503 | Service Unavailable | Ollama service not running |
| 1000-1003 | WebSocket Codes | Normal close, going away, protocol error, unsupported data |

### Workflows and Sequencing

**Workflow 1: Real-time Reactive Control (Story 3.1)**

```
1. Actor starts executing RobotAction (e.g., move_forward 5m)
2. LOOP: Every 64ms during action execution
   a. Actor reads current SensorData
   b. Actor calls reactive.check_and_react(sensor_data, current_action)
   c. HybridReactiveController evaluates:
      - Distance = min(lidar_data['ranges'])

      IF distance < 0.15m (CRITICAL):
         → Return ReactiveDecision(action="EMERGENCY_STOP")
         → Actor.emergency_stop() immediately
         → BREAK loop, return failure to Planner

      ELIF distance < 0.5m (MODERATE):
         → Check LRU cache for similar scenario
         → IF cache miss: Call Ollama tinyllama for detour plan (~680ms avg, ~1027ms P90)
         → Return ReactiveDecision(action="DETOUR", detour_plan=[...])
         → Actor executes 3-step detour
         → Log intervention to reactive_log
         → Resume original action

      ELSE distance >= 0.5m (NORMAL):
         → Return ReactiveDecision(action="CONTINUE")
         → Continue action execution normally

   d. Robot.step(64)  # Advance simulation 64ms
3. END LOOP when action complete
4. Actor passes RobotState (with reactive_log) to Verifier
5. Verifier checks reactive_log:
   - IF reactive_log exists: Adjust position tolerance from 0.1m to 0.3m
   - Verify mission success with adjusted tolerance
```

**Workflow 2: Web-Based Mission Control (Story 3.2)**

```
1. User opens web UI (http://localhost:8000)
2. Browser establishes WebSocket connection to /ws/robot-status
3. FastAPI server broadcasts robot status every 100ms
   - Status includes: position, sensors, mission state, reactive_log summary
4. User types natural language command: "장애물 회피하며 5미터 전진"
5. Browser sends MissionRequest via WebSocket to /ws/control
6. FastAPI server receives request:
   a. Parse and validate MissionRequest
   b. Create MissionCommand Pydantic object
   c. Call orchestrator.execute_mission(mission_command) asynchronously
7. Orchestrator executes standard Planner → Actor → Verifier flow
   - Reactive controller active during Actor execution (Workflow 1)
8. Mission completes, FastAPI broadcasts MissionResponse:
   - {"success": true, "message": "...", "reactive_events": [...]}
9. Browser updates UI with mission result and reactive event timeline
```

**Workflow 3: Environment-Aware Planning (Story 3.3)**

```
1. Planner receives MissionCommand from user
2. Actor collects current SensorData (GPS, Lidar, Camera)
3. EnvironmentDetector.detect_environment(sensor_data):
   a. Extract features:
      - has_gps_signal = GPS strength > threshold
      - ceiling_detected = upward Lidar points < 5m
      - lighting_level = Camera brightness analysis
      - space_openness = Lidar range variance
   b. Apply rule-based classification:
      - No GPS + ceiling → "indoor" or "warehouse" (based on openness)
      - GPS + no ceiling → "outdoor"
   c. Return EnvironmentClassification
4. Planner calls ChromaDB RAG with environment filter:
   - search_constraints(query, where={"environment_type": detected_env})
   - Retrieve only environment-specific constraints
5. Planner generates action plan using filtered constraints
6. Example: Indoor environment → Planner avoids GPS-dependent navigation
```

**Sequence Diagram (E2E with Reactive):**

```
User → WebUI → FastAPI → Orchestrator → Planner → RAG (env filter)
                                ↓
                              Actor → HybridReactive → Ollama (detour)
                                ↓        ↓ (reactive_log)
                              Verifier (adjust tolerance)
                                ↓
                  FastAPI ← MissionResponse
                    ↓
              WebUI (display result)
```

## Non-Functional Requirements

### Performance

**Latency Requirements (Story 3.1 - Reactive Controller):**

| Decision Level | Target Latency | Mechanism | Measured At |
|---------------|----------------|-----------|-------------|
| CRITICAL (<0.15m) | **<1ms** | Rule-based (no AI) | check_and_react() return |
| MODERATE (0.15-0.5m) | **<300ms** (90th percentile) | Ollama tinyllama | Ollama API call + parsing |
| NORMAL (>0.5m) | **<10ms** | Passthrough | check_and_react() return |

**Ollama Performance Targets (Story 3.0):**
- Cold start: <5 seconds (model loading)
- Warm inference: ~200ms average, <300ms p90
- Cache hit rate: >70% for repeated obstacle patterns
- Memory footprint: <4GB RAM (tinyllama model size)

**Web Server Performance (Story 3.2):**
- WebSocket message latency: <50ms (server → client status broadcast)
- Concurrent WebSocket connections: Support 10+ simultaneous clients
- REST API response time: <500ms for /api/mission (async execution)
- Status broadcast frequency: 10Hz (every 100ms)

**Mission Execution Performance Targets (Epic 3 vs Epic 2 Baseline):**

| Metric | Epic 2 Baseline | Epic 3 Target | Improvement |
|--------|-----------------|---------------|-------------|
| Collision Rate | 67% | **<5%** | **93% reduction** |
| Replanning Frequency | 2.3 times/mission | **<0.2 times** | **91% reduction** |
| Mission Completion Time | 16 seconds | **<11 seconds** | **31% faster** |
| Success Rate | 70% | **>95%** | **+25 percentage points** |

**Scalability Constraints:**
- Single-robot system (no multi-robot coordination in Epic 3)
- Simulation-based only (Webots R2025a required)
- Local deployment (no cloud dependencies for Ollama)

### Security

**Threat Model (Development Environment):**

Epic 3 is designed for **local development and research use** only. Production security features are out of scope.

**In-Scope Security Measures:**

1. **Input Validation (Story 3.2):**
   - FastAPI Pydantic validation for all REST/WebSocket requests
   - Command length limits: max 500 characters
   - Rate limiting: 10 requests/second per WebSocket connection

2. **Network Security (Development Only):**
   - FastAPI server binds to localhost:8000 by default
   - CORS policy allows localhost origins only
   - No SSL/TLS encryption (development environment)

3. **Data Privacy:**
   - No user authentication or authorization (single-user system)
   - No persistent storage of mission commands or logs
   - Sensor data remains local (no external transmission)

4. **Ollama Security:**
   - Ollama service runs locally (localhost:11434)
   - No internet access required for tinyllama inference
   - Model weights stored locally (~1.9GB)

**Out-of-Scope (Deferred to Production):**
- User authentication and session management
- API key/token-based authorization
- HTTPS/WSS encryption for web traffic
- Input sanitization for prompt injection attacks
- Audit logging for security events
- Network isolation and firewall rules

**Known Vulnerabilities (Accepted for Development):**
- WebSocket connections are unauthenticated
- No protection against DoS attacks (rate limiting is minimal)
- Ollama prompts are not sanitized for prompt injection
- Web UI accessible to anyone on local network

### Reliability/Availability

**Availability Target (Development Environment):**
- **Uptime**: Not applicable (single-user development, manual start/stop)
- **Recovery Time Objective (RTO)**: N/A (development restarts acceptable)
- **Recovery Point Objective (RPO)**: N/A (no persistent state)

**Error Handling and Resilience:**

1. **Ollama Service Unavailability (Story 3.1):**
   - **Detection**: HTTP connection error when calling localhost:11434
   - **Graceful Degradation**:
     - MODERATE level falls back to CRITICAL behavior (emergency stop)
     - Log warning: "Ollama unavailable, reactive controller degraded"
   - **Recovery**: System continues with rules-only reactive control

2. **WebSocket Connection Failures (Story 3.2):**
   - **Client disconnects**: Server continues mission execution, logs event
   - **Auto-reconnect**: Client attempts reconnect every 5 seconds (max 3 retries)
   - **Message loss**: Accept eventual consistency (status broadcasts resume on reconnect)

3. **Reactive Controller Failures (Story 3.1):**
   - **Ollama timeout (>1 second)**: Fall back to emergency stop
   - **Invalid JSON response**: Log error, use cached detour plan if available
   - **Cache corruption**: Clear cache, continue with fresh Ollama calls

4. **Verifier Tolerance Adjustment (Story 3.1):**
   - **Reactive log corruption**: Ignore reactive_log, use standard tolerance (0.1m)
   - **Multiple detours**: Cap tolerance adjustment at 0.5m maximum

**Failure Modes and Effects Analysis (FMEA):**

| Component | Failure Mode | Impact | Detection | Mitigation |
|-----------|--------------|--------|-----------|------------|
| Ollama Service | Process crash | MODERATE decisions fail | Connection error | Fall back to rules-only |
| FastAPI Server | Process crash | Web control unavailable | Health check fails | Manual restart required |
| WebSocket | Connection drop | Client loses status updates | Connection error | Auto-reconnect (3 attempts) |
| Reactive Cache | Memory overflow | Slower detour decisions | Cache size check | LRU eviction policy |
| Environment Detector | Misclassification | Wrong RAG constraints | Confidence score | Log warning if confidence <0.5 |

**Data Integrity:**
- No persistent state (all state in memory)
- Webots simulation state is authoritative
- Reactive log stored in RobotState (volatile)

### Observability

**Logging Strategy (Extension of Epic 2.5):**

**New Log Categories (Story 3.1, 3.2, 3.3):**

| Category | Level | Destination | Format | Frequency |
|----------|-------|-------------|--------|-----------|
| `reactive.decision` | INFO | `logs/reactive_decisions.json` | Structured JSON | Per reactive check (64ms intervals) |
| `web.request` | INFO | `logs/api_access.log` | FastAPI access log | Per HTTP/WS request |
| `web.mission` | INFO | `logs/missions.json` | Structured JSON | Per mission execution |
| `environment.detection` | DEBUG | `logs/environment.json` | Structured JSON | Per detection call |
| `ollama.inference` | INFO | `logs/ollama_calls.json` | Structured JSON | Per Ollama API call |

**Structured Log Schema (Reactive Decisions):**

```json
{
  "timestamp": "2025-11-02T10:30:45.123Z",
  "category": "reactive.decision",
  "level": "MODERATE",
  "action": "DETOUR",
  "distance_m": 0.35,
  "execution_time_ms": 205,
  "detour_plan": ["rotate_left", "move_forward", "rotate_right"],
  "cache_hit": false,
  "mission_id": "m-1234"
}
```

**Metrics and Telemetry (OpenLit Extension):**

**New Metrics (Story 3.1):**
- `reactive_decisions_total` (counter) - Tagged by level (CRITICAL/MODERATE/NORMAL)
- `reactive_latency_ms` (histogram) - Distribution of check_and_react() latency
- `ollama_inference_time_ms` (histogram) - Ollama API call duration
- `cache_hit_rate` (gauge) - Percentage of cached detour decisions
- `emergency_stops_total` (counter) - Count of CRITICAL interventions

**New Metrics (Story 3.2):**
- `websocket_connections_active` (gauge) - Current WebSocket clients
- `mission_requests_total` (counter) - Total web-initiated missions
- `mission_duration_seconds` (histogram) - End-to-end mission execution time

**Tracing (Distributed Tracing for Web Requests):**
- FastAPI requests tagged with `trace_id` (UUID)
- Propagate `trace_id` through Orchestrator → Planner → Actor → Verifier
- Associate reactive log entries with parent `trace_id`

**Dashboards and Alerts (Recommended):**

**Grafana Dashboard Panels (Story 3.5 validation):**
1. Reactive Decision Breakdown (pie chart: CRITICAL/MODERATE/NORMAL)
2. Ollama Latency P50/P90/P99 (time series)
3. Mission Success Rate with Reactive (gauge: target >95%)
4. WebSocket Connection Health (time series)
5. Environment Detection Accuracy (if ground truth available)

**Alert Conditions (Not implemented in Epic 3, design only):**
- Ollama P90 latency >500ms for 5 consecutive minutes
- Emergency stop rate >10% of total decisions
- WebSocket connection failures >50% for 1 minute
- Mission success rate <80% over 10 missions

**Log Retention:**
- Development: Rotate logs daily, keep 7 days
- Structured logs (JSON): Keep for benchmarking analysis (Story 3.1 AC #7)

## Dependencies and Integrations

**Existing Dependencies (Epic 1-2 - Preserved):**

| Package | Version | Purpose | Epic |
|---------|---------|---------|------|
| crewai | >=0.1.0 | Multi-agent orchestration framework | Epic 1 |
| pydantic | >=2.0.0 | Data validation and schemas | Epic 1 |
| chromadb | >=0.4.0 | Vector database for RAG | Epic 2 |
| openai | >=1.0.0 | OpenAI API client (GPT-4o, GPT-4o-mini) | Epic 1 |
| loguru | >=0.7.0 | Structured logging | Epic 2 |
| openlit | >=0.1.0 | LLM monitoring and tracing | Epic 2 |
| pytest | >=7.4.0 | Testing framework | Epic 1 |
| numpy | >=1.24.0,<2.0.0 | Numerical computations (sensor data) | Epic 1 |
| opencv-python | >=4.12.0 | Camera sensor processing | Epic 2 |

**New Dependencies (Epic 3 - To Be Added):**

| Package | Version | Purpose | Story | Installation |
|---------|---------|---------|-------|--------------|
| **ollama** | >=0.1.0 | Python client for Ollama API | 3.0, 3.1 | `pip install ollama` |
| **fastapi** | >=0.104.0 | Web server framework | 3.2 | `pip install fastapi` |
| **uvicorn** | >=0.24.0 | ASGI server for FastAPI | 3.2 | `pip install uvicorn[standard]` |
| **websockets** | >=12.0 | WebSocket protocol support | 3.2 | Auto-installed with uvicorn |
| **python-socketio** | >=5.10.0 | Socket.IO for real-time communication | 3.2 | `pip install python-socketio` |
| **httpx** | >=0.25.0 | Async HTTP client (for Ollama calls) | 3.1 | `pip install httpx` |

**Optional Dependencies (Story 3.4 - React UI):**

| Package | Version | Purpose | Installation |
|---------|---------|---------|--------------|
| Node.js | >=18.0.0 | JavaScript runtime for React | Download from nodejs.org |
| npm | >=9.0.0 | Package manager for React | Bundled with Node.js |
| React | 18.2+ | Frontend framework | `npx create-react-app ui` |

**External Services and Tools:**

| Service | Version | Purpose | Installation Method | Story |
|---------|---------|---------|---------------------|-------|
| **Ollama** | Latest | Local LLM inference engine | Download from ollama.ai OR `curl https://ollama.ai/install.sh \| sh` | 3.0 |
| **tinyllama** | 1.9B params | Lightweight LLM model | `ollama pull tinyllama` (~1.9GB download) | 3.0 |
| **Webots** | R2025a | Robot simulation environment | Pre-installed (Epic 1) | N/A |

**Integration Points:**

**1. Ollama Integration (Story 3.1):**
- **Connection**: HTTP API at `http://localhost:11434`
- **Model**: tinyllama (must be pre-pulled)
- **Client Library**: `ollama` Python package
- **Usage Pattern**:
  ```python
  from ollama import Client
  client = Client(host='http://localhost:11434')
  response = client.generate(model='tinyllama', prompt='...')
  ```

**2. FastAPI Integration (Story 3.2):**
- **Port**: 8000 (default, configurable via environment variable)
- **CORS**: Enabled for `http://localhost:3000` (React dev server)
- **WebSocket Protocol**: Standard WebSocket (ws://) for development
- **Integration with Orchestrator**: Direct Python import, synchronous calls wrapped in `asyncio.to_thread()`

**3. ChromaDB Extension (Story 3.3):**
- **Metadata Schema Extension**:
  ```python
  # Existing metadata
  {"id": "const_1", "category": "safety"}

  # Extended with environment_type
  {"id": "const_1", "category": "safety", "environment_type": "indoor"}
  ```
- **Query Pattern**:
  ```python
  collection.query(
      query_texts=["obstacle avoidance"],
      where={"environment_type": "indoor"}  # NEW filter
  )
  ```

**4. React UI Integration (Story 3.4 - Optional):**
- **Development Server**: `http://localhost:3000` (React dev server)
- **Production Build**: Static files served by FastAPI (`/static`)
- **Communication**: WebSocket to FastAPI at `ws://localhost:8000/ws/robot-status`

**Dependency Conflicts and Resolutions:**

| Conflict | Resolution |
|----------|------------|
| numpy <2.0 requirement (langchain) | Pin numpy<2.0.0 in requirements.txt |
| FastAPI + OpenLit compatibility | Both use Pydantic 2.x - no conflict |
| Ollama port 11434 + FastAPI port 8000 | Different ports, no conflict |

**Version Constraints Summary:**

- Python: **3.11+** (required for Pydantic 2.x and FastAPI)
- Webots: **R2025a** (fixed version for simulation consistency)
- Ollama: **Latest stable** (backward compatible API)
- Node.js: **18+** (for React 18 support, optional)

## Acceptance Criteria (Authoritative)

The following acceptance criteria are extracted from Epic 3 user stories (epics.md) and normalized into atomic, testable statements. Each AC is mapped to implementing components and test approaches in the Traceability Mapping section below.

**Story 3.0: Ollama Setup & Validation (5 ACs)**

**AC-3.0.1**: Ollama binary is installed on the development environment (Linux/macOS/Windows) with an installation script (`install_ollama.sh`) that verifies service startup at `localhost:11434`.

**AC-3.0.2**: tinyllama model (1.1B parameters) is downloaded via `ollama pull tinyllama` and confirmed loaded via `ollama list`, with minimum 1GB disk space available.

**AC-3.0.3**: Ollama inference latency meets performance targets: 90th percentile <1200ms and average <1000ms (adjusted for TinyLlama), validated across 10 sample prompts with results recorded in a benchmark report.

**AC-3.0.4**: JSON structured output from Ollama is successfully parsed with >95% success rate, including error handling logic for malformed responses.

**AC-3.0.5**: Ollama installation is documented in README.md with environment-specific guides (Linux/macOS/Windows) and troubleshooting section.

---

**Story 3.1: Hybrid Reactive Controller (7 ACs)**

**AC-3.1.1**: CRITICAL level (Lidar <0.15m) triggers immediate emergency stop within <1ms using rule-based logic (no AI), returning action failure to Verifier for replanning.

**AC-3.1.2**: MODERATE level (0.15m < Lidar < 0.5m) triggers Ollama tinyllama-powered detour decision within ~1200ms (P90), generating modified path parameters (x, y, speed) without requiring full replanning.

**AC-3.1.3**: NORMAL level (Lidar >0.5m) allows mission execution to continue as planned without reactive intervention.

**AC-3.1.4**: All reactive interventions are logged with structured data (timestamp, type, reason, action_taken, sensor_state) in `RobotState.reactive_log`, passed to Verifier for tolerance adjustment (0.1m → 0.3m).

**AC-3.1.5**: Reactive controller executes `check_and_react()` every 64ms during action execution without blocking the Planner/Actor/Verifier workflow, returning within <10ms for NORMAL decisions.

**AC-3.1.6**: Test coverage includes unit tests (emergency stop, Ollama detour), integration tests (reactive_log propagation, Verifier tolerance adjustment), and E2E scenarios (detour to success).

**AC-3.1.7**: Performance benchmarking across 50+ missions demonstrates: collision rate <5% (vs 67% Epic 2 baseline), success rate >95% (vs 70%), replanning frequency <0.2 times/mission (vs 2.3), with results published in `docs/epic3_benchmark_report.md`.

---

**Story 3.2: FastAPI Web Control Server (8 ACs)**

**AC-3.2.1**: FastAPI WebSocket server provides `/ws/control` endpoint for bidirectional communication, receiving natural language commands and executing `Orchestrator.execute_mission()`.

**AC-3.2.2**: Real-time robot status broadcast at 10Hz (every 100ms) via WebSocket includes position (x, y, z), sensor data (lidar_min, camera stream), mission state (planning/executing/verifying), and reactive intervention notifications.

**AC-3.2.3**: Basic web UI (HTML + JavaScript) provides natural language input field, status display (position, sensors, logs), and real-time updates via WebSocket connection.

**AC-3.2.4**: Orchestrator integration uses asynchronous execution (`asyncio.to_thread`) to run missions in background while streaming status updates, with error handling and client reconnection support.

**AC-3.2.5**: FastAPI automatic documentation is generated at `/docs` endpoint, with WebSocket message formats explicitly defined.

**AC-3.2.6**: Web server installation and usage are documented in README.md, including dependency installation (FastAPI, uvicorn, websockets), startup commands, and WebSocket protocol specification.

**AC-3.2.7**: Production deployment script (`deploy.sh` or `docker-compose.yml`) is provided with environment variable template (`.env.template`) and deployment guide (port config, firewall, SSL notes).

**AC-3.2.8**: Environment variables are documented in `.env.template` with required variables defined (OPENAI_API_KEY, WEBOTS_PATH, SERVER_PORT) and environment-specific examples (development/production).

---

**Story 3.3: Environment-Aware Planning (5 ACs)**

**AC-3.3.1**: Environment detection uses rule-based sensor analysis (GPS signal strength, Lidar average distance, camera brightness) to classify as "indoor", "outdoor", "warehouse", "hospital", or "unknown".

**AC-3.3.2**: Existing RAG system is extended by adding `environment_type` metadata field to constraints in `src/rag/data/environment_constraints.json` without creating new collections.

**AC-3.3.3**: PlannerAgent's `_retrieve_rag_context()` method filters ChromaDB queries using `where={"environment_type": detected_env}` to retrieve only environment-relevant constraints.

**AC-3.3.4**: RAG extension maintains backward compatibility with `RobotKnowledgeBase` class unchanged and no new ChromaDB collections created (metadata-only extension).

**AC-3.3.5**: Tests validate environment detection logic (4 environments), environment-based constraint filtering, and Planner integration with filtered RAG context.

---

**Story 3.4: React Web UI Dashboard (4 ACs - OPTIONAL)**

**AC-3.4.1**: React application (Create React App or Vite) establishes WebSocket connection via `useWebSocket` hook with real-time state updates.

**AC-3.4.2**: Dashboard components include natural language command panel, 2D robot map, Lidar visualization (Canvas), camera stream (Base64), and log panel (reactive_log, mission events).

**AC-3.4.3**: UI/UX provides responsive layout, real-time position tracking chart, and status color coding (idle/planning/executing/success/failed).

**AC-3.4.4**: Production build generates static files served by FastAPI at `/static` endpoint.

---

**Story 3.5: Epic 3 Integration Testing (5 ACs)**

**AC-3.5.1**: End-to-end integration tests validate full workflow (Web UI → FastAPI WebSocket → Orchestrator → Reactive Controller → Environment Detection) across 10+ scenarios with natural language input, obstacle avoidance, environment detection, and mission success.

**AC-3.5.2**: Performance validation tests handle 10 concurrent web requests, verify WebSocket stability (100+ messages), load-test Ollama concurrent inference, and confirm response times <5 seconds.

**AC-3.5.3**: Error propagation tests validate graceful degradation when Ollama service stops, WebSocket reconnection after disconnect, network error handling, and Webots simulator error recovery.

**AC-3.5.4**: Regression testing re-runs all 270+ Epic 1-2 tests to confirm backward compatibility, no impact on existing functionality, and test coverage maintained at >80%.

**AC-3.5.5**: Integration test documentation includes test plan (`test_plan_epic3.md`), scenario-based test cases, test result report (`integration_test_report.md`), and bug tracking for discovered issues.

---

**Total: 34 Acceptance Criteria (30 core + 4 optional)**

## Traceability Mapping

This section maps each acceptance criterion to its implementing components, relevant specification sections, and test approaches.

| AC ID | Spec Section(s) | Component(s) / API(s) | Test Approach |
|-------|----------------|----------------------|---------------|
| **AC-3.0.1** | Dependencies (External Services), Workflows (Workflow 1 setup) | `scripts/install_ollama.sh`, Ollama binary at `localhost:11434` | Unit test: Execute install script, verify HTTP 200 from `http://localhost:11434/api/tags` |
| **AC-3.0.2** | Dependencies (External Services table), NFRs (Performance - Ollama targets) | Ollama model `tinyllama`, `ollama pull` CLI | Unit test: Run `ollama list`, assert model present, check disk usage >1GB |
| **AC-3.0.3** | NFRs (Performance - Ollama Performance Targets) | Ollama API `/api/generate`, `tests/test_ollama_setup.py` | Performance test: 10 inference calls, calculate p90/avg latency, assert <1200ms/1000ms (adjusted for TinyLlama) |
| **AC-3.0.4** | Data Models (ReactiveDecision - JSON parsing), NFRs (Reliability - Ollama failures) | Ollama structured output prompt, JSON parser with error handling | Unit test: Send malformed JSON, verify error handling; 100 valid prompts, assert >95% parse success |
| **AC-3.0.5** | Dependencies (External Services documentation) | `README.md` Ollama section, `docs/ollama_setup_guide.md` | Manual review: Verify README contains install commands for 3 OSes, troubleshooting section exists |
| **AC-3.1.1** | Detailed Design (HybridReactiveController API), Workflows (Workflow 1 - CRITICAL path), NFRs (Performance - <1ms latency) | `src/reactive/hybrid_controller.py::check_and_react()`, rule-based distance check | Unit test: Mock sensor Lidar=0.1m, assert ReactiveDecision(action="EMERGENCY_STOP"), measure latency <1ms |
| **AC-3.1.2** | Detailed Design (HybridReactiveController), Workflows (Workflow 1 - MODERATE path), NFRs (Performance - <1200ms P90 latency), Data Models (ReactiveDecision) | `HybridReactiveController::_quick_detour_decision()`, Ollama client, LRU cache | Unit test: Mock Lidar=0.3m, assert DETOUR decision, verify detour_plan populated, latency <1200ms P90; Integration test: Verify Ollama API call |
| **AC-3.1.3** | Detailed Design (HybridReactiveController), Workflows (Workflow 1 - NORMAL path) | `check_and_react()` passthrough logic | Unit test: Mock Lidar=1.0m, assert ReactiveDecision(action="CONTINUE"), latency <10ms |
| **AC-3.1.4** | Data Models (RobotState.reactive_log), Workflows (Workflow 1 - steps 4-5), Detailed Design (Verifier tolerance adjustment) | `RobotState.reactive_log`, `ActorAgent::get_reactive_log()`, `VerifierAgent` tolerance logic | Integration test: Execute mission with reactive event, assert log populated, Verifier adjusts tolerance 0.1m→0.3m |
| **AC-3.1.5** | Workflows (Workflow 1 - 64ms loop), Architecture Alignment (Non-blocking execution) | `ActorAgent::_execute_move_with_reactive()`, 64ms polling interval | Integration test: Execute 5-second action, assert check_and_react() called ~78 times (5000ms/64ms), no Planner blocking |
| **AC-3.1.6** | Test Strategy (unit/integration/E2E tests) | `tests/unit/test_reactive_controller.py`, `tests/integration/test_reactive_integration.py` | Pytest execution: Verify test files exist, run tests, assert all pass |
| **AC-3.1.7** | NFRs (Performance - Mission Execution Performance Targets table), Observability (Metrics) | `tests/performance/test_benchmarking.py`, 50+ mission scenarios, metric collection | E2E benchmark: Run 50 missions, calculate collision rate, success rate, replanning frequency; assert targets met; generate `docs/epic3_benchmark_report.md` |
| **AC-3.2.1** | APIs and Interfaces (WebSocket Endpoints `/ws/control`), Workflows (Workflow 2 - steps 5-6) | `api/server.py::websocket_control_handler()`, `Orchestrator.execute_mission()` | Integration test: Connect WebSocket client, send MissionRequest JSON, verify mission executes via Orchestrator |
| **AC-3.2.2** | APIs and Interfaces (WebSocket `/ws/robot-status`), NFRs (Performance - Status broadcast 10Hz), Workflows (Workflow 2 - step 3) | `api/server.py::status_updater()`, ConnectionManager broadcast, 10Hz loop | Integration test: Connect client, receive 100 status messages, assert frequency ~10Hz (100ms intervals), verify fields present |
| **AC-3.2.3** | Detailed Design (Services - FastAPI Server), Dependencies (FastAPI integration) | `api/templates/index.html`, WebSocket client JavaScript | Manual/E2E test: Open browser at `http://localhost:8000`, verify UI elements present, send command, assert status updates |
| **AC-3.2.4** | Workflows (Workflow 2 - step 6-7), APIs (Orchestrator integration), NFRs (Reliability - WebSocket failures) | `asyncio.to_thread()`, error handling, reconnect logic | Integration test: Execute mission via WebSocket, verify async execution, simulate disconnect, verify reconnect |
| **AC-3.2.5** | APIs and Interfaces (REST Endpoints table), Dependencies (FastAPI) | FastAPI `/docs` auto-generated Swagger UI, Pydantic model schemas | Manual test: Open `http://localhost:8000/docs`, verify endpoints documented, test MissionRequest schema |
| **AC-3.2.6** | Dependencies (FastAPI documentation) | `README.md` web server section, WebSocket protocol docs | Manual review: Verify README contains FastAPI install commands, uvicorn startup example, WebSocket message format table |
| **AC-3.2.7** | Dependencies (FastAPI deployment), NFRs (Security - Network Security) | `deploy.sh` or `docker-compose.yml`, `.env.template` | Manual test: Execute deploy script, verify server starts, check .env.template has required variables |
| **AC-3.2.8** | Dependencies (Version Constraints), NFRs (Security - Data Privacy) | `.env.template` file with variable definitions | Manual review: Verify .env.template exists, contains OPENAI_API_KEY, WEBOTS_PATH, SERVER_PORT with examples |
| **AC-3.3.1** | Detailed Design (EnvironmentDetector API), Workflows (Workflow 3 - steps 2-3), Data Models (EnvironmentClassification) | `src/utils/environment_detector.py::detect_environment()`, rule-based classification logic | Unit test: Mock SensorData (GPS=0.9, Lidar=10m, brightness=high) → assert "outdoor"; Test all 4 environments + unknown |
| **AC-3.3.2** | Dependencies (ChromaDB Extension), Detailed Design (Data Models - RAG metadata) | `src/rag/data/environment_constraints.json`, metadata field `environment_type` | Manual review: Verify constraints JSON has `environment_type` field added, no new ChromaDB collections created |
| **AC-3.3.3** | Workflows (Workflow 3 - step 4), APIs (ChromaDB query pattern), Detailed Design (PlannerAgent extension) | `PlannerAgent::_retrieve_rag_context()`, ChromaDB `where` filter | Integration test: Set environment to "indoor", call Planner, assert only indoor constraints retrieved via where filter |
| **AC-3.3.4** | Architecture Alignment (Preserved Components - ChromaDB RAG), Dependencies (ChromaDB) | `RobotKnowledgeBase` class (unchanged), existing ChromaDB collection | Regression test: Run Epic 2 RAG tests, assert all pass; verify no new collections in ChromaDB |
| **AC-3.3.5** | Test Strategy (environment detection tests) | `tests/unit/test_environment_detector.py`, `tests/integration/test_rag_filtering.py` | Unit test: 4 environment scenarios; Integration test: Planner with environment filter, verify correct constraints used |
| **AC-3.4.1** | Detailed Design (React Dashboard service), Dependencies (React optional deps) | `ui/src/hooks/useWebSocket.ts`, React state management | E2E test (optional): Run React dev server, verify WebSocket connection established, state updates on message |
| **AC-3.4.2** | Detailed Design (React Dashboard - component list) | `ui/src/components/CommandPanel.tsx`, `RobotMap.tsx`, `LidarView.tsx`, `CameraStream.tsx`, log panel | Manual test (optional): Verify components render, Lidar canvas draws, camera displays Base64 image |
| **AC-3.4.3** | NFRs (Observability - Dashboard design) | UI/UX components, responsive CSS, status color logic | Manual test (optional): Resize browser, verify responsive layout; trigger mission, verify color changes |
| **AC-3.4.4** | Dependencies (React UI Integration), Detailed Design (FastAPI static files) | `npm run build`, FastAPI static file serving at `/static` | Manual test (optional): Build React app, verify FastAPI serves `index.html` at root, assets at `/static` |
| **AC-3.5.1** | Workflows (all 3 workflows integrated), Test Strategy (E2E tests) | `tests/integration/test_epic3_e2e.py`, 10+ test scenarios | E2E test: Execute `test_web_to_reactive_controller_e2e()`, `test_environment_detection_integration()`, assert all scenarios pass |
| **AC-3.5.2** | NFRs (Performance - Web Server Performance, Scalability), Test Strategy (load tests) | `tests/performance/test_load_testing.py`, concurrent request handler | Performance test: Execute `test_concurrent_web_requests()`, 10 simultaneous WebSocket connections, assert response time <5s |
| **AC-3.5.3** | NFRs (Reliability - FMEA table), Test Strategy (error handling tests) | `tests/integration/test_error_handling.py`, graceful degradation logic | Integration test: Execute `test_ollama_failure_graceful_degradation()`, stop Ollama service, verify system continues |
| **AC-3.5.4** | Architecture Alignment (Backward Compatibility - 270+ tests), Test Strategy (regression tests) | All Epic 1-2 test suites, pytest coverage | Regression test: Run `pytest tests/ --cov=src`, assert 270+ tests pass, coverage >80% |
| **AC-3.5.5** | Test Strategy (documentation) | `docs/test_plan_epic3.md`, `docs/integration_test_report.md`, issue tracker | Manual review: Verify test plan document exists, test report generated after test execution, issues logged |

**Coverage Summary:**

- **Detailed Design**: 18 ACs mapped to components/APIs
- **Workflows**: 12 ACs mapped to sequencing/integration
- **NFRs**: 14 ACs mapped to performance/reliability/observability
- **Dependencies**: 10 ACs mapped to external services/integrations
- **Test Strategy**: 13 ACs mapped to test approaches

**Verification Method Distribution:**

- Unit Tests: 12 ACs
- Integration Tests: 11 ACs
- E2E Tests: 4 ACs
- Performance Tests: 3 ACs
- Manual Review/Test: 8 ACs

**Critical Path Dependencies:**

1. AC-3.0.1, AC-3.0.2 (Ollama setup) → AC-3.1.2, AC-3.1.7 (Reactive controller Ollama features)
2. AC-3.1.1 through AC-3.1.5 (Reactive controller) → AC-3.5.1 (E2E integration)
3. AC-3.2.1 through AC-3.2.4 (FastAPI core) → AC-3.2.6, AC-3.2.7 (Documentation/deployment)
4. AC-3.3.2 (RAG extension) → AC-3.3.3, AC-3.3.5 (Environment filtering and tests)
5. All core ACs → AC-3.5.1 through AC-3.5.5 (Integration testing)

## Risks, Assumptions, Open Questions

### Risks

**Technical Risks (Technology Adoption):**

| Risk ID | Description | Probability | Impact | Mitigation Strategy | Owner |
|---------|-------------|-------------|--------|---------------------|-------|
| **R-3.1** | Ollama tinyllama inference latency exceeds 300ms p90 on target hardware | Medium | High | Story 3.0 includes latency validation before controller implementation; use LRU caching to reduce Ollama calls; fallback to rule-based decisions if timeout | Story 3.1 |
| **R-3.2** | Ollama service instability or crashes during continuous operation | Low | Medium | Implement health checks every 60s; graceful degradation to rules-only mode (AC-3.5.3); auto-restart logic in deployment script | Story 3.0, 3.1 |
| **R-3.3** | FastAPI WebSocket connections drop frequently in Webots simulation environment | Low | Medium | Implement auto-reconnect with exponential backoff (max 3 retries); log connection metrics; test with long-running missions (AC-3.5.2) | Story 3.2 |
| **R-3.4** | JSON parsing failure rate from Ollama >5% due to malformed outputs | Medium | Medium | Use structured output prompts with explicit JSON schema; implement robust error handling; validate JSON before parsing; cache valid responses | Story 3.1 |

**Integration Risks (System Complexity):**

| Risk ID | Description | Probability | Impact | Mitigation Strategy | Owner |
|---------|-------------|-------------|--------|---------------------|-------|
| **R-3.5** | Reactive controller introduces race conditions in Actor execution loop | Medium | High | Thorough integration testing (AC-3.1.6); use thread-safe logging; avoid shared mutable state; 64ms polling ensures deterministic timing | Story 3.1 |
| **R-3.6** | Environment detection misclassifies >20% of scenarios, leading to wrong RAG constraints | Medium | Medium | Test all 4 environments with synthetic sensor data (AC-3.3.5); use confidence thresholds (>0.5); log warnings on low confidence; fallback to all constraints if unknown | Story 3.3 |
| **R-3.7** | Verifier tolerance adjustment (0.1m → 0.3m) causes false positives in mission success | Low | Medium | Test edge cases where detour ends near boundary (AC-3.1.4); log all tolerance adjustments; cap max tolerance at 0.5m | Story 3.1 |
| **R-3.8** | Epic 3 changes break Epic 1-2 regression tests (270+ tests) | Low | Critical | Run regression tests after every story completion (AC-3.5.4); maintain strict backward compatibility; no modifications to existing schemas unless versioned | Story 3.5 |

**Performance Risks (Meeting Targets):**

| Risk ID | Description | Probability | Impact | Mitigation Strategy | Owner |
|---------|-------------|-------------|--------|---------------------|-------|
| **R-3.9** | Collision rate reduction target (<5%) not achieved due to sensor latency | Medium | High | Benchmark early in Story 3.1 (AC-3.1.7); tune reactive thresholds (0.15m, 0.5m) based on data; increase CRITICAL range if needed | Story 3.1 |
| **R-3.10** | WebSocket status broadcast at 10Hz causes CPU bottleneck in simulation | Low | Low | Monitor CPU usage during load testing (AC-3.5.2); reduce broadcast frequency to 5Hz if needed; use delta updates instead of full state | Story 3.2 |
| **R-3.11** | 64ms reactive polling interval too slow for fast-moving obstacles | Low | High | Validate with high-speed obstacle scenarios in testing; reduce to 32ms if collisions occur; optimize check_and_react() to <5ms | Story 3.1 |

**Schedule Risks (Delivery Timeline):**

| Risk ID | Description | Probability | Impact | Mitigation Strategy | Owner |
|---------|-------------|-------------|--------|---------------------|-------|
| **R-3.12** | Story 3.1 (14h) underestimated due to Ollama integration complexity | Medium | Medium | Monitor progress after 8h; descope LRU caching to Story 3.6 (future) if behind schedule; ensure core 3-level decision works first | Story 3.1 |
| **R-3.13** | Story 3.4 (React UI - 12h) expands scope and delays Epic completion | Low | Low | Mark Story 3.4 as OPTIONAL; skip if timeline pressure; basic HTML/JS UI (Story 3.2) sufficient for MVP | Story 3.4 |

---

### Assumptions

**Technical Assumptions:**

1. **A-3.1**: Development environment has sufficient resources to run Ollama tinyllama alongside Webots (minimum 4GB RAM, 2 CPU cores recommended - TinyLlama is lighter than phi3:mini).

2. **A-3.2**: Webots R2025a simulation provides deterministic 64ms timesteps without drift, enabling reliable reactive controller polling.

3. **A-3.3**: Ollama API remains backward compatible across versions; no breaking changes expected during Epic 3 development.

4. **A-3.4**: Python 3.11+ `asyncio` library provides sufficient performance for FastAPI concurrent request handling (10+ clients).

5. **A-3.5**: Epic 2 baseline metrics (collision rate 67%, success rate 70%) are reproducible and serve as valid comparison benchmarks.

6. **A-3.6**: GPS, Lidar, Camera sensor data in Webots provides sufficient signals for environment classification (indoor/outdoor/warehouse/hospital).

7. **A-3.7**: Local deployment (localhost-only) is acceptable for Epic 3; production deployment with SSL/authentication deferred to future epics.

**Integration Assumptions:**

8. **A-3.8**: ChromaDB `where` filter with `environment_type` metadata performs efficiently without requiring re-indexing or query optimization.

9. **A-3.9**: Existing Planner/Actor/Verifier agents accept `reactive_log` extension to `RobotState` without requiring refactoring.

10. **A-3.10**: Orchestrator can be called asynchronously via `asyncio.to_thread()` without introducing threading issues (CrewAI compatibility).

**Scope Assumptions:**

11. **A-3.11**: Story 3.4 (React UI) is truly optional and not a dependency for any other story or acceptance criteria.

12. **A-3.12**: 270+ Epic 1-2 tests provide sufficient regression coverage; no additional Epic 3-specific regression tests needed beyond AC-3.5.4.

**Operational Assumptions:**

13. **A-3.13**: Developers have sudo/admin access to install Ollama binary on Linux/macOS/Windows development environments.

14. **A-3.14**: Network latency to localhost services (Ollama port 11434, FastAPI port 8000) is negligible (<1ms).

---

### Open Questions

**Technical Questions:**

1. **Q-3.1**: Should the reactive controller cache Ollama responses persistently (disk) or only in-memory (LRU cache)?
   - **Impact**: Persistent cache survives restarts but adds I/O latency.
   - **Decision Needed By**: Story 3.1 implementation start
   - **Recommendation**: Start with in-memory LRU (simpler); add persistence in future epic if needed.

2. **Q-3.2**: What should be the maximum detour plan length (number of steps) returned by Ollama for MODERATE decisions?
   - **Impact**: Longer plans may exceed 300ms latency or cause complex execution.
   - **Decision Needed By**: Story 3.1 prompt design
   - **Recommendation**: Cap at 3 steps (rotate, move, rotate) based on architecture.md examples.

3. **Q-3.3**: Should environment detection run once per mission or continuously during execution?
   - **Impact**: Continuous detection handles dynamic environments but adds overhead.
   - **Decision Needed By**: Story 3.3 implementation
   - **Recommendation**: Once per mission (at planning phase) for Epic 3; continuous mode deferred.

**Integration Questions:**

4. **Q-3.4**: Should WebSocket clients receive full RobotState (including reactive_log) or a filtered subset?
   - **Impact**: Full state increases message size; filtered state may miss debugging info.
   - **Decision Needed By**: Story 3.2 API design
   - **Recommendation**: Send summary (position, status, last 5 reactive events) for performance.

5. **Q-3.5**: How should the system handle conflicting environment classifications (e.g., GPS=outdoor but ceiling detected)?
   - **Impact**: Misclassification leads to wrong RAG constraints.
   - **Decision Needed By**: Story 3.3 detection logic
   - **Recommendation**: Use weighted rules (GPS > Lidar > Camera priority); return "unknown" if confidence <0.5.

**Performance Questions:**

6. **Q-3.6**: If Ollama p90 latency is 1027ms (meets target) but p99 is 1500ms, is this acceptable?
   - **Impact**: 1% of MODERATE decisions may cause noticeable delays.
   - **Decision Needed By**: Story 3.0 validation
   - **Recommendation**: Acceptable for Epic 3; add timeout at 1500ms with fallback to CRITICAL stop.

**Scope Questions:**

7. **Q-3.7**: Should Story 3.5 integration tests run in CI/CD pipeline or only manually?
   - **Impact**: CI/CD adds infrastructure complexity; manual testing may be forgotten.
   - **Decision Needed By**: Story 3.5 implementation
   - **Recommendation**: Manual for Epic 3 (pytest locally); CI/CD setup deferred to Epic 4.

---

### Answers to Open Questions (To Be Updated)

| Question ID | Decision | Decided By | Date | Rationale |
|-------------|----------|------------|------|-----------|
| Q-3.1 | In-memory LRU cache only | BMad | 2025-11-02 | Simpler implementation; Epic 3 focuses on proving concept, persistence can be added later if cache hit rate proves valuable |
| Q-3.2 | Max 3-step detour plan | BMad | 2025-11-02 | Aligns with architecture.md examples; keeps latency predictable; more complex plans should trigger replanning instead |
| Q-3.3 | Once per mission (planning phase) | BMad | 2025-11-02 | Reduces overhead; environments typically don't change mid-mission in simulation; continuous mode deferred to future |
| Q-3.4 | Send summary (last 5 reactive events) | BMad | 2025-11-02 | Balances debugging visibility with message size; full log available via REST API if needed |
| Q-3.5 | Weighted rules (GPS > Lidar > Camera), "unknown" if conflict | BMad | 2025-11-02 | GPS most reliable for indoor/outdoor; unknown triggers fallback to all constraints (safe default) |
| Q-3.6 | Acceptable; add 1500ms timeout with fallback | BMad | 2025-11-02 | p90 target met (~1027ms); p99 outliers handled gracefully with timeout → emergency stop (safe failure mode) |
| Q-3.7 | Manual testing for Epic 3 | BMad | 2025-11-02 | CI/CD infrastructure out of scope; pytest locally sufficient for validation; CI/CD deferred to future epic |

## Test Strategy Summary

### Testing Philosophy

Epic 3 testing follows a **risk-based, layered approach** with emphasis on backward compatibility and performance validation. The strategy prioritizes:

1. **Regression Protection**: All 270+ Epic 1-2 tests must pass (AC-3.5.4)
2. **Performance Validation**: Reactive latency and collision reduction targets validated early (AC-3.1.7)
3. **Integration Coverage**: E2E workflows tested across reactive + web + environment components (AC-3.5.1)
4. **Graceful Degradation**: Failure scenarios tested to ensure safe fallbacks (AC-3.5.3)

### Test Levels and Coverage Targets

| Test Level | Target Coverage | Scope | Execution Frequency |
|------------|----------------|-------|---------------------|
| **Unit Tests** | >80% line coverage | Individual components (HybridReactiveController, EnvironmentDetector, FastAPI handlers) isolated with mocks | Every code change (local) |
| **Integration Tests** | All integration points | Reactive controller + Actor, Planner + RAG filtering, FastAPI + Orchestrator, WebSocket + clients | Per story completion |
| **E2E Tests** | 10+ scenarios | Full workflows (Web UI → Reactive → Environment Detection → Mission Success) | Story 3.5 validation |
| **Performance Tests** | Latency targets met | Ollama inference <300ms p90, WebSocket 10Hz, concurrent requests <5s | Story 3.0 (Ollama), Story 3.5 (load) |
| **Regression Tests** | 100% (270+ tests) | All Epic 1-2 functionality unchanged | Every story completion |

### Test Pyramid (Epic 3 Additions)

```
                    E2E Tests (10+ scenarios)
                   Story 3.5 - Epic integration
                  /                            \
                /                                \
             Integration Tests (~20 tests)        Performance Tests (5 tests)
          Story 3.1, 3.2, 3.3 integration      Story 3.0 (Ollama), 3.5 (load)
            /                                 \
          /                                     \
    Unit Tests (~40 new tests)              Regression Tests (270+ existing)
  HybridReactive, Environment,              Epic 1-2 backward compatibility
  FastAPI, Ollama client                    validation (AC-3.5.4)
```

**Expected Test Count:**
- **New Unit Tests**: ~40 tests (Stories 3.0, 3.1, 3.2, 3.3)
- **New Integration Tests**: ~20 tests (Stories 3.1, 3.2, 3.3)
- **New E2E Tests**: 10+ tests (Story 3.5)
- **New Performance Tests**: 5 tests (Stories 3.0, 3.5)
- **Total New Tests**: ~75 tests
- **Total Tests (Epic 3)**: ~345 tests (270 regression + 75 new)

### Test Coverage by Acceptance Criteria

| Story | Total ACs | Unit Test ACs | Integration Test ACs | E2E Test ACs | Performance Test ACs | Manual Test ACs |
|-------|-----------|---------------|---------------------|--------------|---------------------|----------------|
| 3.0 | 5 | 4 | 0 | 0 | 1 | 1 |
| 3.1 | 7 | 3 | 3 | 0 | 1 | 0 |
| 3.2 | 8 | 0 | 4 | 1 | 0 | 5 |
| 3.3 | 5 | 2 | 2 | 0 | 0 | 1 |
| 3.4 | 4 (opt) | 0 | 0 | 1 | 0 | 3 |
| 3.5 | 5 | 0 | 0 | 3 | 1 | 1 |
| **Total** | **34** | **9** | **9** | **5** | **3** | **11** |

*(Note: Some ACs require multiple test types, so totals exceed AC count)*

### Test Implementation by Story

**Story 3.0: Ollama Setup & Validation**

- **Test Files**:
  - `tests/test_ollama_setup.py` (unit tests)
  - `scripts/install_ollama.sh` (installation script with self-test)

- **Key Tests**:
  - `test_ollama_service_running()` - Verify HTTP 200 from `localhost:11434/api/tags`
  - `test_model_loaded()` - Assert model in `ollama list` output
  - `test_inference_latency()` - 10 inference calls, validate p90 <1200ms, avg <1000ms (adjusted for TinyLlama)
  - `test_json_output_parsing()` - 100 prompts, assert >95% parse success rate

- **Performance Benchmark**: Latency validation (AC-3.0.3)

**Story 3.1: Hybrid Reactive Controller**

- **Test Files**:
  - `tests/unit/test_reactive_controller.py` (unit tests)
  - `tests/integration/test_reactive_integration.py` (integration tests)
  - `tests/performance/test_benchmarking.py` (E2E performance)

- **Key Unit Tests**:
  - `test_critical_emergency_stop()` - Mock Lidar=0.1m, assert EMERGENCY_STOP, latency <1ms
  - `test_moderate_ollama_detour()` - Mock Lidar=0.3m, assert DETOUR, verify detour_plan
  - `test_normal_passthrough()` - Mock Lidar=1.0m, assert CONTINUE, latency <10ms
  - `test_reactive_log_populated()` - Verify log structure (timestamp, type, reason, action)

- **Key Integration Tests**:
  - `test_actor_reactive_integration()` - Actor calls reactive controller, executes detour
  - `test_verifier_tolerance_adjustment()` - Reactive log triggers 0.1m → 0.3m tolerance
  - `test_ollama_cache_hit()` - Verify LRU cache reduces Ollama calls

- **Performance Benchmark** (AC-3.1.7):
  - Run 50+ missions with reactive controller enabled
  - Measure: collision rate, success rate, replanning frequency, mission time
  - Assert: <5% collision, >95% success, <0.2 replans/mission
  - Generate: `docs/epic3_benchmark_report.md`

**Story 3.2: FastAPI Web Control Server**

- **Test Files**:
  - `tests/integration/test_fastapi_server.py` (integration tests)
  - `tests/integration/test_websocket_client.py` (WebSocket tests)

- **Key Integration Tests**:
  - `test_websocket_control_endpoint()` - Send MissionRequest, verify Orchestrator called
  - `test_status_broadcast_frequency()` - Receive 100 messages, assert ~10Hz (100ms intervals)
  - `test_async_mission_execution()` - Verify mission runs in background via `asyncio.to_thread()`
  - `test_websocket_reconnect()` - Disconnect client, verify auto-reconnect logic

- **Manual Tests** (documented in test plan):
  - Open `http://localhost:8000` in browser, verify UI renders
  - Test natural language command input, verify execution
  - Verify `/docs` endpoint shows FastAPI Swagger UI
  - Execute deployment script, verify server starts

**Story 3.3: Environment-Aware Planning**

- **Test Files**:
  - `tests/unit/test_environment_detector.py` (unit tests)
  - `tests/integration/test_rag_filtering.py` (integration tests)

- **Key Unit Tests**:
  - `test_detect_indoor()` - Mock GPS=0.2, Lidar=2m, assert "indoor"
  - `test_detect_outdoor()` - Mock GPS=0.9, Lidar=10m, assert "outdoor"
  - `test_detect_warehouse()` - Mock GPS=0.1, Lidar=8m, assert "warehouse"
  - `test_detect_hospital()` - Mock GPS=0.3, Lidar=3m, specific patterns, assert "hospital"
  - `test_unknown_environment()` - Conflicting signals, assert "unknown"

- **Key Integration Tests**:
  - `test_planner_rag_filtering()` - Set environment="indoor", verify Planner retrieves only indoor constraints
  - `test_environment_metadata_extension()` - Verify ChromaDB where filter works

**Story 3.4: React Web UI Dashboard (OPTIONAL)**

- **Test Files** (if implemented):
  - `ui/src/__tests__/App.test.tsx` (React component tests)
  - Manual testing (primary validation method)

- **Manual Tests**:
  - Run React dev server, verify WebSocket connection established
  - Verify all dashboard components render (command panel, map, Lidar, camera, logs)
  - Test responsive layout (resize browser window)
  - Build production bundle, verify FastAPI serves static files

**Story 3.5: Epic 3 Integration Testing**

- **Test Files**:
  - `tests/integration/test_epic3_e2e.py` (E2E tests)
  - `tests/performance/test_load_testing.py` (load tests)
  - `tests/integration/test_error_handling.py` (failure scenarios)
  - `docs/test_plan_epic3.md` (test plan document)
  - `docs/integration_test_report.md` (test results report)

- **E2E Test Scenarios** (10+ scenarios):
  1. `test_web_to_reactive_controller_e2e()` - Web UI → Reactive detour → Success
  2. `test_environment_detection_integration()` - Sensor data → Environment detection → RAG filter → Plan
  3. `test_full_workflow_indoor()` - Indoor mission with reactive events
  4. `test_full_workflow_outdoor()` - Outdoor mission with GPS navigation
  5. `test_concurrent_missions()` - 3 missions sequentially, verify isolation
  6. `test_reactive_log_visualization()` - WebSocket receives reactive events in real-time
  7. `test_ollama_moderate_detour_e2e()` - MODERATE level detour executed successfully
  8. `test_critical_emergency_stop_e2e()` - CRITICAL level emergency stop + replanning
  9. `test_mission_success_with_multiple_detours()` - Multiple reactive interventions in single mission
  10. `test_environment_change_between_missions()` - Different environments across missions

- **Load Tests** (AC-3.5.2):
  - `test_concurrent_web_requests()` - 10 simultaneous WebSocket connections
  - `test_websocket_message_throughput()` - 100+ messages, verify stability
  - `test_ollama_concurrent_inference()` - Simulate multiple reactive calls
  - Assert: All responses <5 seconds

- **Error Handling Tests** (AC-3.5.3):
  - `test_ollama_failure_graceful_degradation()` - Stop Ollama service, verify fallback to rules
  - `test_websocket_disconnect_reconnect()` - Client disconnect, verify auto-reconnect
  - `test_network_error_handling()` - Simulate network errors, verify error responses
  - `test_webots_simulator_error_recovery()` - Simulate Webots crash, verify cleanup

- **Regression Tests** (AC-3.5.4):
  - Run all Epic 1-2 tests: `pytest tests/ -v --cov=src --cov-report=html`
  - Assert: 270+ tests pass
  - Assert: Code coverage >80%
  - Generate HTML coverage report for inspection

### Test Execution Schedule

| Phase | Timeline | Tests Executed | Success Criteria |
|-------|----------|----------------|------------------|
| **Story 3.0 Completion** | Day 0 (2h) | Ollama setup tests (4 tests) | All tests pass, latency <300ms p90 |
| **Story 3.1 Completion** | Day 1-2 (14h) | Reactive unit tests (10), integration (5), benchmark | Unit/integration pass, collision <5% |
| **Story 3.2 Completion** | Day 3 (9h) | FastAPI integration tests (6), manual tests | Integration pass, manual checklist complete |
| **Story 3.3 Completion** | Day 4 (6h) | Environment unit tests (5), integration (2) | All tests pass, RAG filtering works |
| **Story 3.4 (Optional)** | Day 5 (12h) | React component tests, manual UI tests | UI functional, production build succeeds |
| **Story 3.5 Integration** | Day 6 (4h) | E2E tests (10+), load tests (4), error tests (4), regression (270+) | All tests pass, coverage >80% |
| **Epic 3 Validation** | Day 7 | Full test suite (345+ tests), benchmark report review | All tests pass, performance targets met |

### Test Data and Fixtures

**Mock Sensor Data** (for environment detection and reactive testing):
- Indoor scenario: `{"gps_signal": 0.2, "lidar_ranges": [1.5, 2.0, ...], "camera_brightness": 150}`
- Outdoor scenario: `{"gps_signal": 0.9, "lidar_ranges": [10.0, 12.0, ...], "camera_brightness": 220}`
- Warehouse scenario: `{"gps_signal": 0.1, "lidar_ranges": [8.0, 9.0, ...], "camera_brightness": 180}`
- Hospital scenario: `{"gps_signal": 0.3, "lidar_ranges": [3.0, 4.0, ...], "camera_brightness": 200}`

**Obstacle Scenarios** (for reactive controller testing):
- CRITICAL: Obstacle at 0.1m (expected: EMERGENCY_STOP)
- MODERATE: Obstacle at 0.3m (expected: DETOUR via Ollama)
- NORMAL: Clear path at 1.5m (expected: CONTINUE)

**Mission Commands** (for E2E testing):
- Korean: "장애물 회피하며 5미터 전진"
- Korean: "실내 환경에서 목표 지점으로 이동"
- Korean: "야외에서 GPS를 사용하여 좌표로 이동"

### Test Environment Setup

**Prerequisites:**
- Python 3.11+ with all Epic 3 dependencies installed
- Webots R2025a running with test world loaded
- Ollama service running with tinyllama model pulled
- FastAPI server running on port 8000 (for integration tests)
- Sufficient resources: 8GB RAM, 4 CPU cores

**Setup Scripts:**
- `scripts/setup_test_env.sh` - Install dependencies, start services
- `scripts/teardown_test_env.sh` - Stop services, cleanup temp files

**Continuous Testing (Local Development):**
```bash
# Run unit tests only (fast feedback)
pytest tests/unit/ -v

# Run unit + integration tests
pytest tests/unit/ tests/integration/ -v

# Run full test suite including E2E (slow, run before story completion)
pytest tests/ -v --cov=src --cov-report=html

# Run performance benchmarks (Story 3.1, 3.5)
pytest tests/performance/ -v --benchmark-only
```

### Test Reporting and Documentation

**Test Reports Generated:**
1. **Pytest HTML Report**: `htmlcov/index.html` (coverage visualization)
2. **Benchmark Report**: `docs/epic3_benchmark_report.md` (AC-3.1.7)
3. **Integration Test Report**: `docs/integration_test_report.md` (AC-3.5.5)
4. **Test Plan**: `docs/test_plan_epic3.md` (test scenarios and procedures)

**Test Metrics Tracked:**
- Test count: 345+ total (270 regression + 75 new)
- Code coverage: Target >80% line coverage
- Test execution time: <10 minutes for full suite (goal)
- Failure rate: 0% (all tests must pass before story completion)

### Acceptance Gate (Story 3.5 - Epic Completion)

Epic 3 is considered **COMPLETE** when all of the following conditions are met:

✅ **All 34 acceptance criteria validated** (30 core + 4 optional if Story 3.4 implemented)
✅ **345+ tests passing** (270 Epic 1-2 regression + 75 Epic 3 new tests)
✅ **Code coverage >80%** (measured by pytest-cov)
✅ **Performance targets met**: Collision <5%, Success >95%, Replanning <0.2/mission
✅ **Ollama latency validated**: p90 <1200ms, avg <1000ms (AC-3.0.3 - adjusted for TinyLlama)
✅ **E2E integration tests pass**: All 10+ scenarios execute successfully
✅ **Load tests pass**: 10 concurrent clients, <5s response time
✅ **Error handling validated**: Graceful degradation when Ollama/WebSocket fails
✅ **Documentation complete**: Test plan, benchmark report, integration test report
✅ **sprint-status.yaml updated**: epic-3 marked as "contexted"

**Final Validation Checklist** (Story 3.5):
- [ ] Run full pytest suite: `pytest tests/ -v --cov=src`
- [ ] Review HTML coverage report: `htmlcov/index.html`
- [ ] Execute benchmark: `pytest tests/performance/test_benchmarking.py -v`
- [ ] Review benchmark report: `docs/epic3_benchmark_report.md`
- [ ] Verify all 34 ACs traced in traceability matrix
- [ ] Manual testing checklist completed (11 manual test items)
- [ ] Regression tests all pass (270+ Epic 1-2 tests)
- [ ] Integration test report generated: `docs/integration_test_report.md`
- [ ] Update sprint-status.yaml: `epic-3: contexted`

---

**End of Technical Specification**
