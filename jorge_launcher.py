"""
Jorge's Real Estate Bots - Single-File Launcher.

Starts all bot services and command center with one command.
"""
import subprocess
import time
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from bots.shared.logger import get_logger
from bots.shared.config import settings

logger = get_logger(__name__)

SERVICES = [
    {
        "name": "Lead Bot",
        "command": ["python", "-m", "uvicorn", "bots.lead_bot.main:app", "--host", "0.0.0.0", "--port", "8001"],
        "port": 8001,
        "health_url": "http://localhost:8001/health",
        "enabled": True
    },
    {
        "name": "Seller Bot",
        "command": ["python", "-m", "uvicorn", "bots.seller_bot.main:app", "--host", "0.0.0.0", "--port", "8002"],
        "port": 8002,
        "health_url": "http://localhost:8002/health",
        "enabled": False  # Phase 1: Lead Bot only
    },
    {
        "name": "Buyer Bot",
        "command": ["python", "-m", "uvicorn", "bots.buyer_bot.main:app", "--host", "0.0.0.0", "--port", "8003"],
        "port": 8003,
        "health_url": "http://localhost:8003/health",
        "enabled": False  # Phase 1: Lead Bot only
    },
    {
        "name": "Command Center",
        "command": ["streamlit", "run", "command_center/main.py", "--server.port", "8501"],
        "port": 8501,
        "health_url": "http://localhost:8501",
        "enabled": False  # Phase 1: API only
    }
]


def check_dependencies():
    """Check if required dependencies are installed."""
    logger.info("Checking dependencies...")

    required_packages = ["fastapi", "uvicorn", "anthropic", "redis"]
    missing = []

    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        logger.error(f"Missing required packages: {', '.join(missing)}")
        logger.error("Run: pip install -r requirements.txt")
        return False

    logger.info("✅ All dependencies installed")
    return True


def check_env_vars():
    """Check if required environment variables are set."""
    logger.info("Checking environment variables...")

    required_vars = [
        "ANTHROPIC_API_KEY",
        "GHL_API_KEY",
        "GHL_LOCATION_ID"
    ]

    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.error("Copy .env.example to .env and fill in your API keys")
        return False

    logger.info("✅ All environment variables set")
    return True


def start_services():
    """Start all enabled services."""
    logger.info("\n" + "=" * 60)
    logger.info("🚀 Starting Jorge's Real Estate AI Bots")
    logger.info("=" * 60 + "\n")

    processes = []

    for service in SERVICES:
        if not service["enabled"]:
            logger.info(f"⏭️  Skipping {service['name']} (disabled)")
            continue

        logger.info(f"🔥 Starting {service['name']} on port {service['port']}...")

        try:
            process = subprocess.Popen(
                service["command"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(project_root)
            )
            processes.append({
                "name": service["name"],
                "process": process,
                "port": service["port"]
            })
            time.sleep(2)  # Give service time to start
            logger.info(f"✅ {service['name']} started (PID: {process.pid})")

        except Exception as e:
            logger.error(f"❌ Failed to start {service['name']}: {e}")

    logger.info("\n" + "=" * 60)
    logger.info("📊 Jorge's Bots Status")
    logger.info("=" * 60)

    for p in processes:
        logger.info(f"  • {p['name']}: http://localhost:{p['port']}")

    logger.info("\n" + "=" * 60)
    logger.info("Press Ctrl+C to stop all services")
    logger.info("=" * 60 + "\n")

    try:
        # Wait for all processes
        for p in processes:
            p["process"].wait()
    except KeyboardInterrupt:
        logger.info("\n\n🛑 Shutting down services...")
        for p in processes:
            logger.info(f"  Stopping {p['name']}...")
            p["process"].terminate()
            p["process"].wait()
        logger.info("✅ All services stopped")


def main():
    """Main launcher function."""
    print("\n" + "=" * 60)
    print("🏠 Jorge's Real Estate AI Bot Platform")
    print("=" * 60 + "\n")

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Check environment variables
    if not check_env_vars():
        sys.exit(1)

    # Start services
    start_services()


if __name__ == "__main__":
    main()
