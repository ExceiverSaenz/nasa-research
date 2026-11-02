import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(ROOT))
from bbx.contracts import validate_experiment, load_experiment, exit_code
from bbx.environment import classify_artifact, prepare_environment
from bbx.r2 import download_verified, safe_error
from bbx.normalize import normalize_box, normalize
from bbx.compare import compare
from bbx.controller import execute


def config():
    return load_experiment(ROOT / 'experiment.json')


def ready():
    c=config();c['ready']=True;c['locks']={'a':'a','b':'b'};c['model_manifests']=['manifest']
    for t in c['tools'][:2]:t['revision']='pinned'
    from bbx.controller import required_gates
    from bbx.contracts import check
    return c,[check(id,'PASS',config_sha256=hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()) for id in required_gates]


def test_configuration_has_four_tools_two_environments():
    c = config()
    assert exit_code(validate_experiment(c)) == 0
    assert [t['environment'] for t in c['tools']] == ['a', 'a', 'a', 'b']


@pytest.mark.parametrize('change', ['engine', 'duplicate', 'cpu'])
def test_invalid_config(change):
    c = config()
    if change == 'engine': c['tools'][-1]['engine'] = 'llama-cpp'
    if change == 'duplicate': c['tools'][1]['id'] = c['tools'][0]['id']
    if change == 'cpu': c['device'] = 'cpu'
    assert exit_code(validate_experiment(c)) == 1


def test_not_run_blocks():
    assert exit_code([{'status': 'NOT_RUN'}]) == 2


def test_artifact_integrity(tmp_path):
    p = tmp_path / 'w'; p.write_bytes(b'ok')
    m = {'bytes': 2, 'sha256': hashlib.sha256(b'ok').hexdigest()}
    assert classify_artifact(p, m) == 'valid'
    p.write_bytes(b'no')
    assert classify_artifact(p, m) == 'corrupt'
    assert classify_artifact(tmp_path / 'absent', m) == 'missing'


def test_valid_environment_never_installs():
    calls = []
    result = prepare_environment({'python': 'unused'}, checks=[{'status': 'PASS'}], apply=True,
                                 installer=lambda _: calls.append('install'))
    assert result['action'] == 'reuse'
    assert calls == []


def test_invalid_environment_not_patched():
    with pytest.raises(ValueError):
        prepare_environment({}, checks=[{'status': 'FAIL'}], apply=True, installer=lambda _: None)


def test_download_reuses_and_verifies(tmp_path):
    data = b'%PDF-test'; target = tmp_path / 'p.pdf'
    identity = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    calls = []
    def fetch(): calls.append(1); return data
    assert download_verified(fetch, target, identity)['status'] == 'PASS'
    assert download_verified(fetch, target, identity)['reused']
    assert calls == [1]
    assert not list(tmp_path.glob('*.part'))


def test_bad_download_preserves_original(tmp_path):
    target = tmp_path / 'p.pdf'; target.write_bytes(b'original')
    with pytest.raises(ValueError):
        download_verified(lambda: b'bad', target, {'bytes': 3, 'sha256': hashlib.sha256(b'bad').hexdigest()})
    assert target.read_bytes() == b'original'


def test_errors_do_not_leak_urls():
    assert 'SECRET' not in safe_error(RuntimeError('https://host/?token=SECRET'))


@pytest.mark.parametrize('rotation,expected', [(0,[.1,.2,.3,.4]),(90,[.6,.1,.8,.3]),
                                            (180,[.7,.6,.9,.8]),(270,[.2,.7,.4,.9])])
def test_geometry_rotation(rotation, expected):
    assert normalize_box([10,20,30,40],100,100,'pixels_top_left',rotation) == pytest.approx(expected)


def test_bottom_origin():
    assert normalize_box([10,20,30,40],100,100,'points_bottom_left',0) == pytest.approx([.1,.6,.3,.8])


def test_degenerate_box_rejected():
    with pytest.raises(ValueError): normalize_box([2,1,1,4],10,10,'pixels_top_left',0)


def test_no_invented_panel_or_inline_box():
    result = normalize({'type':'equation_inline','content':'x'}, {'tool':'basic','page_idx':0,
        'paper_sha256':'hash','original_ref':'raw.json','original_sha256':'hash',
        'width':100,'height':100,'coordinates':'normalized_top_left'})
    assert result['bbox_normalized'] is None
    assert result['relations'] is None
    assert result['raw_label'] == 'equation_inline'


def test_compare_one_to_many():
    rows = [dict(id='a',tool='a',paper_sha256='p',page_idx=0,bbox_normalized=[0,0,1,1],raw_label='Picture'),
            dict(id='b',tool='b',paper_sha256='p',page_idx=0,bbox_normalized=[0,0,.5,1],raw_label='image'),
            dict(id='c',tool='b',paper_sha256='p',page_idx=0,bbox_normalized=[.5,0,1,1],raw_label='image')]
    assert len(compare(rows, {'iou_threshold':.5})['edges']) == 2


class Services:
    def __init__(self, fail=False): self.calls=[]; self.fail=fail
    def create(self): self.calls.append('create'); return 'session'
    def stage(self, session, tool):
        self.calls.append(tool['id'])
        if self.fail: raise TimeoutError()
        return {'complete':True,'verified':True,'workers_remaining':False}
    def close(self, session): self.calls.append('close')


def test_sequence_one_session_no_concurrency():
    c,g=ready();s=Services(); result=execute(c,s, authorized=True, gates=g)
    assert result['status'] == 'complete'
    assert s.calls == ['create','heron','heron101','basic','standard','close']


def test_no_authorization_or_gate_no_session():
    s=Services()
    with pytest.raises(ValueError): execute(config(),s,authorized=False,gates=[])
    with pytest.raises(ValueError): execute(config(),s,authorized=True,gates=[{'status':'NOT_RUN'}])
    assert s.calls == []


def test_timeout_no_retry_or_close():
    c,g=ready();s=Services(fail=True)
    assert execute(c,s,authorized=True,gates=g)['status']=='manual_review'
    assert s.calls == ['create','heron']


def test_residual_workers_blocks_next():
    c,g=ready()
    s=Services()
    s.stage=lambda *_: {'complete':True,'verified':True,'workers_remaining':True}
    assert execute(c,s,authorized=True,gates=g)['status']=='manual_review'
    assert s.calls == ['create']






def test_unready_pass_receipt_never_starts():
    s=Services()
    with pytest.raises(ValueError):execute(config(),s,authorized=True,gates=[{'status':'PASS'}])
    assert not s.calls


