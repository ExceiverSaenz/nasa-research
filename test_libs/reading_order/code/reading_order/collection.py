"""Explicit full-collection execution over original references and memory-only PDFs."""
import argparse
from dataclasses import dataclass,asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from .contracts import CANDIDATES,Block,require_permutation,identity
from .ingest import Ingestor,LocalReferences,portable_reference
from .runner import Runner,all_runs_pass
from .preflight import require_test_receipt,require_deployment_code,production_fingerprint
from .viewer import build_viewer

ROOT=Path(__file__).resolve().parents[2]


def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False))


def release_session(session,output):
    status=dict(session=session,closed=False)
    try:
        result=subprocess.run([str(Path.home()/'.local/bin/colab'),'stop','-s',session],
            capture_output=True,text=True,timeout=45)
        (Path(output)/'close.log').write_text(result.stdout+result.stderr)
        status['closed']=result.returncode==0 and 'Session terminated.' in result.stdout
    except subprocess.TimeoutExpired as error:
        status['error_type']=type(error).__name__
    finally:
        write(Path(output)/'session-status.json',status)
    if not status['closed']:raise RuntimeError('Session close not confirmed')


@dataclass(frozen=True)
class Selection:
    source_root:Path
    paper_ids:list[str]
    timeout_s:int=300
    def __post_init__(self):
        if (not self.paper_ids or len(set(self.paper_ids))!=len(self.paper_ids)
                or any(not isinstance(p,str) or not p.isdigit() for p in self.paper_ids)
                or self.timeout_s<1):raise ValueError('Expected a unique explicit collection')


def load_selection(path):
    value=json.loads(Path(path).read_text())
    return Selection((Path(path).parent/value['source_root']).resolve(),value['paper_ids'],value.get('timeout_s',300))


def validated_reuse(prior,context,allowed_code_changes=()):
    prior=Path(prior);old=json.loads((prior/'run-context.json').read_text())
    permitted={'code/reading_order/colab_backend.py','code/reading_order/collection.py'}
    if not set(allowed_code_changes)<=permitted:raise ValueError('Recovery may only change transport/controller')
    changes={name for name in set(old['code_files'])|set(context['code_files'])
             if old['code_files'].get(name)!=context['code_files'].get(name)}
    if (not changes<=set(allowed_code_changes) or old['input_profile_id']!=context['input_profile_id']
            or old['environment'].get('lock_sha256')!=context['environment'].get('lock_sha256')):
        raise ValueError('Prior collection uses different code, environment or frozen inputs')
    path=prior/'canonical/manifest.json';raw=path.read_bytes();run=json.loads(raw)
    if run['input_profile_id']!=context['input_profile_id']:raise ValueError('Prior manifest identity differs')
    result={};seen=set()
    for i,pred in enumerate(run['predictions']):
        key=(pred['candidate_id'],pred['scope']['paper_id'],pred['scope']['page_idx'])
        if key in seen:raise ValueError('Duplicate prior case')
        seen.add(key)
        if pred['status']=='PASS':result[key]=dict(pred,reused_from=dict(path=portable_reference(path.resolve()),
            sha256=hashlib.sha256(raw).hexdigest(),json_pointer='/predictions/'+str(i)))
    return result


