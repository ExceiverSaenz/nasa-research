"""USER-ONLY entrypoint. Run with Colab CLI on an existing T4; never locally.

Importing this module is inert. Only main() prepares the remote environment;
only worker() imports torch/MinerU and invokes the archived parser.
"""
import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import traceback
import zipfile

STATE=Path('/content/nasa-localized-labels-v1')
INPUTS=Path('/content/nasa-localized-labels-v1-inputs')
ARCHIVE=Path('/content/nasa-localized-labels-v1.zip')
BUNDLE=Path('/content/nasa-localized-labels-v1-upload.zip')
SIDECAR=Path('/content/nasa-localized-labels-v1-upload.sha256')


def canonical(name):return re.sub(r'[-_.]+','-',name).lower()


def check_environment(observed,expected):
    errors=[]
    for k in ('python','packages'):
        if observed.get(k)!=expected[k]:errors.append(k)
    if observed.get('gpu')!='Tesla T4':errors.append('Tesla T4 required')
    if observed.get('cuda')!='12.6':errors.append('CUDA runtime 12.6 required')
    if observed.get('device')!='cuda' or observed.get('backend')!='torch':errors.append('CUDA/Torch backend')
    for k in ('config_matches','weights_match','parse_options_match','env_matches'):
        if observed.get(k) is not True:errors.append(k)
    if errors:raise ValueError('INCOMPATIBLE; OCR NOT STARTED: '+', '.join(errors))


def worker(inputs,state):
    """Called exclusively by the user-run controller, inside the pinned venv."""
    from page_integration.workflow import read,save,file_hash,digest
    from mineru_probe.remote_job import activate_verified_models,verify_receipt
    plan=read(inputs/'plan.json')
    expected=dict(python=plan['original_run']['python'],packages={})
    for line in (inputs/'requirements-freeze.txt').read_text().splitlines():
        if line.strip():
            if '==' not in line:raise ValueError('Unsupported frozen requirement')
            name,version=line.split('==',1);expected['packages'][canonical(name)]=version
    observed=dict(python=platform.python_version(),packages={canonical(d.metadata['Name']):d.version for d in metadata.distributions()})
    # Stop version drift before importing any model runtime.
    if observed['python']!=expected['python'] or observed['packages']!=expected['packages']:
        save(state/'runtime.json',dict(observed=observed,expected=expected,verified=False))
        raise ValueError('INCOMPATIBLE frozen environment; OCR NOT STARTED')
    import torch
    from mineru.config import config
    from mineru.model.runtime.device import get_device,resolve_small_model_backend
    receipt=read(inputs/'model-download-receipt.json')
    verify_receipt(receipt,Path('/content/mineru-models/MinerU-4_models_torch'))
    original_config=(inputs/'config.yaml').read_bytes()
    observed.update(gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        cuda=torch.version.cuda,device=get_device(),backend=resolve_small_model_backend(),weights_match=True,
        config_matches=(Path(os.environ['MINERU_CONFIG']).read_bytes()==original_config and
            config.model.source=='local' and config.model.small_backend=='torch' and
            str(config.model.base_dir)=='/content/mineru-models' and
            not config.llm_aided.features.title_leveling and not config.llm_aided.features.cross_page_table_cell_merge),
        parse_options_match=True,
        env_matches=all(os.environ.get(k)==v for k,v in {
            'MINERU_DEVICE_MODE':'cuda','MINERU_TABLE_DEVICE':'cpu','HF_HUB_OFFLINE':'1',
            'TRANSFORMERS_OFFLINE':'1','MINERU_HOME':'/content/mineru-home'}.items()))
    save(state/'runtime.json',dict(observed=observed,expected=expected,verified=False))
    check_environment(observed,expected)
    activate_verified_models(inputs/'model-download-receipt.json')
    save(state/'runtime.json',dict(observed=observed,expected=expected,verified=True,
        config_sha256=file_hash(inputs/'config.yaml'),weights_revision=receipt['revision'],
        table_device='cpu',parse_options=dict(tier='basic',ocr_mode='ocr',image_analysis=True)))
    # This is the exact original source and call, verified before it is imported.
    for name in ('__init__.py','run_image.py','outputs.py'):
        if file_hash(inputs/'mineru_probe'/name)!=plan['original_run']['code_sha256'][name]:
            raise ValueError('Original parser wrapper integrity mismatch')
    from mineru_probe.run_image import parse_native
    from mineru_probe.outputs import export_regions,save_json
    from mineru.parser.writer import FileBasedDataWriter
    from PIL import Image
    for target in plan['targets']:
        if target['status']!='ready':raise ValueError('ROI ambiguous; no inference allowed')
        crop=inputs/target['input_member']
        if file_hash(crop)!=target['input_sha256']:raise ValueError('ROI input changed')
        image=Image.open(crop).convert('RGB')
        if list(image.size)!=target['transform']['size_px']:raise ValueError('ROI dimensions changed')
    # Validate ALL inputs before the first inference; no retries.
    for target in plan['targets']:
        folder=state/'rois'/target['roi_id'];folder.mkdir(parents=True,exist_ok=False)
        image_path=inputs/target['input_member']
        save(folder/'input-and-transform.json',target)
        if plan.get('trace_policy') is not None:
            from page_integration.trace_observer import observe_mineru
            with observe_mineru(folder/'traces',plan['trace_policy']):
                result=parse_native(image_path)
        else:
            result=parse_native(image_path)
        document=result.middle_json.to_dict(skip_defaults=False)
        save_json(folder/'middle-native.json',document)
        if result._model_output is not None:save_json(folder/'model-native.json',result._model_output.to_dict(skip_defaults=False))
        result.save(FileBasedDataWriter(str(folder/'native')))
        with Image.open(image_path) as image:export_regions(image.convert('RGB'),document,folder)


