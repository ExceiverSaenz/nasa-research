"""Stress the delivery protocol with empty synthetic inputs, no paper/model load."""
import json,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'code'))
from reading_order.colab_backend import IsolatedColabTransport
base=Path(__file__).parent;out=base/'live-delivery.json'
if out.exists():raise FileExistsError('Preserve previous protocol evidence')
t=IsolatedColabTransport('order-collection-20261102-r6');started=time.monotonic();completed=0
result=dict(status='RUNNING',requested=120,paper_inputs=0,model_weights_loaded=False)
try:
    for index in range(120):
        value=t(dict(action='predict',candidate_id='transport_probe',blocks=[],page={},persist_input=False,timeout_s=30))
        assert value.get('status','PASS')=='PASS' and value['ordered_ids']==[] and value['native']['empty_scope']
        completed+=1
        result.update(completed=completed,elapsed_s=round(time.monotonic()-started,2),
            client_rotations=getattr(t,'rotations',0),delivery_recoveries=getattr(t,'delivery_recoveries',0))
        out.write_text(json.dumps(result,indent=2))
        if completed%20==0:print(json.dumps(result),flush=True)
    result['status']='PASS'
except Exception as error:
    result.update(status='FAIL',error_type=type(error).__name__,failure=getattr(t,'failure',None))
finally:
    t.close();out.write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
raise SystemExit(0 if result['status']=='PASS' else 1)
