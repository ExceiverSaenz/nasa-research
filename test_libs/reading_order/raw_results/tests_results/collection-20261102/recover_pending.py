"""Recover only derived cached responses/metadata, never source request bodies."""
import json,sys
from pathlib import Path
from colab_cli.state import StateStore
from colab_cli.runtime import ColabRuntime
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'code'))
from reading_order.colab_backend import ColabStdinTransport
s=StateStore().get('order-collection-20261102-r4')
r=ColabRuntime(s.url,s.token,kernel_id=s.kernel_id,session_id=None,history=None,session_name=None)
t=ColabStdinTransport.__new__(ColabStdinTransport);t.runtime=r
code="""
import json,hashlib
b=globals().get('_order_bridge')
pending=[dict(request_id=k,candidate=v.get('candidate_id'),page_idx=v.get('page',{}).get('page_idx'),ids=[i['id'] for i in v.get('blocks',[])]) for k,v in globals().get('_order_pending',{}).items()]
print('ORDER_RECOVERY:'+json.dumps(dict(completed=len(b.completed) if b else 0,candidate=b.candidate if b else None,child_status=b.child.poll() if b and b.child else None,last_responses=list(b.completed.values())[-3:] if b else [],pending=pending)))
"""
try:
    outputs=r.execute_code(code,timeout=20,output_hook=lambda output:None)
    text=''.join(o.get('text','') for o in outputs)
    result=json.loads(next(v.split('ORDER_RECOVERY:',1)[1] for v in text.splitlines() if v.startswith('ORDER_RECOVERY:')))
    (Path(__file__).parent/(sys.argv[1] if len(sys.argv)>1 else 'pending-recovery.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(completed=result['completed'],pending=len(result['pending']),candidate=result['candidate'],child_status=result['child_status'])))
except Exception as error:
    print(json.dumps(dict(status='FAIL',error_type=type(error).__name__)));raise SystemExit(1)
finally:t._disconnect()
