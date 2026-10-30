"""Select offline development suites; no model inference or remote operations."""
import argparse
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'new_code/parse_system'), str(ROOT/'new_code/reconciliation_system'), str(ROOT/'new_code')]


def modules(suite):
    workflow = sorted('tests.' + '.'.join(p.relative_to(ROOT/'tests').with_suffix('').parts)
                      for folder in ('parsing_hybrid', 'reconciliation_system')
                      for p in (ROOT/'tests'/folder).glob('test_*.py')
                      if p.name != 'test_hybrid_inputs.py')
    compatibility = ['tests.reconciliation_system.test_hybrid_inputs']
    extended = sorted('tests.' + '.'.join(p.relative_to(ROOT/'tests').with_suffix('').parts)
                      for p in (ROOT/'tests/integration').rglob('test_*.py'))
    return {'workflow': workflow, 'compatibility': compatibility,
            'extended': extended, 'all': workflow + compatibility + extended}[suite]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suite', choices=('workflow','compatibility','extended','all'))
    parser.add_argument('--list', action='store_true', help='List modules without importing or running them')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    selected = modules(args.suite)
    if args.list:
        print('\n'.join(selected))
        return 0
    # Keep temporary fixtures inside the workspace on restricted Windows hosts.
    temporary = ROOT/'analytics/tmp/tests'
    temporary.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(temporary)
    os.environ['TEMP'] = os.environ['TMP'] = str(temporary)
    os.environ['PYTHONPATH'] = os.pathsep.join(sys.path[:4])
    loaded = unittest.defaultTestLoader.loadTestsFromNames(selected)
    return 0 if unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(loaded).wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
