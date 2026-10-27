"""Colab bootstrap/job. Independent env; no LayoutLMv3 install and no kernel replacement."""
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
from urllib.request import urlopen

MODEL_ID='microsoft/table-transformer-detection'
REVISION='2357cbe2b5a5d1c03e54f32764f06058933b65ab'


def execute_archived_job(helper_path, job_path, state, archive):
    """Refuse reuse before cli_job opens/truncates logs; exclusive lock also rejects races."""
    state, archive = Path(state), Path(archive)
    lock = archive.with_suffix('.lock')
    if state.exists() or archive.exists() or archive.with_suffix('.sha256').exists():
        raise FileExistsError('Previous TATR evidence exists; do not rerun on this VM')
    with os.fdopen(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as handle:
        handle.write('TATR job started; retain this lock to prevent overwriting evidence\n')
    helper = runpy.run_path(str(helper_path), run_name='archive_helper')
    return helper['run_job'](job_path, state, archive)


def download_model(destination, opener=urlopen):
    """Verify pinned API revision and each file using Git blob/LFS digest + size.

    Store SHA256 receipts for local loading; never log redirect URLs in exceptions.
    """
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    try:
        with opener('https://huggingface.co/api/models/'+MODEL_ID+'/revision/'+REVISION+'?blobs=true',timeout=60) as source:
            metadata=json.load(source)
        if metadata['sha']!=REVISION: raise ValueError('Revision mismatch')
        siblings={item['rfilename']:item for item in metadata['siblings']}
    except Exception:
        raise RuntimeError('Could not verify pinned model metadata') from None
    receipt={'model_id':MODEL_ID,'revision':REVISION,'files':{}}
    for name in ('config.json','preprocessor_config.json','model.safetensors'):
        partial=destination/(name+'.part')
        try:
            info=siblings[name]; lfs=info.get('lfs')
            size=info['size']
            if type(size) is not int or size<=0: raise ValueError('Invalid file size')
            if lfs:
                expected=lfs['sha256']; digest=hashlib.sha256()
                if not re.fullmatch('[0-9a-f]{64}',expected): raise ValueError('Invalid LFS hash')
            else:
                expected=info['blobId'];digest=hashlib.sha1(b'blob '+str(size).encode()+b'\0')
                if not re.fullmatch('[0-9a-f]{40}',expected): raise ValueError('Invalid Git blob hash')
            sha=hashlib.sha256();total=0
            print('Downloading pinned file:',name,'bytes:',size,flush=True)
            with opener('https://huggingface.co/'+MODEL_ID+'/resolve/'+REVISION+'/'+name,timeout=60) as source, partial.open('wb') as output:
                while True:
                    block=source.read(min(4*1024*1024,size-total+1))
                    if not block: break
                    total+=len(block)
                    if total>size: raise ValueError('Oversized file')
                    digest.update(block);sha.update(block);output.write(block)
            if total!=size or digest.hexdigest()!=expected: raise ValueError('File integrity mismatch')
            partial.replace(destination/name)
            receipt['files'][name]={'bytes':size,'sha256':sha.hexdigest(),
                                    'source_digest':expected,'source_digest_type':'sha256' if lfs else 'git_blob_sha1'}
        except Exception:
            raise RuntimeError('Pinned model download/verification failed: '+name) from None
        finally:
            if partial.exists(): partial.unlink()
    (destination/'download-manifest.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    return receipt


def main():
    inputs=Path('/content/tatr-inputs');state=Path('/content/tatr-state')
    state.mkdir(parents=True,exist_ok=True)
    unpack=runpy.run_path('/content/nasa_tatr_prepare.py',run_name='bundle_helper')['unpack_bundle']
    manifest=unpack('/content/table-transformer-page.zip','/content/table-transformer-page.sha256',inputs)
    (state/'input-manifest.json').write_text(json.dumps(manifest,indent=2))
    (state/'source.json').write_bytes((inputs/'source.json').read_bytes())
    receipt=download_model('/content/tatr-model')
    (state/'model-manifest.json').write_text(json.dumps(receipt,indent=2))
    env=os.environ.copy()
    for key in ('PYTHONHOME','PYTHONPATH','VIRTUAL_ENV'): env.pop(key,None)
    env['PYTHONNOUSERSITE']='1'
    tools=Path('/content/tatr-tools')
    subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check',
                    '--target',str(tools),'uv==0.6.14'],check=True,env=env)
    uv_env=env.copy();uv_env['PYTHONPATH']=str(tools)
    uv=[sys.executable,'-m','uv']
    def uv_run(*args,stdout=None):
        subprocess.run(uv+list(map(str,args)),check=True,env=uv_env,stdout=stdout)
    venv=Path('/content/tatr-probe/env')
    if venv.exists(): raise FileExistsError('Use a new VM; TATR environment already exists')
    uv_run('venv','--python','3.11.11',venv)
    python=venv/'bin/python'
    uv_run('pip','install','--python',python,'--index-url','https://download.pytorch.org/whl/cu121',
           'torch==2.5.1+cu121','torchvision==0.20.1+cu121')
    constraints=state/'constraints.txt'
    constraints.write_text('torch==2.5.1+cu121\ntorchvision==0.20.1+cu121\n')
    uv_run('pip','install','--python',python,'-c',constraints,'-r',inputs/'requirements.txt')
    uv_run('pip','check','--python',python)
    with (state/'requirements-freeze.txt').open('w') as output:
        uv_run('pip','freeze','--python',python,stdout=output)
    env['PYTHONPATH']=str(inputs);env['HF_HUB_OFFLINE']='1';env['TRANSFORMERS_OFFLINE']='1'
    check="import torch,json; assert torch.cuda.is_available(); name=torch.cuda.get_device_name(0); assert 'T4' in name, name; print(json.dumps({'gpu':name,'torch':torch.__version__,'cuda':torch.version.cuda}))"
    subprocess.run([str(python),'-u','-c',check],check=True,env=env)
    subprocess.run([str(python),'-u','-m','table_transformer.run_image','--image',str(inputs/'render.png'),
                    '--model-dir','/content/tatr-model','--output',str(state/'page')],check=True,env=env,cwd=inputs)


if __name__=='__main__': main()
