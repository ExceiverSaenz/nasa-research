"""End-to-end offline reference -> six results -> viewer -> review -> analytics."""
import hashlib
import json
from pathlib import Path
import threading
import urllib.request
import pytest


def synthetic_run(tmp_path):
    from reading_order.ingest import Ingestor,LocalReferences
    from reading_order.runner import Runner
    folder = tmp_path/'source/assembled/basic/12'
    folder.mkdir(parents=True)
    middle = dict(metadata={'document':{'page_count':2}},extensions={'docvortex_layout':{'pages':[
                  dict(page_idx=i,width_pt=600,height_pt=800) for i in range(2)]}},pages=[
                  {'page_idx':i,'blocks':[{'type':'text','bbox':[.1,.1,.9,.2],'content':[
                      {'type':'text','content':'<script>unsafe()</script>'}]}]} for i in range(2)])
    raw = json.dumps(middle).encode()
    (folder/'middle.json').write_bytes(raw)
    rows = [dict(id=f'block-{i}',paper_sha256='a'*64,page_idx=i,raw_label='text',bbox_normalized=[.1,.1,.9,.2],
                 original_ref=f'/content/12/middle.json#/pages/{i}/blocks/0',original_sha256=hashlib.sha256(raw).hexdigest(),
                 native_parent_ref=None) for i in range(2)]
    (folder/'normalized.json').write_text(json.dumps(rows))
    ingestor = Ingestor(LocalReferences(tmp_path/'source/assembled/basic'))
    frozen = ingestor.freeze(['12'],tmp_path/'input',pdf_metadata={'12':[dict(width=600,height=800,rotation=0)]*2})
    class Engine:
        def predict(self,candidate,blocks,page,timeout):
            return dict(ordered_ids=[b['id'] for b in blocks],native={'fake_engine':True})
    run = tmp_path/'run'
    Runner(Engine()).execute(ingestor.resolve(frozen),frozen,run)
    return run


def test_full_offline_flow_preserves_source_and_human_revision(tmp_path):
    from reading_order.viewer import build_viewer,ViewerData
    from reading_order.reviews import ReviewStore
    from compare_orders import analyze_run
    from summarize_reviews import summarize_reviews
    run = synthetic_run(tmp_path)
    index = build_viewer(run)
    assert len(index['documents'][0]['pages']) == 2
    assert ViewerData(run).page('12',0)['blocks'][0]['text'] == '<script>unsafe()</script>'
    store = ReviewStore(run)
    observation = dict(id='cross',run_id='run',run_sha256=store.run_sha256,input_profile_id=store.run['input_profile_id'],
        case_id='12:0:hantian',candidate_id='hantian',control='docling',paper_id='12',pages=[0,1],block_ids=['block-0','block-1'],
        scope='cross_page',preference='equivalent',issue_type=None,note='<img src=x onerror=alert(1)>',
        author='test',ambiguity=True,review_state='reviewed')
    store.save(observation,0)
    assert store.load()['revision'] == 1
    assert analyze_run(run,tmp_path/'analysis')['coverage']['produced_valid'] == 12
    assert summarize_reviews(run,1,tmp_path/'summary')['reviewed_cases'] == 1
    assert not list(run.rglob('normalized.json'))
    assert not list(run.rglob('*.pdf'))


