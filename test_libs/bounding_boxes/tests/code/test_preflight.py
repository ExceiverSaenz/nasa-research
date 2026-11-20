import json
import sys
from pathlib import Path
from unittest.mock import patch
import pytest
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file());sys.path.insert(0,str(ROOT))
from bbx.preflight import inspect_local, inventory
from bbx.resources import parse_gpu
from bbx.adapters.mineru import project_middle


def test_local_inspect_does_not_create_session(tmp_path):
    with patch('subprocess.run') as run:
        result=inspect_local(ROOT,tmp_path)
    assert run.call_count==0
    assert any(c['id']=='remote_gpu' and c['status']=='NOT_RUN' for c in result)


def test_inventory_pdf_hash(tmp_path):
    (tmp_path/'1.pdf').write_bytes(b'%PDF-synthetic')
    with patch.dict(sys.modules,{'pypdfium2':None}):
        row=inventory(tmp_path)[0]
    assert row['bytes']==14 and len(row['sha256'])==64 and row['pages'] is None


def test_gpu_cannot_accept_other_device():
    assert parse_gpu('NVIDIA A100-SXM4-40GB, 40960, 20')[0]['a100']
    assert not parse_gpu('Tesla T4, 15000, 20')[0]['a100']


def test_middle_projection_preserves_no_inline_bbox(tmp_path):
    p=tmp_path/'middle.json';p.write_text(json.dumps({'pages':[{'page_idx':0,'blocks':[
        {'type':'image','bbox':[0,0,1,1],'content':[{'type':'image_body','bbox':[0,0,1,1]}]},
        {'type':'text','bbox':[0,0,.5,.1],'content':[{'type':'equation_inline','content':'x'}]}
    ]}]}))
    out=project_middle(p,{'tool':'basic','paper_sha256':'p'})
    inline=next(d for d in out if d['raw_label']=='equation_inline')
    assert inline['bbox_normalized'] is None
    assert all(d['relations'] is None for d in out)


def test_native_parent_relationship_preserved(tmp_path):
    p=tmp_path/'middle.json';p.write_text(json.dumps({'pages':[{'page_idx':0,'blocks':[
        {'type':'image','bbox':[0,0,1,1],'content':[{'type':'image_caption','content':'Fig 1'}]}
    ]}]}))
    child=project_middle(p,{'tool':'basic','paper_sha256':'p'})[1]
    assert child['native_parent_ref'].endswith('/blocks/0')


def test_installed_dry_run_does_not_mean_satisfied(tmp_path):
    from bbx.environment import verify_pip_report
    assert not verify_pip_report({'install':[{'metadata':{'name':'torch'}}]})
    assert verify_pip_report({'install':[]})


def test_installer_requires_hashed_lock_and_absent_target(tmp_path):
    from bbx.prepare import install_environment
    target=tmp_path/'env'; target.mkdir()
    with pytest.raises(ValueError): install_environment('unused',target,tmp_path/'missing.lock')


def test_remote_probe_no_models_or_downloads():
    from bbx.preflight import remote_probe
    with patch('bbx.resources.gpu_snapshot',return_value=[]):
        checks=remote_probe()
    assert any(c['id']=='a100' and c['status']=='FAIL' for c in checks)
