"""Remote phases invoked by colab_run.py in a newly-created A100 session."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT=Path('/content/new_code')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def bundle_input_root(runtime, name):
    root=(Path(runtime)/'bundle-inputs').resolve()
    path=(root/name).resolve()
    if path.parent!=root or not name or '/' in name or '\\' in name:raise ValueError('Unsafe bundle root')
    return path


def main(payload):
    import fcntl
    runtime=ROOT/'runtime';runtime.mkdir(exist_ok=True)
    with (runtime/'.colab-workflow.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        profile=payload.get('mode','both')
        if profile not in ('parser','integrator','both'):raise ValueError('Unknown workflow profile')
        previous_profile=os.environ.get('NASA_ENV_PROFILE')
        phase=payload['phase'];receipt=runtime/(phase+'-phase.json')
        if receipt.exists():raise RuntimeError('Phase already attempted; inspect its receipt instead of retrying')
        os.environ['NASA_ENV_PROFILE']=profile
        status=dict(status='running',phase=phase,run_id=payload['run_id'])
        receipt.write_text(json.dumps(status))
        def run(args,check=True):
            print('+ '+' '.join(map(str,args)),flush=True)
            with (runtime/'workflow.log').open('a') as log:
                process=subprocess.Popen(list(map(str,args)),cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                for line in process.stdout:print(line,end='',flush=True);log.write(line);log.flush()
                code=process.wait()
                if check and code:raise RuntimeError('Stage exited with code '+str(code))
                return code
        try:
            env=runtime/'environment';python=env/'.venv/bin/python'
            if phase in ('prepare','prepare-continuation'):
                gpu='' if profile=='integrator' else subprocess.check_output(['nvidia-smi','--query-gpu=name','--format=csv,noheader'],text=True)
                if profile!='integrator' and 'A100' not in gpu:raise RuntimeError('Expected A100 GPU')
                args=['python3','-u','-B','setup_environment.py','--destination',env,'--profile',profile]
                if (payload['reuse'] or payload.get('build_only')) and not (env/'environment.json').exists():
                    bundle=(ROOT.parent/'environment-bundle.tar.gz')
                    if sha(bundle)!=payload['bundle_sha256']:raise ValueError('Bundle upload hash mismatch')
                    bundle_root=bundle_input_root(runtime,payload['bundle_root'])
                    if bundle_root.exists():
                        if profile=='integrator':
                            sys.path.insert(0,str(ROOT/'reconciliation_system'))
                            from integration.environment import validate_bundle
                        else:
                            sys.path.insert(0,str(ROOT/'parse_system'))
                            from parsing.unified.environment_bundle import validate_bundle
                        if payload.get('build_only'):validate_bundle(bundle_root,check_host=False,check_candidate=False)
                        else:validate_bundle(bundle_root,check_host=False)
                    else:
                        bundle_root.parent.mkdir(exist_ok=True)
                        with tarfile.open(bundle) as archive:
                            for member in archive.getmembers():
                                if (member.issym() or member.islnk()
                                        or not (bundle_root.parent/member.name).resolve().is_relative_to(bundle_root.parent.resolve())):
                                    raise ValueError('Unsafe bundle member')
                            archive.extractall(bundle_root.parent,filter='data')
                    args+=['--reuse-build-bundle' if payload.get('build_only') else '--reuse-bundle',bundle_root]
                if (env/'environment.json').exists():
                    sys.path.insert(0,str(ROOT/'parse_system'))
                    from parsing.unified.environment import candidate_text
                    requirements=ROOT/({'parser':'parse_system/parsing/unified/requirements.in','integrator':'reconciliation_system/requirements.in','both':'requirements.in'}[profile])
                    if (env/'requirements-candidate.in').read_text()!=candidate_text(requirements):
                        raise ValueError('Existing environment requirements differ; preserve for review')
                    run(['python3','-u','-B','setup_environment.py','--check','--destination',env,'--profile',profile])
                elif env.exists():
                    raise ValueError('Incomplete environment exists; preserve for review')
                else:
                    run(args)
                if not payload['reuse'] and not (runtime/'export-bundle.tar.gz').exists():
                    run(['python3','-u','-B','setup_environment.py','--destination',env,'--export-bundle',runtime/'export-bundle','--profile',profile])
                if profile!='integrator':
                    config_path=runtime/'models-config/hybrid-runtime.json'
                    if config_path.exists():
                        # Revalidate cached weights against current manifests without downloading.
                        sys.path.insert(0,str(ROOT/'parse_system'))
                        from parsing.unified.environment import verify_files
                        config=json.loads(config_path.read_text())
                        if config['env_manifest']!=str(env/'environment.json'):
                            raise ValueError('Existing model configuration uses another environment')
                        for name in ('layoutlmv3','table_transformer','mineru'):
                            model_receipt=json.loads((ROOT/'model_manifests'/(name+'.json')).read_text())
                            verify_files(Path(config['model_dirs'][name]),model_receipt['files'])
                    else:
                        run([python,'-u','-B','setup_models.py','--env-manifest',env/'environment.json','--output-dir',runtime/'models-config'])
            elif phase=='parse':
                if profile=='integrator':raise ValueError('Integrator-only session cannot parse')
                request=(ROOT.parent/'papers-request.json')
                try:
                    value=json.loads(request.read_text())
                    if {item['name'] for item in value['files']}!=set(payload['papers']):raise ValueError('R2 selection differs')
                    run([python,'-u','-B','prepare_papers.py','download','--request',request,'--input-dir','inputs/sic_papers'])
                finally:
                    request.unlink(missing_ok=True)
                config=runtime/'models-config/hybrid-runtime.json'
                # run itself checks the shared environment; workers check CUDA before inference.
                destination=ROOT/'results/parse_results'/payload['run_id']
                args=[python,'-u','-B','parse_system/run.py','run','--runtime',config,'--output',payload['run_id'],
                      '--max-inflight','2','--load-timeout','600','--task-timeout','600','--user-run']
                for name in payload['papers']:args+=['--paper',ROOT/'inputs/sic_papers'/name]
                code=run(args,check=False)
                # TAR is only transport; results remain a manifest-based directory.
                archive=(ROOT.parent/'results-transport.tar.gz')
                with tarfile.open(archive,'x:gz') as saved:
                    if destination.is_dir():saved.add(destination,arcname='parser-result')
                    saved.add(runtime/'workflow.log',arcname='workflow.log')
                    saved.add(env/'environment.json',arcname='environment.json')
                    saved.add(ROOT/'inputs/sic_papers/r2-download-receipt.json',arcname='r2-download-receipt.json')
                (ROOT.parent/'results-transport.sha256').write_text(sha(archive))
                status['parser_exit_code']=code
            elif phase=='integrate':
                if profile=='parser':raise ValueError('Parser-only session cannot integrate')
                args=[python,'-u','-B','reconciliation_system/run.py','run','--output',payload['run_id'],
                      '--workers',str(payload['workers'])]
                if profile=='integrator':
                    request=(ROOT.parent/'papers-request.json')
                    try:
                        value=json.loads(request.read_text())
                        if {item['name'] for item in value['files']}!=set(payload['papers']):raise ValueError('R2 selection differs')
                        expected={p['name']:p['sha256'] for p in payload['selection']['papers']}
                        if {p['name']:p['sha256'] for p in value['files']}!=expected:raise ValueError('R2 identity differs from parser source')
                        run([python,'-u','-B','prepare_papers.py','download','--request',request,'--input-dir','inputs/sic_papers'])
                    finally:request.unlink(missing_ok=True)
                    source=(ROOT.parent/'parser-source.tar.gz')
                    if sha(source)!=payload['source_sha256']:raise ValueError('Selected parser transport hash differs')
                    staging=runtime/'integration-input'
                    if staging.exists():raise FileExistsError('Integration input already staged; inspect receipt')
                    staging.mkdir()
                    with tarfile.open(source) as archive:
                        seen=set()
                        for member in archive.getmembers():
                            if member.name in seen or not member.isfile() or not (staging/member.name).resolve().is_relative_to(staging.resolve()):raise ValueError('Unsafe selected parser transport')
                            seen.add(member.name)
                        archive.extractall(staging,filter='data')
                    selected=staging/'parser-source'
                    if sha(selected/'manifest.json')!=payload['selection']['manifest_sha256']:raise ValueError('Original parser manifest changed')
                    args+=['--parse-run',selected,'--runtime-profile','integrator','--pdf-directory',ROOT/'inputs/sic_papers']
                    for pid in payload['selection']['paper_ids']:args+=['--paper-id',pid]
                else:
                    args+=['--parse-run',ROOT/'results/parse_results'/payload['run_id']]
                code=run(args,check=False)
                destination=ROOT/'results/reconciliation_results'/payload['run_id']
                archive=(ROOT.parent/'integration-transport.tar.gz')
                with tarfile.open(archive,'x:gz') as saved:
                    if destination.is_dir():saved.add(destination,arcname='integration-result')
                    saved.add(runtime/'workflow.log',arcname='workflow.log')
                    saved.add(env/'environment.json',arcname='environment.json')
                    saved.add(ROOT/'inputs/sic_papers/r2-download-receipt.json',arcname='r2-download-receipt.json')
                (ROOT.parent/'integration-transport.sha256').write_text(sha(archive))
                status['integration_exit_code']=code
            else:raise ValueError('Unknown phase')
            status['status']='completed'
        except BaseException as error:
            status.update(status='failed',error=repr(error));raise
        finally:
            if previous_profile is None:os.environ.pop('NASA_ENV_PROFILE',None)
            else:os.environ['NASA_ENV_PROFILE']=previous_profile
            receipt.write_text(json.dumps(status,indent=2))


if __name__=='__main__':
    main(json.loads(sys.argv[1]))

