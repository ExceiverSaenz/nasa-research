import json,sys,traceback
from pathlib import Path
from dataclasses import asdict
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'code'))
from colab_cli.runtime import ColabRuntime
original=ColabRuntime.execute_code
def observed(self,*a,**kw):
    try:
        outputs=original(self,*a,**kw)
        print('OUTPUT_TYPES',[(o.get('output_type'),o.get('ename')) for o in outputs],flush=True)
        for o in outputs:
            if o.get('output_type')=='error':print('REMOTE_ERROR',o.get('evalue'),flush=True)
        return outputs
    except Exception as error:
        print('CLIENT_EXCEPTION',type(error).__name__,[(f.name,f.lineno) for f in traceback.extract_tb(error.__traceback__)],flush=True)
        raise
ColabRuntime.execute_code=observed
from reading_order.colab_backend import ColabStdinTransport,MemoryBackend
from reading_order.contracts import Block
from reading_order.contracts import CANDIDATES
t=ColabStdinTransport('order-stability-20261102')
if '--unique' in sys.argv:
    from colab_cli.state import StateStore
    s=StateStore().get('order-stability-20261102')
    t._runtime_factory=lambda:ColabRuntime(s.url,s.token,history=None,session_name=None,kernel_id=s.kernel_id,session_id=None)
blocks=[asdict(Block(f'synthetic-{i}','0'*64,0,label,[.1,.1+i*.2,.8,.2+i*.2],None,'synthetic',text='test')) for i,label in enumerate(('doc_title','text','image'))]
try:
    for candidate in CANDIDATES:
        print('CANDIDATE',candidate,flush=True)
        result=MemoryBackend(t).predict(candidate,blocks,dict(page_idx=0,width=600,height=800,rotation=0),60)
        print(dict(status=result.get('status','PASS'),ids=result.get('ordered_ids'),reason=result.get('reason')),flush=True)
except Exception as error:print('TRANSPORT_EXCEPTION',type(error).__name__,flush=True)
