"""One fresh Colab A100, current source snapshot, R2 papers and verified results."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent
EXCLUDED = {'runtime','results','inputs','__pycache__','.git'}


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def source_files(root):
    return sorted(p for p in Path(root).rglob('*') if p.is_file()
                  and p.relative_to(root).parts[0] not in {'runtime','results','inputs'}
                  and not {'__pycache__','.git'}.intersection(p.relative_to(root).parts)
                  and p.suffix != '.pyc')


def candidate(root, path=None, seen=None, *, profile='both'):
    entries={'parser':'parse_system/parsing/unified/requirements.in','integrator':'reconciliation_system/requirements.in','both':'requirements.in'}
    if profile not in entries:raise ValueError('Unknown environment profile')
    path=(path or root/entries[profile]).resolve()
    seen=set() if seen is None else set(seen)
    if path in seen or not path.is_relative_to(root.resolve()):raise ValueError('Unsafe requirements include')
    seen.add(path);lines=[]
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip().startswith(('-r ','--requirement ')):
            lines.append(candidate(root,path.parent/line.strip().split(None,1)[1],seen))
        else:lines.append(line)
    return '\n'.join(lines)+'\n'


def environment_key(root, *, profile='both'):
    root=Path(root)
    inputs={'profile':profile,'candidate':candidate(root,profile=profile)}
    for name in ('setup_environment.py','parse_system/parsing/unified/environment.py',
                 'parse_system/parsing/unified/environment_bundle.py','reconciliation_system/integration/dependencies.py',
                 'reconciliation_system/integration/environment.py'):
        if (root/name).is_file():inputs[name]=digest(root/name)
    return hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()


def inspect_bundle(path, root, *, profile='both'):
    """Read-only validation of an existing archive before any GPU is allocated."""
    sidecar=path.with_name(path.name+'.sha256')
    if not sidecar.is_file() or digest(path)!=sidecar.read_text().split()[0]:
        raise ValueError('Bundle SHA256 missing or different')
    with tarfile.open(path) as archive:
        members={}
        for member in archive.getmembers():
            name=Path(member.name)
            if (member.name in members or name.is_absolute() or '..' in name.parts
                    or '\\' in member.name or ':' in member.name or not member.isfile()):
                raise ValueError('Unsafe bundle member')
            members[member.name]=member
        roots={name.split('/')[0] for name in members}
        if len(roots)!=1:raise ValueError('Expected one bundle root')
        folder=next(iter(roots))
        def raw(name):
            stream=archive.extractfile(members[folder+'/'+name])
            with stream:return stream.read()
        def value(name):return json.loads(raw(name))
        data=value('bundle.json')
        expected_schema='integration-environment-bundle/1' if profile=='integrator' else 'shared-environment-bundle/1'
        if data.get('schema')!=expected_schema:raise ValueError('Unsupported bundle for profile')
        if raw('requirements-candidate.in').decode('utf-8')!=candidate(root,profile=profile):
            raise ValueError('Requirements changed')
        for name,record in data['files'].items():
            content=raw(name)
            if len(content)!=record['bytes'] or hashlib.sha256(content).hexdigest()!=record['sha256']:
                raise ValueError('Bundle member hash differs')
        source_name=data.get('source_receipt','source-environment.json')
        if source_name not in data['files']:raise ValueError('Unverified source receipt')
        source=value(source_name)
        if profile=='integrator':
            from automation.integrator_bundle import validate_source
            validate_source(data,source,raw)
            return dict(path=path,bundle_root=folder,sha256=digest(path),host=data['host'])
        # Use current installer constraints, rather than trusting the old cache filename.
        sys.path.insert(0,str(ROOT/'parse_system'))
        from parsing.unified import environment as env
        from parsing.unified.environment_bundle import require_build,relocate_lock
        if source.get('status')!='imports-validated' or source.get('python')!=env.PYTHON_VERSION:
            raise ValueError('Incompatible source environment')
        for name,expected in env.CANDIDATE.items():
            if source.get('versions',{}).get(name)!=expected:raise ValueError('Current package pin differs: '+name)
        for name,record in source['artifacts'].items():
            content=raw(name)
            if len(content)!=record['bytes'] or hashlib.sha256(content).hexdigest()!=record['sha256']:
                raise ValueError('Source artifact hash differs')
        for name in (data['wheel'],data['build_receipt']):
            if name not in data['files']:raise ValueError('Unverified build artifact')
        build=value(data['build_receipt'])
        require_build(build,Path(data['wheel']).name,hashlib.sha256(raw(data['wheel'])).hexdigest())
        relocate_lock(raw('requirements-complete.lock').decode('utf-8'),data['source_wheel_uri'],
                      'file:///validated-placeholder.whl',build['sha256'])
        return dict(path=path,bundle_root=folder,sha256=digest(path),host=data['host'])


def find_bundle(root, key, *, profile='both'):
    root=Path(root)
    preferred=root/'runtime/colab-bundles'/(key+'.tar.gz')
    candidates=[preferred]+sorted((root/'runtime/colab-bundles').glob('*.tar.gz'),reverse=True)+sorted((root/'runtime/environment-bundles').glob('*.tar.gz'),reverse=True)
    seen=set()
    for path in candidates:
        if path in seen or not path.is_file() or '.pending.' in path.name:continue
        seen.add(path)
        try:return inspect_bundle(path,root,profile=profile)
        except (ValueError,KeyError,IndexError,OSError,tarfile.TarError,json.JSONDecodeError) as error:
            print('Bundle not selected: '+str(path)+' ('+str(error)+')',file=sys.stderr)
    return None


def select_papers(directory, names, all_sic):
    directory=Path(directory)
    selected=[p.name for p in directory.glob('*.pdf')] if all_sic else [n if n.endswith('.pdf') else n+'.pdf' for n in names]
    if not selected or len(set(selected))!=len(selected):raise ValueError('Choose unique papers or --all')
    for name in selected:
        if not re.fullmatch(r'[0-9]+\.pdf',name) or not (directory/name).is_file():raise ValueError('Unknown SiC paper: '+name)
    return sorted(selected,key=lambda n:int(n[:-4])) if all_sic else selected


def verify_result(root, schema='parsing-hybrid-files/2'):
    value=json.loads((root/'manifest.json').read_text())
    if value.get('schema')!=schema:raise ValueError('Unexpected output contract')
    files=value['outputs']
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p != root/'manifest.json'}
    if set(files)!=actual:raise ValueError('Result inventory differs')
    for name,sha in files.items():
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()) or digest(path)!=sha:raise ValueError('Result hash differs: '+name)
    return json.loads((root/'status.json').read_text())


def require_remote_success(output, marker):
    if marker not in output.splitlines():
        raise RuntimeError('Remote phase did not confirm success; inspect existing session, do not retry automatically')


def extract_transport(archive,destination):
    with tarfile.open(archive) as source:
        for member in source.getmembers():
            if not member.isfile() and not member.isdir():raise ValueError('Transport links are forbidden')
            if not (destination/member.name).resolve().is_relative_to(destination.resolve()):raise ValueError('Unsafe transport path')
        source.extractall(destination,filter='data')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('parser','integrator','both'),help='Parser, integrator or both in one session')
    parser.add_argument('--parse-run',type=Path,help='Existing directory inside new_code/results/parse_results (integrator mode)')
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--papers',nargs='+',help='One paper, a group or native ids from the selected parser run')
    group.add_argument('--all',action='store_true',help='All papers from local SiC collection or chosen parser run')
    parser.add_argument('--keep-session',action='store_true',help='Keep session after verified downloads')
    parser.add_argument('--workers',type=int,default=2,help='Concurrent papers during integration')
    parser.add_argument('--plan',action='store_true',help='Read-only selection and fingerprints; no session/transfer')
    args=parser.parse_args(argv)
    if args.workers<1:parser.error('--workers must be positive')
    if args.mode is None:
        if args.papers or args.all or args.plan:args.mode='parser'  # Existing direct commands.
        else:
            choice=input('1. Parser  2. Integrator  3. Parser + integrator: ').strip()
            if choice not in ('1','2','3'):parser.error('Choose 1, 2 or 3')
            args.mode={'1':'parser','2':'integrator','3':'both'}[choice]
    if args.parse_run and args.mode!='integrator':parser.error('--parse-run is only for integrator mode')
    if args.mode=='integrator' and not args.parse_run:
        if args.plan:parser.error('--parse-run is required for integrator mode')
        available=sorted(p.name for p in (ROOT/'results/parse_results').glob('*') if p.is_dir())
        print('Available parser runs: '+', '.join(available))
        args.parse_run=Path(input('Parser run directory/name: ').strip())
    if not args.papers and not args.all:
        if args.plan:parser.error('Specify --papers or --all with --plan')
        choice=input('Papers (12, 1 3 12, or all): ').strip()
        args.all=choice.lower() in ('all','todos');args.papers=[] if args.all else choice.replace(',',' ').split()
    selection=None;source_run=None
    if args.mode=='integrator':
        from automation.selection import select_run
        base=(ROOT/'results/parse_results').resolve()
        source_run=(args.parse_run if args.parse_run.is_absolute() else
                    base/args.parse_run if len(args.parse_run.parts)==1 else args.parse_run).resolve(strict=True)
        if source_run.parent!=base:parser.error('--parse-run must select one directory inside new_code/results/parse_results')
        selection=select_run(source_run,args.papers or [],args.all)
        papers=[p['name'] for p in selection['papers']]
        if len(papers)!=len(set(papers)):raise ValueError('Selected PDFs have ambiguous names for R2')
        # The local originals identify the expected R2 objects, never replace R2.
        for paper in selection['papers']:
            name=paper['name']
            if not re.fullmatch(r'[0-9]+\.pdf',name) or digest(ROOT.parent/'papers/SiC_papers'/name)!=paper['sha256']:
                raise ValueError('R2 reference PDF differs from parser source: '+name)
    else:papers=select_papers(ROOT.parent/'papers/SiC_papers',args.papers or [],args.all)
    key=environment_key(ROOT,profile=args.mode)
    selected_bundle=find_bundle(ROOT,key,profile=args.mode)
    build_bundle=(find_bundle(ROOT,environment_key(ROOT),profile='both')
                  if args.mode=='parser' and selected_bundle is None else None)
    if args.plan:
        print(json.dumps(dict(mode=args.mode,papers=papers,source_run=str(source_run) if source_run else None,
                             paper_ids=selection['paper_ids'] if selection else None,
                             selected_files=len(selection['files'])+1 if selection else None,
                             environment_key=key,gpu='A100',fresh_session=True,
                             environment_action='reuse_bundle' if selected_bundle else 'reuse_build' if build_bundle else 'install_new',
                             build_bundle=str(build_bundle['path']) if build_bundle else None,
                             bundle=str(selected_bundle['path']) if selected_bundle else None),indent=2));return 0
    if sys.platform!='linux' or not shutil.which('colab'):parser.error('Run from Ubuntu/WSL with Colab CLI configured')
    from prepare_papers import read_settings,sign_request
    settings=read_settings(Path.home()/'.config/nasa-research/r2.env')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    session='sic-'+run_id.lower()
    local=ROOT/'runtime/colab-attempts'/run_id;local.mkdir(parents=True,exist_ok=False)
    record=dict(id=run_id,session=session,mode=args.mode,papers=papers,environment_key=key,status='prepared',automatic_retries=False)
    def save():(local/'status.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    save()
    def command(argv,**kw):
        chunks=[]
        print('+ '+' '.join(map(str,argv)),flush=True)
        with (local/'cli.log').open('a',encoding='utf-8') as log:
            process=subprocess.Popen(list(map(str,argv)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,**kw)
            for line in process.stdout:print(line,end='',flush=True);log.write(line);log.flush();chunks.append(line)
            if process.wait():raise RuntimeError('CLI command failed; inspect existing session, do not retry automatically')
        return ''.join(chunks)
    def remote(phase,**values):
        script=local/(phase+'.py')
        payload=dict(phase=phase,run_id=run_id,mode=args.mode,environment_key=key,**values)
        marker='SIC_PHASE_COMPLETED:'+run_id+':'+phase
        script.write_text('import runpy,sys\nsys.argv=["driver",'+repr(json.dumps(payload))+']\n_result=runpy.run_path("/content/new_code/automation/colab_worker.py",run_name="__main__")\nprint('+repr(marker)+')\n')
        require_remote_success(command(['colab','exec','-s',session,'-f',script,'--timeout','14400']),marker)
    def request_papers():
        with tempfile.TemporaryDirectory(prefix='sic-r2-') as private:
            request=Path(private)/'request.json'
            sign_request(ROOT.parent/'papers/SiC_papers',papers,settings,request)
            command(['colab','upload','-s',session,request,'/content/papers-request.json'])
    def download(kind):
        prefix='results' if kind=='parser' else 'integration'
        archive=local/(prefix+'-transport.tar.gz');checksum=local/(prefix+'-transport.sha256')
        command(['colab','download','-s',session,'/content/'+archive.name,archive])
        command(['colab','download','-s',session,'/content/'+checksum.name,checksum])
        if digest(archive)!=checksum.read_text().strip():raise ValueError('Transport hash mismatch')
        staging=local/(kind+'-download');staging.mkdir(exist_ok=False)
        extract_transport(archive,staging)
        source=staging/(kind+'-result')
        status=verify_result(source,'parsing-hybrid-files/2' if kind=='parser' else 'hybrid-integration-files/1')
        destination=ROOT/'results'/('parse_results' if kind=='parser' else 'reconciliation_results')/run_id
        destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():raise FileExistsError(destination)
        source.rename(destination)
        record[kind+'_result_directory']=str(destination);save()
        if status['status']!='completed':raise ValueError(kind+' attempt incomplete; partial backup downloaded')
        record[kind+'_backup_verified']=True;save()
        return status
    cache=ROOT/'runtime/colab-bundles';cache.mkdir(parents=True,exist_ok=True)
    bundle=cache/(key+'.tar.gz');sidecar=bundle.with_name(bundle.name+'.sha256')
    reuse=selected_bundle is not None
    record.update(bundle_source=str(selected_bundle['path']) if reuse else None,
                  environment_action='reuse_bundle' if reuse else 'reuse_build' if build_bundle else 'install_new',
                  build_bundle_source=str(build_bundle['path']) if build_bundle else None);save()
    print('Environment precheck:',args.mode,record['environment_action'],record['bundle_source'] or '',flush=True)
    try:
        code=local/'source.tar.gz';files=source_files(ROOT)
        hashes={p.relative_to(ROOT).as_posix():digest(p) for p in files}
        with tarfile.open(code,'w:gz') as archive:
            for path in files:
                if path.is_symlink():raise ValueError('Source links are forbidden')
                archive.add(path,arcname='new_code/'+path.relative_to(ROOT).as_posix(),recursive=False)
        if any(digest(ROOT/name)!=sha for name,sha in hashes.items()):raise ValueError('Code changed while packaging')
        (local/'source-manifest.json').write_text(json.dumps(hashes,indent=2))
        if selection:
            from automation.selection import package_selection
            package_selection(source_run,selection,local/'parser-source.tar.gz')
            (local/'selection.json').write_text(json.dumps(selection,indent=2))
            record['source_parser_run']=str(source_run);record['selected_paper_ids']=selection['paper_ids'];save()
        command(['colab','new','-s',session,'--gpu','A100']);record['status']='session_created';save()
        command(['colab','upload','-s',session,code,'/content/source.tar.gz'])
        bootstrap=local/'extract.py'
        bootstrap.write_text('import hashlib,tarfile\nfrom pathlib import Path\np=Path("/content/source.tar.gz")\nassert hashlib.sha256(p.read_bytes()).hexdigest()=='+repr(digest(code))+'\nassert not Path("/content/new_code").exists()\nwith tarfile.open(p) as a:a.extractall("/content",filter="data")\n')
        command(['colab','exec','-s',session,'-f',bootstrap])
        transfer_bundle=selected_bundle or build_bundle
        if transfer_bundle:command(['colab','upload','-s',session,transfer_bundle['path'],'/content/environment-bundle.tar.gz'])
        record['status']='preparing';save()
        remote('prepare',reuse=reuse,build_only=build_bundle is not None,
               bundle_sha256=transfer_bundle['sha256'] if transfer_bundle else None,
               bundle_root=transfer_bundle['bundle_root'] if transfer_bundle else None)
        if not reuse:
            pending=cache/(key+'.pending.tar.gz')
            command(['colab','download','-s',session,'/content/new_code/runtime/export-bundle.tar.gz',pending])
            command(['colab','download','-s',session,'/content/new_code/runtime/export-bundle.tar.gz.sha256',sidecar])
            if digest(pending)!=sidecar.read_text().split()[0]:raise ValueError('Environment bundle download differs')
            pending.replace(bundle)
            inspect_bundle(bundle,ROOT,profile=args.mode)
        if args.mode in ('parser','both'):
            request_papers();record['status']='parsing';save()
            remote('parse',papers=papers)
            status=download('parser');record['parser_metrics']=status.get('metrics');save()
        if args.mode=='integrator':
            command(['colab','upload','-s',session,local/'parser-source.tar.gz','/content/parser-source.tar.gz'])
            request_papers()
        if args.mode in ('integrator','both'):
            record['status']='integrating';save()
            remote('integrate',papers=papers,workers=args.workers,selection=selection,
                   source_sha256=digest(local/'parser-source.tar.gz') if selection else None)
            download('integration')
        record['status']='backup_verified';save()
        if not args.keep_session:
            command(['colab','stop','-s',session]);record['session_closed']=True;save()
        print('Verified '+args.mode+' results for '+run_id)
        return 0
    except BaseException as error:
        record.update(status='manual_review',error=type(error).__name__+': '+str(error),session_closed=False);save()
        print('Stopped without retry. Review session '+session+' and '+str(local/'status.json'),file=sys.stderr)
        raise


if __name__=='__main__':
    raise SystemExit(main())
