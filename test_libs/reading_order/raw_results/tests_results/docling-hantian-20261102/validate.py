"""Authorized targeted A100 validation. No collection/confirmation or PDF reads."""
import json,sys,hashlib,subprocess,time
from dataclasses import asdict
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path[:0]=[str(root/'code'),str(root/'analytics')]
from reading_order.preflight import require_test_receipt,require_deployment_code
from reading_order.ingest import Ingestor,LocalReferences
from reading_order.contracts import Block,require_permutation
from reading_order.runner import Runner,all_runs_pass
from reading_order.colab_backend import ColabStdinTransport,MemoryBackend
from reading_order.stability import read_reference,verify_unchanged
from colab_cli.runtime import ColabRuntime

base=Path(__file__).resolve().parent
require_test_receipt(root,base/'offline-final/test-receipt.json')
environment=json.loads((base/'environment-r2/environment.json').read_text())
require_deployment_code(root,environment)
assert environment['session']=='order-docling-hantian-20261102-r2' and environment['accelerator']=='A100'
primary,reference=read_reference(root/'raw_results/code_results/pilot-12-20261102/manifest.json')
old_paths=[root/'raw_results/code_results/stability-12-recovery-20261102-comm'/('permutation-'+str(seed))/'manifest.json' for seed in (1729,1730)]
references=[reference,*[read_reference(path)[1] for path in old_paths]]
frozen=primary['input_reference']
assert [d['paper_id'] for d in frozen['documents']]==['12']
ingestor=Ingestor(LocalReferences(frozen['source_root']));docs=ingestor.resolve(frozen)
output=root/'raw_results/code_results/docling-hantian-validation-20261102'
output.mkdir(parents=True,exist_ok=False)
original=ColabRuntime.execute_code
def observed(self,*args,**kwargs):
    start=time.monotonic()
    def progress(value):
        text=value.get('text','')
        with (base/'protocol-events.jsonl').open('a') as f:
            f.write(json.dumps(dict(elapsed_s=time.monotonic()-start,result_marker='ORDER_RESULT:' in text,
                                   progress_messages=text.count('ORDER_PROGRESS:')))+'\n')
    kwargs['output_hook']=progress
    return original(self,*args,**kwargs)
ColabRuntime.execute_code=observed
transport=ColabStdinTransport(environment['session'])
backend=MemoryBackend(transport,capture_diagnostics=('hantian',))
sample=[asdict(Block(f'synthetic-{i}','0'*64,0,label,[.1,.1+i*.2,.8,.2+i*.2],None,
                    f'synthetic#/pages/0/blocks/{i}',text='test')) for i,label in enumerate(('doc_title','text','image'))]
checks=[]
for candidate in ('docling','hantian'):
    value=backend.predict(candidate,sample,dict(page_idx=0,width=600,height=800,rotation=0),300)
    assert value.get('status','PASS')=='PASS'
    require_permutation(value['ordered_ids'],[b['id'] for b in sample])
    if candidate=='hantian':assert len(value['native']['rank_logits'])==3
    checks.append(dict(candidate_id=candidate,status='PASS'))
(output/'smoke.json').write_text(json.dumps(checks,indent=2))
reports=[];conditions=[]
for name,seed,candidates in [('canonical',None,('docling','hantian')),('permutation-1729',1729,('docling','hantian')),
                            ('permutation-1730',1730,('docling','hantian')),('hantian-repeat',None,('hantian',))]:
    print('Executing '+name+' '+','.join(candidates),flush=True)
    report=Runner(backend,300,seed,candidates=candidates).execute(docs,frozen,output/name)
    report.update(environment=environment,condition=name,primary_reference=reference,diagnostics=['hantian_rank_logits'])
    (output/name/'manifest.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    reports.append(report)
    conditions.append(dict(name=name,seed=seed,candidates=candidates,
        statuses={s:sum(p['status']==s for p in report['predictions']) for s in ('PASS','FAIL','NOT_RUN','UNSUPPORTED')}))
    print(json.dumps(conditions[-1]),flush=True)
ingestor.resolve(frozen);verify_unchanged(references)
summary=dict(status='PASS' if all_runs_pass(reports) else 'INCOMPLETE',environment=environment,conditions=conditions,
             preserved_references=references,confirmation_executed=False,collection_executed=False,
             pdf_reads=0,source_copies=False,session_closed=False)
(output/'summary.json').write_text(json.dumps(summary,indent=2))
transport.close()
if all_runs_pass(reports):
    result=subprocess.run([str(Path.home()/'.local/bin/colab'),'stop','-s',environment['session']],capture_output=True,text=True)
    (output/'close.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0 and 'Session terminated.' in result.stdout
    summary['session_closed']=True
    (output/'summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(dict(status=summary['status'],session_closed=summary['session_closed'])),flush=True)
sys.exit(0 if all_runs_pass(reports) else 1)
