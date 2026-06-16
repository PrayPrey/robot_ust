"""
LLM_ROBOT_2 Main Entry Point

Example usage for Multi-Agent Robot Control System.

Story 2.5: Enhanced with Loguru structured logging and OpenLit LLM monitoring.
"""

from loguru import logger
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.orchestrator import MissionOrchestrator
from src.schemas import MissionCommand
from src.utils import setup_logger, setup_openlit


def setup_logging():
    """
    Configure logging with Story 2.5 enhancements.

    Sets up:
    - Loguru structured logging with JSON serialization
    - OpenLit LLM monitoring for cost/latency tracking
    """
    # Use new LoggerConfig setup (Story 2.5: AC #1)
    mission_name = f"example_mission_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    setup_logger(
        mission_name=mission_name,
        log_dir="logs",
        console_level="INFO",
        file_level="DEBUG"
    )

    # Initialize OpenLit for LLM monitoring (Story 2.5: AC #2)
    setup_openlit(
        application_name="LLM_robot_2",
        environment="production"
    )

    logger.info("Logging and monitoring systems initialized", mission=mission_name)


def run_example_missions(orchestrator: MissionOrchestrator):
    """Run example missions."""

    # Example 1: Korean mission - Move forward and scan
    logger.info("\n" + "="*60)
    logger.info("Example 1: Korean Mission")
    logger.info("="*60)

    mission1 = MissionCommand(
        command="앞으로 2미터 이동한 후 5초간 주변을 탐색하세요",
        language="ko",
        priority=5
    )

    result1 = orchestrator.execute_mission(mission1)
    logger.info(f"\nResult: {'SUCCESS' if result1['success'] else 'FAILED'}")
    logger.info(f"Message: {result1['message']}")

    # Example 2: English mission - Navigate and rotate
    logger.info("\n" + "="*60)
    logger.info("Example 2: English Mission")
    logger.info("="*60)

    mission2 = MissionCommand(
        command="Move to position x=1.5, y=1.0 and rotate 90 degrees to the left",
        language="en",
        priority=7
    )

    result2 = orchestrator.execute_mission(mission2)
    logger.info(f"\nResult: {'SUCCESS' if result2['success'] else 'FAILED'}")
    logger.info(f"Message: {result2['message']}")

    # Summary
    logger.info("\n" + "="*60)
    logger.info("MISSION SUMMARY")
    logger.info("="*60)
    logger.info(f"Mission 1 (Korean): {'✓ SUCCESS' if result1['success'] else '✗ FAILED'}")
    logger.info(f"Mission 2 (English): {'✓ SUCCESS' if result2['success'] else '✗ FAILED'}")


