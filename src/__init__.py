"""
LLM_ROBOT_2 - Generic LLM-based Robot Control Framework

Multi-agent system for natural language robot control.
"""

from .orchestrator import MissionOrchestrator, OrchestratorFactory
from .agents import (
    PlannerAgent,
    PlannerAgentFactory,
    ActorAgent,
    ActorAgentFactory,
    VerifierAgent,
    VerifierAgentFactory
)
from .schemas import (
    RobotAction,
    ActionType,
    RobotState,
    RobotStatus,
    SensorData,
    MissionCommand,
    MissionStatus
)

__version__ = "1.0.0"

__all__ = [
    # Orchestrator
    "MissionOrchestrator",
    "OrchestratorFactory",
    # Agents
    "PlannerAgent",
    "PlannerAgentFactory",
    "ActorAgent",
    "ActorAgentFactory",
    "VerifierAgent",
    "VerifierAgentFactory",
    # Schemas
    "RobotAction",
    "ActionType",
    "RobotState",
    "RobotStatus",
    "SensorData",
    "MissionCommand",
    "MissionStatus",
]