def execute_collection(selection,transport,url_for,output,code_files,environment,resume=None,
        pdf_metadata=None,pdf_metadata_reference=None,allowed_code_changes=()):
    from .colab_backend import MemoryBackend
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    reader=Ingestor(LocalReferences(selection.source_root))
    documents=[reader.read(p) for p in selection.paper_ids]
    inventory=[dict(d.references,paper_sha256=d.paper_sha256,pages=len(d.pages),eligible=sum(b.exclusion is None for b in d.blocks)) for d in documents]
    write(output/'inventory.json',dict(documents=inventory,candidates=list(CANDIDATES),
        expected_predictions=sum(len(d.pages) for d in documents)*len(CANDIDATES),condition='canonical_sha256_id_order'))
    write(output/'state.json',dict(phase='synthetic_smoke',status='RUNNING'))
    backend=MemoryBackend(transport)
    sample=[asdict(Block(f'synthetic-{i}','0'*64,0,label,[.1,.05+i*.2,.8,.15+i*.2],None,
        f'synthetic#/pages/0/blocks/{i}',text='synthetic')) for i,label in enumerate(('doc_title','text','image','index'))]
    smoke=[]
    for candidate in CANDIDATES:
        value=backend.predict(candidate,sample,dict(page_idx=0,width=600,height=800,rotation=0),selection.timeout_s)
        if value.get('status','PASS')!='PASS':raise ValueError('Production adapter smoke failed: '+candidate)
        require_permutation(value['ordered_ids'],[b['id'] for b in sample])
        smoke.append(dict(candidate_id=candidate,status='PASS',transformations=value.get('transformations',{})))
    write(output/'smoke.json',smoke)
    metadata={}
    for d in documents:
        write(output/'state.json',dict(phase='pdf_metadata',paper_id=d.paper_id,verified=len(metadata),status='RUNNING'))
        if pdf_metadata is None:
            value=transport(dict(action='pdf_metadata',persist_input=False,timeout_s=120,
                url=url_for(d.paper_id),sha256=d.paper_sha256))
        else:
            value=pdf_metadata[d.paper_id]
            if value.get('source')!=d.references:raise ValueError('Verified PDF metadata source reference differs')
        if value.get('status')!='PASS' or value.get('sha256')!=d.paper_sha256:
            raise ValueError('R2 PDF identity could not be verified')
        # Validate geometry before the first real ordering request.
        reader.read(d.paper_id,pdf_pages=value['pages'],expected=d.references)
        metadata[d.paper_id]=value['pages']
        write(output/'pdf-metadata.json',metadata)
        print('Verified PDF metadata '+d.paper_id,flush=True)
    with tempfile.TemporaryDirectory(prefix='order-reference-',dir=output) as temp:
        frozen=reader.freeze(selection.paper_ids,Path(temp)/'input',pdf_metadata=metadata)
        # Detect changes between initial inventory and freeze, before inference.
        for expected in inventory:reader.read(expected['paper_id'],expected=expected)
        context=dict(code_files=code_files,input_profile_id=frozen['input_profile_id'],environment=environment,
            pdf_metadata_reference=pdf_metadata_reference,
            allowed_recovery_code_changes=list(allowed_code_changes),
            selection=dict(source_root=portable_reference(selection.source_root),paper_ids=selection.paper_ids,timeout_s=selection.timeout_s),
            candidates=list(CANDIDATES),condition='canonical_sha256_id_order',
            xycut_plus_plus='home-still variant; diverges from paper v1')
        write(output/'run-context.json',context)
        reuse=validated_reuse(resume,context,allowed_code_changes) if resume else {}
        docs=reader.resolve(frozen)
        write(output/'state.json',dict(phase='inference',status='RUNNING',reused=len(reuse)))
        class ObservedBackend:
            def __init__(self):self.completed=len(reuse)
            def predict(self,candidate,blocks,page,timeout):
                result=backend.predict(candidate,blocks,page,timeout)
                self.completed+=1
                if self.completed%20==0:print(json.dumps(dict(completed=self.completed,candidate=candidate)),flush=True)
                return result
        run=Runner(ObservedBackend(),selection.timeout_s,None).execute(docs,frozen,output/'canonical',reuse=reuse)
        reader.resolve(frozen)
    expected=sum(len(d.pages) for d in documents)*len(CANDIDATES)
    if len(run['predictions'])!=expected:raise ValueError('Incomplete result inventory')
    run.update(environment=environment,condition='canonical_sha256_id_order',collection=True,
        candidate_display_names={'xycut_plus_plus':'XY-Cut++ (home-still variant)'},
        config_identity=identity(context),source_input_persistence='none')
    write(output/'canonical/manifest.json',run)
    build_viewer(output/'canonical')
    summary=dict(status='PASS' if all_runs_pass([run]) else 'COMPLETE_WITH_FAILURES',papers=len(documents),
        pages=sum(len(d.pages) for d in documents),expected=expected,reused=len(reuse),
        per_candidate=[dict(candidate_id=c,expected=sum(len(d.pages) for d in documents),
            statuses={s:sum(p['candidate_id']==c and p['status']==s for p in run['predictions']) for s in ('PASS','FAIL','UNSUPPORTED','NOT_RUN')}) for c in CANDIDATES],
        source_copies=False,source_hashes_verified=True,pdf_persistence='memory_only',
        stability_permutations_executed=False,client_rotations=getattr(transport,'rotations',0),
        cached_replies_recovered=getattr(transport,'recovered_cached',0),historical_cached_results=getattr(transport,'historical_cache_hits',0),
        bootstrap_retries=getattr(transport,'bootstrap_retries',0),selection='selection_pending')
    summary['delivery_recoveries']=getattr(transport,'delivery_recoveries',0)
    write(output/'summary.json',summary);write(output/'state.json',dict(phase='results_recovered',status=summary['status']))
    return summary


