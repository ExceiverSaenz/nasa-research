"""Standalone reconciliation entry point; no project helpers required."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from integration.runner import main

if __name__ == '__main__':
    raise SystemExit(main())
