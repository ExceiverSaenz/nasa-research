"""Synthetic connection-only comparison; no models, PDFs or source payloads."""
import json,sys,time,traceback
from pathlib import Path
from colab_cli.state import StateStore
from colab_cli.runtime import ColabRuntime
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'code'))
from reading_order.colab_backend import ColabStdinTransport
mode=sys.argv[1];s=StateStore().get('order-collection-20261102-r3')
r=ColabRuntime(s.url,s.token,history=None,session_name=None,kernel_id=s.kernel_id,session_id=s.session_id if mode=='saved' else None)
t=ColabStdinTransport.__new__(ColabStdinTransport);t.runtime=r
started=time.monotonic();result=dict(mode=mode,saved_kernel_present=bool(s.kernel_id),saved_session_present=bool(s.session_id))
try:
    outputs=r.execute_code("print('ORDER_CONNECTION_OK')",timeout=15,output_hook=lambda value:None)
    result['status']='PASS' if any('ORDER_CONNECTION_OK' in o.get('text','') for o in outputs) else 'FAIL'
except Exception as error:
    result.update(status='FAIL',error_type=type(error).__name__,frames=[dict(function=f.name,line=f.lineno,file=Path(f.filename).name) for f in traceback.extract_tb(error.__traceback__)])
finally:
    result['elapsed_s']=time.monotonic()-started
    print(json.dumps(result),flush=True)
    with (Path(__file__).parent/'connection-probes.jsonl').open('a') as stream:stream.write(json.dumps(result)+'\n')
    t._disconnect()
