"""Local, append-only integration of completed hybrid-parser runs.

Independent papers execute in bounded spawned processes from this interpreter.
The established reconciliation, classification, capsule and operational functions
run in that order within each process. No model/service/download is started.
"""
import argparse
import html
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime, timezone
import json
import multiprocessing
import os
from pathlib import Path
import re
import sys
import traceback
import uuid
import zipfile

from .common import digest, read_json, write_json
from .storage import resolve_output

STAGES=('reconcile','classify','capsules','integrate')


def now():
    return datetime.now(timezone.utc).isoformat()


def replace_json(path,value):
    path=Path(path)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    write_json(temporary,value)
    os.replace(temporary,path)


def verify_sources(sources):
    for name,sha in sources.items():
        if digest(name)!=sha:
            raise ValueError('Protected input changed: '+name)


def verify_manifests(root):
    """Verify every output/protected-input claim emitted by scientific exports."""
    checked=0
    for manifest in sorted(Path(root).rglob('manifest.json')):
        value=read_json(manifest)
        for rel,sha in value.get('outputs',{}).items():
            path=(manifest.parent/rel).resolve()
            if not path.is_relative_to(manifest.parent.resolve()) or digest(path)!=sha:
                raise ValueError('Output manifest differs: '+str(path))
            checked+=1
        verify_sources(value.get('protected_inputs',{}))
    return checked


