"""Authenticated comm payloads stay in memory, outside code/history/files."""
import json
import uuid
import time
import hashlib

class TransportError(ConnectionError):
    pass


class PollingSignal:
    """Bound queue polling even when the upstream event notification is lost."""
    def __init__(self,event):self.event=event
    def __getattr__(self,name):return getattr(self.event,name)
    def wait(self,timeout=None):
        if timeout is not None and timeout<=0:raise TimeoutError('Client deadline exceeded')
        return self.event.wait(timeout=.5 if timeout is None else min(.5,timeout))


def comm_setup(receipt_root='/content/order-receipts'):
    """Register an idempotent memory inbox; durable receipts contain no source."""
    return """
import json,hashlib
from pathlib import Path
if '_order_pending' not in globals():_order_pending={}
if '_order_deliveries' not in globals():_order_deliveries={}
if '_order_started' not in globals():_order_started=set()
def _order_receipt(key,stage=None):
    value=_order_deliveries[key]
    if stage is not None:value['stage']=stage
    directory=Path(RECEIPT_ROOT);directory.mkdir(exist_ok=True)
    temporary=directory/(key+'.tmp')
    temporary.write_text(json.dumps(dict(request_id=key,response=value)))
    temporary.replace(directory/(key+'.json'))
def _order_receive(comm,msg):
    key=comm.comm_id;payload=msg['content']['data']
    if payload.get('request_id')!=key:raise ValueError('Input UUID differs')
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    if key in _order_deliveries:
        if _order_deliveries[key]['input_sha256']!=digest:raise ValueError('Conflicting input UUID')
    else:
        _order_pending[key]=payload
        _order_deliveries[key]=dict(stage='RECEIVED',input_sha256=digest)
    _order_receipt(key)
    comm.close()
get_ipython().kernel.comm_manager.register_target('reading_order_memory',_order_receive)
print('ORDER_COMM_READY',flush=True)
""".replace('RECEIPT_ROOT',repr(receipt_root))

class MemoryBackend:
    def __init__(self,transport,capture_diagnostics=()):
        self.transport=transport
        self.capture_diagnostics=set(capture_diagnostics)
    def predict(self,candidate,blocks,page,timeout_s):
        return self.transport(dict(action='predict',candidate_id=candidate,blocks=blocks,page=page,
                                   timeout_s=timeout_s,persist_input=False,
                                   capture_diagnostics=candidate in self.capture_diagnostics))


class CachedCaseTransport:
    """Compose an audited historical reply with the normal live transport."""
    def __init__(self,delegate,candidate,page,paper_sha256,ids,response,reference):
        from .contracts import require_permutation
        require_permutation(response['ordered_ids'],ids)
        self.delegate,self.candidate,self.page=delegate,candidate,page
        self.paper_sha256,self.ids,self.response,self.reference=paper_sha256,ids,response,reference
        self.historical_cache_hits=0
    def __getattr__(self,name):return getattr(self.delegate,name)
    def __call__(self,request):
        blocks=request.get('blocks',[])
        if (request.get('action')=='predict' and request.get('candidate_id')==self.candidate
                and request.get('page')==self.page and [b['id'] for b in blocks]==self.ids
                and all(b['paper_sha256']==self.paper_sha256 for b in blocks)):
            if self.historical_cache_hits:raise ValueError('Historical case already consumed')
            self.historical_cache_hits+=1
            return dict(self.response,transformations=dict(self.response.get('transformations',{}),
                historical_reply_recovery=self.reference))
        return self.delegate(request)

