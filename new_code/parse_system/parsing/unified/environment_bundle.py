"""Export/reuse a validated environment's locks and wheel, never its venv."""
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from email.parser import Parser
from . import environment as env


def host_fingerprint():
    release=platform.freedesktop_os_release()
    caps=subprocess.check_output(['nvidia-smi','--query-gpu=compute_cap','--format=csv,noheader'],text=True)
    return {'system':platform.system(),'machine':platform.machine(),
            'python':platform.python_version(),'os':[release['ID'],release['VERSION_ID']],
            'libc':list(platform.libc_ver()),'compute_caps':sorted(set(caps.split()))}


def require_compatible(expected, actual):
    for key in ('system','machine','python','os','libc','compute_caps'):
        if key not in expected or expected[key]!=actual.get(key):
            raise ValueError('Bundle host compatibility differs: '+key)


def require_build(receipt, wheel_name, digest):
    if (receipt.get('commit')!=env.D2_COMMIT or receipt.get('torch')!=env.CANDIDATE['torch']
            or receipt.get('wheel')!=wheel_name or receipt.get('sha256')!=digest):
        raise ValueError('Detectron2 build identity differs')


def relocate_lock(text, original_url, new_url, digest):
    logical=re.sub(r'\\\r?\n',' ',text)
    matches=list(re.finditer(r'^detectron2\s*@\s*(\S+)(.*)$',logical,re.M))
    if (len(matches)!=1 or matches[0][1]!=original_url
            or '--hash=sha256:'+digest not in matches[0][2].split()):
        raise ValueError('Expected exact Detectron2 wheel URL and hash in lock')
    active='\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#'))
    if any(url!=original_url for url in re.findall(r'file://[^\s\\]+',active)):
        raise ValueError('Unexpected local file dependency in lock')
    return text.replace(original_url,new_url)


def read_bundle(root):
    root=Path(root).resolve(strict=True)
    value=json.loads((root/'bundle.json').read_text(encoding='utf-8'))
    if value.get('schema')!='shared-environment-bundle/1':
        raise ValueError('Unsupported environment bundle schema')
    env.verify_files(root,value['files'])
    return value


def validate_bundle(root, *, check_host=True, check_candidate=True):
    root=Path(root).resolve(strict=True)
    data=read_bundle(root)
    if check_host:require_compatible(data['host'],host_fingerprint())
    package=Path(__file__).resolve().parents[3]
    candidate=env.candidate_text(env.selected_requirements(package))
    if check_candidate and (root/'requirements-candidate.in').read_text(encoding='utf-8')!=candidate:
        raise ValueError('Current requirements differ from exported candidate')
    source_name=data.get('source_receipt','source-environment.json')
    if source_name not in data['files']:raise ValueError('Source receipt is not verified')
    source=json.loads((root/source_name).read_text(encoding='utf-8'))
    if source.get('status')!='imports-validated' or source.get('python')!=env.PYTHON_VERSION:
        raise ValueError('Source environment was not validated')
    env.verify_files(root,source['artifacts'])
    for key in ('wheel','build_receipt'):
        if data[key] not in data['files']:
            raise ValueError('Bundle metadata references unverified file: '+key)
    wheel=root/data['wheel']
    build=json.loads((root/data['build_receipt']).read_text(encoding='utf-8'))
    require_build(build,wheel.name,env.sha256(wheel))
    relocate_lock((root/'requirements-complete.lock').read_text(encoding='utf-8'),
                  data['source_wheel_uri'],wheel.as_uri(),build['sha256'])
    return data,build


