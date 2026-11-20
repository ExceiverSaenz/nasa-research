"""Read kernel request state through a durable output; no model execution."""
import json,sys,uuid,os
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'code'))
from reading_order.colab_backend import ColabStdinTransport
t=ColabStdinTransport('order-collection-20261102-r6',rotate=False,direct_results=True)
key=uuid.uuid4().hex
code="""
import json
from pathlib import Path
b=globals().get('_order_bridge')
pending=[dict(request_id=k,candidate=v.get('candidate_id'),page_idx=v.get('page',{}).get('page_idx'),ids=[i['id'] for i in v.get('blocks',[])]) for k,v in globals().get('_order_pending',{}).items()]
report=dict(bridge_exists=b is not None,candidate=b.candidate if b else None,child_status=b.child.poll() if b and b.child else None,
 completed=len(b.completed) if b else 0,last_responses=list(b.completed.values())[-3:] if b else [],pending=pending)
p=Path('/content/order-results')/KEY
p.write_text(json.dumps(dict(request_id=REQUEST,response=report)))
""".replace('KEY',repr(key+'.json')).replace('REQUEST',repr(key))
try:
    t._register("print('ORDER_COMM_READY')")
    for attempt in range(3):
        t._submit_code(code)
        try:
            result,digest=t._wait_api(key,15);break
        except TimeoutError:
            if attempt==2:raise
    (Path(__file__).parent/'pending-r6.json').write_text(json.dumps(dict(result=result,artifact_sha256=digest),indent=2))
    print(json.dumps(dict(status='PASS',candidate=result['candidate'],completed=result['completed'],pending=len(result['pending']),child_status=result['child_status'])),flush=True)
except Exception as error:print(json.dumps(dict(status='FAIL',error_type=type(error).__name__)),flush=True)
os._exit(0)