def main(argv=None,transport_factory=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection',type=Path,default=ROOT/'code/config/collection.json')
    parser.add_argument('--session',required=True)
    parser.add_argument('--environment-receipt',type=Path,required=True)
    parser.add_argument('--test-receipt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--resume',type=Path)
    parser.add_argument('--pdf-metadata-receipt',type=Path)
    parser.add_argument('--resume-transport-update',action='store_true')
    args=parser.parse_args(argv)
    if args.output.exists():raise FileExistsError('Collection output already exists')
    if args.resume_transport_update and not args.resume:raise ValueError('Explicit transport recovery requires a prior run')
    require_test_receipt(ROOT,args.test_receipt)
    environment=json.loads(args.environment_receipt.read_text());require_deployment_code(ROOT,environment)
    if environment['session']!=args.session or environment['status']!='prepared' or environment['accelerator']!='A100':
        raise ValueError('Expected the prepared A100')
    selection=load_selection(args.selection)
    verified=None;metadata_reference=None
    if args.pdf_metadata_receipt:
        raw=args.pdf_metadata_receipt.read_bytes();receipt=json.loads(raw)
        if receipt.get('status')!='PASS' or set(receipt['documents'])!=set(selection.paper_ids):
            raise ValueError('PDF metadata receipt is not a complete verified collection')
        verified=receipt['documents']
        metadata_reference=dict(path=portable_reference(args.pdf_metadata_receipt.resolve()),sha256=hashlib.sha256(raw).hexdigest())
    from .colab_backend import IsolatedColabTransport
    sys.path.insert(0,str(ROOT.parents[1]/'new_code'))
    from prepare_papers import read_settings,presign
    settings=read_settings(Path.home()/'.config/nasa-research/r2.env')
    def url_for(paper):return presign(settings,settings['R2_PREFIX'].strip('/')+'/'+paper+'.pdf',600)
    transport=(transport_factory or IsolatedColabTransport)(args.session)
    summary=None
    try:
        summary=execute_collection(selection,transport,url_for,args.output,production_fingerprint(ROOT),environment,args.resume,
            pdf_metadata=verified,pdf_metadata_reference=metadata_reference,
            allowed_code_changes=('code/reading_order/colab_backend.py','code/reading_order/collection.py') if args.resume_transport_update else ())
        sys.path.insert(0,str(ROOT/'analytics'))
        from compare_orders import analyze_run
        analyze_run(args.output/'canonical',args.output/'agreement')
    except Exception as error:
        if args.output.is_dir():write(args.output/'failure.json',dict(status='FAIL',error_type=type(error).__name__,
            transport_failure=getattr(transport,'failure',None),automatic_retry=False))
        print(json.dumps(dict(status='FAIL',error_type=type(error).__name__,automatic_retry=False)),flush=True)
        return 1
    finally:
        try:transport.close()
        except Exception:pass
        # All recoverable outputs are local before releasing this owned VM.
        release_session(args.session,args.output)
    print(json.dumps(summary),flush=True)
    return 0 if summary['status']=='PASS' else 1
