"""Explicit Linux-only common-environment installer and fail-closed runtime check.

requirements.in is a candidate, never a resolved lock. prepare creates one new
venv, resolves hashes, builds pinned Detectron2 and records actual imports.
It does not download model weights or run inference.
"""
import argparse
import hashlib
import importlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import uuid
import shlex

PYTHON_VERSION = '3.11.16'
CANDIDATE = {'torch':'2.7.1+cu126','torchvision':'0.22.1+cu126',
             'transformers':'5.10.1','mineru':'4.0.12'}
# Official immutable revision, observed in upstream commit history 2026-10-28.
D2_COMMIT = 'e0ec4e189d438848521aee7926f9900e114229f5'
D2_URL = 'https://github.com/facebookresearch/detectron2.git'


def selected_requirements(package=None):
    package=Path(package) if package is not None else Path(__file__).resolve().parents[3]
    profile=os.environ.get('NASA_ENV_PROFILE','both')
    if profile not in ('parser','both'):raise ValueError('Parser environment requires parser or both profile')
    combined=package/'requirements.in'
    return (Path(__file__).with_name('requirements.in') if profile=='parser' or not combined.is_file() else combined)


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''): digest.update(block)
    return digest.hexdigest()


def verify_files(root, files):
    root=Path(root).resolve(strict=True)
    if not files: raise ValueError('Empty integrity receipt')
    for name, expected in files.items():
        path=(root/name).resolve()
        if not path.is_relative_to(root): raise ValueError('Receipt path escapes root')
        if (not path.is_file() or path.stat().st_size!=expected['bytes']
                or sha256(path)!=expected['sha256']):
            raise ValueError('Integrity mismatch: '+str(name))


def _save(path, value):
    with Path(path).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)


def _observed():
    if platform.python_version()!=PYTHON_VERSION: raise ValueError('Expected Python '+PYTHON_VERSION)
    if sys.prefix==sys.base_prefix: raise ValueError('Dedicated virtual environment required')
    versions={d.metadata['Name'].lower().replace('_','-'):d.version for d in metadata.distributions()}
    for name, version in CANDIDATE.items():
        if metadata.version(name)!=version: raise ValueError('Wrong package version: '+name)
    imports={}
    for name in ('torch','torchvision','transformers','mineru','detectron2','detectron2._C'):
        module=importlib.import_module(name)
        path=Path(module.__file__).resolve()
        if not path.is_relative_to(Path(sys.prefix).resolve()):
            raise ValueError('Package outside common venv: '+str(path))
        imports[name]={'path':str(path),'sha256':sha256(path)}
    import torch
    from detectron2 import _C
    if torch.version.cuda!='12.6': raise ValueError('Expected CUDA build 12.6')
    cuda_build=_C.get_cuda_version()
    validate_cuda_build(cuda_build)
    return {'prefix':str(Path(sys.prefix).resolve()),'executable':str(Path(sys.executable).absolute()),
            'python':platform.python_version(),'versions':versions,'imports':imports,
            'cuda_build':torch.version.cuda,'detectron2_cuda_build':cuda_build}


def check_runtime(manifest: Path, require_cuda=True):
    manifest=Path(manifest).resolve(strict=True)
    data=json.loads(manifest.read_text(encoding='utf-8'))
    if data.get('status')!='imports-validated': raise ValueError('Runtime manifest is not imports-validated')
    if str(Path(sys.prefix).resolve())!=data['prefix']: raise ValueError('Wrong shared environment prefix')
    if str(Path(sys.executable).absolute())!=data['executable']: raise ValueError('Wrong shared Python executable')
    verify_files(manifest.parent,data['artifacts'])
    observed=_observed()
    for key in ('python','versions','imports','cuda_build','detectron2_cuda_build'):
        if observed[key]!=data[key]: raise ValueError('Runtime fingerprint changed: '+key)
    try:
        subprocess.run([sys.executable,'-m','pip','check'],check=True,capture_output=True,text=True)
    except subprocess.CalledProcessError as exc:
        if exc.stdout: print(exc.stdout,file=sys.stderr,flush=True)
        if exc.stderr: print(exc.stderr,file=sys.stderr,flush=True)
        raise
    if require_cuda:
        import torch
        if not torch.cuda.is_available(): raise RuntimeError('CUDA is unavailable; no CPU fallback')
        observed['gpu']=torch.cuda.get_device_name(0)
    return observed