def process_document(document,destination,prediction_fn=None,*,runtime_profile='shared'):
    """Execute all maintained scientific stages for one validated document."""
    from .reconciliation.engine import reconcile, VERSION
    from .reconciliation.export import encoded
    from .classification.export_reconciled import export_collection as classify
    from .reading_order.export import export_collection as capsules
    from .operational.pipeline import export_collection as integrate

    destination=Path(destination); destination.mkdir(parents=True,exist_ok=False)
    paper=document['paper_id']; stages=[]; active=None

    def stage(name,action):
        nonlocal active
        active=name; started=now()
        write_json(destination/'stages'/f'{name}.json',dict(stage=name,status='running',started_utc=started))
        result=action()
        replace_json(destination/'stages'/f'{name}.json',dict(stage=name,status='completed',started_utc=started,ended_utc=now()))
        stages.append(name)
        return result

    def reconciliation():
        root=destination/'reconciliation'
        pages=[reconcile(page) for page in document['pages']]
        for before,after in zip(document['pages'],pages):
            records={r['id']:r for r in after['records']}
            if len(records)!=len(before['records']) or any(any(records.get(r['id'],{}).get(k)!=v for k,v in r.items()) for r in before['records']):
                raise ValueError('Native record changed/lost during reconciliation')
        doc=dict(schema_version='autonomous-document/1',rule_version=VERSION,
                 document=document['document'],document_sha256=document['document_sha256'],
                 pages=pages,parser_configuration=document['parser_configuration'],
                 validation='technical_only_semantic_pending')
        # A one-paper collection uses transport slot 1, never a PDF identity.
        # Source ids/hashes remain in native records and the outer run mapping.
        relative='papers/1/document.json'; path=root/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(encoded(doc))
        write_json(root/'summary.json',dict(documents=[dict(paper=1,source_paper_id=paper,data=relative)],
                   physical_pages=len(pages),records=sum(len(p['records']) for p in pages)))
        write_json(root/'manifest.json',dict(protected_inputs=document['source_inputs'],
                   outputs={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*.json')}))
        return doc

    try:
        verify_sources(document['source_inputs'])
        stage('reconcile',reconciliation)
        stage('classify',lambda:classify(destination/'reconciliation',destination/'classification'))
        stage('capsules',lambda:capsules(destination/'classification',destination/'capsules'))
        result=stage('integrate',lambda:integrate(destination/'capsules',destination/'operational',
                      prediction_fn=prediction_fn,runtime_profile=runtime_profile,
                      build_views=all(p.get('render_path') for p in document['pages'])))
        checks=verify_manifests(destination);verify_sources(document['source_inputs'])
        report=dict(paper_id=paper,status='completed',stages=stages,pid=os.getpid(),python=sys.executable,
                    manifest_entries_verified=checks,metrics={k:v for k,v in result.items() if k not in ('documents','code_hashes')},
                    index='operational/index.html',semantic_validation='pending_after_full_mvp')
        write_json(destination/'status.json',report)
        return report
    except BaseException:
        error=traceback.format_exc()
        if active:
            replace_json(destination/'stages'/f'{active}.json',dict(stage=active,status='failed',error=error,ended_utc=now()))
        write_json(destination/'status.json',dict(paper_id=paper,status='failed',failed_stage=active,error=error,
                   outputs_may_be_partial=True,completed_stages=stages))
        raise


def archive_run(root):
    archive=root.with_name(root.name+'.zip');sidecar=root.with_name(root.name+'.zip.sha256')
    partial=archive.with_name(archive.name+'.partial')
    if archive.exists() or sidecar.exists() or partial.exists():raise FileExistsError('Archive destination already exists')
    with zipfile.ZipFile(partial,'x',zipfile.ZIP_DEFLATED) as stream:
        for path in sorted(root.rglob('*')):
            if path.is_symlink():raise ValueError('Refuse symbolic link in run output')
            if path.is_file():stream.write(path,path.relative_to(root).as_posix())
    with zipfile.ZipFile(partial) as stream:
        if stream.testzip() is not None:raise ValueError('Archive CRC verification failed')
    os.replace(partial,archive)
    with sidecar.open('x',encoding='ascii') as stream:stream.write(digest(archive)+'\n')
    return str(archive)


def run_collection(collection,destination,*,max_workers=2,worker=process_document,prediction_fn=None,runtime=None):
    """Coordinator API. CLI additionally validates input/output roots and runtime."""
    destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError(destination)
    if destination.with_name(destination.name+'.zip').exists() or destination.with_name(destination.name+'.zip.sha256').exists():
        raise FileExistsError('Archive destination already exists')
    if type(max_workers) is not int or max_workers<1:raise ValueError('workers must be positive')
    source_run=Path(collection['source_run']).resolve()
    if destination==source_run or destination.is_relative_to(source_run) or source_run.is_relative_to(destination):
        raise ValueError('Reconciliation output must be separate from parser input run')
    documents=collection['documents']; ids=[d['paper_id'] for d in documents]
    if not ids or len(set(x.casefold() for x in ids))!=len(ids) or any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',x) for x in ids):
        raise ValueError('Unique safe paper identities required')
    for source in collection['source_inputs']:
        path=Path(source).resolve()
        if path==destination or destination in path.parents:raise ValueError('Output overlaps protected inputs')
    verify_sources(collection['source_inputs'])
    destination.mkdir(parents=True,exist_ok=False)
    write_json(destination/'inputs.json',collection)
    folders={paper:'papers/p'+str(index).zfill(6) for index,paper in enumerate(ids,1)}
    write_json(destination/'execution-profile.json',dict(schema='hybrid-integration-execution/1',
               source_run=collection['source_run'],initiated_utc=now(),python=sys.executable,
               runtime=runtime,workers=min(max_workers,len(documents)),concurrency='independent_papers',
               stages=list(STAGES),models_executed=False,automatic_retries=False,
               fixture_predictor=prediction_fn is not None,paper_directories=folders,
               transport_id_policy='one-paper stage collections use slot 1; original ids remain in paper_directories and native records'))
    write_json(destination/'status.json',dict(status='running',source_run=collection['source_run']))
    rows={}; pending={}; remaining=iter(documents); error=None
    try:
        with ProcessPoolExecutor(max_workers=min(max_workers,len(documents)),mp_context=multiprocessing.get_context('spawn')) as pool:
            def submit():
                document=next(remaining,None)
                if document is not None:
                    options={'runtime_profile':runtime.get('profile','shared')} if worker is process_document and runtime else {}
                    pending[pool.submit(worker,document,str(destination/folders[document['paper_id']]),prediction_fn,**options)]=document['paper_id']
                    return True
                return False
            for _ in range(min(max_workers,len(documents))):submit()
            while pending:
                done,_=wait(pending,return_when=FIRST_COMPLETED)
                for future in done:
                    paper=pending.pop(future)
                    try:rows[paper]=dict(paper_id=paper,directory=folders[paper],status='completed',result=future.result())
                    except Exception:rows[paper]=dict(paper_id=paper,directory=folders[paper],status='failed',error=traceback.format_exc())
                    with (destination/'events.jsonl').open('a',encoding='utf-8') as stream:
                        stream.write(json.dumps(dict(utc=now(),**rows[paper]),ensure_ascii=False)+'\n')
                    replace_json(destination/'status.json',dict(status='running',papers=list(rows.values())))
                    submit()
        verify_sources(collection['source_inputs'])
    except BaseException:
        error=traceback.format_exc()
    for paper in ids:
        if paper not in rows:rows[paper]=dict(paper_id=paper,status='cancelled')
    completed=all(x['status']=='completed' for x in rows.values()) and error is None
    report=dict(schema='hybrid-integration-run/1',status='completed' if completed else 'failed',
                source_run=collection['source_run'],ended_utc=now(),papers=[rows[x] for x in ids],
                error=error,outputs_may_be_partial=not completed,automatic_retries=False,
                semantic_validation='pending_after_full_mvp',visual_QA=False)
    summary=dict(schema='hybrid-integration-collection/1',status=report['status'],source_run=collection['source_run'],
                 papers=len(ids),completed=sum(row['status']=='completed' for row in rows.values()),
                 failed=sum(row['status']=='failed' for row in rows.values()),documents=report['papers'],
                 semantic_validation='pending_after_full_mvp')
    write_json(destination/'summary.json',summary)
    links=[]
    for row in report['papers']:
        name=html.escape(row['paper_id'])
        result=row.get('result',{})
        if row['status']=='completed' and result.get('index'):
            name='<a href="'+html.escape(row['directory']+'/'+result['index'],quote=True)+'">'+name+'</a>'
        links.append('<li>'+name+' — '+html.escape(row['status'])+'</li>')
    with (destination/'index.html').open('x',encoding='utf-8') as stream:
        stream.write('<!doctype html><html lang="en"><meta charset="utf-8"><title>Integration attempt</title>'
                     '<h1>Integration attempt</h1><p>Technical status: '+html.escape(report['status'])+
                     '. Semantic validation remains pending.</p><ul>'+''.join(links)+'</ul></html>')
    replace_json(destination/'status.json',report)
    def manifest():
        return dict(schema='hybrid-integration-files/1',protected_inputs=collection['source_inputs'],
                    outputs={p.relative_to(destination).as_posix():digest(p) for p in destination.rglob('*') if p.is_file() and p!=destination/'manifest.json'})
    try:
        write_json(destination/'manifest.json',manifest())
        # Per-file manifest is the durable integrity contract; no mandatory ZIP.
    except BaseException:
        report.update(status='failed',outputs_may_be_partial=True,archive_status='failed',error=traceback.format_exc())
        replace_json(destination/'status.json',report)
        summary['status']='failed';replace_json(destination/'summary.json',summary)
        index=destination/'index.html'
        index.write_text(index.read_text(encoding='utf-8').replace('Technical status: completed.','Technical status: failed.'),encoding='utf-8')
        replace_json(destination/'manifest.json',manifest())
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    run=sub.add_parser('run',help='Integrate a completed parser attempt')
    run.add_argument('--parse-run',required=True,type=Path)
    run.add_argument('--paper-id',action='append',help='Native paper identity from a reduced Colab transfer; requires original per-file manifest')
    run.add_argument('--pdf-directory',type=Path,help='Verified R2 PDF download directory in this Colab session')
    run.add_argument('--runtime-profile',choices=('shared','integrator'),default='shared')
    run.add_argument('--output',type=Path,help='Optional run name inside reconciliation_results')
    run.add_argument('--workers',type=int,default=min(4,os.cpu_count() or 1))
    pre=sub.add_parser('preflight',help='Verify local runtime without executing scientific stages')
    pre.add_argument('--runtime-profile',choices=('shared','integrator'),default='shared')
    args=parser.parse_args(argv)
    from .dependencies import preflight
    if args.command=='preflight':
        print(json.dumps(preflight(profile='integrator') if args.runtime_profile=='integrator' else preflight(),ensure_ascii=False,indent=2));return 0
    try:
        output=resolve_output(args.output)
        if args.workers<1:raise ValueError('workers must be positive')
        if output.exists():raise FileExistsError(output)
        runtime=preflight(profile='integrator') if args.runtime_profile=='integrator' else preflight()
        from .hybrid_inputs import load_run
        collection=(load_run(args.parse_run,paper_ids=args.paper_id,pdf_directory=args.pdf_directory)
                    if args.paper_id or args.pdf_directory else load_run(args.parse_run))
        manifest_sha=runtime.get('manifest_sha256')
        source_manifest=collection.get('parser_configuration',{}).get('env_manifest_sha256')
        if (not isinstance(manifest_sha,str) or not re.fullmatch('[a-f0-9]{64}',manifest_sha)
                or not isinstance(source_manifest,str) or not re.fullmatch('[a-f0-9]{64}',source_manifest)
                or (args.runtime_profile=='shared' and source_manifest!=manifest_sha)):
            raise ValueError('Parser and reconciliation must use the same verified shared environment receipt')
        if args.runtime_profile=='integrator':
            runtime=dict(runtime,source_parser_environment_sha256=source_manifest,
                         same_parser_environment=source_manifest==manifest_sha)
        result=run_collection(collection,output,max_workers=args.workers,runtime=runtime)
        print(json.dumps(dict(status=result['status'],output=str(output)),ensure_ascii=False,indent=2))
        return 0 if result['status']=='completed' else 1
    except (ValueError,FileNotFoundError,FileExistsError) as exc:
        parser.error(str(exc))


if __name__=='__main__':
    raise SystemExit(main())