def test_real_http_host_origin_token_and_static_path_limits(tmp_path):
    from reading_order.server import make_server
    from urllib.error import HTTPError
    run = synthetic_run(tmp_path)
    server = make_server(run,0)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        state = json.load(urllib.request.urlopen(base+'/api/state'))
        assert state['run']['run_id']=='run'
        with pytest.raises(HTTPError) as error:
            urllib.request.urlopen(urllib.request.Request(base+'/api/reviews',data=b'{}',method='PUT',headers={'Content-Type':'application/json'}))
        assert error.value.code == 403
        for route in ('/../manifest.json','/%2e%2e/manifest.json','/api/page?paper=../12&page=0'):
            with pytest.raises(HTTPError):
                urllib.request.urlopen(base+route)
        html = urllib.request.urlopen(base+'/').read()
        assert b'Reading order review' in html
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_stdin_transport_never_embeds_input_in_code_or_history():
    from reading_order.colab_backend import ColabStdinTransport
    class Runtime:
        def __init__(self):
            from types import SimpleNamespace
            self.sent=[]
            self.kernel_client=SimpleNamespace(_manager=SimpleNamespace(client=SimpleNamespace(
                session=SimpleNamespace(msg=lambda kind,content:content),shell_channel=SimpleNamespace(send=self.sent.append))))
        def execute_code(self,code,**kwargs):
            compile(code,'colab-memory-bridge','exec')
            assert 'private-input-text' not in code
            assert not kwargs.get('allow_stdin',False)
            assert callable(kwargs.get('output_hook')), 'Use the validated interactive client path explicitly'
            if 'register_target' in code:return [{'output_type':'stream','text':'ORDER_COMM_READY\n'}]
            assert self.sent[-1]['data']['secret_test']=='private-input-text'
            return [{'output_type':'stream','text':'ORDER_RESULT:'+json.dumps(dict(
                request_id=self.sent[-1]['data']['request_id'],response={'status':'PASS'}))}]
    transport = ColabStdinTransport.__new__(ColabStdinTransport)
    transport.runtime,transport.remote_code,transport.environment = Runtime(),'/content/code','/content/env'
    assert transport(dict(persist_input=False,secret_test='private-input-text'))['status']=='PASS'


def test_transport_preserves_kernel_but_allocates_new_client_session(monkeypatch):
    import sys
    from types import SimpleNamespace
    from reading_order.colab_backend import ColabStdinTransport
    captured={}
    socket_limits=[]
    monkeypatch.setitem(sys.modules,'websocket',SimpleNamespace(setdefaulttimeout=socket_limits.append))
    def runtime(url,token,**kwargs):captured.update(kwargs);return object()
    saved=SimpleNamespace(accelerator='A100',url='private-url',token='private-token',kernel_id='existing-kernel',session_id='old-client-session')
    monkeypatch.setitem(sys.modules,'colab_cli.state',SimpleNamespace(StateStore=lambda:SimpleNamespace(get=lambda name:saved)))
    monkeypatch.setitem(sys.modules,'colab_cli.runtime',SimpleNamespace(ColabRuntime=runtime))
    ColabStdinTransport('owned')._runtime_factory()
    assert captured['kernel_id']=='existing-kernel'
    assert captured['session_id'] is None
    assert captured['history'] is None and captured['session_name'] is None
    assert socket_limits==[10]


def test_transport_message_wait_polls_and_expires():
    from reading_order.colab_backend import PollingSignal
    import threading
    signal=PollingSignal(threading.Event())
    signal.set();assert signal.is_set() and signal.wait(300)
    signal.clear();assert not signal.is_set()
    with pytest.raises(TimeoutError):signal.wait(0)
    class Waiting:
        def wait(self,timeout):assert timeout<=.5;return False
    assert signal.__class__(Waiting()).wait(300) is False


def test_transport_recovers_cached_reply_without_resending_input():
    from types import SimpleNamespace
    from reading_order.colab_backend import ColabStdinTransport
    sent=[]
    class Runtime:
        def __init__(self,broken=False):
            self.broken=broken
            self.kernel_client=SimpleNamespace(_manager=SimpleNamespace(client=SimpleNamespace(
                session=SimpleNamespace(msg=lambda kind,content:content),shell_channel=SimpleNamespace(send=sent.append))))
        def execute_code(self,code,**kwargs):
            if 'register_target' in code:return [{'output_type':'stream','text':'ORDER_COMM_READY\n'}]
            if self.broken:raise TimeoutError('simulated lost wakeup')
            assert 'private-body' not in code and '.handle(' not in code and 'completed' in code
            return [{'output_type':'stream','text':'ORDER_RESULT:'+json.dumps(dict(request_id=sent[0]['data']['request_id'],response={'status':'PASS'}))}]
    t=ColabStdinTransport.__new__(ColabStdinTransport)
    t.runtime=Runtime(True);t.remote_code='/code';t.environment='/env';t._failed=False;t._runtime_factory=lambda:Runtime()
    value=t(dict(persist_input=False,secret='private-body'))
    assert value['status']=='PASS'
    assert value['transformations']['transport_reply_recovery']['request_id']==sent[0]['data']['request_id']
    assert len(sent)==1 and t.recovered_cached==1 and not t._failed


