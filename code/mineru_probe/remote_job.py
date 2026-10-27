"""Bootstrap a separate MinerU environment on an existing authorized T4."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import subprocess
import sys
from urllib.request import urlopen


def verify_receipt(receipt, root):
    for name,expected in receipt['files'].items():
        path=Path(root)/name;digest=hashlib.sha256()
        with path.open('rb') as source:
            for block in iter(lambda:source.read(4*1024*1024),b''):digest.update(block)
        if path.stat().st_size!=expected['bytes'] or digest.hexdigest()!=expected['sha256']:
            raise ValueError('Local model integrity mismatch: '+name)


def activate_verified_models(receipt_path):
    """Let MinerU mark completion only after its official path checks and our SHA checks.

    4.0.12 lacks revision in its download API. A local provider replaces only the
    snapshot transport; the public download flow retains locks/path checks/markers.
    """
    from mineru.model import download
    from mineru.model.registry import MINERU_4_MODELS_TORCH as repo
    receipt=json.loads(Path(receipt_path).read_text())
    if (receipt['model_id']!='opendatalab/MinerU-4_models_torch'
            or receipt['revision']!='2b3afb86f4d23fa623f6b2f4b2279ed4ef93a89d'):
        raise ValueError('Unexpected snapshot identity')
    def local_snapshot(source, requested_repo, patterns):
        if requested_repo is not repo or source!='huggingface':raise ValueError('Unexpected model request')
        verify_receipt(receipt,repo.local_dir())
        return str(repo.local_dir())
    original=download._snapshot_download
    try:
        download._snapshot_download=local_snapshot
        download.download_model_repo(repo,source='huggingface')
    finally:download._snapshot_download=original
    if not download.verify_model_repo(repo).ready:raise ValueError('Incomplete local model bundle')


def execute_archived_job(helper_path, job_path, state, archive):
    state,archive=Path(state),Path(archive)
    if state.exists() or archive.exists() or archive.with_suffix('.sha256').exists():
        raise FileExistsError('Previous MinerU evidence exists; do not repeat')
    with os.fdopen(os.open(archive.with_suffix('.lock'),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:
        f.write('Retain lock; do not overwrite evidence\n')
    return runpy.run_path(str(helper_path),run_name='archive_helper')['run_job'](job_path,state,archive)


def download_models(manifest, destination, opener=urlopen):
    if not re.fullmatch('[0-9a-f]{40}',manifest['revision']):raise ValueError('Revision must be pinned')
    destination=Path(destination);receipt={'model_id':manifest['model_id'],'revision':manifest['revision'],'files':{}}
    # Validate every path before any network or file mutation.
    for name in manifest['files']:
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
            raise ValueError('Unsafe model path')
    for name,expected in manifest['files'].items():
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
        partial=target.with_suffix(target.suffix+'.part');size=expected['bytes']
        digest=hashlib.sha256() if expected['digest_type']=='sha256' else hashlib.sha1(b'blob '+str(size).encode()+b'\0')
        sha=hashlib.sha256();total=0
        print('Downloading pinned model file:',name,'bytes:',size,flush=True)
        try:
            url='https://huggingface.co/'+manifest['model_id']+'/resolve/'+manifest['revision']+'/'+name
            with opener(url,timeout=60) as source,partial.open('wb') as output:
                while True:
                    block=source.read(min(4*1024*1024,size-total+1))
                    if not block:break
                    total+=len(block)
                    if total>size:raise ValueError('Oversized download')
                    sha.update(block);digest.update(block);output.write(block)
            if total!=size or digest.hexdigest()!=expected['source_digest']:raise ValueError('Integrity mismatch')
            partial.replace(target)
            receipt['files'][name]={'bytes':size,'sha256':sha.hexdigest()}
        except Exception:
            raise RuntimeError('Model download/verification failed: '+name) from None
        finally:
            if partial.exists():partial.unlink()
    return receipt


def main():
    state=Path('/content/mineru-state');state.mkdir(parents=True,exist_ok=True)
    inputs=Path('/content/mineru-inputs')
    unpack=runpy.run_path('/content/nasa_mineru_prepare.py',run_name='bundle_helper')['unpack_bundle']
    manifest=unpack('/content/mineru-page.zip','/content/mineru-page.sha256',inputs)
    (state/'input-manifest.json').write_text(json.dumps(manifest,indent=2))
    for name in ('requirements.lock','model-manifest.json'):
        (state/name).write_bytes((inputs/name).read_bytes())
    models=json.loads((inputs/'model-manifest.json').read_text())
    model_base=Path('/content/mineru-models')
    receipt=download_models(models,model_base/'MinerU-4_models_torch')
    (state/'model-download-receipt.json').write_text(json.dumps(receipt,indent=2))
    env=os.environ.copy()
    for key in list(env):
        if key.startswith('MINERU_') or key in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'):env.pop(key)
    env['PYTHONNOUSERSITE']='1'
    tools=Path('/content/mineru-tools')
    subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--target',str(tools),'uv==0.12.21'],check=True,env=env)
    uv_env=env.copy();uv_env['PYTHONPATH']=str(tools)
    def uv(*args,stdout=None):
        subprocess.run([sys.executable,'-m','uv',*map(str,args)],check=True,env=uv_env,stdout=stdout)
    venv=Path('/content/mineru-probe/env')
    if venv.exists():raise FileExistsError('MinerU environment already exists; do not overwrite')
    uv('venv','--python','3.11.16',venv)
    python=venv/'bin/python'
    uv('pip','sync','--python',python,'--require-hashes','--only-binary',':all:','--no-binary','jieba',
       '--extra-index-url','https://download.pytorch.org/whl/cu126','--index-strategy','unsafe-best-match',inputs/'requirements.lock')
    uv('pip','check','--python',python)
    with (state/'requirements-freeze.txt').open('w') as output:uv('pip','freeze','--python',python,stdout=output)
    config=state/'config.yaml'
    config.write_text('model:\n  source: local\n  small_backend: torch\n  base_dir: '+str(model_base)+
                      '\nllm_aided:\n  features:\n    title_leveling: false\n    cross_page_table_cell_merge: false\n')
    env.update(PYTHONPATH=str(inputs),MINERU_HOME='/content/mineru-home',MINERU_CONFIG=str(config),
               MINERU_DEVICE_MODE='cuda',MINERU_TABLE_DEVICE='cpu',
               HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    check=("import torch,transformers,json; assert torch.cuda.is_available(); "
           "assert 'T4' in torch.cuda.get_device_name(0); assert torch.__version__=='2.7.1+cu126'; "
           "assert transformers.__version__=='5.10.1'; "
           "print(json.dumps({'gpu':torch.cuda.get_device_name(0),'torch':torch.__version__,'cuda':torch.version.cuda}))")
    subprocess.run([str(python),'-u','-c',check],check=True,env=env)
    activation="import runpy; runpy.run_path('/content/nasa_mineru_remote.py',run_name='helper')['activate_verified_models']('/content/mineru-state/model-download-receipt.json')"
    subprocess.run([str(python),'-u','-c',activation],check=True,env=env)
    # Local source mode verifies required files without requesting latest remote revisions.
    subprocess.run([str(venv/'bin/mineru-kit'),'models','verify','--tier','basic','--small-backend','torch'],check=True,env=env)
    subprocess.run([str(python),'-u','-m','mineru_probe.run_image','--image',str(inputs/'render.png'),
                    '--output',str(state/'page')],check=True,env=env,cwd=inputs)


if __name__=='__main__':main()
