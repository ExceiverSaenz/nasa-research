"""Connection lifecycle only: static print messages, no models or documents."""
import sys,json,time,faulthandler
from pathlib import Path
from colab_cli.state import StateStore
from colab_cli.runtime import ColabRuntime
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'code'))
from reading_order.colab_backend import ColabStdinTransport
base=Path(__file__).parent
stack=(base/'lifecycle-stacks.log').open('a');faulthandler.enable(file=stack)
faulthandler.dump_traceback_later(10,repeat=True,file=stack)
s=StateStore().get('order-collection-20261102-r4')
for i in range(10):
    r=ColabRuntime(s.url,s.token,kernel_id=s.kernel_id,session_id=None,history=None,session_name=None)
    t=ColabStdinTransport.__new__(ColabStdinTransport);t.runtime=r
    for j in range(20):
        print(json.dumps(dict(cycle=i,call=j,phase='execute')),flush=True)
        out=r.execute_code("print('ORDER_LIFECYCLE_OK')",timeout=15,output_hook=lambda output:None)
        assert any('ORDER_LIFECYCLE_OK' in v.get('text','') for v in out)
    print(json.dumps(dict(cycle=i,phase='disconnect')),flush=True)
    t._disconnect()
    print(json.dumps(dict(cycle=i,phase='closed')),flush=True)
print('LIFECYCLE_PASS',flush=True)