def test_transport_can_retry_bootstrap_before_any_input_is_sent():
    from types import SimpleNamespace
    from reading_order.colab_backend import ColabStdinTransport
    sent=[]
    class Runtime:
        def __init__(self,broken=False):
            self.broken=broken
            self.kernel_client=SimpleNamespace(_manager=SimpleNamespace(client=SimpleNamespace(
                session=SimpleNamespace(msg=lambda kind,content:content),shell_channel=SimpleNamespace(send=sent.append))))
        def execute_code(self,code,**kwargs):
            if self.broken:
                assert not sent and 'register_target' in code
                raise ConnectionError('synthetic bootstrap failure')
            if 'register_target' in code:return [{'output_type':'stream','text':'ORDER_COMM_READY\n'}]
            return [{'output_type':'stream','text':'ORDER_RESULT:'+json.dumps(dict(request_id=sent[0]['data']['request_id'],response={'status':'PASS'}))}]
    t=ColabStdinTransport.__new__(ColabStdinTransport)
    t.runtime=Runtime(True);t.remote_code='/code';t.environment='/env';t._failed=False;t._runtime_factory=lambda:Runtime()
    assert t(dict(persist_input=False))['status']=='PASS'
    assert len(sent)==1 and t.bootstrap_retries==1


def test_historical_cached_case_is_used_once_with_exact_input_order():
    from reading_order.colab_backend import CachedCaseTransport
    calls=[]
    class Delegate:
        def __call__(self,request):calls.append(request);return {'status':'PASS','ordered_ids':['other']}
        def close(self):calls.append('closed')
    page=dict(page_idx=2,width=600,height=800,rotation=0)
    response=dict(status='PASS',ordered_ids=['b','a'],native={'ranks':[1,0]})
    cached=CachedCaseTransport(Delegate(),'hantian',page,'paper-sha',['a','b'],response,{'path':'cache.json','sha256':'verified'})
    request=dict(action='predict',candidate_id='hantian',page=page,
        blocks=[dict(id=i,paper_sha256='paper-sha') for i in ['a','b']])
    value=cached(request)
    assert value['ordered_ids']==['b','a'] and not calls
    assert value['transformations']['historical_reply_recovery']['sha256']=='verified'
    with pytest.raises(ValueError):cached(request)
    cached(dict(request,blocks=list(reversed(request['blocks']))))
    assert len(calls)==1
    cached.close();assert calls[-1]=='closed'


def test_lost_websocket_reply_recovers_derived_output_via_api_without_resend():
    from types import SimpleNamespace
    from reading_order.colab_backend import ColabStdinTransport
    sent=[]
    class Runtime:
        kernel_client=SimpleNamespace(_manager=SimpleNamespace(client=SimpleNamespace(
            session=SimpleNamespace(msg=lambda kind,content:content),shell_channel=SimpleNamespace(send=sent.append))))
        def execute_code(self,code,**kwargs):
            if 'register_target' in code:return [{'output_type':'stream','text':'ORDER_COMM_READY\n'}]
            assert '/content/order-results' in code and 'write_text' in code
            assert 'private-body' not in code and kwargs['timeout']<=15
            raise TimeoutError('synthetic missing WebSocket acknowledgment')
    t=ColabStdinTransport.__new__(ColabStdinTransport)
    t.runtime=Runtime();t.remote_code='/code';t.environment='/env';t._failed=False
    def forbidden():pytest.fail('Result API recovery must not reconnect or submit a second request')
    t._runtime_factory=forbidden
    t._result_reader=lambda request_id:dict(request_id=request_id,response={'status':'PASS'},artifact_sha256='verified-output')
    result=t(dict(persist_input=False,secret='private-body'))
    assert len(sent)==1 and result['status']=='PASS'
    recovery=result['transformations']['transport_reply_recovery']
    assert recovery['kind']=='authenticated_result_api' and recovery['sha256']=='verified-output'
    assert t._comm_ready is False