def candidate_text(path, seen=None):
    """Expand relative candidate includes before moving the input next to locks."""
    path=Path(path).resolve(strict=True)
    seen=set() if seen is None else set(seen)
    if path in seen: raise ValueError('Requirements include cycle: '+str(path))
    seen.add(path); lines=[]
    for line in path.read_text(encoding='utf-8').splitlines():
        stripped=line.strip()
        if stripped.startswith('-r ') or stripped.startswith('--requirement '):
            lines.append(candidate_text(path.parent/stripped.split(None,1)[1],seen))
        else: lines.append(line)
    return '\n'.join(lines)+'\n'


def validate_cuda_build(value):
    if str(value).strip() not in ('12060','12.6','CUDA 12.6'):
        raise ValueError('Detectron2 CUDA build differs: '+str(value))


def resolve_lock(executable, requirements, output, run):
    run([executable,'-m','piptools','compile','--quiet','--generate-hashes',
         '--resolver=backtracking','--output-file',output,requirements])


def _probe_json(command, clean):
    try:
        raw=subprocess.check_output(list(map(str,command)),env=clean,text=True,stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        if exc.output: print(exc.output,file=sys.stderr,flush=True)
        if exc.stderr: print(exc.stderr,file=sys.stderr,flush=True)
        raise
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError('Probe returned invalid JSON. Output:\n'+raw) from exc


def seal_environment(destination, executable, clean, actual, compiler, toolkit, wheel, combined):
    """Validate a staged receipt before publishing it; no installs or inference."""
    if (destination/'environment.json').exists(): raise FileExistsError('Environment receipt already exists')
    suffix=uuid.uuid4().hex[:12]
    integration_source=Path(__file__).resolve().parents[3]/'reconciliation_system'
    probe_prefix='import sys,json;sys.path.insert(0,'+repr(str(integration_source))+');from integration.dependencies import preflight;'
    integration_probe=None
    if combined:
        print('Checking integration dependencies before receipt publication',flush=True)
        observed_integration=_probe_json([executable,'-B','-c',probe_prefix+
            'print(json.dumps(preflight(require_shared_environment=False)))'],clean)
        integration_probe=destination/('integration-probe-'+suffix+'.json')
        _save(integration_probe,observed_integration)
    receipt={'source_url':D2_URL,'commit':actual,'compiler':compiler,'cuda_toolkit':toolkit,
             'torch':CANDIDATE['torch'],'wheel':wheel.name,'sha256':sha256(wheel)}
    if (destination/'reuse-receipt.json').is_file():
        receipt['reused_from_bundle']=json.loads((destination/'reuse-receipt.json').read_text(encoding='utf-8'))
    build_receipt=destination/('detectron2-build-'+suffix+'.json')
    _save(build_receipt,receipt)
    probe=destination/('runtime_probe-'+suffix+'.py')
    with probe.open('x',encoding='utf-8') as stream: stream.write(Path(__file__).read_text())
    print('Checking actual parser imports and CUDA build ABI',flush=True)
    observed=_probe_json([executable,probe,'_observe'],clean)
    artifacts=[destination/'requirements.lock',destination/'requirements-complete.lock',
               destination/'requirements-candidate.in',wheel,build_receipt,probe]
    if integration_probe is not None: artifacts.append(integration_probe)
    for name in ('reuse-receipt.json','source-environment.json'):
        if (destination/name).is_file():artifacts.append(destination/name)
    files={p.relative_to(destination).as_posix():{'bytes':p.stat().st_size,'sha256':sha256(p)} for p in artifacts}
    pending=destination/('environment.pending-'+suffix+'.json')
    _save(pending,dict(observed,status='imports-validated',artifacts=files,
                       checkpoint_validation='pending',gpu_validation='pending'))
    if combined:
        print('Checking strict integration with the staged shared receipt',flush=True)
        _probe_json([executable,'-B','-c',probe_prefix+
                     'print(json.dumps(preflight(manifest='+repr(str(pending))+')))'],clean)
    manifest=destination/'environment.json'
    # Linux: atomic no-clobber publication; leave staged evidence if validation fails.
    os.link(pending,manifest)
    pending.unlink()
    return manifest


def finalize(destination):
    """Seal an already-installed attempt; do not resolve, install or build again."""
    destination=Path(destination).resolve(strict=True)
    if Path(sys.prefix).resolve()!=(destination/'.venv').resolve():
        raise ValueError('Finalize must run with the installed destination venv Python')
    if platform.system()!='Linux': raise RuntimeError('Finalize requires Linux')
    if any(part.startswith('nasa-sic12-document-v1-env-') for part in destination.parts):
        raise ValueError('Cannot finalize a protected baseline')
    if (destination/'environment.json').exists(): raise FileExistsError('Environment receipt already exists; use check')
    clean=dict(os.environ)
    for key in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'): clean.pop(key,None)
    clean['PYTHONNOUSERSITE']='1'
    required=['requirements.lock','requirements-complete.lock','requirements-candidate.in','requirements-complete.in']
    for name in required:
        if not (destination/name).is_file(): raise ValueError('Missing installed-attempt artifact: '+name)
    package=Path(__file__).resolve().parents[3]
    combined=package/'requirements.in'
    candidate=candidate_text(selected_requirements(package))
    if (destination/'requirements-candidate.in').read_text(encoding='utf-8')!=candidate:
        raise ValueError('Candidate changed since installation; finalize is not a reinstall')
    built=list((destination/'wheels').glob('detectron2-*.whl'))
    if len(built)!=1: raise ValueError('Expected one preserved Detectron2 wheel')
    wheel=built[0]
    lock=(destination/'requirements-complete.lock').read_text(encoding='utf-8')
    if '--hash=sha256:'+sha256(wheel) not in lock:
        raise ValueError('Preserved Detectron2 wheel does not match final lock')
    if (destination/'reuse-receipt.json').is_file():
        from .environment_bundle import validate_bundle
        reused=json.loads((destination/'reuse-receipt.json').read_text(encoding='utf-8'))
        bundle_root=Path(reused['bundle_path'])
        if sha256(bundle_root/'bundle.json')!=reused['bundle_sha256']:
            raise ValueError('Source reuse bundle changed')
        _,build=validate_bundle(bundle_root,check_candidate=not reused.get('build_only',False))
        if sha256(wheel)!=build['sha256']:raise ValueError('Reused wheel changed')
        actual,compiler,toolkit=build['commit'],build['compiler'],build['cuda_toolkit']
    else:
        source=destination/'detectron2-source'
        actual=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],env=clean,text=True).strip()
        if actual!=D2_COMMIT: raise ValueError('Detectron2 source revision differs')
        compiler=subprocess.check_output(['c++','--version'],env=clean,text=True)
        toolkit=subprocess.check_output(['/usr/local/cuda-12.6/bin/nvcc','--version'],env=clean,text=True)
    if 'release 12.6' not in toolkit: raise ValueError('CUDA toolkit 12.6 required')
    subprocess.run([sys.executable,'-m','pip','check'],env=clean,check=True)
    return seal_environment(destination,Path(sys.executable),clean,actual,compiler,toolkit,wheel,combined.is_file() and os.environ.get('NASA_ENV_PROFILE','both')=='both')


