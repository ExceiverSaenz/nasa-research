"""Synthetic protocol diagnosis only: no models, PDF or source blocks."""
import sys,traceback
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'code'))
from colab_cli.runtime import ColabRuntime
from colab_cli.state import StateStore
s=StateStore().get('order-stability-20261102')
r=ColabRuntime(s.url,s.token,history=None,session_name=None,kernel_id=s.kernel_id,session_id=s.session_id)
try:
    r.kernel_client.interrupt()
    print('INTERRUPT_SENT',flush=True)
finally:r.stop()
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
from reading_order.colab_backend import ColabStdinTransport
t=ColabStdinTransport('order-stability-20261102')
try:print('PING',t(dict(action='ping',persist_input=False,timeout_s=10)),flush=True)
except Exception as error:print('TRANSPORT_EXCEPTION',type(error).__name__,flush=True)
