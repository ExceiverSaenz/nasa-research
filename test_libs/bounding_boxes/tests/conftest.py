"""Keep test artifacts in the authorized workspace; never change Windows ACLs."""
from pathlib import Path
from uuid import uuid4
import pytest
import sys
import os
ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'code'))


def pytest_addoption(parser):
    parser.addoption('--native-contract',action='store_true',help='Run CPU ABI checks with verified cached DocVortex wheels; no GPU or downloads')


@pytest.fixture
def tmp_path(request):
    kind='analytics' if Path(request.node.path).is_relative_to(ROOT/'tests/analytics') else 'code'
    base=Path(os.environ['BBX_TEST_ARTIFACT_ROOT'])/kind if os.environ.get('BBX_TEST_ARTIFACT_ROOT') else ROOT/'raw_results/tests'/kind/'fixtures'
    path=base/uuid4().hex
    path.mkdir(parents=True)
    return path