def test_isolated_transport_retires_clients_at_confirmed_batch_boundary(monkeypatch):
    from reading_order.colab_backend import IsolatedColabTransport
    from reading_order import memory_bridge
    children=[];submitted=[]
    class Child:
        def __init__(self):self.dead=False
        def poll(self):return 0 if self.dead else None
        def kill(self):self.dead=True
        def wait(self,timeout):return 0
    def launch():
        child=Child();children.append(child);return child
    def exchange(child,request,*args,**kwargs):
        if request.get('kind')=='bootstrap':return {'status':'READY'}
        submitted.append(request);return dict(request_id=request['request_id'],response={'status':'PASS'})
    monkeypatch.setattr(memory_bridge,'exchange',exchange)
    t=IsolatedColabTransport.__new__(IsolatedColabTransport)
    t._child=None;t._count=0;t._failed=False;t._launch=launch
    for i in range(41):assert t(dict(persist_input=False))['status']=='PASS'
    assert len(children)==3 and all(c.dead for c in children[:-1])
    assert len(submitted)==41 and len({v['request_id'] for v in submitted})==41
    t.close();assert children[-1].dead


def test_isolated_child_failure_recovers_output_without_replaying_model(monkeypatch):
    from reading_order.colab_backend import IsolatedColabTransport
    from reading_order import memory_bridge
    from types import SimpleNamespace
    submitted=[]
    class Child:
        def poll(self):return None
        def kill(self):pass
        def wait(self,timeout):return 0
    def exchange(child,request,*args,**kwargs):
        if request.get('kind')=='bootstrap':return {'status':'READY'}
        submitted.append(request);raise EOFError('synthetic client crash')
    monkeypatch.setattr(memory_bridge,'exchange',exchange)
    def recover(request_id,timeout):
        assert request_id==submitted[0]['request_id']
        return {'status':'PASS','transformations':{'transport_reply_recovery':{'request_id':request_id}}}
    t=IsolatedColabTransport.__new__(IsolatedColabTransport)
    t._child=None;t._count=0;t._failed=False;t._launch=Child;t._api=SimpleNamespace(_recover_cached=recover)
    assert t(dict(persist_input=False,timeout_s=1))['status']=='PASS'
    assert len(submitted)==1 and t.recovered_cached==1


def test_transport_rejects_invalid_explicit_uuid_before_opening_connection():
    from reading_order.colab_backend import ColabStdinTransport
    t=ColabStdinTransport.__new__(ColabStdinTransport);t.runtime=None;t._failed=False
    t._runtime_factory=lambda:pytest.fail('Invalid UUID reached client creation')
    with pytest.raises(ValueError):t(dict(persist_input=False,request_id='../unsafe'))


