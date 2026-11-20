import json
import sys
from pathlib import Path
from unittest.mock import Mock
import pytest
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file());sys.path.insert(0,str(ROOT))
from bbx.workflow import Workflow
from bbx.remote import ensure_python,prepare_remote
from bbx.r2 import presign_get


def test_unapproved_remote_workflow_has_zero_side_effects(tmp_path):
    transport=Mock();flow=Workflow(ROOT,tmp_path,transport)
    with pytest.raises(ValueError):flow.prepare([],allow_remote=False)
    transport.assert_not_called();assert not list(tmp_path.iterdir())


def test_phase_order_rejects_execute_before_smoke(tmp_path):
    flow=Workflow(ROOT,tmp_path,Mock())
    with pytest.raises(ValueError):flow.execute(None,allow_inference=True)


def test_existing_python_reused_without_installer():
    runner=Mock();finder=lambda name:'/python3.11' if name=='python3.11' else None
    runner.return_value.stdout='3.11\n'
    assert ensure_python('/runtime',runner=runner,finder=finder)=='/python3.11'
    assert runner.call_count==1


def test_remote_host_gate_stops_before_installing(tmp_path):
    installer=Mock()
    with pytest.raises(ValueError):prepare_remote(tmp_path,{},host_checks=[{'status':'FAIL'}],installer=installer)
    installer.assert_not_called()


def test_presigning_does_not_export_permanent_secret():
    c={'R2_ENDPOINT_URL':'https://example.r2.cloudflarestorage.com','R2_BUCKET':'papers',
       'AWS_ACCESS_KEY_ID':'ACCESS','AWS_SECRET_ACCESS_KEY':'PERMANENT_SECRET'}
    url=presign_get(c,'sic/12.pdf',expires=600)
    assert 'PERMANENT_SECRET' not in url and 'X-Amz-Signature=' in url
    assert 'X-Amz-Expires=600' in url


def test_pack_wheels_requires_verified_identity(tmp_path):
    from bbx.workflow import pack_wheels
    with pytest.raises(ValueError):pack_wheels(ROOT,tmp_path/'wheels.zip',expected={'missing.whl':'f'*64})


def test_heron_load_once_for_multiple_papers():
    from bbx.adapters.heron import stage_model
    loader=Mock(return_value=('processor','model'));config={}
    assert stage_model(config,loader)==stage_model(config,loader)
    loader.assert_called_once()