class ColabStdinTransport:
    def __init__(self,session,remote_code='/content/order-code',environment='/content/order-config-20261102',rotate=True,direct_results=True):
        from colab_cli.state import StateStore
        from colab_cli.runtime import ColabRuntime
        state=StateStore().get(session)
        if state is None or state.accelerator!='A100':raise ValueError('An existing A100 session is required')
        def factory():
            import websocket
            websocket.setdefaulttimeout(10)
            return ColabRuntime(state.url,state.token,session_name=None,history=None,
                                kernel_id=state.kernel_id,session_id=None)
        self._runtime_factory=factory
        def artifact_reader(request_id,directory='order-results'):
            import requests,base64
            from colab_cli.contents import ContentsClient
            connection=ContentsClient(state)
            response=requests.get(connection.base_url+'/api/contents/content/'+directory+'/'+request_id+'.json',
                params={'authuser':'0','colab-runtime-proxy-token':connection.token,'format':'base64'},timeout=10)
            if response.status_code==404:return None
            response.raise_for_status();value=response.json()
            raw=base64.b64decode(value['content']) if value['format']=='base64' else value['content'].encode()
            result=json.loads(raw);result['artifact_sha256']=hashlib.sha256(raw).hexdigest()
            return result
        self._result_reader=artifact_reader
        self._receipt_reader=lambda key:artifact_reader(key,'order-receipts')
        self.runtime=None
        self.remote_code,self.environment=remote_code,environment
        self._failed=False
        self.rotate=rotate
        self.direct_results=direct_results

    def _ensure_runtime(self):
        if self.runtime is None:
            self.runtime=self._runtime_factory();self._opened=time.monotonic();self._confirmed=0

    def _run_code(self,code,timeout):
        self._ensure_runtime()
        kernel=getattr(self.runtime,'kernel_client',None)
        client=getattr(getattr(kernel,'_manager',None),'client',None)
        event=getattr(client,'_message_received',None)
        if event is not None and not isinstance(event,PollingSignal):client._message_received=PollingSignal(event)
        return self.runtime.execute_code(code,allow_stdin=False,timeout=timeout,output_hook=lambda output:None)

    @staticmethod
    def _decode(outputs,request_id):
        if any(o.get('output_type')=='error' for o in outputs):raise RuntimeError('Remote bridge error')
        for line in ''.join(o.get('text','') for o in outputs).splitlines():
            if line.startswith('ORDER_RESULT:'):
                value=json.loads(line[len('ORDER_RESULT:'):])
                if value['request_id']!=request_id:raise ValueError('Mismatched response identity')
                return value['response']
        raise RuntimeError('No confirmed worker result')

    def _register(self,setup):
        # Only static bootstrap is retried; no source request has been sent.
        ready_id=uuid.uuid4().hex
        setup+= "\nimport json\nfrom pathlib import Path\n_order_out=Path('/content/order-results');_order_out.mkdir(exist_ok=True)\n(_order_out/"+repr(ready_id+'.json')+").write_text(json.dumps(dict(request_id="+repr(ready_id)+",response={'status':'READY'})))\n"
        for attempt in range(3):
            try:
                if getattr(self,'direct_results',False):
                    self._submit_code(setup)
                    ready,_=self._wait_api(ready_id,30)
                    if ready.get('status')!='READY':raise RuntimeError('Comm setup not confirmed')
                else:
                    ready=self._run_code(setup,30)
                    if not any('ORDER_COMM_READY' in o.get('text','') for o in ready):raise RuntimeError('Comm setup not confirmed')
                self._comm_ready=True;return
            except Exception:
                reader=getattr(self,'_result_reader',None)
                if reader is not None:
                    try:
                        value=reader(ready_id)
                        client=self.runtime.kernel_client._manager.client
                        alive=getattr(client,'connection_ready',None)
                        if (value and value['request_id']==ready_id and value['response'].get('status')=='READY'
                                and (alive is None or alive.is_set())):
                            self._comm_ready=True;return
                    except Exception:pass
                self._disconnect();self._comm_ready=False
                if attempt==2:raise
                self.bootstrap_retries=getattr(self,'bootstrap_retries',0)+1

    def _recover_cached(self,request_id,timeout=30):
        # Query only. Never call handle(), forward inputs, or recreate a bridge.
        self._comm_ready=False
        reader=getattr(self,'_result_reader',None);artifact_sha=None
        if reader is not None:
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                try:
                    value=reader(request_id)
                    if value is not None:
                        if value['request_id']!=request_id:raise ValueError('Mismatched API result identity')
                        result=value['response'];artifact_sha=value['artifact_sha256'];break
                except ValueError:raise
                except Exception:pass
                time.sleep(.25)
            else:raise TimeoutError('No committed result received through API')
        else:
            result=self._query_kernel_cache(request_id)
        result=dict(result)
        result['transformations']=dict(result.get('transformations',{}),
            transport_reply_recovery=dict(kind='authenticated_result_api' if reader else 'kernel_completed_cache',
                                          request_id=request_id,sha256=artifact_sha))
        self.recovered_cached=getattr(self,'recovered_cached',0)+1
        self._failed=False;self._confirmed=getattr(self,'_confirmed',0)+1
        return result

    def _submit_code(self,code):
        self._ensure_runtime()
        client=self.runtime.kernel_client._manager.client
        client.shell_channel.send(client.session.msg('execute_request',content=dict(code=code,silent=True,
            store_history=False,user_expressions={},allow_stdin=False,stop_on_error=True)))

    def _wait_api(self,request_id,timeout):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                value=self._result_reader(request_id)
                if value is not None:
                    if value['request_id']!=request_id:raise ValueError('Mismatched API result identity')
                    return value['response'],value['artifact_sha256']
            except ValueError:raise
            except Exception:pass
            time.sleep(.1)
        raise TimeoutError('No committed API result')

    def _receipt(self,request_id,payload_hash,stages,timeout=10):
        reader=getattr(self,'_receipt_reader',None)
        if reader is None:return None
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:value=reader(request_id)
            except Exception:value=None
            if value is not None:
                receipt=value['response']
                if value['request_id']!=request_id or receipt.get('input_sha256')!=payload_hash:
                    raise ValueError('Delivery receipt identity differs')
                if receipt.get('stage') in stages:return receipt
            time.sleep(.1)
        raise TimeoutError('No delivery receipt')

    def _query_kernel_cache(self,request_id):
        code="""
import json
_cached=globals().get('_order_bridge')
_reply=_cached.completed.get(REQUEST_ID) if _cached is not None else None
if _reply is not None:print('ORDER_RESULT:'+json.dumps(_reply,allow_nan=False),flush=True)
else:print('ORDER_CACHE_MISS',flush=True)
""".replace('REQUEST_ID',repr(request_id))
        self._comm_ready=False
        return self._decode(self._run_code(code,30),request_id)

    def __call__(self,request):
        self._input_submitted=False
        if request.get('persist_input') is not False:raise ValueError('Only nonpersistent input requests are accepted')
        if getattr(self,'_failed',False):raise TransportError('Transport unavailable; no input resubmitted')
        request_id=request.get('request_id',uuid.uuid4().hex)
        if not isinstance(request_id,str) or len(request_id)!=32 or any(c not in '0123456789abcdef' for c in request_id):
            raise ValueError('Expected a hexadecimal request UUID')
        # Rotate only at an acknowledged boundary. The worker/kernel remain
        # alive; no request is replayed and no pending call is retried.
        if getattr(self,'rotate',True) and self.runtime is not None and getattr(self,'_confirmed',0) and (
                self._confirmed>=20 or time.monotonic()-getattr(self,'_opened',time.monotonic())>=20):
            self._disconnect();self._comm_ready=False
            self.rotations=getattr(self,'rotations',0)+1
        self._ensure_runtime()
        payload=dict(request,request_id=request_id)
        resume=payload.pop('_delivery_resume',False)
        payload_hash=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        json.dumps(payload,allow_nan=False)
        code="""
import json,sys
sys.path.insert(0,REMOTE_CODE)
from reading_order.memory_bridge import KernelBridge
if '_order_bridge' not in globals():
    _order_bridge=KernelBridge(REMOTE_CODE,ENVIRONMENT)
try:
    _completed=getattr(_order_bridge,'completed',{})
    if REQUEST_ID in _completed:
        _order_result=_completed[REQUEST_ID]
    else:
        if '_order_started' not in globals():_order_started=set()
        if REQUEST_ID in _order_started:raise RuntimeError('Started request cannot be replayed')
        _order_request=_order_pending.pop(REQUEST_ID)
        _order_started.add(REQUEST_ID)
        if '_order_receipt' in globals():_order_receipt(REQUEST_ID,'STARTED')
        _order_result=_order_bridge.handle(_order_request)
except Exception as _bridge_error:
    _child=getattr(_order_bridge,'child',None)
    _exit_code=_child.poll() if _child is not None else None
    _order_result=dict(request_id=REQUEST_ID,response=dict(status='FAIL',ordered_ids=None,
        reason='worker_bridge_'+type(_bridge_error).__name__,native=dict(failure_layer='worker_bridge',worker_exit_code=_exit_code)))
    _completed=getattr(_order_bridge,'completed',None)
    if _completed is not None:_completed[REQUEST_ID]=_order_result
    try:_order_bridge.close()
    except Exception:pass
finally:
    if '_order_request' in globals():del _order_request
try:
    from pathlib import Path
    _order_out=Path(RESULT_ROOT);_order_out.mkdir(exist_ok=True)
    _order_temp=_order_out/(REQUEST_ID+'.tmp')
    _order_temp.write_text(json.dumps(_order_result,allow_nan=False))
    _order_temp.replace(_order_out/(REQUEST_ID+'.json'))
    print('ORDER_RESULT:'+json.dumps(_order_result,allow_nan=False),flush=True)
finally:
    pass
""".replace('REMOTE_CODE',repr(self.remote_code)).replace('ENVIRONMENT',repr(self.environment)).replace('REQUEST_ID',repr(request_id)).replace('RESULT_ROOT',repr(getattr(self,'result_root','/content/order-results')))
        phase='register_comm'
        try:
            if not getattr(self,'_comm_ready',False):
                self._register(comm_setup())
            phase='submit_comm'
            client=self.runtime.kernel_client._manager.client
            alive=getattr(client,'connection_ready',None)
            if alive is not None and not alive.is_set():raise ConnectionError('Client closed before input submission')
            receipt=None
            if resume and getattr(self,'_receipt_reader',None):
                value=self._receipt_reader(request_id)
                if value is not None:
                    receipt=self._receipt(request_id,payload_hash,{'RECEIVED','STARTED'})
                    cached=self._result_reader(request_id)
                    if cached is not None:
                        return self._recover_cached(request_id,10)
            self._input_submitted=True
            if receipt is None:
                client.shell_channel.send(client.session.msg('comm_open',content=dict(
                    comm_id=request_id,target_name='reading_order_memory',data=payload)))
                self._receipt(request_id,payload_hash,{'RECEIVED','STARTED'})
            phase='execute_bridge'
            deadline=time.monotonic()+request.get('timeout_s',300)+30
            if getattr(self,'direct_results',False):
                self._submit_code(code)
                self._receipt(request_id,payload_hash,{'STARTED'})
                result,digest=self._wait_api(request_id,request.get('timeout_s',300)+30)
                result=dict(result,transformations=dict(result.get('transformations',{}),
                    result_artifact=dict(request_id=request_id,sha256=digest)))
                self._confirmed=getattr(self,'_confirmed',0)+1
                return result
            outputs=self._run_code(code,min(15,request.get('timeout_s',300)+30))
            phase='parse_result'
            result=self._decode(outputs,request_id)
            self._confirmed=getattr(self,'_confirmed',0)+1
            return result
        except Exception as error:
            self.failure=dict(phase=phase,error_type=type(error).__name__)
            self._failed=True
            self._disconnect()
            if phase in ('execute_bridge','parse_result'):
                if getattr(self,'_receipt_reader',None):
                    raise TransportError('Unconfirmed delivery; resume by UUID') from None
                try:return self._recover_cached(request_id,max(.1,deadline-time.monotonic()))
                except Exception:self._disconnect()
            raise TransportError('Transport unavailable; no input resubmitted') from None

    def _disconnect(self):
        runtime,self.runtime=self.runtime,None
        if runtime is None:return
        # Wake the installed websocket client's blocking reader before its
        # stop_channels clears the socket reference. Never shut down the kernel.
        kernel=getattr(runtime,'_kernel_client',None)
        client=getattr(getattr(kernel,'_manager',None),'client',None)
        app=getattr(client,'kernel_socket',None)
        thread=getattr(client,'connection_thread',None)
        if app is not None:
            app.keep_running=False
            socket=getattr(app,'sock',None)
            if socket is not None:
                try:socket.abort()
                except OSError:pass
            if thread is not None:thread.join(timeout=5)
        if hasattr(runtime,'stop'):runtime.stop()

    def close(self):
        runtime=self.runtime or self._runtime_factory()
        try:
            runtime.execute_code("if '_order_bridge' in globals():\n _order_bridge.close()\n",timeout=20,output_hook=lambda output:None)
        finally:
            self.runtime=runtime
            self._disconnect()


