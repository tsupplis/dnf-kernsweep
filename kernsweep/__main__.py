"""
Entry point for running kernsweep as a module.

Usage:
    python -m kernsweep [options]
"""

import sys
from kernsweep.cli import main

if __name__ == "__main__":
    sys.exit(main())
