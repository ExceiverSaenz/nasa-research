import hashlib
import json
import sys
import zipfile
from pathlib import Path
import pytest
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file());sys.path.insert(0,str(ROOT))
from bbx.workflow import Workflow,extract_verified


@pytest.fixture
def simulated_wheel_bundle(monkeypatch):
    # Transport is simulated: supply a synthetic bundle, never a host wheel cache.
    # Real cache/hash verification has dedicated pack_wheels controls.
    def bundle(root,destination,expected=None):
        with zipfile.ZipFile(destination,'x') as archive:
            archive.writestr('fixture-only.txt','Synthetic transport fixture; no installable wheels')
    monkeypatch.setattr('bbx.workflow.pack_wheels',bundle)


class SimulatedTransport:
    def __init__(self):self.calls=[];self.private=[];self.archive=None
    def create(self,session,authorized=False):assert authorized;self.calls.append('create')
    def command(self,args):assert args==['sessions'];self.calls.append('auth');return ''
    def upload(self,session,local,remote):
        if remote.endswith('private-requests.json'):
            self.private.append(Path(local));rows=json.loads(Path(local).read_text());assert rows[0]['url'].startswith('https://')
        self.calls.append('upload')
    def exec_code(self,session,code,marker,timeout=600):
        compile(code,'remote-phase','exec')
        assert 'PERMANENT_SECRET' not in code
        if marker.startswith('BBX_PHASE_COMPLETED:'):
            phase=marker.split(':')[-1];self.calls.append(phase)
            status='prepared' if phase=='prepare' else 'complete'
            return marker+'\nBBX_RESULT:'+json.dumps({'status':status})
        if marker=='BBX_ARCHIVE_COMPLETED':
            payload={}
            for t in ('heron','heron101','basic','standard'):
                files={name:{'bytes':2,'sha256':hashlib.sha256(b'[]').hexdigest()} for name in ('normalized.json','raw.json')}
                payload[f'{t}/receipt.json']=json.dumps({'results':[{'paper':'1.pdf','status':'complete','result':{'page_indices':[0]},'files':files}]}).encode()
                for name in files:payload[f'{t}/1/{name}']=b'[]'
            manifest={k:{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for k,v in payload.items()}
            import io
            buf=io.BytesIO()
            with zipfile.ZipFile(buf,'w') as z:
                for k,v in payload.items():z.writestr(k,v)
                z.writestr('manifest.json',json.dumps(manifest))
            self.archive=buf.getvalue()
            return marker+'\nBBX_ARCHIVE:'+json.dumps({'sha256':hashlib.sha256(self.archive).hexdigest()})
        return marker
    def download(self,session,remote,local):Path(local).write_bytes(self.archive);self.calls.append('download')
    def stop(self,session):self.calls.append('stop')


def r2_config(tmp):
    p=tmp/'r2.env';p.write_text('R2_ENDPOINT_URL=https://example.r2.cloudflarestorage.com\nR2_BUCKET=papers\nAWS_ACCESS_KEY_ID=ACCESS\nAWS_SECRET_ACCESS_KEY=PERMANENT_SECRET\n');return p


def passing_probe(_config,papers):
    return [{'id':'r2_head:'+p['name'],'status':'PASS'} for p in papers]+[{'id':'r2_get:'+papers[0]['name'],'status':'PASS'}]


def test_full_simulated_cycle_reuses_single_session(tmp_path,simulated_wheel_bundle):
    transport=SimulatedTransport();flow=Workflow(ROOT,tmp_path/'attempt',transport,prober=passing_probe)
    papers=[{'name':'1.pdf','sha256':'a'*64,'bytes':1,'pages':1}]
    assert flow.prepare(papers,allow_remote=True,r2_config=r2_config(tmp_path))['status']=='prepared'
    assert flow.smoke(r2_config(tmp_path),allow_inference=True)['status']=='smoke_passed'
    assert flow.execute(r2_config(tmp_path),allow_inference=True)['status']=='complete'
    assert transport.calls.count('create')==1 and transport.calls[-1]=='stop'
    assert all(not p.exists() for p in transport.private)
    assert 'PERMANENT_SECRET' not in flow.state_path.read_text()
    with pytest.raises(ValueError):flow.prepare(papers,allow_remote=True)
    assert transport.calls.count('create')==1


def test_timeout_retains_session_and_never_closes(tmp_path,simulated_wheel_bundle):
    transport=SimulatedTransport();flow=Workflow(ROOT,tmp_path/'attempt',transport,prober=passing_probe)
    transport.exec_code=lambda *_args,**_kw:(_ for _ in ()).throw(TimeoutError())
    with pytest.raises(TimeoutError):flow.prepare([{'name':'1.pdf','sha256':'a'*64,'bytes':1,'pages':1}],allow_remote=True,r2_config=r2_config(tmp_path))
    assert flow.state()['status']=='manual_review'
    assert 'stop' not in transport.calls and transport.calls.count('create')==1


def test_corrupt_return_archive_rejected(tmp_path):
    p=tmp_path/'return.zip';p.write_bytes(b'bad')
    with pytest.raises(ValueError):extract_verified(p,tmp_path/'out','0'*64)


def test_plan_command_never_allocates():
    import subprocess
    result=subprocess.run([sys.executable,str(ROOT/'run.py'),'colab','plan','--attempt','unused'],capture_output=True,text=True,check=True)
    assert json.loads(result.stdout)['session_will_start'] is False


def test_r2_failure_never_allocates(tmp_path):
    transport=SimulatedTransport();flow=Workflow(ROOT,tmp_path/'attempt',transport,prober=lambda *_:[{'id':'r2_head:1.pdf','status':'FAIL'}])
    with pytest.raises(ValueError):flow.prepare([{'name':'1.pdf','sha256':'a'*64,'bytes':1,'pages':1}],allow_remote=True,r2_config=r2_config(tmp_path))
    assert transport.calls==[]


def test_native_page_coverage_is_required_even_with_complete_paper(tmp_path):
    from bbx.workflow import verify_collection
    p=tmp_path/'basic';p.mkdir()
    (p/'receipt.json').write_text(json.dumps({'results':[{'paper':'1.pdf','status':'complete','result':{'page_indices':[0]},'files':{}}]}))
    with pytest.raises(ValueError,match='coverage'):verify_collection(tmp_path,[{'name':'1.pdf','pages':2}],['basic'])


def test_archive_includes_environment_and_smoke_provenance(tmp_path):
    from bbx.remote import archive_results
    for rel in ['results/execute/basic/receipt.json','results/smoke/basic/receipt.json','inventory.json',
                'runtime/environment-receipt.json','runtime/prepared.json','runtime/smoke.json','runtime/execute.json',
                'runtime/effective-config.json','runtime/mineru-config.json']:
        p=tmp_path/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
    (tmp_path/'experiment.json').write_text(json.dumps({'locks':{},'model_manifests':[]}))
    identity=archive_results(tmp_path)
    with zipfile.ZipFile(tmp_path/'results.zip') as z:
        assert 'provenance/runtime/environment-receipt.json' in z.namelist()
        assert 'provenance/smoke-results/basic/receipt.json' in z.namelist()
    extract_verified(tmp_path/'results.zip',tmp_path/'extracted',identity['sha256'])
