"""
Jorge's Real Estate Bots - Single-File Launcher.

Starts all bot services and command center with one command.

Usage:
    python jorge_launcher.py          # Production mode (requires .env)
    python jorge_launcher.py --demo   # Demo mode (zero config, SQLite, seeded data)
"""
import os
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Demo mode: set env vars BEFORE config is imported so Settings picks them up
# ---------------------------------------------------------------------------
DEMO_MODE = "--demo" in sys.argv

if DEMO_MODE:
    _demo_db_dir = Path(__file__).parent / ".demo_data"
    _demo_db_dir.mkdir(exist_ok=True)
    _demo_db = _demo_db_dir / "jorge_demo.db"

    os.environ.setdefault("DEMO_MODE", "true")
    os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_demo_db}")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("ANTHROPIC_API_KEY", "demo-key-not-real")
    os.environ.setdefault("GHL_API_KEY", "demo-key-not-real")
    os.environ.setdefault("GHL_LOCATION_ID", "demo-location-id")
    os.environ.setdefault("ZILLOW_API_KEY", "demo-key")
    os.environ.setdefault("TWILIO_ACCOUNT_SID", "demo-sid")
    os.environ.setdefault("TWILIO_AUTH_TOKEN", "demo-token")
    os.environ.setdefault("TWILIO_PHONE_NUMBER", "+10000000000")
    os.environ.setdefault("SENDGRID_API_KEY", "demo-key")
    os.environ.setdefault("USE_MOCK_LLM", "true")
    os.environ.setdefault("TEST_MODE", "true")

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from bots.shared.logger import get_logger

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
        "command": ["streamlit", "run", "command_center/dashboard_v3.py", "--server.port", "8501"],
        "port": 8501,
        "health_url": "http://localhost:8501",
        "enabled": False  # Phase 1: API only
    }
]


def check_dependencies():
    """Check if required dependencies are installed."""
    logger.info("Checking dependencies...")

    required_packages = ["fastapi", "uvicorn"]
    if not DEMO_MODE:
        required_packages.extend(["anthropic", "redis"])

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

    logger.info("All dependencies installed")
    return True


def check_env_vars():
    """Check if required environment variables are set."""
    if DEMO_MODE:
        logger.info("Demo mode -- skipping env var checks")
        return True

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

    logger.info("All environment variables set")
    return True


def seed_demo_data():
    """Seed demo data into SQLite database."""
    logger.info("Seeding demo data...")

    try:
        seed_script = project_root / "scripts" / "seed_demo_data.py"
        if seed_script.exists():
            result = subprocess.run(
                [sys.executable, str(seed_script)],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info("Demo data seeded successfully")
            else:
                logger.warning(f"Seed script output: {result.stderr[:200]}")
        else:
            logger.warning("Seed script not found -- dashboard will start without demo data")
    except Exception as e:
        logger.warning(f"Could not seed demo data: {e}")


def start_services():
    """Start all enabled services."""
    logger.info("\n" + "=" * 60)
    if DEMO_MODE:
        logger.info("DEMO MODE -- Jorge's Real Estate AI Bots")
        logger.info("Zero API keys required. Using mock services + SQLite.")
    else:
        logger.info("Starting Jorge's Real Estate AI Bots")
    logger.info("=" * 60 + "\n")

    # In demo mode, propagate env vars to child processes
    env = os.environ.copy()

    processes = []

    for service in SERVICES:
        if not service["enabled"]:
            logger.info(f"  Skipping {service['name']} (disabled)")
            continue

        logger.info(f"  Starting {service['name']} on port {service['port']}...")

        try:
            process = subprocess.Popen(
                service["command"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(project_root),
                env=env,
            )
            processes.append({
                "name": service["name"],
                "process": process,
                "port": service["port"]
            })
            time.sleep(2)  # Give service time to start
            logger.info(f"  {service['name']} started (PID: {process.pid})")

        except Exception as e:
            logger.error(f"  Failed to start {service['name']}: {e}")

    logger.info("\n" + "=" * 60)
    logger.info("Jorge's Bots Status")
    logger.info("=" * 60)

    for p in processes:
        logger.info(f"  {p['name']}: http://localhost:{p['port']}")

    logger.info("\n" + "=" * 60)
    logger.info("Press Ctrl+C to stop all services")
    logger.info("=" * 60 + "\n")

    try:
        # Wait for all processes
        for p in processes:
            p["process"].wait()
    except KeyboardInterrupt:
        logger.info("\n\nShutting down services...")
        for p in processes:
            logger.info(f"  Stopping {p['name']}...")
            p["process"].terminate()
            p["process"].wait()
        logger.info("All services stopped")


def main():
    """Main launcher function."""
    print("\n" + "=" * 60)
    if DEMO_MODE:
        print("  Jorge's Real Estate AI Bot Platform -- DEMO MODE")
        print("  No API keys, no PostgreSQL, no Redis required")
    else:
        print("  Jorge's Real Estate AI Bot Platform")
    print("=" * 60 + "\n")

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Check environment variables
    if not check_env_vars():
        sys.exit(1)

    # In demo mode, enable all services and seed data
    if DEMO_MODE:
        for service in SERVICES:
            service["enabled"] = True
        seed_demo_data()

    # Start services
    start_services()


if __name__ == "__main__":
    main()
