"""Standalone hybrid CLI. run requires --user-run; installation is explicit."""
from pathlib import Path
import sys

PACKAGE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE_ROOT))
from parsing.unified.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
