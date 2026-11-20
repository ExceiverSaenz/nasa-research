import json,subprocess,sys,time
from types import SimpleNamespace
import pytest


def test_partial_worker_line_cannot_bypass_deadline():
    from reading_order.memory_bridge import exchange
    child=subprocess.Popen([sys.executable,'-u','-c',"import sys,time;sys.stdin.readline();sys.stdout.write('partial');sys.stdout.flush();time.sleep(20)"],
                           stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    started=time.monotonic()
    with pytest.raises(TimeoutError):exchange(child,{'synthetic':True},.2,lambda:None,interval=.05)
    assert time.monotonic()-started<3
    assert child.poll() is not None


def test_long_exchange_emits_progress_without_input():
    from reading_order.memory_bridge import exchange
    child=subprocess.Popen([sys.executable,'-u','-c',"import sys,time;sys.stdin.readline();time.sleep(.25);print('ORDER_RESULT:{\"status\":\"PASS\"}',flush=True)"],
                           stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    beats=[]
    assert exchange(child,{'secret':'private'},3,lambda:beats.append('alive'),interval=.05)['status']=='PASS'
    child.wait(timeout=2)
    assert len(beats)>=2


class Runtime:
    def __init__(self,fail=False):
        self.fail=fail;self.stopped=False;self.payload=None
        self.kernel_client=SimpleNamespace(_manager=SimpleNamespace(client=SimpleNamespace(
            session=SimpleNamespace(msg=lambda kind,content:dict(msg_type=kind,content=content)),
            shell_channel=SimpleNamespace(send=self.send))))
    def send(self,message):self.payload=message['content']['data']
    def execute_code(self,code,**kw):
        assert 'private-text' not in code
        if self.fail:raise TimeoutError('sensitive URL must not escape')
        assert not kw.get('allow_stdin',False)
        if 'register_target' in code:return [dict(output_type='stream',text='ORDER_COMM_READY\n')]
        if 'ORDER_RESULT:' not in code:return []
        return [dict(output_type='stream',text='ORDER_RESULT:'+json.dumps(dict(request_id=self.payload['request_id'],response={'status':'PASS'})))]
    def stop(self):self.stopped=True


def test_confirmed_requests_share_one_client_until_explicit_close():
    from reading_order.colab_backend import ColabStdinTransport
    transport=ColabStdinTransport.__new__(ColabStdinTransport)
    runtimes=[Runtime()]
    transport.runtime=None;transport._runtime_factory=lambda:runtimes.pop(0)
    transport.remote_code='/code';transport.environment='/env'
    first=runtimes[0]
    assert transport(dict(persist_input=False,text='private-text'))['status']=='PASS'
    assert not first.stopped
    assert transport(dict(persist_input=False,text='private-text'))['status']=='PASS'
    assert not runtimes
    transport.close()
    assert first.stopped


def test_lost_connection_is_latched_without_resending():
    from reading_order.colab_backend import ColabStdinTransport,TransportError
    transport=ColabStdinTransport.__new__(ColabStdinTransport)
    runtime=Runtime(fail=True)
    transport.runtime=runtime;transport.remote_code='/code';transport.environment='/env'
    for _ in range(2):
        with pytest.raises(TransportError,match='Transport unavailable'):
            transport(dict(persist_input=False,text='private-text'))
    assert runtime.stopped


def test_runner_reuses_only_exact_passing_results(tmp_path):
    from reading_order.runner import Runner
    from reading_order.contracts import InputDocument,Block
    calls=[]
    class Backend:
        def predict(self,candidate,blocks,page,timeout):
            calls.append(candidate);return dict(ordered_ids=[b['id'] for b in blocks],native={})
    doc=InputDocument('12','f'*64,[dict(page_idx=0,width=600,height=800,rotation=0)],
                      [Block('a','f'*64,0,'text',[.1,.1,.2,.2],None,'synthetic')],{})
    original=Runner(Backend(),seed=1729).execute([doc],{'input_profile_id':'fixed'},tmp_path/'first')
    reused={('hantian','12',0):dict(original['predictions'][0],reused_from={'synthetic':True})}
    calls.clear()
    result=Runner(Backend(),seed=1729).execute([doc],{'input_profile_id':'fixed'},tmp_path/'resume',reuse=reused)
    assert len(result['predictions'])==6 and 'hantian' not in calls
    assert result['predictions'][0]['reused_from']=={'synthetic':True}
    reused[('hantian','12',0)]['scope']['permutation_seed']=1730
    with pytest.raises(ValueError):Runner(Backend(),seed=1729).execute([doc],{'input_profile_id':'fixed'},tmp_path/'bad',reuse=reused)


def test_transport_loss_stops_unsent_model_calls(tmp_path):
    from reading_order.runner import Runner
    from reading_order.colab_backend import TransportError
    from reading_order.contracts import InputDocument,Block
    calls=[]
    class Backend:
        def predict(self,*args):calls.append(1);raise TransportError('Transport unavailable')
    doc=InputDocument('12','f'*64,[dict(page_idx=0,width=600,height=800,rotation=0)],
                      [Block('a','f'*64,0,'text',[.1,.1,.2,.2],None,'synthetic')],{})
    report=Runner(Backend()).execute([doc],{'input_profile_id':'fixed'},tmp_path/'lost')
    assert len(calls)==1
    assert [p['status'] for p in report['predictions']]==['FAIL']+['NOT_RUN']*5


def test_stability_selection_rejects_changed_input_and_preserves_passes(tmp_path):
    from reading_order.stability import stability_inputs,verify_unchanged
    from reading_order.contracts import CANDIDATES
    primary=tmp_path/'primary';primary.mkdir()
    predictions=[dict(candidate_id=c,status='PASS',ordered_ids=[],scope=dict(paper_id='12',page_idx=p,permutation_seed=None))
                 for c in CANDIDATES for p in range(13)]
    run=dict(condition='canonical_sha256_id_order',predictions=predictions,input_profile_id='frozen',
             input_reference={'test':'references'},stability_runs=[])
    for seed in [1729,1730]:
        directory=tmp_path/str(seed);directory.mkdir()
        old=dict(run,predictions=[dict(p,status='PASS' if i<10 else 'FAIL',scope=dict(p['scope'],permutation_seed=seed)) for i,p in enumerate(predictions)])
        (directory/'manifest.json').write_text(json.dumps(old))
        run['stability_runs'].append(dict(seed=seed,run_id=str(seed)))
    path=primary/'manifest.json';path.write_text(json.dumps(run))
    _,ref,conditions=stability_inputs(path)
    assert [len(c['reuse']) for c in conditions]==[10,10]
    verify_unchanged([ref,*[c['reference'] for c in conditions]])
    changed=json.loads((tmp_path/'1729/manifest.json').read_text());changed['input_reference']={'changed':True}
    (tmp_path/'1729/manifest.json').write_text(json.dumps(changed))
    with pytest.raises(ValueError):stability_inputs(path)
