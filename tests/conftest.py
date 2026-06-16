"""
Pytest configuration file

Automatically loads .env file for all tests.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


# Load .env file from project root
project_root = Path(__file__).parent.parent
env_file = project_root / ".env"

if env_file.exists():
    load_dotenv(env_file)
    print(f"\n.env loaded from: {env_file}")

    # Verify OPENAI_API_KEY is loaded
    if os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY: Found")
    else:
        print("OPENAI_API_KEY: NOT FOUND")
else:
    print(f"\nWarning: .env file not found at {env_file}")
