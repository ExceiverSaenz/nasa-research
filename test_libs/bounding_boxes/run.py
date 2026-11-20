"""Local launcher for the application in code/; imports allocate no resources."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    code = Path(__file__).resolve().parent / 'code'
    sys.path.insert(0, str(code))
    runpy.run_path(str(code / 'run.py'), run_name='__main__')