class IsolatedColabTransport:
    """Supervise SDK clients outside the controller and source-reader process."""
    def __init__(self,session):
        self.session=session;self._child=None;self._count=0;self._failed=False
        self._api=ColabStdinTransport(session)
        self.batch_size=20
        self.max_client_age_s=20

    def _launch(self):
        import subprocess,sys,os
        from pathlib import Path
        env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]),PYTHONDONTWRITEBYTECODE='1')
        return subprocess.Popen([sys.executable,'-B','-m','reading_order.colab_backend','--session',self.session,'--max-requests',str(self.batch_size)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,env=env)

    def _retire(self):
        child,self._child=self._child,None
        if child is not None:
            if child.poll() is None:child.kill()
            child.wait(timeout=10)
            for name in ('stdin','stdout'):
                stream=getattr(child,name,None)
                if stream is not None:stream.close()
        self._count=0

    def _ensure_child(self):
        from .memory_bridge import exchange
        if (self._child is not None and self._child.poll() is None
                and self._count<getattr(self,'batch_size',20)
                and time.monotonic()-self._child_started<getattr(self,'max_client_age_s',20)):return
        if self._child is not None:
            self._retire();self.rotations=getattr(self,'rotations',0)+1
        for attempt in range(3):
            try:
                self._child=self._launch()
                self._child_started=time.monotonic()
                value=exchange(self._child,dict(kind='bootstrap'),60,lambda:None)
                if value.get('status')!='READY':raise ConnectionError('SDK child bootstrap failed')
                return
            except Exception:
                self._retire()
                if attempt==2:raise
                self.bootstrap_retries=getattr(self,'bootstrap_retries',0)+1

    def __call__(self,request):
        from .memory_bridge import exchange
        if request.get('persist_input') is not False:raise ValueError('Only nonpersistent inputs accepted')
        if self._failed:raise TransportError('Transport unavailable; input not resubmitted')
        request_id=uuid.uuid4().hex;payload=dict(request,request_id=request_id)
        submitted=False;deadline=time.monotonic()+request.get('timeout_s',300)+90
        try:
            for attempt in range(3):
                self._ensure_child()
                submitted=True
                value=exchange(self._child,payload,request.get('timeout_s',300)+60,lambda:None)
                if '_transport_error' in value and value.get('input_submitted') is False:
                    submitted=False;self._retire()
                    if attempt==2:raise ConnectionError('Client never submitted input')
                    self.bootstrap_retries=getattr(self,'bootstrap_retries',0)+1
                    continue
                break
            if value.get('request_id')!=request_id or '_transport_error' in value:
                raise ConnectionError('Unconfirmed SDK child response')
            result=value['response'];self._count+=1
            if 'transport_reply_recovery' in result.get('transformations',{}):
                self.recovered_cached=getattr(self,'recovered_cached',0)+1
                self._count=getattr(self,'batch_size',20)
            return result
        except Exception as error:
            self.failure=dict(phase='sdk_process',error_type=type(error).__name__)
            self._retire()
            if submitted:
                if getattr(self._api,'_receipt_reader',None) is not None:
                    try:
                        result=self._resume_delivery(payload,deadline)
                        self.delivery_recoveries=getattr(self,'delivery_recoveries',0)+1
                        return result
                    except Exception:pass
                try:
                    result=self._api._recover_cached(request_id,max(.1,deadline-time.monotonic()))
                    self.recovered_cached=getattr(self,'recovered_cached',0)+1
                    return result
                except Exception:pass
            self._failed=True
            raise TransportError('SDK process failed; input not resubmitted') from None

    def _resume_delivery(self,payload,deadline):
        """Retry delivery with the same UUID; remote receipts prevent re-inference."""
        from .memory_bridge import exchange
        for attempt in range(3):
            if time.monotonic()>=deadline:break
            try:
                cached=self._api._result_reader(payload['request_id'])
                if cached is not None:
                    self.recovered_cached=getattr(self,'recovered_cached',0)+1
                    return self._api._recover_cached(payload['request_id'],10)
                self._ensure_child()
                value=exchange(self._child,dict(payload,_delivery_resume=True),
                    max(.1,deadline-time.monotonic()),lambda:None)
                if value.get('request_id')!=payload['request_id'] or '_transport_error' in value:
                    raise ConnectionError('Delivery resumption unconfirmed')
                self._count+=1
                result=value['response']
                return dict(result,transformations=dict(result.get('transformations',{}),
                    delivery_recovery=dict(request_id=payload['request_id'],attempts=attempt+1)))
            except Exception:
                self._retire()
        raise TransportError('Delivery could not be confirmed')

    def close(self):self._retire()


def connection_worker():
    """Client-only stdio service; exiting never runs SDK TLS finalizers."""
    import argparse,sys,os,contextlib,io
    parser=argparse.ArgumentParser();parser.add_argument('--session',required=True);parser.add_argument('--max-requests',type=int,default=20);args=parser.parse_args()
    client=ColabStdinTransport(args.session,rotate=False,direct_results=True)
    count=0
    for line in sys.stdin:
        request=json.loads(line)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                if request.get('kind')=='bootstrap':
                    client._register(comm_setup());result=dict(status='READY')
                else:
                    result=dict(request_id=request['request_id'],response=client(request));count+=1
        except Exception as error:
            result=dict(_transport_error=type(error).__name__,request_id=request.get('request_id'),
                        input_submitted=getattr(client,'_input_submitted',False))
        print('ORDER_RESULT:'+json.dumps(result,allow_nan=False),flush=True)
        recovered='transport_reply_recovery' in result.get('response',{}).get('transformations',{})
        if '_transport_error' in result or count>=args.max_requests or recovered:os._exit(0)
    os._exit(0)


if __name__=='__main__':connection_worker()
