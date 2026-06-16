"""
LLM-based Rescue Robot Controller - Web Control Version

Integrates Multi-Agent System (Planner-Actor-Verifier) with Webots and FastAPI web server.
This controller waits for commands from the web interface instead of executing predefined missions.
"""

import sys
import os
from pathlib import Path
import asyncio
import threading

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from controller import Robot
from src.orchestrator import MissionOrchestrator
from loguru import logger


# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="DEBUG"  # Temporarily DEBUG to see rotation details
)
logger.add(
    str(project_root / "logs" / "webots_web_control.log"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="DEBUG"
)


def start_web_server(orchestrator):
    """
    Start FastAPI web server in a separate thread.

    Args:
        orchestrator: MissionOrchestrator instance to register with web server
    """
    logger.info("Starting FastAPI web server...")

    try:
        import uvicorn
        from src.web.server import app, set_orchestrator

        # Register orchestrator with web server
        set_orchestrator(orchestrator)
        logger.info("✅ Orchestrator registered with web server")

        # Start uvicorn server
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="info"
        )
        server = uvicorn.Server(config)

        logger.info("🌐 Web server starting at http://localhost:8000")
        logger.info("📡 WebSocket endpoints:")
        logger.info("   - ws://localhost:8000/ws/control")
        logger.info("   - ws://localhost:8000/ws/robot-status")

        # Run server (this blocks)
        server.run()

    except ImportError as e:
        logger.error(f"Failed to import web server dependencies: {e}")
        logger.error("Install dependencies: pip install fastapi uvicorn websockets")
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

        # Use absolute path for RAG data directory
        rag_persist_dir = str(project_root / "data" / "chroma_test")

        # Define step callback for coordinated simulation stepping
        def controlled_step(time_step):
            """Step callback that ensures only one place calls robot.step()"""
            return robot.step(time_step)

        orchestrator = MissionOrchestrator(
            robot=robot,
            planner_model="gpt-4o-mini",  # Using cheaper model for web control
            actor_model="gpt-4o-mini",
            verifier_model="gpt-4o-mini",
            verbose=True,
            enable_rag=True,
            rag_persist_directory=rag_persist_dir,
            step_callback=controlled_step  # Use callback for step coordination
        )
        logger.info("✅ Multi-Agent System initialized (Web mode with step callback)")

        # Wait for sensors to initialize
        logger.info("Initializing sensors...")
        for i in range(10):
            if robot.step(TIME_STEP) == -1:
                logger.warning("Simulation stopped during sensor initialization")
                return
        logger.info("✅ Sensors initialized")

        # Get initial system status
        status = orchestrator.get_system_status()
        logger.info(f"✅ Robot operational: {status['robot']['operational']}")
        logger.info(f"📍 Initial position: X={status['robot']['position']['x']:.2f}m, Y={status['robot']['position']['y']:.2f}m")

        # Start web server in background thread
        logger.info("\n" + "="*70)
        logger.info("🚀 Starting Web Server...")
        logger.info("="*70)

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
        logger.info("\nExamples:")
        logger.info('  - "동쪽으로 3미터 이동"')
        logger.info('  - "좌측 90도 회전"')
        logger.info('  - "Move forward 2 meters"')
        logger.info('  - "생존자 탐색"')
        logger.info("\n" + "="*70)
        logger.info("Press Ctrl+C to stop the controller")
        logger.info("="*70 + "\n")

        # IMPORTANT: Actor Agent uses step_callback, so it calls robot.step() through our controlled_step function
        # This ensures only one place calls robot.step(), preventing timing conflicts
        # The main loop is not needed since Actor handles all stepping during missions
        # We just keep the thread alive for the web server

        logger.info("✅ Main loop paused - Actor Agent controls all simulation steps via callback")
        logger.info("🌐 Web server ready for commands at http://localhost:8000")

        # Keep controller alive without interfering with Actor's step control
        while True:
            time.sleep(0.1)  # Just keep thread alive, Actor manages simulation

    except KeyboardInterrupt:
        logger.info("\n🛑 Controller stopped by user")
    except Exception as e:
        logger.error(f"❌ Controller error: {e}", exc_info=True)
    finally:
        logger.info("Controller shutdown")


if __name__ == "__main__":
    main()
