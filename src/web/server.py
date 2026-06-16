"""
FastAPI Web Control Server

Main server application providing:
- REST API endpoints for mission control
- WebSocket endpoints for real-time updates
- Web UI serving
- Natural language robot command processing

Story 3.2: FastAPI Web Control Server - Tasks 1, 3, 4, 5
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import List, Dict, Any, Optional
import asyncio
import os
from datetime import datetime
from loguru import logger

from .schemas import MissionRequest, MissionResponse, SystemStatus, HealthResponse
from ..schemas import MissionCommand, RobotState
from ..orchestrator import MissionOrchestrator


# ============================================================================
# ConnectionManager Class - WebSocket Connection Management
# ============================================================================

class ConnectionManager:
    """
    Manages active WebSocket connections for real-time status broadcasting.

    Responsibilities:
    - Accept new WebSocket connections
    - Track active connections
    - Broadcast messages to all connected clients
    - Remove disconnected clients

    Story 3.2: Task 3 - WebSocket Connection Manager
    """

    def __init__(self):
        """Initialize connection manager with empty connection list."""
        self.active_connections: List[WebSocket] = []
        self.connection_count = 0
        logger.info("ConnectionManager initialized")

    async def connect(self, websocket: WebSocket):
        """
        Accept a new WebSocket connection and add to active list.

        Args:
            websocket: WebSocket connection to accept

        Example:
            await manager.connect(websocket)
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_count += 1
        logger.info(f"WebSocket connected. Total active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """
        Remove WebSocket from active connections.

        Args:
            websocket: WebSocket connection to remove

        Example:
            manager.disconnect(websocket)
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total active: {len(self.active_connections)}")

    async def send_to_client(self, message: dict, websocket: WebSocket):
        """
        Send JSON message to a specific client.

        Args:
            message: Dictionary to send as JSON
            websocket: Target WebSocket connection

        Example:
            await manager.send_to_client({"status": "ok"}, websocket)
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send message to client: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: dict):
        """
        Broadcast JSON message to all connected clients.

        Args:
            message: Dictionary to send as JSON to all clients

        Example:
            await manager.broadcast({"type": "status_update", "data": {...}})
        """
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to client: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    def get_connection_count(self) -> int:
        """Get current number of active connections."""
        return len(self.active_connections)


# ============================================================================
# FastAPI Application Setup
# ============================================================================

app = FastAPI(
    title="LLM Robot Control API",
    version="1.0.0",
    description="""
    Web-based control interface for LLM_ROBOT_2 multi-agent robot system.

    Features:
    - Natural language mission commands via REST API
    - Real-time status updates via WebSocket
    - Reactive controller integration
    - Multi-agent system (Planner/Actor/Verifier) execution

    Story 3.2: FastAPI Web Control Server
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for React frontend compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://localhost:8000",  # FastAPI server
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for web UI
# Get path to templates directory relative to this file
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
if os.path.exists(templates_dir):
    from fastapi.responses import FileResponse

    @app.get("/")
    async def serve_root():
        """Serve the web UI index.html at root path."""
        index_path = os.path.join(templates_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
            return {"message": "Web UI not found. Check templates directory."}

    logger.info(f"Web UI templates directory mounted: {templates_dir}")
else:
    logger.warning(f"Templates directory not found: {templates_dir}")

# Initialize ConnectionManager
manager = ConnectionManager()

# Global orchestrator instance (initialized on startup)
orchestrator: Optional[MissionOrchestrator] = None
server_start_time = datetime.now()

# Background task state
status_broadcast_task: Optional[asyncio.Task] = None
broadcast_enabled = False


# ============================================================================
# Startup and Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Initialize server resources on startup.

    Note: Orchestrator requires Webots Robot instance which is not
    available in web server context. Will be initialized when needed.

    Story 3.2: Task 8.1 - Start background broadcasting
    """
    logger.info("FastAPI Web Control Server starting...")
    logger.info(f"Server docs available at: http://localhost:8000/docs")
    logger.info(f"WebSocket endpoints: /ws/control, /ws/robot-status")

    # Start background status broadcasting if orchestrator is available
    if orchestrator:
        await start_status_broadcasting()
        logger.info("Status broadcasting started automatically")
    else:
        logger.info("Orchestrator not initialized - status broadcasting disabled")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Clean up resources on server shutdown.

    Story 3.2: Task 8.1 - Stop background broadcasting
    """
    logger.info("FastAPI Web Control Server shutting down...")

    # Stop background broadcasting
    await stop_status_broadcasting()

    # Close all active WebSocket connections
    for connection in manager.active_connections[:]:
        try:
            await connection.close()
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")


# ============================================================================
# REST API Endpoints - Task 5
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns server status and basic metrics.

    Story 3.2: Task 5.3 - Health endpoint
    """
    uptime = (datetime.now() - server_start_time).total_seconds()

    return HealthResponse(
        status="ok" if orchestrator else "degraded",
        timestamp=datetime.now(),
        details={
            "uptime_seconds": uptime,
            "active_connections": manager.get_connection_count(),
            "orchestrator_status": "ready" if orchestrator else "not_initialized",
            "total_connections": manager.connection_count
        }
    )


@app.get("/api/status", response_model=SystemStatus, tags=["API"])
async def get_status():
    """
    Get current robot status.

    Returns:
        SystemStatus: Current robot position, sensors, mission state

    Story 3.2: Task 5.2 - Status endpoint (updated with Task 8.2)
    """
    return await get_current_system_status()


@app.post("/api/mission", response_model=MissionResponse, tags=["API"])
async def execute_mission_api(request: MissionRequest):
    """
    Execute mission command asynchronously.

    Args:
        request: MissionRequest with natural language command

    Returns:
        MissionResponse: Mission execution result

    Raises:
        HTTPException: If orchestrator not initialized or execution fails

    Story 3.2: Task 5.1 - Mission execution endpoint
    """
    if not orchestrator:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not initialized. Robot must be running."
        )

    # Convert MissionRequest to MissionCommand
    mission = MissionCommand(
        command=request.command,
        language=request.language
    )

    try:
        # Execute mission asynchronously (wrapped with asyncio.to_thread)
        # This prevents blocking the FastAPI event loop
        start_time = datetime.now()

        result = await asyncio.to_thread(
            orchestrator.execute_mission,
            mission
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Extract reactive events from robot state
        reactive_events = []
        if 'robot_state' in result and hasattr(result['robot_state'], 'reactive_log'):
            reactive_events = result['robot_state'].reactive_log

        # Get final position
        final_position = (0.0, 0.0, 0.0)
        if 'robot_state' in result:
            final_position = result['robot_state'].position

        # Create response
        response = MissionResponse(
            success=result.get('success', False),
            message=result.get('message', 'Mission execution completed'),
            duration_seconds=duration,
            final_position=final_position,
            reactive_events=reactive_events
        )

        # Broadcast completion to all WebSocket clients
        await manager.broadcast({
            "type": "mission_complete",
            "result": response.model_dump()
        })

        return response

    except Exception as e:
        logger.error(f"Mission execution failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Mission execution failed: {str(e)}"
        )


@app.post("/api/stop", tags=["API"])
async def stop_robot():
    """
    Emergency stop - immediately halt all robot movement.

    Returns:
        JSONResponse: Stop confirmation

    Raises:
        HTTPException: If orchestrator not initialized
    """
    if not orchestrator:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not initialized. Robot must be running."
        )

    try:
        # Stop motors immediately
        if hasattr(orchestrator, 'actor') and orchestrator.actor:
            orchestrator.actor.left_motor.setVelocity(0.0)
            orchestrator.actor.right_motor.setVelocity(0.0)

            # Clear execution flag
            orchestrator.is_executing = False

            logger.warning("🛑 Emergency stop triggered via Web UI")

        return JSONResponse({
            "success": True,
            "message": "Robot stopped successfully",
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Emergency stop failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Emergency stop failed: {str(e)}"
        )


# ============================================================================
# WebSocket Endpoints - Task 4 (Placeholder for Phase 2)
# ============================================================================

@app.websocket("/ws/control")
async def websocket_control_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for mission command submission.

    Bidirectional communication:
    - Client → Server: MissionRequest JSON
    - Server → Client: MissionResponse JSON

    Story 3.2: Task 4 - WebSocket command endpoint

    Note: Full implementation in Phase 2
    """
    await manager.connect(websocket)

    try:
        while True:
            # Receive command from client
            data = await websocket.receive_json()

            # Validate as MissionRequest
            try:
                request = MissionRequest(**data)
            except Exception as e:
                await websocket.send_json({
                    "error": "Invalid request format",
                    "details": str(e)
                })
                continue

            # Execute mission (same as REST API)
            if not orchestrator:
                await websocket.send_json({
                    "error": "Orchestrator not initialized"
                })
                continue

            # Execute mission in background thread (non-blocking)
            try:
                # Send acknowledgment
                await websocket.send_json({
                    "status": "executing",
                    "message": f"Mission started: {request.command}"
                })

                # Convert MissionRequest to MissionCommand
                mission = MissionCommand(
                    command=request.command,
                    language=request.language,
                    priority=request.priority
                    # timeout_seconds uses default=60.0 from MissionCommand schema
                )

                # Execute mission (blocking call, run in thread)
                result = await asyncio.to_thread(
                    orchestrator.execute_mission,
                    mission
                )

                # Calculate duration
                duration_seconds = result.get("duration_seconds", 0.0)
                if not duration_seconds and "started_at" in result and "completed_at" in result:
                    try:
                        duration_seconds = (result["completed_at"] - result["started_at"]).total_seconds()
                    except:
                        duration_seconds = 0.0

                # Get final position from robot state
                final_position = [0.0, 0.0, 0.0]
                if "robot_state" in result and hasattr(result["robot_state"], "get_position"):
                    pos = result["robot_state"].get_position()
                    if pos:
                        final_position = list(pos)

                # Send result back to client
                # Convert complex objects to JSON-serializable format
                def safe_serialize(obj, depth=0):
                    """Safely convert objects to JSON-serializable format."""
                    if depth > 10:  # Prevent infinite recursion
                        return str(obj)
                    if obj is None:
                        return None
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    elif isinstance(obj, (str, int, float, bool)):
                        return obj
                    elif isinstance(obj, bytes):
                        return f"<bytes: {len(obj)} bytes>"
                    elif isinstance(obj, dict):
                        return {str(k): safe_serialize(v, depth + 1) for k, v in obj.items()}
                    elif isinstance(obj, (list, tuple)):
                        return [safe_serialize(item, depth + 1) for item in obj]
                    elif hasattr(obj, 'model_dump'):  # Pydantic model
                        return safe_serialize(obj.model_dump(), depth + 1)
                    elif hasattr(obj, '__dict__'):
                        return safe_serialize(obj.__dict__, depth + 1)
                    else:
                        return str(obj)

                # Safe access to result fields FIRST (before any serialization)
                is_success = result.get("success", False)
                message = result.get("message", "Mission completed" if is_success else "Mission failed")
                status_str = "completed" if is_success else "failed"

                # Try to serialize full result, but always send at least minimal response
                try:
                    serialized_result = safe_serialize(result)
                    await websocket.send_json({
                        "status": status_str,
                        "success": is_success,
                        "message": message,
                        "attempts": result.get("attempts", 1),
                        "duration_seconds": duration_seconds,
                        "final_position": final_position,
                        "data": serialized_result
                    })
                    logger.info(f"Mission result sent to client: status={status_str}")
                except Exception as send_error:
                    logger.error(f"Failed to send full mission result: {send_error}")
                    # CRITICAL: Always send minimal response so client can reset state
                    try:
                        await websocket.send_json({
                            "status": status_str,
                            "success": is_success,
                            "message": message,
                            "duration_seconds": duration_seconds
                        })
                        logger.info(f"Minimal mission result sent to client: status={status_str}")
                    except Exception as fallback_error:
                        logger.error(f"Failed to send even minimal result: {fallback_error}")

            except Exception as e:
                logger.error(f"Mission execution error: {e}", exc_info=True)
                await websocket.send_json({
                    "status": "error",
                    "message": f"Execution failed: {str(e)}"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket /ws/control client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.websocket("/ws/robot-status")
async def websocket_status_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time status broadcasting.

    Server → Client: SystemStatus JSON every 100ms (10Hz)

    This endpoint now benefits from the background broadcasting task.
    When a client connects, it will receive status updates from the
    background worker that broadcasts to all connected clients.

    Story 3.2: Task 8.4 - WebSocket status broadcast endpoint (Phase 2 complete)
    """
    await manager.connect(websocket)

    # Ensure background broadcasting is running
    if not broadcast_enabled and orchestrator:
        await start_status_broadcasting()

    try:
        # Keep connection alive and receive any client messages
        # The actual status broadcasting is handled by status_broadcast_worker()
        while True:
            # Wait for client messages (or pings to keep connection alive)
            try:
                # Receive with timeout to check for disconnections
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)

                # Handle client control messages (e.g., toggle broadcasting)
                if data.get("action") == "toggle_broadcast":
                    enabled = data.get("enabled", True)
                    toggle_status_broadcasting(enabled)
                    await websocket.send_json({
                        "type": "broadcast_control",
                        "enabled": enabled
                    })

            except asyncio.TimeoutError:
                # No message received, send ping to keep connection alive
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket /ws/robot-status client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# ============================================================================
# Helper Functions
# ============================================================================

async def get_current_system_status() -> SystemStatus:
    """
    Get current robot system status for real-time broadcasting.

    Returns:
        SystemStatus: Current position, sensors, mission state, reactive log summary

    Story 3.2: Task 8.2 - System status aggregation
    """
    if not orchestrator or not hasattr(orchestrator, 'actor'):
        # Return idle status when orchestrator not available
        return SystemStatus(
            position=(0.0, 0.0, 0.0),
            sensors={"status": "orchestrator_not_initialized"},
            mission_state="idle",
            reactive_log_summary={},
            timestamp=datetime.now()
        )

    try:
        # Get current robot state from Actor agent
        robot_state = orchestrator.actor.get_robot_state()

        # Extract position
        position = robot_state.get_position()
        if not position:
            position = (0.0, 0.0, 0.0)

        # Summarize sensor data
        sensors_summary = {
            "lidar_min": robot_state.sensors.lidar_min_distance or 999.0,
            "lidar_avg": robot_state.sensors.lidar_avg_distance or 999.0,
            "camera_active": robot_state.sensors.camera_has_data,
            "yaw": robot_state.sensors.yaw or 0.0,
            "battery": robot_state.battery_level
        }

        # Summarize reactive log by intervention type (Story 3.1)
        reactive_summary = {}
        if robot_state.reactive_log:
            for entry in robot_state.reactive_log:
                intervention_type = entry.get('type', 'UNKNOWN')
                reactive_summary[intervention_type] = reactive_summary.get(intervention_type, 0) + 1

        # Add dynamic objects info (pickup object position)
        if hasattr(orchestrator, 'dynamic_objects') and orchestrator.dynamic_objects:
            sensors_summary["dynamic_objects"] = orchestrator.dynamic_objects

        # Determine mission state based on robot status
        mission_state_map = {
            "idle": "idle",
            "moving": "executing",
            "rotating": "executing",
            "scanning": "executing",
            "error": "failed",
            "stopped": "complete"
        }
        mission_state = mission_state_map.get(robot_state.status.value, "idle")

        return SystemStatus(
            position=position,
            sensors=sensors_summary,
            mission_state=mission_state,
            reactive_log_summary=reactive_summary,
            timestamp=datetime.now()
        )

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        # Return error status
        return SystemStatus(
            position=(0.0, 0.0, 0.0),
            sensors={"error": str(e)},
            mission_state="idle",
            reactive_log_summary={},
            timestamp=datetime.now()
        )


async def status_broadcast_worker():
    """
    Background worker that broadcasts robot status at 10Hz (every 100ms).

    This task runs continuously while broadcast_enabled is True,
    sending SystemStatus updates to all connected WebSocket clients.

    Story 3.2: Task 8.1 - Background broadcasting task
    """
    logger.info("Status broadcast worker started (10Hz)")

    while broadcast_enabled:
        try:
            # Get current status
            status = await get_current_system_status()

            # Broadcast to all connected clients
            if manager.get_connection_count() > 0:
                # Convert to dict with JSON-compatible types
                status_dict = status.model_dump(mode='json')
                message = {
                    "type": "status_update",
                    "data": status_dict
                }
                # DEBUG: Log first broadcast to verify structure
                if not hasattr(status_broadcast_worker, '_logged_first'):
                    logger.debug(f"Broadcasting status message structure: {list(message.keys())}")
                    status_broadcast_worker._logged_first = True
                await manager.broadcast(message)

            # Wait 100ms for 10Hz frequency
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error in status broadcast worker: {e}")
            await asyncio.sleep(0.1)  # Continue despite errors

    logger.info("Status broadcast worker stopped")


def set_orchestrator(orch: MissionOrchestrator):
    """
    Set the global orchestrator instance and start status broadcasting.

    This should be called from the main application after
    initializing the Webots robot and orchestrator.

    Args:
        orch: Initialized MissionOrchestrator instance

    Example:
        from src.web.server import app, set_orchestrator
        orchestrator = MissionOrchestrator(robot, api_key=...)
        set_orchestrator(orchestrator)

    Story 3.2: Task 6 - Orchestrator integration
    """
    global orchestrator, broadcast_enabled, status_broadcast_task
    orchestrator = orch
    logger.info("Orchestrator instance registered with web server")

    # Start background broadcasting task
    if not broadcast_enabled:
        broadcast_enabled = True
        # Note: This requires asyncio event loop to be running
        # In production, call start_status_broadcasting() after server startup
        logger.info("Status broadcasting will start when event loop is available")


async def start_status_broadcasting():
    """
    Start the background status broadcasting task.

    This should be called from an async context after the event loop is running.

    Story 3.2: Task 8.1 - Broadcasting lifecycle management
    """
    global status_broadcast_task, broadcast_enabled

    if status_broadcast_task and not status_broadcast_task.done():
        logger.warning("Status broadcasting already running")
        return

    broadcast_enabled = True
    status_broadcast_task = asyncio.create_task(status_broadcast_worker())
    logger.info("Status broadcasting task started")


async def stop_status_broadcasting():
    """
    Stop the background status broadcasting task.

    Story 3.2: Task 8.1 - Broadcasting lifecycle management
    """
    global status_broadcast_task, broadcast_enabled

    broadcast_enabled = False

    if status_broadcast_task and not status_broadcast_task.done():
        status_broadcast_task.cancel()
        try:
            await status_broadcast_task
        except asyncio.CancelledError:
            pass
        logger.info("Status broadcasting task stopped")


def toggle_status_broadcasting(enabled: bool):
    """
    Toggle status broadcasting on/off.

    Args:
        enabled: True to enable, False to disable

    Story 3.2: Task 8.5 - Broadcasting control
    """
    global broadcast_enabled
    broadcast_enabled = enabled
    logger.info(f"Status broadcasting {'enabled' if enabled else 'disabled'}")


# ============================================================================
# Main Entry Point (for development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting FastAPI Web Control Server (development mode)...")
    logger.warning("Note: Orchestrator not initialized. Robot control will not work.")
    logger.info("Use this server for API testing only.")

    uvicorn.run(
        "src.web.server:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
