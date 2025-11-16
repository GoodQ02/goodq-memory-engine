"""
Control Agent Runner - Convenience script
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.control_agent import main

if __name__ == "__main__":
    main()
