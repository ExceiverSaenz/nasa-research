"""Remote phase entrypoints. None is called by import or local inspection."""
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from .contracts import load_experiment,write_json,sha256,exit_code
from .environment import inspect_environment,prepare_environment
from .prepare import install_environment
from .preflight import remote_probe
from .models import fetch_models,validate_manifest


def ensure_uv(root):
    import urllib.request
    import urllib.parse
    import zipfile
    import hashlib
    root=Path(root);spec=load_experiment(root/'tool_manifests/uv-linux.json')
    existing=shutil.which('uv')
    if existing:
        p=subprocess.run([existing,'--version'],capture_output=True,text=True,timeout=15,check=True)
        if p.stdout.split()[:2]==['uv',spec['version']]:return existing
    target=root/'runtime/tools/uv'
    if target.exists():
        p=subprocess.run([str(target),'--version'],capture_output=True,text=True,timeout=15,check=True)
        if p.stdout.split()[:2]==['uv',spec['version']]:return str(target)
        raise ValueError('Existing bootstrap tool differs')
    url=urllib.parse.urlsplit(spec['url'])
    if url.scheme!='https' or url.netloc!='files.pythonhosted.org':raise ValueError('Untrusted tool origin')
    target.parent.mkdir(parents=True,exist_ok=True);wheel=target.parent/spec['filename']
    from .environment import classify_artifact
    state=classify_artifact(wheel,spec)
    if state=='corrupt':raise ValueError('Corrupt tool preserved')
    if state=='missing':
        with urllib.request.urlopen(spec['url'],timeout=60) as r:data=r.read()
        if len(data)!=spec['bytes'] or hashlib.sha256(data).hexdigest()!=spec['sha256']:raise ValueError('Bootstrap tool hash mismatch')
        wheel.write_bytes(data)
    with zipfile.ZipFile(wheel) as z:
        candidates=[n for n in z.namelist() if n.endswith('/uv')]
        if len(candidates)!=1:raise ValueError('Ambiguous uv executable')
        target.write_bytes(z.read(candidates[0]));target.chmod(0o700)
    return str(target)


def ensure_python(runtime,runner=subprocess.run,finder=shutil.which):
    python=finder('python3.11')
    if python:
        result=runner([python,'-c','import sys; print("%s.%s" % sys.version_info[:2])'],capture_output=True,text=True,check=True,timeout=15)
        if result.stdout.strip()=='3.11':return python
    uv=finder('uv')
    if not uv:raise ValueError('Python 3.11 and uv absent; explicit bootstrap required')
    # uv verifies its managed interpreter download. No system Python or driver mutation.
    env={**os.environ,'UV_PYTHON_INSTALL_DIR':str(Path(runtime)/'python')}
    result=runner([uv,'python','find','3.11','--offline'],env=env,capture_output=True,text=True,timeout=30)
    if result.returncode:
        runner([uv,'python','install','3.11.16'],env=env,capture_output=True,text=True,check=True,timeout=300)
        result=runner([uv,'python','find','3.11.16','--offline'],env=env,capture_output=True,text=True,check=True,timeout=30)
    return result.stdout.strip()


def manifest_data(path):
    m=load_experiment(path)
    if 'repo' not in m:m['repo']=m['model_id']
    validate_manifest(m);return m


def prepare_remote(root,config,*,host_checks=None,installer=install_environment):
    root=Path(root).resolve();checks=host_checks if host_checks is not None else remote_probe()
    if exit_code(checks):raise ValueError('Remote host gates failed')
    if tuple(map(int,platform.libc_ver()[1].split('.')[:2]))<(2,39):raise ValueError('Locks require glibc >= 2.39')
    runtime=root/'runtime'
    if not shutil.which('python3.11'):
        uv=ensure_uv(root)
        finder=lambda name:uv if name=='uv' else shutil.which(name)
        python=ensure_python(runtime,finder=finder)
    else:python=ensure_python(runtime)
    results={}
    for env in ('a','b'):
        target=runtime/'envs'/env;spec={'python':target/'bin/python','lock':root/config['locks'][env]}
        before=inspect_environment(spec['python'],spec['lock'])
        result=prepare_environment(spec,checks=before,apply=True,installer=lambda s:installer(python,target,s['lock']))
        after=inspect_environment(spec['python'],spec['lock'])
        if exit_code(after):raise ValueError('Environment verification failed: '+env)
        if env=='b':subprocess.run([str(spec['python']),'-I','-c','import vllm'],check=True,timeout=60)
        results[env]={'action':result['action'],'checks':after,'lock_sha256':sha256(spec['lock'])}
        write_json(runtime/'environment-receipt.json',results)
    # Verified model files are reused before any download. No completion markers are fabricated.
    for rel in config['model_manifests']:
        manifest=manifest_data(root/rel);name=Path(rel).stem
        cache=runtime/'model-cache'/name
        model_checks=fetch_models(cache,manifest,apply=True)
        if exit_code(model_checks):raise ValueError('Model verification failed')
    # Prepare a version-specific MinerU snapshot using its official completion flow.
    subprocess.run([str(runtime/'envs/a/bin/python'),'-m','bbx.mineru_snapshot','--root',str(root)],cwd=root,check=True,timeout=300)
    write_json(runtime/'prepared.json',{'status':'prepared','environments':results})
    return {'status':'prepared'}