def setup_and_run(inputs,state,experiment='localized-labels-v1'):
    """Mirror the original locked installer, then launch the user-requested worker."""
    from page_integration.workflow import read,save
    from mineru_probe.remote_job import download_models,verify_receipt
    plan=read(inputs/'plan.json')
    if plan['execution_policy']!='USER_ONLY_COLAB_CLI_T4':raise ValueError('Wrong execution policy')
    for name in ('plan.json','config.yaml','requirements.lock','requirements-freeze.txt','model-manifest.json','model-download-receipt.json','bundle-manifest.json'):
        (state/name).write_bytes((inputs/name).read_bytes())
    env=os.environ.copy()
    for key in list(env):
        if key.startswith('MINERU_') or key in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'):env.pop(key)
    env['PYTHONNOUSERSITE']='1'
    if experiment not in ('localized-labels-v1','table1-header-v1','table1-square-v1'):raise ValueError('Unknown approved experiment')
    tools=Path('/content/nasa-'+experiment+'-tools')
    venv=Path('/content/nasa-'+experiment+'-env')
    if tools.exists() or venv.exists():raise FileExistsError('Dedicated environment exists; do not retry blindly')
    subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--target',str(tools),'uv==0.12.21'],check=True,env=env)
    uv_env=env.copy();uv_env['PYTHONPATH']=str(tools)
    def uv(*args,stdout=None):subprocess.run([sys.executable,'-m','uv',*map(str,args)],check=True,env=uv_env,stdout=stdout)
    uv('venv','--python','3.11.16',venv)
    python=venv/'bin/python'
    uv('pip','sync','--python',python,'--require-hashes','--only-binary',':all:','--no-binary','jieba',
        '--extra-index-url','https://download.pytorch.org/whl/cu126','--index-strategy','unsafe-best-match',inputs/'requirements.lock')
    uv('pip','check','--python',python)
    with (state/'requirements-freeze-current.txt').open('w') as f:uv('pip','freeze','--python',python,stdout=f)
    env.update(PYTHONPATH=str(inputs),MINERU_HOME='/content/mineru-home',MINERU_CONFIG=str(state/'config.yaml'),
        MINERU_DEVICE_MODE='cuda',MINERU_TABLE_DEVICE='cpu',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    # GPU/version check before any weights download. The complete worker check follows.
    subprocess.run([str(python),'-c',
        "import torch; assert torch.cuda.is_available(); assert torch.cuda.get_device_name(0)=='Tesla T4'; "
        "assert torch.__version__=='2.7.1+cu126'; assert torch.version.cuda=='12.6'"],check=True,env=env)
    model_root=Path('/content/mineru-models/MinerU-4_models_torch')
    model_manifest=read(inputs/'model-manifest.json');receipt=read(inputs/'model-download-receipt.json')
    if model_manifest['revision']!='2b3afb86f4d23fa623f6b2f4b2279ed4ef93a89d':raise ValueError('Wrong model revision')
    if model_root.exists():verify_receipt(receipt,model_root)
    else:
        actual=download_models(model_manifest,model_root)
        if actual!=receipt:raise ValueError('Original model receipt mismatch')
    subprocess.run([str(python),'-B','-u','-m','page_integration.remote_labels','--worker',str(inputs),str(state)],check=True,env=env,cwd=inputs)


def main():
    p=argparse.ArgumentParser(description='USER ONLY: Colab CLI/T4 OCR, never run locally')
    p.add_argument('--worker',nargs=2,metavar=('INPUTS','STATE'))
    args=p.parse_args()
    if not Path('/content').is_dir() or platform.system()!='Linux':raise RuntimeError('Colab /content Linux required; local OCR forbidden')
    if args.worker:
        worker(*map(Path,args.worker));return
    for path in (STATE,INPUTS,ARCHIVE,ARCHIVE.with_suffix('.sha256')):
        if path.exists():raise FileExistsError('Existing evidence; inspect, never overwrite: '+str(path))
    if not BUNDLE.is_file() or not SIDECAR.is_file():raise FileNotFoundError('Upload bundle and sidecar first')
    # zipimport of the user-prepared package is only used to invoke its verified unpacker.
    if hashlib.sha256(BUNDLE.read_bytes()).hexdigest()!=SIDECAR.read_text().strip():raise ValueError('Bundle hash mismatch')
    sys.path.insert(0,str(BUNDLE))
    from page_integration.workflow import unpack,save,file_hash
    unpack(BUNDLE,SIDECAR,INPUTS)
    sys.path[0]=str(INPUTS)
    STATE.mkdir(exist_ok=False)
    status=dict(status='failed',ocr_scope='two_rois_only',initiator='human_colab_cli',error=None)
    try:
        setup_and_run(INPUTS,STATE)
        status['status']='completed'
    except Exception:
        status['error']=traceback.format_exc();(STATE/'error.log').write_text(status['error'],encoding='utf-8')
        print(status['error'],file=sys.stderr)
    finally:
        save(STATE/'execution-status.json',status)
        with zipfile.ZipFile(ARCHIVE,'x',zipfile.ZIP_DEFLATED) as z:
            for path in sorted(STATE.rglob('*')):
                if path.is_file() and not path.is_symlink():z.write(path,path.relative_to(STATE).as_posix())
        ARCHIVE.with_suffix('.sha256').write_text(file_hash(ARCHIVE)+'\n',encoding='ascii')
        print('Archived:',ARCHIVE,'status:',status['status'],flush=True)
    if status['status']!='completed':raise SystemExit(1)


if __name__=='__main__':main()
