"""Observe protocol markers only, without logging request/response bodies."""
import json,sys,time,faulthandler,signal
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'code'))
from colab_cli.runtime import ColabRuntime
original=ColabRuntime.execute_code
session=sys.argv[sys.argv.index('--session')+1]
log=Path(__file__).parent/(session+'-protocol.jsonl')
stack=(Path(__file__).parent/(session+'-stacks.log')).open('a')
faulthandler.enable(file=stack)
faulthandler.register(signal.SIGUSR1,file=stack,all_threads=True)
def record(value):
    with log.open('a') as stream:stream.write(json.dumps(value)+'\n')
def observed(self,*args,**kwargs):
    started=time.monotonic();record(dict(event='start',time=time.time()))
    consumer=kwargs.get('output_hook')
    def progress(value):
        text=value.get('text','')
        record(dict(event='output',elapsed_s=round(time.monotonic()-started,3),
            progress_messages=text.count('ORDER_PROGRESS:'),result_marker='ORDER_RESULT:' in text,
            ready_marker='ORDER_COMM_READY' in text,output_type=value.get('output_type')))
        if consumer:consumer(value)
    kwargs['output_hook']=progress
    try:
        value=original(self,*args,**kwargs)
        record(dict(event='return',elapsed_s=round(time.monotonic()-started,3)));return value
    except Exception as error:
        record(dict(event='error',elapsed_s=round(time.monotonic()-started,3),error_type=type(error).__name__));raise
ColabRuntime.execute_code=observed
from reading_order.collection import main
factory=None
if '--historical-cache' in sys.argv:
    sys.argv.remove('--historical-cache')
    from reading_order.colab_backend import IsolatedColabTransport,CachedCaseTransport
    from reading_order.ingest import Ingestor,LocalReferences
    from reading_order.context import permute
    from reading_order.contracts import require_permutation,identity,ranks_to_ids
    import hashlib
    prior=root/'raw_results/code_results/collection-20261102-r4-continuation/canonical/manifest.json'
    prior_raw=prior.read_bytes();run=json.loads(prior_raw)
    failed=[(i,p) for i,p in enumerate(run['predictions']) if p['status']=='FAIL']
    assert len(failed)==1
    index,pred=failed[0];scope=pred['scope'];assert pred['candidate_id']=='hantian' and pred['reason']=='TransportError'
    frozen=run['input_reference'];row=next(v for v in frozen['documents'] if v['paper_id']==scope['paper_id'])
    pages=[dict(width=p['pdf_width'],height=p['pdf_height'],rotation=p['rotation']) for p in row['pages']]
    doc=Ingestor(LocalReferences(frozen['source_root'])).read(scope['paper_id'],pdf_pages=pages,expected=row)
    ids=permute(doc.eligible(scope['page_idx']),None);assert identity(sorted(ids))==scope['eligible_ids_hash']
    cache=Path(__file__).parent/'pending-recovery-200.json';raw=cache.read_bytes();snapshot=json.loads(raw)
    assert not snapshot['pending'] and snapshot['candidate']=='hantian'
    matches=[(i,v) for i,v in enumerate(snapshot['last_responses']) if set(v['response'].get('ordered_ids',[]))==set(ids)]
    assert len(matches)==1
    cached_index,envelope=matches[0];response=envelope['response']
    require_permutation(response['ordered_ids'],ids)
    assert ranks_to_ids(response['native']['ranks'],ids)==response['ordered_ids']
    reference=dict(path=str(cache),sha256=hashlib.sha256(raw).hexdigest(),json_pointer='/last_responses/'+str(cached_index)+'/response',
        request_id=envelope['request_id'],prior_failure_reference=dict(path=str(prior),sha256=hashlib.sha256(prior_raw).hexdigest(),json_pointer='/predictions/'+str(index)))
    (Path(__file__).parent/'historical-cache-validation.json').write_text(json.dumps(dict(status='PASS',scope=scope,
        source_hashes_verified=True,reference=reference,previous_pass=sum(p['status']=='PASS' for p in run['predictions']),recovered=1),indent=2))
    def factory(session):
        return CachedCaseTransport(IsolatedColabTransport(session),'hantian',doc.pages[scope['page_idx']],doc.paper_sha256,ids,response,reference)
raise SystemExit(main(transport_factory=factory))
