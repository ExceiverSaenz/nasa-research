"""USER-ONLY Colab controller. Never invoked by preparation/offline evaluation."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import traceback
import uuid
from urllib.request import urlopen
import zipfile
from .common import MODELS,read,save,sha,validate_bundle,verify_terminal
from .command_log import run_logged

PREFIX=Path('/content/nasa-sic12-document-v1')

def archive_state(state,archive):
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(state.rglob('*')):
            if path.is_file() and 'models' not in path.relative_to(state).parts:z.write(path,path.relative_to(state).as_posix())
    archive.with_suffix('.sha256').write_text(sha(archive)+'\n',encoding='ascii')

def download_exact(manifest,destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    repo=manifest.get('model_id',manifest.get('repository'));revision=manifest['revision']
    for name,spec in manifest['files'].items():
        path=Path(name)
        if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe model path')
        target=destination/path;target.parent.mkdir(parents=True,exist_ok=True)
        with urlopen('https://huggingface.co/'+repo+'/resolve/'+revision+'/'+name,timeout=60) as src,target.open('xb') as output:
            remaining=spec['bytes']
            while True:
                data=src.read(min(4*1024*1024,remaining+1))
                if not data:break
                remaining-=len(data)
                if remaining<0:raise ValueError('Oversized model file')
                output.write(data)
        if remaining or sha(target)!=spec['sha256']:raise ValueError('Pinned model verification failed: '+name)
    save(destination/'download-manifest.json',manifest)

def setup(inputs,state):
    plan=read(inputs/'plan.json')
    if 'documents' in plan:
        from .batch import validate_batch
        validate_batch(inputs,plan)
    if plan['execution_policy']!='USER_ONLY_COLAB_CLI_T4' or plan['automatic_recovery'] or plan['automatic_retries']:raise ValueError('Unapproved execution policy')
    env=os.environ.copy()
    for k in list(env):
        if k.startswith('MINERU_') or k in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'):env.pop(k)
    env['PYTHONNOUSERSITE']='1';env['NASA_DOCUMENT_USER_RUN']='COLAB_CLI_T4'
    tools=PREFIX.with_name(PREFIX.name+'-tools')
    if tools.exists():raise FileExistsError('Tool directory exists; no automatic reuse/retry')
    run_logged([sys.executable,'-m','pip','install','--target',str(tools),'uv==0.12.21'],state,env=env,stage='bootstrap-uv')
    uv_env=dict(env,PYTHONPATH=str(tools))
    def uv(*args):return run_logged([sys.executable,'-m','uv',*map(str,args)],state,env=uv_env,stage='setup:'+model+':uv')
    vendor=Path('/content/nasa-layoutlm/layoutlmv3')
    if vendor.exists():raise FileExistsError('Original LM editable path exists; use a clean user-owned session')
    vendor.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(inputs/'vendor/layoutlmv3',vendor)
    runners={}
    for model in MODELS:
        if model=='table_transformer':
            tatr_tools=PREFIX.with_name(PREFIX.name+'-tools-tatr')
            if tatr_tools.exists():raise FileExistsError('TATR bootstrap already exists')
            run_logged([sys.executable,'-m','pip','install','--target',str(tatr_tools),'uv==0.6.14'],state,env=env,stage='bootstrap-uv-tatr')
            uv_env=dict(env,PYTHONPATH=str(tatr_tools))
        else:uv_env=dict(env,PYTHONPATH=str(tools))
        venv=PREFIX.with_name(PREFIX.name+'-env-'+model)
        if venv.exists():raise FileExistsError('Environment exists; no reuse or retry')
        uv('venv','--python',plan['models'][model]['python'],venv)
        python=venv/'bin/python'
        if model=='mineru':
            uv('pip','sync','--python',python,'--require-hashes','--only-binary',':all:','--no-binary','jieba',
               '--extra-index-url','https://download.pytorch.org/whl/cu126','--index-strategy','unsafe-best-match',inputs/'mineru/requirements.lock')
        else:
            if model=='layoutlmv3':uv('pip','install','--python',python,'setuptools==80.9.0','pip==25.1.1')
            uv('pip','install','--python',python,'--no-deps','--no-build-isolation','-r',inputs/model/'freeze.txt',
               '--extra-index-url','https://download.pytorch.org/whl/cu121','--index-strategy','unsafe-best-match')
        uv('pip','check','--python',python)
        runenv=dict(env,PYTHONPATH=str(inputs),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        if model=='mineru':
            (state/'config.yaml').write_bytes((inputs/'mineru/config.yaml').read_bytes())
            runenv.update(MINERU_HOME='/content/mineru-home',MINERU_CONFIG=str(state/'config.yaml'),MINERU_DEVICE_MODE='cuda',MINERU_TABLE_DEVICE='cpu')
        runners[model]=(python,runenv)
    def work(model,stage,source=inputs,destination=state):
        python,runenv=runners[model]
        runenv=dict(runenv)
        if model=='mineru':runenv['MINERU_CONFIG']=str(destination/'config.yaml')
        run_logged([str(python),'-B','-u','-m','document_trial.worker','--model',model,'--stage',stage,
                        '--inputs',str(source),'--state',str(destination)],destination,env=runenv,cwd=inputs,stage=model+':'+stage)
    # Full version/GPU gate for all branches BEFORE any parse/predict call.
    for model in MODELS:work(model,'probe')
    if 'documents' not in plan:work('layoutlmv3','render')
    for model in MODELS:
        if model=='mineru':
            sys.path.insert(0,str(inputs))
            from mineru_probe.remote_job import download_models,verify_receipt
            root=Path('/content/mineru-models/MinerU-4_models_torch')
            expected=read(inputs/'mineru/model-download-receipt.json')
            if root.exists():verify_receipt(expected,root)
            elif download_models(read(inputs/'mineru/model-manifest.json'),root)!=expected:raise ValueError('MinerU receipt differs')
        else:download_exact(read(inputs/model/'models.json'),state/'models'/model)
    save(state/'model-verification.json',dict(all_pinned_models_verified=True,
        layoutlmv3=read(inputs/'layoutlmv3/models.json'),table_transformer=read(inputs/'table_transformer/models.json'),
        mineru=read(inputs/'mineru/model-download-receipt.json')))
    if 'documents' in plan:
        from .batch import run_documents
        return run_documents(inputs,state,work)
    # Model branch errors are retained and other independent branches still run.
    failures={}
    for model in MODELS:
        try:work(model,'infer')
        except Exception:failures[model]=traceback.format_exc()
    save(state/'branch-failures.json',failures)
    if failures:raise RuntimeError('One or more parser branches failed; inspect backup. No automatic retry.')

def main():
    if platform.system()!='Linux' or not Path('/content').is_dir() or os.environ.get('NASA_DOCUMENT_USER_RUN')!='COLAB_CLI_T4':raise RuntimeError('User-only Colab CLI entry point')
    state=PREFIX;inputs=PREFIX.with_name(PREFIX.name+'-inputs');archive=PREFIX.with_suffix('.zip')
    for path in (state,inputs,archive,archive.with_suffix('.sha256')):
        if path.exists():raise FileExistsError('Existing evidence; no overwrite/retry: '+str(path))
    bundle=PREFIX.with_name(PREFIX.name+'-upload.zip');sidecar=bundle.with_suffix('.sha256')
    attempt=read(PREFIX.with_name(PREFIX.name+'-attempt.json'))['attempt_id']
    if not isinstance(attempt,str) or uuid.UUID(attempt).hex!=attempt:raise ValueError('Invalid attempt identity')
    plan=validate_bundle(bundle,sidecar,inputs);state.mkdir()
    (state/'plan.json').write_bytes((inputs/'plan.json').read_bytes())
    save(state/'execution.json',dict(execution_id='document-parsing-'+uuid.uuid4().hex,document_sha256=plan.get('document_sha256'),batch_sha256=plan.get('batch_sha256'),
        initiator='human_colab_cli',bundle_sha256=sha(bundle),attempt_id=attempt))
    status=dict(status='failed',initiator='human_colab_cli',error=None,automatic_recovery=False)
    try:setup(inputs,state);status['status']='completed'
    except Exception:status['error']=traceback.format_exc();print(status['error'],flush=True)
    finally:
        from .batch import account_missing
        account_missing(plan,state)
        save(state/'execution-status.json',status)
        archive_state(state,archive)
    return 0 if status['status']=='completed' else 1

if __name__=='__main__':raise SystemExit(main())