def prepare(destination: Path, python: Path, detectron2_source=None, detectron2_commit=D2_COMMIT, build_bundle=None):
    destination=Path(destination).resolve()
    if any(part.startswith('nasa-sic12-document-v1-env-') for part in destination.parts):
        raise ValueError('Destination is inside a protected baseline environment')
    if destination.exists(): raise ValueError('Destination must be new')
    if platform.system()!='Linux': raise RuntimeError('Explicit installation requires Linux/WSL')
    if not re.fullmatch('[0-9a-f]{40}',detectron2_commit): raise ValueError('Full source commit required')
    clean=dict(os.environ)
    for key in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'): clean.pop(key,None)
    clean['PYTHONNOUSERSITE']='1'
    if build_bundle:
        from .environment_bundle import validate_bundle
        bundle_data,bundle_build=validate_bundle(build_bundle,check_candidate=False)
    version=subprocess.check_output([str(python),'-c','import platform;print(platform.python_version())'],env=clean,text=True).strip()
    if version!=PYTHON_VERSION: raise ValueError('Installer Python must be '+PYTHON_VERSION)
    destination.mkdir(parents=True,exist_ok=False)
    log=destination/'install.log'
    def run(args, **kwargs):
        with log.open('a',encoding='utf-8') as output:
            output.write('\n+ '+shlex.join(list(map(str,args)))+'\n')
            output.flush()
            subprocess.run(list(map(str,args)),env=clean,stdout=output,stderr=subprocess.STDOUT,check=True,**kwargs)
    try:
        venv=destination/'.venv'; run([python,'-m','venv',venv]); executable=venv/'bin/python'
        run([executable,'-m','pip','install','pip==25.1.1','pip-tools==7.5.1','setuptools==80.9.0','wheel==0.45.1'])
        package=Path(__file__).resolve().parents[3]
        combined=package/'requirements.in'
        requirements=destination/'requirements-candidate.in'
        requirements.write_text(candidate_text(selected_requirements(package)),encoding='utf-8')
        lock=destination/'requirements.lock'
        resolve_lock(executable,requirements,lock,run)
        run([executable,'-m','pip','install','--require-hashes','-r',lock])
        if build_bundle:
            source_bundle=Path(build_bundle).resolve(strict=True)
            wheel=destination/bundle_data['wheel'];wheel.parent.mkdir(parents=True,exist_ok=True)
            import shutil
            shutil.copy2(source_bundle/bundle_data['wheel'],wheel)
            wheels=wheel.parent
            actual,compiler,toolkit=bundle_build['commit'],bundle_build['compiler'],bundle_build['cuda_toolkit']
            source_receipt=source_bundle/bundle_data.get('source_receipt','source-environment.json')
            shutil.copy2(source_receipt,destination/'source-environment.json')
            _save(destination/'reuse-receipt.json',dict(build_only=True,bundle_path=str(source_bundle),
                  bundle_sha256=sha256(source_bundle/'bundle.json'),source_environment_sha256=sha256(source_receipt)))
        else:
            # A fresh checkout/build even when a verified local repository is provided.
            source=destination/'detectron2-source'
            run(['git','clone',str(detectron2_source or D2_URL),source])
            run(['git','-C',source,'checkout','--detach',detectron2_commit])
            actual=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],env=clean,text=True).strip()
            if actual!=detectron2_commit: raise ValueError('Detectron2 source identity mismatch')
            compiler=subprocess.check_output(['c++','--version'],env=clean,text=True)
            toolkit=subprocess.check_output(['nvcc','--version'],env=clean,text=True)
            if 'release 12.6' not in toolkit: raise ValueError('CUDA toolkit 12.6 required for build')
            wheels=destination/'wheels'; wheels.mkdir()
            # Build uses installed common Torch, never a build-isolation Torch.
            clean['FORCE_CUDA']='1'
            clean.setdefault('MAX_JOBS','2')
            run([executable,'-m','pip','wheel','--no-deps','--no-build-isolation','--wheel-dir',wheels,source])
            built=list(wheels.glob('detectron2-*.whl'))
            if len(built)!=1: raise ValueError('Expected exactly one Detectron2 wheel')
            wheel=built[0]
        # Resolve D2's metadata and all dependencies into the final hashed lock.
        full=destination/'requirements-complete.in'
        full.write_text(requirements.read_text()+'\ndetectron2 @ '+wheel.as_uri()+'\n',encoding='utf-8')
        final_lock=destination/'requirements-complete.lock'
        resolve_lock(executable,full,final_lock,run)
        run([executable,'-m','pip','install','--require-hashes','-r',final_lock])
        run([executable,'-m','pip','check'])
        return seal_environment(destination,executable,clean,actual,compiler,toolkit,wheel,combined.is_file() and os.environ.get('NASA_ENV_PROFILE','both')=='both')
    except Exception as exc:
        _save(destination/'failed.json',{'status':'failed','error':repr(exc)})
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare'); prep.add_argument('--destination',type=Path,required=True)
    prep.add_argument('--python',type=Path,required=True)
    prep.add_argument('--detectron2-source',type=Path)
    prep.add_argument('--build-bundle',type=Path,help='Verified compatible Detectron2 build; resolve current profile independently')
    prep.add_argument('--detectron2-commit',default=D2_COMMIT)
    finish=sub.add_parser('finalize'); finish.add_argument('--destination',type=Path,required=True)
    export=sub.add_parser('export'); export.add_argument('--destination',type=Path,required=True)
    export.add_argument('--output',type=Path,required=True)
    reuse=sub.add_parser('reuse'); reuse.add_argument('--destination',type=Path,required=True)
    reuse.add_argument('--python',type=Path,required=True); reuse.add_argument('--bundle',type=Path,required=True)
    check=sub.add_parser('check'); check.add_argument('--manifest',type=Path,required=True)
    check.add_argument('--no-cuda',action='store_true')
    sub.add_parser('_observe')
    args=parser.parse_args(argv)
    if args.command=='_observe': print(json.dumps(_observed())); return 0
    if args.command=='prepare': print(prepare(args.destination,args.python,args.detectron2_source,args.detectron2_commit,args.build_bundle)); return 0
    if args.command=='finalize': print(finalize(args.destination)); return 0
    if args.command=='export':
        from .environment_bundle import export_bundle
        print(export_bundle(args.destination,args.output)); return 0
    if args.command=='reuse':
        from .environment_bundle import restore_bundle
        print(restore_bundle(args.destination,args.python,args.bundle)); return 0
    print(json.dumps(check_runtime(args.manifest,not args.no_cuda),indent=2)); return 0

if __name__=='__main__': raise SystemExit(main())