def preserve_built_wheels(cache, output, source, lock):
    """Keep only cached wheels matching installed versions and locked source hashes."""
    names=[]
    cache=Path(cache)
    for wheel in sorted((cache/'wheels').rglob('*.whl')):
        if wheel.name.startswith('detectron2-'):continue  # already preserved as the primary wheel
        origin_path=wheel.parent/'origin.json'
        if not origin_path.is_file():continue
        with zipfile.ZipFile(wheel) as archive:
            metadata_names=[name for name in archive.namelist() if name.endswith('.dist-info/METADATA')]
            if len(metadata_names)!=1:raise ValueError('Invalid cached wheel metadata')
            info=Parser().parsestr(archive.read(metadata_names[0]).decode('utf-8'))
        name=re.sub(r'[-_.]+','-',info['Name']).lower()
        version=info['Version']
        if source['versions'].get(name)!=version:continue
        origin=json.loads(origin_path.read_text(encoding='utf-8'))['archive_info']
        digest=origin.get('hashes',{}).get('sha256')
        if not digest and origin.get('hash','').startswith('sha256='):digest=origin['hash'][7:]
        logical=re.sub(r'\\\r?\n',' ',lock)
        entry=re.search(r'^'+re.escape(name+'=='+version)+r'\s+(.*)$',logical,re.M)
        if not digest or not entry or '--hash=sha256:'+digest not in entry[1].split():
            raise ValueError('Cached wheel source is not in frozen lock: '+wheel.name)
        for path in (wheel,origin_path):
            relative=Path('wheel-cache')/path.relative_to(cache)
            target=output/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target);names.append(relative.as_posix())
        print('Preserved compiled cache wheel: '+wheel.name,flush=True)
    return names


def seed_wheel_cache(root, data, cache):
    root=Path(root);cache=Path(cache).resolve()
    for name in data.get('cache_files',[]):
        if name not in data['files'] or not name.startswith('wheel-cache/wheels/'):
            raise ValueError('Unverified wheel cache member')
        target=cache/Path(name).relative_to('wheel-cache')
        if not target.resolve().is_relative_to(cache):raise ValueError('Cache member escapes target')
        expected=data['files'][name]
        if target.exists():
            if target.stat().st_size!=expected['bytes'] or env.sha256(target)!=expected['sha256']:
                raise ValueError('Existing wheel cache differs: '+str(target))
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(root/name,target)


def export_bundle(destination, output):
    destination=Path(destination).resolve(strict=True)
    output=Path(output).resolve()
    archive=output.with_name(output.name+'.tar.gz')
    if output.exists() or archive.exists():raise FileExistsError('Export destination must be new')
    print('Validating installed environment before export',flush=True)
    env.check_runtime(destination/'environment.json',require_cuda=True)
    source=json.loads((destination/'environment.json').read_text(encoding='utf-8'))
    names=list(source['artifacts'])
    wheels=[name for name in names if name.startswith('wheels/detectron2-') and name.endswith('.whl')]
    builds=[name for name in names if name.startswith('detectron2-build-') and name.endswith('.json')]
    if len(wheels)!=1 or len(builds)!=1:raise ValueError('Expected one verified wheel and build receipt')
    wheel=destination/wheels[0]
    build=json.loads((destination/builds[0]).read_text(encoding='utf-8'))
    require_build(build,wheel.name,env.sha256(wheel))
    relocate_lock((destination/'requirements-complete.lock').read_text(encoding='utf-8'),
                  wheel.as_uri(),wheel.as_uri(),build['sha256'])
    output.mkdir(parents=True,exist_ok=False)
    for name in names:
        target=output/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(destination/name,target)
    source_name='bundle-source-environment.json'
    if source_name in names:raise ValueError('Reserved bundle receipt name collision')
    shutil.copy2(destination/'environment.json',output/source_name)
    names.append(source_name)
    cache_files=preserve_built_wheels(os.environ.get('PIP_CACHE_DIR',destination.parent/'pip-cache'),
                                      output,source,(destination/'requirements-complete.lock').read_text(encoding='utf-8'))
    names.extend(cache_files)
    data={'schema':'shared-environment-bundle/1','host':host_fingerprint(),
          'source_receipt':source_name,
          'cache_files':cache_files,
          'wheel':wheels[0],'build_receipt':builds[0],'source_wheel_uri':wheel.as_uri(),
          'files':{name:{'bytes':(output/name).stat().st_size,'sha256':env.sha256(output/name)} for name in names}}
    env._save(output/'bundle.json',data)
    validate_bundle(output)
    with archive.open('xb') as stream, tarfile.open(fileobj=stream,mode='w:gz') as tar:
        for name in names+['bundle.json']:
            tar.add(output/name,arcname=output.name+'/'+name,recursive=False)
    digest=env.sha256(archive)
    archive.with_name(archive.name+'.sha256').write_text(digest+'  '+archive.name+'\n',encoding='utf-8')
    print('Exported: '+str(archive)+'\nSHA256: '+digest,flush=True)
    return archive