def download_inputs(root,request_file):
    import urllib.request
    from .r2 import download_verified
    root=Path(root);request_file=Path(request_file);rows=load_experiment(request_file)
    result=[]
    try:
        for row in rows:
            name=row['identity']['name']
            if Path(name).name!=name or not name.endswith('.pdf'):raise ValueError('Invalid PDF name')
            if time.time()>=row['expires_at']-30:raise ValueError('Request expired')
            def fetch(url=row['url']):
                with urllib.request.urlopen(url,timeout=60) as response:return response.read()
            result.append(download_verified(fetch,root/'runtime/inputs'/name,row['identity']))
    finally:request_file.unlink(missing_ok=True)
    return result


def gpu_pids():
    p=subprocess.run(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,timeout=15)
    return {int(s.strip()) for s in p.stdout.splitlines() if s.strip().isdigit()}


def configure_models(root,config):
    """Point Heron at immutable local snapshots; keep MinerU configuration isolated."""
    root=Path(root)
    for tool in config['tools'][:2]:tool['model_path']=str(root/'runtime/model-cache'/tool['id'])
    # A local HF snapshot does not satisfy MinerU's official completion contract by itself.
    # Preparation uses the version-pinned helper below, in environment A, before inference.
    modelbase=root/'runtime/mineru-models'
    mconfig={'model':{'source':'local','base_dir':str(modelbase),'small_backend':'torch','vlm':{'engine':'vllm'}}}
    write_json(root/'runtime/mineru-config.json',mconfig)
    config['mineru_config']=str(root/'runtime/mineru-config.json')
    write_json(root/'runtime/effective-config.json',config)


def run_phase(root,phase):
    root=Path(root).resolve();config=load_experiment(root/'experiment.json')
    if phase=='prepare':return prepare_remote(root,config)
    if phase not in ('smoke','execute'):raise ValueError('Unknown phase')
    if not (root/'runtime/prepared.json').exists():raise ValueError('Preparation receipt missing')
    if phase=='execute' and not (root/'runtime/smoke.json').exists():raise ValueError('Smoke receipt missing')
    inventory=load_experiment(root/'inventory.json')
    request=root/'private-requests.json';download_inputs(root,request)
    configure_models(root,config)
    out=root/'results'/phase
    if out.exists():raise ValueError('Existing phase preserved; no repeated inference')
    out.mkdir(parents=True)
    baseline=gpu_pids();receipts=[]
    for tool in config['tools']:
        if gpu_pids()!=baseline:raise ValueError('Residual or foreign GPU workers')
        python=root/'runtime/envs'/tool['environment']/'bin/python'
        command=[str(python),'-m','bbx.worker','--config',str(root/'runtime/effective-config.json'),'--tool',tool['id'],
                 '--inventory',str(root/'inventory.json'),'--pdf-dir',str(root/'runtime/inputs'),'--output',str(out/tool['id'])]
        if phase=='smoke':command.append('--smoke')
        proc=run_isolated(command,root)
        (out/(tool['id']+'.log')).write_text(proc.stdout+'\n'+proc.stderr,encoding='utf-8')
        if proc.returncode or 'BBX_STAGE_COMPLETED:'+tool['id'] not in proc.stdout.splitlines():raise ValueError('Worker failed: '+tool['id'])
        if gpu_pids()!=baseline:raise ValueError('Worker remains after stage: '+tool['id'])
        receipts.append({'tool':tool['id'],'status':'complete'})
    write_json(root/'runtime'/(phase+'.json'),{'status':'complete','tools':receipts})
    return {'status':'complete','tools':receipts}


def run_isolated(command,root):
    proc=subprocess.Popen(command,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:stdout,stderr=proc.communicate(timeout=7200)
    except subprocess.TimeoutExpired:
        # Preserve session and workers for explicit review; never retry/kill automatically.
        raise
    try:os.killpg(proc.pid,0)
    except ProcessLookupError:pass
    else:raise ValueError('CPU or GPU worker process group remains')
    return subprocess.CompletedProcess(command,proc.returncode,stdout,stderr)


def archive_results(root):
    import zipfile
    root=Path(root);archive=root/'results.zip'
    if archive.exists():raise ValueError('Existing archive preserved')
    files=[p for p in (root/'results/execute').rglob('*') if p.is_file()]
    if not files:raise ValueError('No results to archive')
    entries={str(p.relative_to(root/'results/execute')):p for p in files}
    required=['experiment.json','inventory.json','runtime/environment-receipt.json','runtime/prepared.json',
              'runtime/smoke.json','runtime/execute.json','runtime/effective-config.json','runtime/mineru-config.json']
    config=load_experiment(root/'experiment.json')
    required.extend(config['locks'].values());required.extend(config['model_manifests'])
    for rel in required:
        p=root/rel
        if not p.is_file():raise ValueError('Missing provenance receipt: '+rel)
        entries['provenance/'+rel]=p
    for p in (root/'results/smoke').rglob('*'):
        if p.is_file():entries['provenance/smoke-results/'+str(p.relative_to(root/'results/smoke'))]=p
    manifest={name:{'bytes':p.stat().st_size,'sha256':sha256(p)} for name,p in entries.items()}
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for name,p in entries.items():z.write(p,name)
        z.writestr('manifest.json',json.dumps(manifest))
    return {'sha256':sha256(archive),'bytes':archive.stat().st_size}
