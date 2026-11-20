import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
from .contracts import CANDIDATES,InputDocument,Block,identity,load_experiment,require_permutation
from .ingest import Ingestor,LocalReferences,portable_reference
from .preflight import code_fingerprint,require_test_receipt,require_deployment_code

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT.parents[1]


def stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]


def write(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Reading-order comparison on fixed MinerU references')
    parser.add_argument('action',choices=('inspect','verify','prepare','freeze','run','resume-stability','compare','build-viewer','serve','summarize'))
    parser.add_argument('--experiment',type=Path,default=ROOT/'code/config/experiment.json')
    parser.add_argument('--session')
    parser.add_argument('--environment-receipt',type=Path)
    parser.add_argument('--resume-attempt',type=Path,help='Reuse additional confirmed stability results by hash')
    parser.add_argument('--test-receipt',type=Path)
    parser.add_argument('--run',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--metadata',type=Path,help='Verified PDF metadata receipt for freeze; PDFs are not copied')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--revision',type=int)
    parser.add_argument('--keep-session',action='store_true')
    args = parser.parse_args(argv)
    exp = load_experiment(args.experiment)
    ingestor = Ingestor(LocalReferences(exp.source_root))
    try:
        if args.action=='inspect':
            docs = [ingestor.read(p) for p in exp.pilot_document_ids]
            print(json.dumps([dict(paper_id=d.paper_id,pages=len(d.pages),entities=len(d.blocks),
                             eligible=sum(b.exclusion is None for b in d.blocks),pdf_rotation_verified=False) for d in docs]))
            return 0
        if args.action=='verify':
            output = args.output or ROOT/'raw_results/tests_results'/('code-'+stamp())
            output.mkdir(parents=True,exist_ok=False)
            print('Output: '+str(output),flush=True)
            command = [sys.executable,'-B','-m','pytest',str(ROOT/'test'),'-q','-p','no:cacheprovider',
                       '--basetemp',str(output/'tmp'),'--junitxml',str(output/'tests.xml')]
            with (output/'pytest.log').open('w') as stream:
                result = subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
            write(output/'test-receipt.json',dict(status='PASS' if result.returncode==0 else 'FAIL',
                                                 command=command,code_files=code_fingerprint(ROOT)))
            print((output/'pytest.log').read_text()[-2500:])
            return result.returncode
        if args.action=='prepare':
            if not args.test_receipt or not args.session:
                raise ValueError('prepare requires --test-receipt and an explicit --session name')
            require_test_receipt(ROOT,args.test_receipt)
            from .deployment import ColabController
            output = args.output or ROOT/'raw_results/tests_results'/('environment-'+stamp())
            print('Output: '+str(output),flush=True)
            print(json.dumps(ColabController(PROJECT,output,args.session).prepare()))
            return 0
        if args.action=='freeze':
            if not args.output or not args.metadata:
                raise ValueError('freeze requires explicit --output and verified --metadata')
            print('Output: '+str(args.output),flush=True)
            metadata = json.loads(args.metadata.read_text())
            print(json.dumps(ingestor.freeze(exp.pilot_document_ids,args.output,pdf_metadata=metadata)))
            return 0
        if args.action=='run':
            if not args.session or not args.environment_receipt or not args.test_receipt:
                raise ValueError('run requires session, environment receipt and current passing test receipt')
            require_test_receipt(ROOT,args.test_receipt)
            environment = json.loads(args.environment_receipt.read_text())
            if environment['session']!=args.session or environment['status']!='prepared' or environment['accelerator']!='A100':
                raise ValueError('Environment receipt does not identify this A100')
            require_deployment_code(ROOT,environment)
            from .colab_backend import ColabStdinTransport,MemoryBackend
            from .runner import Runner,all_runs_pass
            from .viewer import build_viewer
            sys.path.insert(0,str(ROOT/'analytics'))
            from compare_orders import analyze_run
            backend_transport = ColabStdinTransport(args.session)
            backend = MemoryBackend(backend_transport)
            output = args.output or ROOT/'raw_results/code_results'/('pilot-'+stamp())
            print('Output: '+str(output),flush=True)
            # Smoke production adapters before any real PDF request.
            sample = [asdict(Block(f'synthetic-{i}','0'*64,0,label,[.1,.1+i*.2,.8,.2+i*.2],None,f'synthetic#/pages/0/blocks/{i}',text='test'))
                      for i,label in enumerate(('doc_title','text','image'))]
            smoke = []
            for candidate in CANDIDATES:
                value = backend.predict(candidate,sample,dict(page_idx=0,width=600,height=800,rotation=0),exp.timeout_s)
                if value.get('status','PASS')!='PASS':
                    raise ValueError('Production adapter smoke failed: '+candidate+':'+value.get('reason','unknown'))
                require_permutation(value['ordered_ids'],[b['id'] for b in sample])
                smoke.append(dict(candidate_id=candidate,status='PASS',native=value['native']))
            smoke_output = ROOT/'raw_results/tests_results'/('adapter-smoke-'+stamp())
            smoke_output.mkdir(parents=True,exist_ok=False)
            write(smoke_output/'smoke.json',dict(checks=smoke,environment=environment,code_files=code_fingerprint(ROOT)))
            # Reuse the existing R2 signer, never its disk-download operation.
            sys.path.insert(0,str(PROJECT/'new_code'))
            from prepare_papers import read_settings,presign
            settings = read_settings(Path.home()/'.config/nasa-research/r2.env')
            metadata = {}
            for paper in exp.pilot_document_ids:
                doc = ingestor.read(paper)
                key = settings['R2_PREFIX'].strip('/')+'/'+paper+'.pdf'
                result = backend_transport(dict(action='pdf_metadata',persist_input=False,timeout_s=120,
                    url=presign(settings,key,600),sha256=doc.paper_sha256))
                if result.get('status')!='PASS' or result['sha256']!=doc.paper_sha256:
                    raise ValueError('R2 PDF metadata verification failed')
                metadata[paper] = result['pages']
            with tempfile.TemporaryDirectory(prefix='order-references-') as temp:
                frozen = ingestor.freeze(exp.pilot_document_ids,Path(temp)/'input',pdf_metadata=metadata)
                docs = ingestor.resolve(frozen)
                report = Runner(backend,exp.timeout_s,None).execute(docs,frozen,output)
                # Stability conditions are separate runs over the same frozen references.
                stability = []
                reports = [report]
                for seed in (exp.seed,exp.seed+1):
                    target = output.with_name(output.name+'-permutation-'+str(seed))
                    variant = Runner(backend,exp.timeout_s,seed).execute(docs,frozen,target)
                    variant.update(environment=environment,condition='input_permutation_stability')
                    reports.append(variant)
                    write(target/'manifest.json',variant)
                    stability.append(dict(seed=seed,run_id=target.name,
                        statuses={s:sum(p['status']==s for p in variant['predictions']) for s in ('PASS','FAIL','UNSUPPORTED','NOT_RUN')}))
                ingestor.resolve(frozen)  # Originals must still have their frozen hashes after inference.
            report.update(environment=environment,experiment=asdict(exp)|{'source_root':portable_reference(exp.source_root)},
                          adapter_smoke_reference=portable_reference(smoke_output),source_input_persistence='none',
                          stability_runs=stability,condition='canonical_sha256_id_order',
                          requested_runs_complete=all_runs_pass(reports))
            write(output/'manifest.json',report)
            build_viewer(output)
            analyze_run(output,ROOT/'raw_results/analytics_results'/('agreement-'+stamp()))
            backend_transport.close()
            close_session = not args.keep_session and all_runs_pass(reports)
            if close_session:
                close = subprocess.run([str(Path.home()/'.local/bin/colab'),'stop','-s',args.session],capture_output=True,text=True)
                (output/'close.log').write_text(close.stdout+close.stderr)
                if close.returncode:
                    raise RuntimeError('Output recovered but session close not confirmed')
            print(json.dumps(dict(run_id=report['run_id'],predictions=len(report['predictions']),
                                  statuses={s:sum(p['status']==s for p in report['predictions']) for s in ('PASS','FAIL','UNSUPPORTED','NOT_RUN')},
                                  session_closed=close_session,requested_runs_complete=all_runs_pass(reports))))
            return 0 if all_runs_pass(reports) else 1
        if args.action=='resume-stability':
            if not all((args.run,args.output,args.session,args.test_receipt,args.environment_receipt)):
                raise ValueError('Continuation requires primary run, output, session and both receipts')
            require_test_receipt(ROOT,args.test_receipt)
            environment=json.loads(args.environment_receipt.read_text())
            if environment['session']!=args.session or environment['accelerator']!='A100' or environment['status']!='prepared':
                raise ValueError('Expected the prepared A100')
            require_deployment_code(ROOT,environment)
            from .stability import stability_inputs,verify_unchanged
            from .runner import Runner,all_runs_pass
            from .colab_backend import MemoryBackend,ColabStdinTransport
            primary,primary_ref,conditions=stability_inputs(args.run/'manifest.json',args.resume_attempt)
            frozen=primary['input_reference']
            docs=Ingestor(LocalReferences(frozen['source_root'])).resolve(frozen)
            references=[primary_ref,*[c['reference'] for c in conditions],
                        *[ref for c in conditions for ref in c['additional_references']]]
            args.output.mkdir(parents=True,exist_ok=False)
            transport=ColabStdinTransport(args.session)
            backend=MemoryBackend(transport)
            sample=[asdict(Block(f'synthetic-{i}','0'*64,0,label,[.1,.1+i*.2,.8,.2+i*.2],None,f'synthetic#/pages/0/blocks/{i}',text='test'))
                    for i,label in enumerate(('doc_title','text','image'))]
            checks=[]
            for candidate in CANDIDATES:
                value=backend.predict(candidate,sample,dict(page_idx=0,width=600,height=800,rotation=0),exp.timeout_s)
                if value.get('status','PASS')!='PASS':raise ValueError('Adapter smoke failed')
                require_permutation(value['ordered_ids'],[b['id'] for b in sample])
                checks.append(dict(candidate_id=candidate,status='PASS'))
            write(args.output/'smoke.json',dict(checks=checks,environment=environment))
            reports=[]
            sys.path.insert(0,str(ROOT/'analytics'))
            from compare_orders import analyze_run
            for condition in conditions:
                target=args.output/('permutation-'+str(condition['seed']))
                print('Continuing seed '+str(condition['seed'])+'; reused '+str(len(condition['reuse'])),flush=True)
                report=Runner(backend,exp.timeout_s,condition['seed']).execute(docs,frozen,target,reuse=condition['reuse'])
                report.update(environment=environment,condition='input_permutation_stability',
                    continuation_of=condition['reference'],primary_reference=primary_ref,
                    additional_references=condition['additional_references'],
                    reused_predictions=len(condition['reuse']),new_predictions=78-len(condition['reuse']))
                write(target/'manifest.json',report)
                analyze_run(target,args.output/('agreement-'+str(condition['seed'])))
                reports.append(report)
            Ingestor(LocalReferences(frozen['source_root'])).resolve(frozen)
            verify_unchanged(references)
            summary=dict(status='PASS' if all_runs_pass(reports) else 'INCOMPLETE',primary_reference=primary_ref,
                         primary_unchanged=True,confirmation_executed=False,pdf_reads=0,source_input_persistence='none',
                         environment=environment,conditions=[dict(seed=c['seed'],reused=len(c['reuse']),
                         statuses={s:sum(p['status']==s for p in r['predictions']) for s in ('PASS','FAIL','UNSUPPORTED','NOT_RUN')})
                         for c,r in zip(conditions,reports)])
            write(args.output/'summary.json',summary)
            transport.close()
            if all_runs_pass(reports) and not args.keep_session:
                close=subprocess.run([str(Path.home()/'.local/bin/colab'),'stop','-s',args.session],capture_output=True,text=True)
                (args.output/'close.log').write_text(close.stdout+close.stderr)
                if close.returncode:raise RuntimeError('Session close not confirmed')
                summary['session_closed']=True;write(args.output/'summary.json',summary)
            print(json.dumps(dict(status=summary['status'],conditions=summary['conditions'])),flush=True)
            return 0 if all_runs_pass(reports) else 1
        if not args.run:
            raise ValueError('This action requires --run')
        if args.action=='serve':
            from .server import serve
            serve(args.run,port=args.port)
        elif args.action=='build-viewer':
            from .viewer import build_viewer
            print(json.dumps(build_viewer(args.run)))
        else:
            sys.path.insert(0,str(ROOT/'analytics'))
            if not args.output:
                raise ValueError('Analysis requires explicit --output')
            print('Output: '+str(args.output),flush=True)
            if args.action=='compare':
                from compare_orders import analyze_run
                analyze_run(args.run,args.output)
            else:
                from summarize_reviews import summarize_reviews
                if args.revision is None:
                    raise ValueError('Summary requires an explicit review revision')
                summarize_reviews(args.run,args.revision,args.output)
        return 0
    except Exception as error:
        # Never leak bearer URLs from transports or credentials from upstream exceptions.
        print(json.dumps(dict(status='FAIL',error_type=type(error).__name__,
                              phase=args.action,session=args.session,automatic_retry=False)),file=sys.stderr)
        return 1