def restore_bundle(destination, python, bundle_root):
    destination=Path(destination).resolve()
    bundle_root=Path(bundle_root).resolve(strict=True)
    if destination.exists():raise FileExistsError('Restore destination must be new')
    if any(part.startswith('nasa-sic12-document-v1-env-') for part in destination.parts):
        raise ValueError('Cannot overwrite protected baseline')
    if platform.system()!='Linux':raise RuntimeError('Reuse requires Linux')
    data,build=validate_bundle(bundle_root)
    # CLI runs this module with the managed installation interpreter.
    version=subprocess.check_output([str(python),'-c','import platform;print(platform.python_version())'],text=True).strip()
    if version!=env.PYTHON_VERSION:raise ValueError('Wrong target Python version')
    clean=dict(os.environ)
    for key in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'):clean.pop(key,None)
    clean['PYTHONNOUSERSITE']='1'
    cache=Path(clean.get('PIP_CACHE_DIR',destination.parent/'pip-cache')).resolve()
    clean['PIP_CACHE_DIR']=str(cache)
    seed_wheel_cache(bundle_root,data,cache)
    destination.mkdir(parents=True,exist_ok=False)
    log=destination/'install.log'
    def run(command):
        with log.open('a',encoding='utf-8') as stream:
            stream.write('\n+ '+env.shlex.join(list(map(str,command)))+'\n');stream.flush()
            subprocess.run(list(map(str,command)),env=clean,stdout=stream,stderr=subprocess.STDOUT,check=True)
    try:
        wheel=destination/data['wheel'];wheel.parent.mkdir(parents=True)
        shutil.copy2(bundle_root/data['wheel'],wheel)
        for name in ('requirements.lock','requirements-candidate.in'):
            shutil.copy2(bundle_root/name,destination/name)
        lock=relocate_lock((bundle_root/'requirements-complete.lock').read_text(encoding='utf-8'),
                           data['source_wheel_uri'],wheel.as_uri(),build['sha256'])
        (destination/'requirements-complete.lock').write_text(lock,encoding='utf-8')
        (destination/'requirements-complete.in').write_text(
            (destination/'requirements-candidate.in').read_text(encoding='utf-8')+
            '\ndetectron2 @ '+wheel.as_uri()+'\n',encoding='utf-8')
        # Preserve the original validated source; never pretend a new build occurred.
        source_receipt=bundle_root/data.get('source_receipt','source-environment.json')
        shutil.copy2(source_receipt,destination/'source-environment.json')
        provenance={'bundle_path':str(bundle_root),'bundle_sha256':env.sha256(bundle_root/'bundle.json'),
                    'source_build':build,'source_environment_sha256':env.sha256(source_receipt)}
        env._save(destination/'reuse-receipt.json',provenance)
        executable=destination/'.venv/bin/python'
        run([python,'-m','venv',destination/'.venv'])
        run([executable,'-m','pip','install','--no-deps','--require-hashes','-r',destination/'requirements-complete.lock'])
        run([executable,'-m','pip','check'])
        return env.seal_environment(destination,executable,clean,build['commit'],build['compiler'],
                                    build['cuda_toolkit'],wheel,os.environ.get('NASA_ENV_PROFILE','both')=='both')
    except Exception as exc:
        env._save(destination/'failed.json',{'status':'failed','error':repr(exc),'mode':'reuse'})
        raise
