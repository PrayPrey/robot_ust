"""
LLM-based Rescue Robot Controller - Web Control Mode

Integrates Multi-Agent System (Planner-Actor-Verifier) with Webots.
Waits for commands from web interface at http://localhost:8000

The controller automatically starts the FastAPI web server and
connects the Orchestrator for natural language command processing.
"""

import sys
import os
from pathlib import Path
import threading

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from controller import Robot
from src.orchestrator import MissionOrchestrator
from src.schemas import MissionCommand
from loguru import logger


# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)
logger.add(
    str(project_root / "logs" / "webots_mission.log"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="DEBUG"
)


def start_web_server(orchestrator):
    """Start FastAPI web server in a separate thread."""
    logger.info("Starting FastAPI web server...")

    try:
        import uvicorn
        from src.web.server import app, set_orchestrator

        # Register orchestrator with web server
        set_orchestrator(orchestrator)
        logger.info("✅ Orchestrator registered with web server")

        # Start uvicorn server
        config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="info")
        server = uvicorn.Server(config)

        logger.info("🌐 Web server: http://localhost:8000")
        server.run()

    except Exception as e:
        logger.error(f"Web server error: {e}", exc_info=True)


def main():
    """Main controller loop - Web control mode."""

    logger.info("="*70)
    logger.info("🤖 LLM-Based Rescue Robot Controller - WEB CONTROL MODE")
    logger.info("="*70)

    # Initialize robot
    robot = Robot()
    TIME_STEP = 64

    try:
        # Create Multi-Agent Orchestrator
        logger.info("Initializing Multi-Agent System...")
        orchestrator = MissionOrchestrator(
            robot=robot,
            planner_model="gpt-4o",
            actor_model="gpt-4o-mini",
            verifier_model="gpt-4o-mini",
            verbose=True
        )

        # Get system status
        status = orchestrator.get_system_status()
        logger.info(f"System ready - Robot operational: {status['robot']['operational']}")

        # Wait for sensors to initialize (GPS/IMU/Lidar need data from first robot.step() calls)
        logger.info("Waiting for sensors to initialize...")
        for i in range(10):
            if robot.step(TIME_STEP) == -1:
                logger.warning("Simulation stopped during sensor initialization")
                return
            if i == 4:  # Log progress halfway
                logger.info("Sensors initializing... (50%)")
        logger.info("✅ Sensors initialized successfully")
        logger.info("✅ System ready for web commands")

        # ============================================================
        # Start Web Server
        # ============================================================
        logger.info("\n" + "="*70)
        logger.info("🚀 Starting Web Server...")
        logger.info("="*70)

        # Start web server in background thread
        server_thread = threading.Thread(
            target=start_web_server,
            args=(orchestrator,),
            daemon=True
        )
        server_thread.start()

        # Wait for server to start
        import time
        time.sleep(2)

        # Display instructions
        logger.info("\n" + "="*70)
        logger.info("✅ SYSTEM READY - Waiting for web commands")
        logger.info("="*70)
        logger.info("🌐 Open your browser: http://localhost:8000")
        logger.info("💬 Enter natural language commands in Korean or English")
        logger.info("\nCommand Examples:")
        logger.info('  • "동쪽으로 3미터 이동" (Move 3m east)')
        logger.info('  • "좌측 90도 회전" (Rotate 90° left)')
        logger.info('  • "앞으로 2미터 전진" (Move forward 2m)')
        logger.info('  • "생존자 탐색" (Search for survivors)')
        logger.info('  • "주변 환경 스캔" (Scan surroundings)')
        logger.info("\n" + "="*70)
        logger.info("Press Ctrl+C to stop the controller")
        logger.info("="*70 + "\n")

        # Keep simulation running and wait for web commands

        while robot.step(TIME_STEP) != -1:
            pass

    except KeyboardInterrupt:
        logger.info("\nController stopped by user")
    except Exception as e:
        logger.error(f"Controller error: {e}", exc_info=True)
    finally:
        logger.info("Controller shutdown")


if __name__ == "__main__":
    main()