def run_arm_demo_missions(orchestrator: MissionOrchestrator):
    """
    Run arm manipulation demo missions.

    Demonstrates LLM-based Mobile Manipulator control:
    - Arm movement via natural language
    - Grip/Release operations
    - Pick and Place sequence
    """
    results = []

    # Demo 1: Simple Arm Movement (Korean)
    logger.info("\n" + "="*60)
    logger.info("ARM DEMO 1: Simple Arm Movement (Korean)")
    logger.info("="*60)

    mission1 = MissionCommand(
        command="팔을 앞으로 뻗어",
        language="ko",
        priority=5
    )

    result1 = orchestrator.execute_mission(mission1)
    results.append(("Arm Extend (KO)", result1['success']))
    logger.info(f"Result: {'SUCCESS' if result1['success'] else 'FAILED'}")

    # Demo 2: Grip Object (English)
    logger.info("\n" + "="*60)
    logger.info("ARM DEMO 2: Grip Object (English)")
    logger.info("="*60)

    mission2 = MissionCommand(
        command="grab the object",
        language="en",
        priority=5
    )

    result2 = orchestrator.execute_mission(mission2)
    results.append(("Grip (EN)", result2['success']))
    logger.info(f"Result: {'SUCCESS' if result2['success'] else 'FAILED'}")

    # Demo 3: Lift Arm (Korean)
    logger.info("\n" + "="*60)
    logger.info("ARM DEMO 3: Lift Arm (Korean)")
    logger.info("="*60)

    mission3 = MissionCommand(
        command="팔을 위로 올려",
        language="ko",
        priority=5
    )

    result3 = orchestrator.execute_mission(mission3)
    results.append(("Lift Arm (KO)", result3['success']))
    logger.info(f"Result: {'SUCCESS' if result3['success'] else 'FAILED'}")

    # Demo 4: Move Forward While Holding (English)
    logger.info("\n" + "="*60)
    logger.info("ARM DEMO 4: Move Forward While Holding (English)")
    logger.info("="*60)

    mission4 = MissionCommand(
        command="move forward 1 meter",
        language="en",
        priority=5
    )

    result4 = orchestrator.execute_mission(mission4)
    results.append(("Move Forward (EN)", result4['success']))
    logger.info(f"Result: {'SUCCESS' if result4['success'] else 'FAILED'}")

    # Demo 5: Lower Arm and Release (Korean)
    logger.info("\n" + "="*60)
    logger.info("ARM DEMO 5: Lower Arm and Release (Korean)")
    logger.info("="*60)

    mission5 = MissionCommand(
        command="팔을 내리고 물체를 놓아줘",
        language="ko",
        priority=5
    )

    result5 = orchestrator.execute_mission(mission5)
    results.append(("Lower & Release (KO)", result5['success']))
    logger.info(f"Result: {'SUCCESS' if result5['success'] else 'FAILED'}")

    # Demo 6: Complete Pick and Place Sequence (English)
    logger.info("\n" + "="*60)
    logger.info("ARM DEMO 6: Complete Pick & Place (English)")
    logger.info("="*60)

    mission6 = MissionCommand(
        command="pick up object, move forward 2 meters, then put it down",
        language="en",
        priority=7
    )

    result6 = orchestrator.execute_mission(mission6)
    results.append(("Pick & Place (EN)", result6['success']))
    logger.info(f"Result: {'SUCCESS' if result6['success'] else 'FAILED'}")

    # Summary
    logger.info("\n" + "="*60)
    logger.info("ARM DEMO SUMMARY")
    logger.info("="*60)
    for name, success in results:
        logger.info(f"  {name}: {'SUCCESS' if success else 'FAILED'}")

    success_count = sum(1 for _, s in results if s)
    logger.info(f"\nTotal: {success_count}/{len(results)} missions succeeded")


def main():
    """
    Main entry point.

    Usage:
        python -m src.main          # Run basic missions
        python -m src.main --arm    # Run arm manipulation demo
        python -m src.main --all    # Run all demos
    """
    import argparse
    parser = argparse.ArgumentParser(description="LLM_ROBOT_2 - Multi-Agent Robot Control System")
    parser.add_argument("--arm", action="store_true", help="Run arm manipulation demo")
    parser.add_argument("--all", action="store_true", help="Run all demos (basic + arm)")
    args = parser.parse_args()

    setup_logging()

    logger.info("="*60)
    logger.info("LLM_ROBOT_2 - Multi-Agent Robot Control System")
    logger.info("  Now with LLM-based Mobile Manipulator Control!")
    logger.info("="*60)

    try:
        # Import Webots Robot (only works in Webots environment)
        try:
            from controller import Robot
            logger.info("Running in Webots environment")
            robot = Robot()
        except ImportError:
            logger.warning("Webots not available - using mock robot")
            robot = None

        # Create orchestrator
        if robot:
            orchestrator = MissionOrchestrator(
                robot=robot,
                planner_model="gpt-4o",
                actor_model="gpt-4o-mini",
                verifier_model="gpt-4o-mini",
                verbose=True
            )

            # Get system status
            status = orchestrator.get_system_status()
            logger.info(f"System Status: {status['system']}")
            logger.info(f"Robot Operational: {status['robot']['operational']}")

            # Run appropriate demos based on args
            if args.all:
                logger.info("\n>>> Running ALL DEMOS <<<")
                run_example_missions(orchestrator)
                run_arm_demo_missions(orchestrator)
            elif args.arm:
                logger.info("\n>>> Running ARM MANIPULATION DEMO <<<")
                run_arm_demo_missions(orchestrator)
            else:
                # Default: run basic missions
                run_example_missions(orchestrator)

        else:
            logger.info("Webots Robot not available - see README for setup instructions")

    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    logger.info("\nSystem shutdown complete")


if __name__ == "__main__":
    main()