def test_real_child_exit_preserves_controller_and_does_not_replay_input(tmp_path):
    import subprocess,sys
    from types import SimpleNamespace
    from reading_order.colab_backend import IsolatedColabTransport
    marker=tmp_path/'submitted-uuid'
    program="""
import sys,json,os
ready=json.loads(sys.stdin.readline())
assert ready['kind']=='bootstrap'
print('ORDER_RESULT:'+json.dumps({'status':'READY'}),flush=True)
request=json.loads(sys.stdin.readline())
with open(sys.argv[1],'a') as stream:stream.write(request['request_id']+'\\n')
os._exit(17)
"""
    t=IsolatedColabTransport.__new__(IsolatedColabTransport)
    t._child=None;t._count=0;t._failed=False
    t._launch=lambda:subprocess.Popen([sys.executable,'-B','-u','-c',program,str(marker)],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
    def recover(request_id,timeout):
        assert marker.read_text().splitlines()==[request_id]
        return {'status':'PASS','transformations':{'transport_reply_recovery':{'request_id':request_id}}}
    t._api=SimpleNamespace(_recover_cached=recover)
    assert t(dict(persist_input=False,timeout_s=2,synthetic='not a document'))['status']=='PASS'
    assert len(marker.read_text().splitlines())==1 and t._child is None


def test_bridge_error_publishes_page_failure_without_source_data(tmp_path,monkeypatch):
    import sys
    from types import SimpleNamespace
    from reading_order.colab_backend import ColabStdinTransport
    sent=[];captured=[]
    class Runtime:
        kernel_client=SimpleNamespace(_manager=SimpleNamespace(client=SimpleNamespace(
            session=SimpleNamespace(msg=lambda kind,content:content),shell_channel=SimpleNamespace(send=sent.append))))
        def execute_code(self,code,**kwargs):
            if 'register_target' in code:return [{'output_type':'stream','text':'ORDER_COMM_READY\n'}]
            captured.append(code)
            return [{'output_type':'stream','text':'ORDER_RESULT:'+json.dumps(dict(request_id=sent[0]['data']['request_id'],response={'status':'PASS'}))}]
    t=ColabStdinTransport.__new__(ColabStdinTransport)
    t.runtime=Runtime();t.remote_code='/code';t.environment='/env';t._failed=False;t.result_root=str(tmp_path/'derived')
    t(dict(persist_input=False,private='private-source-body'))
    class Bridge:
        child=SimpleNamespace(poll=lambda:-11)
        def handle(self,request):raise RuntimeError('simulated worker exit')
    monkeypatch.setitem(sys.modules,'reading_order.memory_bridge',SimpleNamespace(KernelBridge=Bridge))
    monkeypatch.setattr(sys,'path',list(sys.path))
    request=sent[0]['data'];namespace=dict(_order_bridge=Bridge(),_order_pending={request['request_id']:request})
    exec(captured[0],namespace)
    raw=(tmp_path/'derived'/(request['request_id']+'.json')).read_text()
    value=json.loads(raw)
    assert value['response']['status']=='FAIL' and value['response']['native']['worker_exit_code']==-11
    assert 'private-source-body' not in raw and '_order_request' not in namespace


def test_supervisor_retries_only_when_child_confirms_no_remote_input(monkeypatch):
    from reading_order.colab_backend import IsolatedColabTransport
    from reading_order import memory_bridge
    submitted=[];children=[]
    class Child:
        def poll(self):return None
        def kill(self):pass
        def wait(self,timeout):return 0
    def launch():children.append(Child());return children[-1]
    def exchange(child,request,*args,**kwargs):
        if request.get('kind')=='bootstrap':return {'status':'READY'}
        submitted.append(request)
        if len(submitted)==1:return dict(request_id=request['request_id'],_transport_error='ConnectionError',input_submitted=False)
        return dict(request_id=request['request_id'],response={'status':'PASS'})
    monkeypatch.setattr(memory_bridge,'exchange',exchange)
    t=IsolatedColabTransport.__new__(IsolatedColabTransport)
    t._child=None;t._count=0;t._failed=False;t._launch=launch
    assert t(dict(persist_input=False))['status']=='PASS'
    assert len(children)==2 and len(submitted)==2 and submitted[0]['request_id']==submitted[1]['request_id']


def test_direct_result_mode_submits_once_and_reads_api_without_sdk_reply():
    from types import SimpleNamespace
    from reading_order.colab_backend import ColabStdinTransport
    sent=[]
    class Runtime:
        kernel_client=SimpleNamespace(_manager=SimpleNamespace(client=SimpleNamespace(
            session=SimpleNamespace(msg=lambda kind,content:dict(kind=kind,**content)),shell_channel=SimpleNamespace(send=sent.append))))
        def execute_code(self,*args,**kwargs):pytest.fail('Direct mode must not wait for an SDK execution reply')
    t=ColabStdinTransport.__new__(ColabStdinTransport)
    t.runtime=Runtime();t.remote_code='/code';t.environment='/env';t._failed=False;t._comm_ready=True;t.direct_results=True
    t._result_reader=lambda request_id:dict(request_id=request_id,response={'status':'PASS'},artifact_sha256='verified')
    result=t(dict(persist_input=False,secret='private-source'))
    assert result['status']=='PASS' and len(sent)==2
    assert sent[0]['kind']=='comm_open' and sent[1]['kind']=='execute_request'
    assert sent[1]['store_history'] is False and 'private-source' not in sent[1]['code']
    assert result['transformations']['result_artifact']['sha256']=='verified'


def test_supervisor_retires_idle_client_before_next_source_request(monkeypatch):
    import time
    from reading_order.colab_backend import IsolatedColabTransport
    from reading_order import memory_bridge
    now=[0.0];monkeypatch.setattr(time,'monotonic',lambda:now[0])
    children=[];sent=[]
    class Child:
        def poll(self):return None
        def kill(self):pass
        def wait(self,timeout):return 0
    def launch():children.append(Child());return children[-1]
    def exchange(child,request,*args,**kwargs):
        if request.get('kind')=='bootstrap':return {'status':'READY'}
        sent.append(request);return dict(request_id=request['request_id'],response={'status':'PASS'})
    monkeypatch.setattr(memory_bridge,'exchange',exchange)
    t=IsolatedColabTransport.__new__(IsolatedColabTransport)
    t._child=None;t._count=0;t._failed=False;t._launch=launch
    t(dict(persist_input=False));now[0]=21;t(dict(persist_input=False))
    assert len(children)==2 and len(sent)==2


def test_remote_comm_deduplicates_uuid_and_persists_only_receipt(tmp_path):
    from types import SimpleNamespace
    from reading_order.colab_backend import comm_setup
    callbacks={}
    kernel=SimpleNamespace(comm_manager=SimpleNamespace(register_target=lambda name,fn:callbacks.update({name:fn})))
    namespace={'get_ipython':lambda:SimpleNamespace(kernel=kernel)}
    exec(comm_setup(str(tmp_path)),namespace)
    receive=callbacks['reading_order_memory'];key='a'*32
    comm=SimpleNamespace(comm_id=key,close=lambda:None)
    payload=dict(request_id=key,persist_input=False,secret='private-source')
    receive(comm,dict(content=dict(data=payload)))
    namespace['_order_pending'].pop(key)
    receive(comm,dict(content=dict(data=payload)))
    assert not namespace['_order_pending']
    receipt=(tmp_path/(key+'.json')).read_text()
    assert json.loads(receipt)['response']['stage']=='RECEIVED'
    assert 'private-source' not in receipt
    with pytest.raises(ValueError):receive(comm,dict(content=dict(data=dict(payload,secret='different'))))


@pytest.mark.parametrize('evict_completed',[False,True])
def test_duplicate_static_dispatch_cannot_repeat_model_forward(tmp_path,monkeypatch,evict_completed):
    import sys
    from types import SimpleNamespace
    from reading_order.colab_backend import ColabStdinTransport
    captured=[];sent=[]
    class Runtime:
        kernel_client=SimpleNamespace(_manager=SimpleNamespace(client=SimpleNamespace(
            session=SimpleNamespace(msg=lambda kind,content:content),shell_channel=SimpleNamespace(send=sent.append))))
        def execute_code(self,code,**kwargs):
            if 'register_target' in code:return [{'text':'ORDER_COMM_READY'}]
            captured.append(code)
            return [{'text':'ORDER_RESULT:'+json.dumps(dict(request_id=sent[0]['data']['request_id'],response={'status':'PASS'}))}]
    t=ColabStdinTransport.__new__(ColabStdinTransport)
    t.runtime=Runtime();t.remote_code='/code';t.environment='/env';t._failed=False;t.result_root=str(tmp_path)
    t(dict(persist_input=False,private='private-source'))
    class Bridge:
        def __init__(self):self.completed={};self.calls=0
        def handle(self,request):
            self.calls+=1
            value=dict(request_id=request['request_id'],response={'status':'PASS','ordered_ids':['synthetic']})
            self.completed[request['request_id']]=value;return value
    bridge=Bridge();request=sent[0]['data']
    monkeypatch.setitem(sys.modules,'reading_order.memory_bridge',SimpleNamespace(KernelBridge=Bridge))
    monkeypatch.setattr(sys,'path',list(sys.path))
    namespace=dict(_order_bridge=bridge,_order_pending={request['request_id']:request})
    exec(captured[0],namespace)
    if evict_completed:bridge.completed.clear()
    exec(captured[0],namespace)
    result=json.loads((tmp_path/(request['request_id']+'.json')).read_text())
    assert bridge.calls==1 and result['response']['status']==('FAIL' if evict_completed else 'PASS')


@pytest.mark.parametrize('lost_phase',['comm','after_comm','dispatch','after_forward'])
def test_delivery_recovery_survives_lost_frames_without_second_forward(tmp_path,monkeypatch,lost_phase):
    import sys,hashlib
    from types import SimpleNamespace
    from reading_order.colab_backend import ColabStdinTransport,IsolatedColabTransport,comm_setup
    from reading_order import memory_bridge
    receipt_root=tmp_path/'receipts';result_root=tmp_path/'results'
    callbacks={};dropped=[];messages=[]
    kernel=SimpleNamespace(comm_manager=SimpleNamespace(register_target=lambda name,fn:callbacks.update({name:fn})))
    class Bridge:
        def __init__(self):self.completed={};self.calls=0
        def handle(self,request):
            self.calls+=1
            result=dict(request_id=request['request_id'],response=dict(status='PASS',ordered_ids=['synthetic']))
            self.completed[request['request_id']]=result;return result
    bridge=Bridge();namespace=dict(get_ipython=lambda:SimpleNamespace(kernel=kernel),_order_bridge=bridge)
    monkeypatch.setattr(memory_bridge,'KernelBridge',Bridge)
    monkeypatch.setattr(sys,'path',list(sys.path))
    def read(directory,key):
        path=directory/(key+'.json')
        if not path.exists():return None
        raw=path.read_bytes();return dict(json.loads(raw),artifact_sha256=hashlib.sha256(raw).hexdigest())
    def drop(phase):
        if phase==lost_phase and not dropped:
            dropped.append(phase);raise ConnectionError('simulated lost frame')
    def client():
        t=ColabStdinTransport.__new__(ColabStdinTransport)
        t._failed=False;t.rotate=False;t.direct_results=True;t.remote_code='/code';t.environment='/env'
        t.result_root=str(result_root);t._receipt_reader=lambda key:read(receipt_root,key)
        t._result_reader=lambda key:read(result_root,key)
        def send(message):
            kind=message['kind'];messages.append(kind)
            if kind=='comm_open':
                drop('comm')
                callbacks['reading_order_memory'](SimpleNamespace(comm_id=message['comm_id'],close=lambda:None),dict(content=dict(data=message['data'])))
                drop('after_comm')
            else:
                drop('dispatch');exec(message['code'],namespace);drop('after_forward')
        t.runtime=SimpleNamespace(kernel_client=SimpleNamespace(_manager=SimpleNamespace(client=SimpleNamespace(
            session=SimpleNamespace(msg=lambda kind,content:dict(kind=kind,**content)),shell_channel=SimpleNamespace(send=send)))))
        t._disconnect=lambda:None
        def register(setup):
            exec(comm_setup(str(receipt_root)),namespace);t._comm_ready=True
        t._register=register
        return t
    class Child:
        def __init__(self):self.client=client()
        def poll(self):return None
        def kill(self):pass
        def wait(self,timeout):return 0
    def exchange(child,request,*args,**kwargs):
        if request.get('kind')=='bootstrap':child.client._register('');return {'status':'READY'}
        try:return dict(request_id=request['request_id'],response=child.client(request))
        except Exception as error:return dict(request_id=request['request_id'],_transport_error=type(error).__name__,input_submitted=child.client._input_submitted)
    monkeypatch.setattr(memory_bridge,'exchange',exchange)
    t=IsolatedColabTransport.__new__(IsolatedColabTransport)
    t._child=None;t._count=0;t._failed=False;t._launch=Child;t._api=client()
    result=t(dict(persist_input=False,secret='private-source',timeout_s=1))
    assert result['status']=='PASS' and bridge.calls==1 and t.delivery_recoveries==1
    assert messages.count('comm_open')==(2 if lost_phase=='comm' else 1)
    assert all('private-source' not in p.read_text() for p in tmp_path.rglob('*.json'))


@pytest.mark.parametrize('age_boundary',[False,True])
def test_transport_rotates_only_between_confirmed_requests(monkeypatch,age_boundary):
    from types import SimpleNamespace
    from reading_order import colab_backend
    import time
    clock=[0.0];monkeypatch.setattr(time,'monotonic',lambda:clock[0])
    created=[]
    class Runtime:
        def __init__(self):
            self.sent=[];self.stopped=False;self.registrations=0
            self.kernel_client=SimpleNamespace(_manager=SimpleNamespace(client=SimpleNamespace(
                session=SimpleNamespace(msg=lambda kind,content:content),shell_channel=SimpleNamespace(send=self.sent.append))))
        def execute_code(self,code,**kwargs):
            if 'register_target' in code:
                self.registrations+=1
                return [{'output_type':'stream','text':'ORDER_COMM_READY\n'}]
            return [{'output_type':'stream','text':'ORDER_RESULT:'+json.dumps(dict(request_id=self.sent[-1]['data']['request_id'],response={'status':'PASS'}))}]
        def stop(self):self.stopped=True
    def factory():
        value=Runtime();created.append(value);return value
    t=colab_backend.ColabStdinTransport.__new__(colab_backend.ColabStdinTransport)
    t.runtime=None;t.remote_code='/code';t.environment='/env';t._failed=False;t._runtime_factory=factory
    count=2 if age_boundary else 21
    for i in range(count):
        if age_boundary and i:clock[0]=21
        assert t(dict(persist_input=False))['status']=='PASS'
    assert len(created)==2 and created[0].stopped
    assert [r.registrations for r in created]==[1,1]
    messages=[m for r in created for m in r.sent]
    assert len(messages)==count and len({m['comm_id'] for m in messages})==count


def test_test_receipt_is_invalidated_by_code_change(tmp_path):
    from reading_order.preflight import code_fingerprint,require_test_receipt
    (tmp_path/'code').mkdir()
    source = tmp_path/'code/module.py'
    source.write_text('x=1')
    receipt = tmp_path/'receipt.json'
    receipt.write_text(json.dumps(dict(status='PASS',code_files=code_fingerprint(tmp_path))))
    assert require_test_receipt(tmp_path,receipt)['status']=='PASS'
    source.write_text('x=2')
    with pytest.raises(ValueError):
        require_test_receipt(tmp_path,receipt)


def test_bootstrap_build_manifest_has_real_newlines():
    from reading_order.deployment import BOOTSTRAP
    captured = []
    class Target:
        def __truediv__(self,key):
            return self
        def write_text(self,text):
            captured.append(text)
    line = next(line for line in BOOTSTRAP.splitlines() if "(worker/'Cargo.toml').write_text" in line)
    exec(line,{'worker':Target(),'dependency':Path('/verified-dependency')})
    assert '\n' in captured[0]
    assert '\\n' not in captured[0]


def test_rotated_non_square_reference_roundtrip(tmp_path):
    from reading_order.ingest import Ingestor,LocalReferences
    synthetic_run(tmp_path)
    ingest = Ingestor(LocalReferences(tmp_path/'source/assembled/basic'))
    manifest = ingest.freeze(['12'],tmp_path/'rotated-input',pdf_metadata={
        '12':[dict(width=800,height=600,rotation=90)]*2})
    doc = ingest.resolve(manifest)[0]
    assert doc.pages[0]['width']==600
    assert doc.pages[0]['height']==800
    assert doc.pages[0]['rotation']==90


def test_stability_failure_blocks_overall_completion():
    from reading_order import runner
    assert hasattr(runner,'all_runs_pass'), 'stability completion gate is absent'
    good={'predictions':[{'status':'PASS'}]}
    bad={'predictions':[{'status':'FAIL'}]}
    assert runner.all_runs_pass([good,good])
    assert not runner.all_runs_pass([good,bad])


def test_uploaded_code_must_match_current_code(tmp_path):
    from reading_order import preflight
    assert hasattr(preflight,'require_deployment_code'), 'deployment identity gate is absent'
    path=tmp_path/'code/reading_order'
    path.mkdir(parents=True)
    (path/'engine.py').write_text('version=1')
    receipt={'code_files':preflight.production_fingerprint(tmp_path)}
    assert preflight.require_deployment_code(tmp_path,receipt)
    (path/'engine.py').write_text('version=2')
    with pytest.raises(ValueError):
        preflight.require_deployment_code(tmp_path,receipt)
