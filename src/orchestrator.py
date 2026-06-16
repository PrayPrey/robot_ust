"""
Multi-Agent Orchestrator

Coordinates Planner, Actor, and Verifier agents to execute missions.

Story 2.5: Enhanced with structured logging for monitoring and evaluation.
Story 3.3: Added RAG integration with RobotKnowledgeBase for environment-aware planning.
"""

from typing import Optional, Dict, Any, List
from loguru import logger
import os
import threading
from datetime import datetime

from .agents import PlannerAgent, ActorAgent, VerifierAgent
from .schemas import MissionCommand, RobotState, MissionStatus, FailureReason, ReplanRequest
from .utils import LoggerConfig
from .rag import RobotKnowledgeBase


class MissionOrchestrator:
    """
    Orchestrates multi-agent mission execution.

    Workflow:
    1. Planner: Natural language → Action plan
    2. Actor: Execute action plan on Webots
    3. Verifier: Check success/failure
    4. If failed and retries available: Loop back to Planner
    5. Return final result

    Example:
        >>> from controller import Robot
        >>> robot = Robot()
        >>> orchestrator = MissionOrchestrator(robot, api_key="sk-...")
        >>>
        >>> mission = MissionCommand(
        ...     command="앞으로 2미터 이동 후 주변 탐색",
        ...     language="ko"
        ... )
        >>>
        >>> result = orchestrator.execute_mission(mission)
        >>> print(f"Success: {result['success']}")
    """

    def __init__(
        self,
        robot,  # Webots Robot instance
        api_key: Optional[str] = None,
        planner_model: str = "gpt-4o",
        actor_model: str = "gpt-4o-mini",
        verifier_model: str = "gpt-4o-mini",
        verbose: bool = True,
        enable_rag: bool = True,
        rag_persist_directory: str = "./data/chromadb",
        step_callback: Optional[callable] = None,  # For Web mode coordination
        dynamic_objects: Optional[Dict[str, Dict[str, float]]] = None  # Dynamic object positions
    ):
        """
        Initialize Multi-Agent Orchestrator.

        Args:
            robot: Webots Robot instance
            api_key: OpenAI API key (reads from env if None)
            planner_model: Model for Planner Agent
            actor_model: Model for Actor Agent
            verifier_model: Model for Verifier Agent
            verbose: Enable verbose logging
            enable_rag: Enable RAG integration for environment-aware planning (Story 3.3)
            rag_persist_directory: ChromaDB persist directory for RAG
            dynamic_objects: Dictionary of dynamic object positions (e.g., pickup_object)
        """
        self.robot = robot
        self.verbose = verbose
        self.is_executing = False  # Flag to coordinate robot.step() calls with web controller
        self.dynamic_objects = dynamic_objects or {}  # Store dynamic object positions

        # Get API key
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment")

        # Initialize agents
        logger.info("Initializing Multi-Agent System...")

        # Initialize RAG Knowledge Base (Story 3.3)
        knowledge_base = None
        if enable_rag:
            try:
                logger.info(f"Initializing RobotKnowledgeBase (persist_directory={rag_persist_directory})...")
                knowledge_base = RobotKnowledgeBase(
                    persist_directory=rag_persist_directory,
                    openai_api_key=api_key
                )

                # Populate knowledge base if empty
                if knowledge_base.capabilities_collection.count() == 0:
                    logger.info("Populating RobotKnowledgeBase from data files...")

                    # Use absolute paths for data files
                    from pathlib import Path
                    project_root = Path(__file__).parent.parent
                    capabilities_path = str(project_root / "src" / "rag" / "data" / "robot_capabilities.json")
                    constraints_path = str(project_root / "src" / "rag" / "data" / "environment_constraints.json")

                    knowledge_base.populate_robot_capabilities(capabilities_path)
                    knowledge_base.populate_environment_constraints(constraints_path)
                    logger.info("RobotKnowledgeBase populated successfully")

                logger.info(f"RobotKnowledgeBase initialized with {knowledge_base.capabilities_collection.count()} capabilities, "
                           f"{knowledge_base.constraints_collection.count()} constraints")
            except Exception as e:
                logger.warning(f"Failed to initialize RobotKnowledgeBase: {e}")
                logger.warning("Continuing without RAG integration")
                knowledge_base = None

        self.planner = PlannerAgent(
            api_key=api_key,
            knowledge_base=knowledge_base,  # Story 3.3: Pass knowledge base
            model=planner_model,
            temperature=0.3,
            verbose=verbose,
            dynamic_objects=self.dynamic_objects  # Pass dynamic object positions
        )

        # Story 3.6: Add planner_agent alias for compatibility with integration tests
        self.planner_agent = self.planner

        # Story 3.7: Add mission lock for concurrent mission handling
        self._mission_lock = threading.Lock()
        self._mission_in_progress = False

        # Story 3.7: Add emergency stop flag
        self._emergency_stop_flag = False

        self.actor = ActorAgent(
            robot=robot,
            api_key=api_key,
            model=actor_model,
            temperature=0.1,
            verbose=verbose,
            step_callback=step_callback  # Pass callback for Web mode
        )

        self.verifier = VerifierAgent(
            api_key=api_key,
            knowledge_base=knowledge_base,  # Pass RAG for goal location verification
            model=verifier_model,
            temperature=0.1,
            verbose=verbose
        )

        rag_status = "enabled" if knowledge_base else "disabled"
        logger.info(f"Multi-Agent System initialized successfully (RAG: {rag_status})")

    def execute_mission(
        self,
        mission: MissionCommand,
        current_state: Optional[RobotState] = None
    ) -> Dict[str, Any]:
        """
        Execute complete mission with Planner-Actor-Verifier workflow.

        Args:
            mission: Mission command to execute
            current_state: Current robot state (optional)

        Returns:
            Result dictionary with success status, message, report, and execution_log
        """
        # Story 3.7: Acquire mission lock for concurrent mission handling
        acquired = self._mission_lock.acquire(timeout=5.0)
        if not acquired:
            logger.warning("Mission lock acquisition failed - another mission in progress")
            return {
                "success": False,
                "message": "Another mission is currently in progress",
                "report": {},
                "attempts": 0,
                "final_state": None,
                "execution_log": []
            }

        try:
            self._mission_in_progress = True

            # Story 3.7: Reset emergency stop flag at mission start
            self._emergency_stop_flag = False

            # Story 3.7: Reset environment detector for fresh detection
            if hasattr(self.planner, 'environment_detector') and self.planner.environment_detector:
                if hasattr(self.planner.environment_detector, 'reset'):
                    self.planner.environment_detector.reset()
                    logger.debug("Environment detector reset for new mission")

            # Story 3.7: Initialize execution log
            execution_log: List[Dict[str, Any]] = []

            # Initialize retry configuration
            attempt = 0
            max_attempts = 3

            # Log mission start with structured data (Story 2.5: AC #1)
            mission_start_time = datetime.now()

            # Story 3.7: Log mission start to execution_log
            execution_log.append({
                "timestamp": mission_start_time.isoformat(),
                "phase": "initialization",
                "action": "mission_start",
                "result": "started",
                "details": {"command": mission.command, "language": mission.language}
            })

            LoggerConfig.log_mission_event(
                event="mission_start",
                status="started",
                details={
                    "command": mission.command,
                    "language": mission.language,
                    "priority": mission.priority,
                    "max_attempts": max_attempts
                }
            )

            logger.info("="*60)
            logger.info(f"Starting Mission Execution")
            logger.info(f"Command: {mission.command}")
            logger.info(f"Language: {mission.language}")
            logger.info(f"Priority: {mission.priority}/10")
            logger.info("="*60)

            # Set flag to prevent web controller from calling robot.step() during execution
            self.is_executing = True

            try:
                while attempt < max_attempts:
                    attempt += 1
                    logger.info(f"\n--- Attempt {attempt}/{max_attempts} ---\n")

                    # Story 3.7: Check emergency stop flag
                    if self._emergency_stop_flag:
                        logger.warning("Emergency stop activated - aborting mission")
                        execution_log.append({
                            "timestamp": datetime.now().isoformat(),
                            "phase": "execution",
                            "action": "emergency_stop",
                            "result": "aborted",
                            "details": {"reason": "Emergency stop flag set"}
                        })
                        return {
                            "success": False,
                            "message": "Mission aborted due to emergency stop",
                            "report": {},
                            "attempts": attempt,
                            "final_state": None,
                            "execution_log": execution_log
                        }

                    try:
                        # Step 1: Planning
                        logger.info("STEP 1: PLANNING")

                        # Story 3.7: Log planning phase
                        execution_log.append({
                            "timestamp": datetime.now().isoformat(),
                            "phase": "planning",
                            "action": "create_plan",
                            "result": "started",
                            "details": {"attempt": attempt}
                        })

                        if not mission.action_plan:
                            # Get current state for context-aware planning
                            if current_state is None and hasattr(self.actor, 'get_robot_state'):
                                current_state = self.actor.get_robot_state()

                            # Save starting position for relative movement verification
                            if current_state and mission.starting_position_x is None:
                                position = current_state.get_position()
                                orientation = current_state.get_orientation()
                                if position:
                                    mission.starting_position_x = position[0]
                                    mission.starting_position_y = position[1]
                                    logger.debug(f"Starting position saved: ({position[0]:.2f}, {position[1]:.2f})")
                                if orientation:
                                    mission.starting_yaw = orientation[2]  # yaw in degrees
                                    logger.debug(f"Starting yaw saved: {orientation[2]:.1f}°")

                            # Generate action plan
                            action_plan = self.planner.plan_mission(mission, current_state)
                            mission.action_plan = action_plan
                            mission.status = MissionStatus.PLANNING

                            logger.info(f"✓ Action plan generated: {len(action_plan)} actions")
                            for i, action in enumerate(action_plan, 1):
                                logger.info(f"  {i}. {action.action.value}: {action.reason}")

                            # Story 3.7: Log plan created
                            execution_log[-1]["result"] = "success"
                            execution_log[-1]["details"]["actions_count"] = len(action_plan)
                        else:
                            logger.info(f"✓ Using existing action plan: {len(mission.action_plan)} actions")
                            execution_log[-1]["result"] = "reused"
                            execution_log[-1]["details"]["actions_count"] = len(mission.action_plan)

                        # Step 2: Execution
                        logger.info("\nSTEP 2: EXECUTION")

                        # Story 3.7: Log execution phase
                        execution_log.append({
                            "timestamp": datetime.now().isoformat(),
                            "phase": "execution",
                            "action": "execute_plan",
                            "result": "started",
                            "details": {}
                        })

                        execution_success = self.actor.execute_mission(mission)

                        # Story 3.7: Update execution log
                        execution_log[-1]["result"] = "success" if execution_success else "failed"

                        if execution_success:
                            logger.info("✓ All actions executed successfully")
                        else:
                            logger.warning("✗ Execution failed")

                        # Get final robot state
                        final_state = self.actor.get_robot_state()

                        # Step 3: Verification
                        logger.info("\nSTEP 3: VERIFICATION")

                        # Story 3.7: Log verification phase
                        execution_log.append({
                            "timestamp": datetime.now().isoformat(),
                            "phase": "verification",
                            "action": "verify_mission",
                            "result": "started",
                            "details": {}
                        })

                        verification_success, verification_message = self.verifier.verify_mission(
                            mission,
                            final_state,
                            execution_success
                        )

                        # Story 3.7: Update verification log
                        execution_log[-1]["result"] = "success" if verification_success else "failed"
                        execution_log[-1]["details"]["message"] = verification_message

                        if verification_success:
                            logger.info(f"✓ Mission verified successful: {verification_message}")
                        else:
                            logger.warning(f"✗ Mission verification failed: {verification_message}")

                        # Generate verification report
                        report = self.verifier.generate_report(
                            mission,
                            verification_success,
                            verification_message
                        )

                        # Check if mission succeeded
                        if verification_success:
                            # Log mission success with metrics (Story 2.5: AC #1)
                            mission_duration = (datetime.now() - mission_start_time).total_seconds()
                            LoggerConfig.log_mission_event(
                                event="mission_end",
                                status="completed",
                                details={
                                    "attempts": attempt,
                                    "duration_seconds": mission_duration,
                                    "success": True,
                                    "message": verification_message
                                }
                            )

                            logger.info("\n" + "="*60)
                            logger.info("MISSION COMPLETED SUCCESSFULLY")
                            logger.info("="*60)

                            # Story 3.7: Add success to execution log
                            execution_log.append({
                                "timestamp": datetime.now().isoformat(),
                                "phase": "completion",
                                "action": "mission_success",
                                "result": "success",
                                "details": {"duration_seconds": mission_duration}
                            })

                            return {
                                "success": True,
                                "message": verification_message,
                                "report": report,
                                "attempts": attempt,
                                "final_state": final_state.model_dump() if final_state else None,
                                "duration_seconds": mission_duration,
                                "execution_log": execution_log  # Story 3.7: Include execution log
                            }

                        # Mission failed - Analyze failure reason (Story 2.4)
                        logger.info("\n--- Failure Analysis ---")
                        failure_reason = self.verifier.analyze_failure_reason(mission, final_state)
                        logger.info(f"Failure reason: {failure_reason.value}")

                        # Log failure event (Story 2.5: AC #1)
                        LoggerConfig.log_failure_event(
                            failure_type=failure_reason.value,
                            agent_name="Verifier",
                            details={
                                "attempt": attempt,
                                "max_attempts": max_attempts,
                                "message": verification_message
                            },
                            replan_triggered=False  # Will update below if replanning
                        )

                        # Update robot state with failure reason
                        final_state.failure_reason = failure_reason

                        # Check if replanning is possible (Story 2.4)
                        if not self.verifier.should_replan(failure_reason, mission):
                            # Log final mission failure (Story 2.5: AC #1)
                            mission_duration = (datetime.now() - mission_start_time).total_seconds()
                            LoggerConfig.log_mission_event(
                                event="mission_end",
                                status="failed",
                                details={
                                    "attempts": attempt,
                                    "duration_seconds": mission_duration,
                                    "failure_reason": failure_reason.value,
                                    "message": verification_message,
                                    "replan_possible": False
                                },
                                level="ERROR"
                            )

                            logger.error("\n" + "="*60)
                            logger.error(f"MISSION FAILED - {failure_reason.value.upper()}")
                            logger.error("Replanning not possible (max retries or non-recoverable failure)")
                            logger.error("="*60)

                            # Stop robot motors for safety
                            logger.warning("⏹ Stopping robot motors (mission failed)")
                            self.actor.left_motor.setVelocity(0.0)
                            self.actor.right_motor.setVelocity(0.0)

                            # Story 3.7: Log failure to execution log
                            execution_log.append({
                                "timestamp": datetime.now().isoformat(),
                                "phase": "completion",
                                "action": "mission_failed",
                                "result": "failed",
                                "details": {"failure_reason": failure_reason.value, "replan_possible": False}
                            })

                            return {
                                "success": False,
                                "message": f"Mission failed ({failure_reason.value}): {verification_message}",
                                "report": report,
                                "attempts": attempt,
                                "final_state": final_state.model_dump() if final_state else None,
                                "failure_reason": failure_reason.value,
                                "duration_seconds": mission_duration,
                                "execution_log": execution_log  # Story 3.7: Include execution log
                            }

                        # Prepare for replanning (Story 2.4)
                        logger.info("\n--- Replanning ---")
                        self.verifier.prepare_retry(mission, verification_message)

                        # Build ReplanRequest with failure context
                        replan_request = ReplanRequest(
                            failure_reason=failure_reason,
                            sensor_data=final_state.sensors,
                            previous_plan=mission.action_plan if mission.action_plan else [],
                            retry_count=mission.retry_count,
                            original_command=mission.command,
                            failure_details=verification_message,
                            original_target_x=final_state.original_target_x,
                            original_target_y=final_state.original_target_y
                        )

                        # Delegate to PlannerAgent for alternative plan (Story 2.4)
                        try:
                            logger.info(f"Requesting alternative plan from PlannerAgent...")

                            # Log replanning trigger (Story 2.5: AC #1)
                            LoggerConfig.log_failure_event(
                                failure_type=failure_reason.value,
                                agent_name="Orchestrator",
                                details={
                                    "retry_count": mission.retry_count,
                                    "max_retries": 3
                                },
                                replan_triggered=True
                            )

                            alternative_plan = self.verifier.delegate_to_planner(
                                planner_agent=self.planner,
                                replan_request=replan_request,
                                mission=mission,
                                current_state=final_state
                            )

                            # Update mission with alternative action plan
                            mission.action_plan = alternative_plan
                            mission.current_action_index = 0  # Reset action index

                            logger.info(f"Alternative plan received: {len(alternative_plan)} actions")
                            for i, action in enumerate(alternative_plan, 1):
                                logger.info(f"  {i}. {action.action.value}: {action.reason}")

                            logger.info(f"\nRetry {mission.retry_count}/3 with alternative plan prepared\n")

                            # Continue to next iteration to retry with new plan
                            # Don't increment attempt counter - this is a retry within the same attempt
                            continue

                        except Exception as replan_error:
                            logger.error(f"Replanning failed: {replan_error}")
                            logger.error("\n" + "="*60)
                            logger.error("MISSION FAILED - REPLANNING ERROR")
                            logger.error("="*60)

                            # Story 3.7: Log replanning error
                            execution_log.append({
                                "timestamp": datetime.now().isoformat(),
                                "phase": "replanning",
                                "action": "replan_failed",
                                "result": "error",
                                "details": {"error": str(replan_error)}
                            })

                            return {
                                "success": False,
                                "message": f"Mission failed, replanning error: {replan_error}",
                                "report": report,
                                "attempts": attempt,
                                "final_state": final_state.model_dump() if final_state else None,
                                "failure_reason": failure_reason.value,
                                "execution_log": execution_log  # Story 3.7: Include execution log
                            }

                    except Exception as e:
                        logger.error(f"\nMission execution error: {e}")

                        # Story 3.7: Log execution error
                        execution_log.append({
                            "timestamp": datetime.now().isoformat(),
                            "phase": "execution",
                            "action": "execution_error",
                            "result": "error",
                            "details": {"error": str(e), "attempt": attempt}
                        })

                        if attempt >= max_attempts:
                            logger.error("\n" + "="*60)
                            logger.error("MISSION FAILED - EXECUTION ERROR")
                            logger.error("="*60)

                            # Stop robot motors for safety
                            logger.warning("⏹ Stopping robot motors (execution error)")
                            self.actor.left_motor.setVelocity(0.0)
                            self.actor.right_motor.setVelocity(0.0)

                            return {
                                "success": False,
                                "message": f"Mission failed with error: {e}",
                                "report": {"error": str(e)},
                                "attempts": attempt,
                                "final_state": None,
                                "execution_log": execution_log  # Story 3.7: Include execution log
                            }

                        # Retry on error
                        logger.warning(f"Retrying due to error... (attempt {attempt + 1}/{max_attempts})")

                # Should not reach here, but just in case
                logger.error("\n" + "="*60)
                logger.error("MISSION FAILED - UNEXPECTED EXIT")
                logger.error("="*60)

                # Stop robot motors for safety
                logger.warning("⏹ Stopping robot motors (unexpected exit)")
                self.actor.left_motor.setVelocity(0.0)
                self.actor.right_motor.setVelocity(0.0)

                # Story 3.7: Log unexpected exit
                execution_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "phase": "completion",
                    "action": "unexpected_exit",
                    "result": "error",
                    "details": {"attempts": attempt}
                })

                return {
                    "success": False,
                    "message": "Mission failed unexpectedly",
                    "report": {},
                    "attempts": attempt,
                    "final_state": None,
                    "execution_log": execution_log  # Story 3.7: Include execution log
                }
            finally:
                # Always reset is_executing flag when mission ends
                self.is_executing = False

        finally:
            # Story 3.7: Release mission lock
            self._mission_in_progress = False
            self._mission_lock.release()

    def emergency_stop(self):
        """
        Story 3.7: External emergency stop request.

        Sets the emergency stop flag which will be checked during mission execution.
        """
        logger.warning("Emergency stop requested!")
        self._emergency_stop_flag = True
        # Also stop motors immediately
        if hasattr(self, 'actor') and self.actor:
            try:
                self.actor.left_motor.setVelocity(0.0)
                self.actor.right_motor.setVelocity(0.0)
            except Exception as e:
                logger.error(f"Failed to stop motors during emergency stop: {e}")

    def execute_mission_batch(
        self,
        missions: list[MissionCommand]
    ) -> list[Dict[str, Any]]:
        """
        Execute multiple missions sequentially.

        Args:
            missions: List of mission commands

        Returns:
            List of result dictionaries
        """
        logger.info(f"Starting batch execution: {len(missions)} missions")

        results = []
        for i, mission in enumerate(missions, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Mission {i}/{len(missions)}")
            logger.info(f"{'='*60}")

            result = self.execute_mission(mission)
            results.append(result)

            if not result["success"]:
                logger.warning(f"Mission {i} failed, continuing to next mission...")

        # Summary
        success_count = sum(1 for r in results if r["success"])
        logger.info(f"\n{'='*60}")
        logger.info(f"Batch Execution Complete")
        logger.info(f"Success: {success_count}/{len(missions)}")
        logger.info(f"{'='*60}")

        return results

    def get_system_status(self) -> Dict[str, Any]:
        """
        Get current system status.

        Returns:
            Status dictionary
        """
        # Get robot state
        robot_state = self.actor.get_robot_state()

        status = {
            "system": "Multi-Agent Orchestrator",
            "agents": {
                "planner": {
                    "model": self.planner.model,
                    "temperature": self.planner.temperature
                },
                "actor": {
                    "model": self.actor.model,
                    "time_step": self.actor.time_step
                },
                "verifier": {
                    "model": self.verifier.model
                }
            },
            "robot": {
                "status": robot_state.status.value,
                "operational": robot_state.is_operational(),
                "position": robot_state.get_position(),
                "orientation": robot_state.get_orientation()
            }
        }

        return status


class OrchestratorFactory:
    """Factory for creating MissionOrchestrator instances."""

    _instance: Optional[MissionOrchestrator] = None

    @classmethod
    def create(
        cls,
        robot,
        api_key: Optional[str] = None,
        planner_model: str = "gpt-4o",
        actor_model: str = "gpt-4o-mini",
        verifier_model: str = "gpt-4o-mini",
        verbose: bool = True,
        enable_rag: bool = True,
        rag_persist_directory: str = "./data/chromadb"
    ) -> MissionOrchestrator:
        """
        Create or return singleton MissionOrchestrator instance.

        Args:
            robot: Webots Robot instance
            api_key: OpenAI API key
            planner_model: Model for Planner
            actor_model: Model for Actor
            verifier_model: Model for Verifier
            verbose: Enable verbose logging
            enable_rag: Enable RAG integration (Story 3.3)
            rag_persist_directory: ChromaDB persist directory

        Returns:
            MissionOrchestrator instance
        """
        if cls._instance is None:
            cls._instance = MissionOrchestrator(
                robot=robot,
                api_key=api_key,
                planner_model=planner_model,
                actor_model=actor_model,
                verifier_model=verifier_model,
                verbose=verbose,
                enable_rag=enable_rag,
                rag_persist_directory=rag_persist_directory
            )
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None
