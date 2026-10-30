"""Integrator-only environment: hashed locks and validated reusable bundles, no models."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
from .dependencies import preflight, digest, SHARED_PYTHON, PINS


def candidate():
    root=Path(__file__).resolve().parents[1]
    def expand(path, seen):
        path=path.resolve(strict=True)
        if path in seen or not path.is_relative_to(root):raise ValueError('Unsafe integrator requirements include')
        lines=[]
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip().startswith(('-r ','--requirement ')):
                lines.append(expand(path.parent/line.strip().split(None,1)[1],seen|{path}))
            else:lines.append(line)
        return '\n'.join(lines)+'\n'
    return expand(root/'requirements.in',set())


def host():
    release=platform.freedesktop_os_release()
    return dict(system=platform.system(),machine=platform.machine(),python=SHARED_PYTHON,
                os=[release['ID'],release['VERSION_ID']],libc=list(platform.libc_ver()))


def verify_files(root, records):
    if not records:raise ValueError('Empty environment artifact inventory')
    for name,record in records.items():
        path=(Path(root)/name).resolve(strict=True)
        if not path.is_relative_to(Path(root).resolve()) or path.stat().st_size!=record['bytes'] or digest(path)!=record['sha256']:
            raise ValueError('Environment artifact differs: '+name)


def validate_bundle(root, check_host=True):
    root=Path(root).resolve(strict=True);data=json.loads((root/'bundle.json').read_text())
    if data.get('schema')!='integration-environment-bundle/1':raise ValueError('Integrator bundle required')
    verify_files(root,data['files'])
    if check_host and data['host']!=host():raise ValueError('Integrator bundle host differs')
    if (root/'requirements-candidate.in').read_text()!=candidate():raise ValueError('Integrator requirements changed')
    source_name=data['source_receipt']
    if source_name not in data['files']:raise ValueError('Unverified source environment')
    source=json.loads((root/source_name).read_text())
    if source.get('schema')!='integration-environment/1' or source.get('status')!='imports-validated' or source.get('python')!=SHARED_PYTHON:
        raise ValueError('Invalid integrator bundle source receipt')
    for name,pin in PINS.items():
        if source['versions'].get(name.lower().replace('_','-'))!=pin:raise ValueError('Integrator source pin differs: '+name)
    verify_files(root,source['artifacts'])
    return data


def seal(destination):
    destination=Path(destination).resolve(strict=True)
    if Path(sys.prefix).resolve()!=(destination/'.venv').resolve():raise ValueError('Seal with destination Python')
    if (destination/'requirements-candidate.in').read_text()!=candidate():raise ValueError('Integrator candidate changed')
    observed=preflight(require_shared_environment=False)
    if observed['python']!=SHARED_PYTHON:raise ValueError('Wrong integrator Python')
    if any(not Path(v['path']).is_relative_to(Path(sys.prefix).resolve()) for v in observed['imports'].values()):raise ValueError('Integrator import outside venv')
    from importlib import metadata
    value=dict(schema='integration-environment/1',status='imports-validated',python=SHARED_PYTHON,
               prefix=str(Path(sys.prefix).resolve()),executable=str(Path(sys.executable).absolute()),
               versions={d.metadata['Name'].lower().replace('_','-'):d.version for d in metadata.distributions()},
               imports=observed['imports'],artifacts={n:dict(bytes=(destination/n).stat().st_size,sha256=digest(destination/n)) for n in ('requirements-candidate.in','requirements-complete.lock')})
    path=destination/'environment.json'
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2)
    preflight(profile='integrator')
    return path


def prepare(destination, python, bundle=None):
    destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError('Integrator environment destination exists')
    if platform.system()!='Linux':raise RuntimeError('Integrator installation requires Linux')
    clean=dict(os.environ)
    for name in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'):clean.pop(name,None)
    clean['PYTHONNOUSERSITE']='1'
    def run(args):
        with (destination/'install.log').open('a') as stream:
            subprocess.run(list(map(str,args)),env=clean,stdout=stream,stderr=subprocess.STDOUT,check=True)
    if bundle:validate_bundle(bundle)
    destination.mkdir(parents=True)
    executable=destination/'.venv/bin/python'
    run([python,'-m','venv',destination/'.venv'])
    (destination/'requirements-candidate.in').write_text(candidate(),encoding='utf-8')
    lock=destination/'requirements-complete.lock'
    if bundle:
        shutil.copy2(Path(bundle)/lock.name,lock)
    else:
        run([executable,'-m','pip','install','pip==25.1.1','pip-tools==7.5.1','setuptools==80.9.0','wheel==0.45.1'])
        run([executable,'-m','piptools','compile','--generate-hashes','--resolver=backtracking','--output-file',lock,destination/'requirements-candidate.in'])
    run([executable,'-m','pip','install','--no-deps','--require-hashes','-r',lock])
    run([executable,'-m','pip','check'])
    code='import sys;sys.path.insert(0,'+repr(str(Path(__file__).resolve().parents[1]))+');from integration.environment import seal;seal('+repr(str(destination))+')'
    run([executable,'-B','-c',code])


def export_bundle(destination, output):
    destination=Path(destination).resolve();output=Path(output).resolve()
    preflight(profile='integrator')
    archive=output.with_name(output.name+'.tar.gz')
    if output.exists() or archive.exists():raise FileExistsError('Bundle destination exists')
    output.mkdir(parents=True)
    names=['requirements-candidate.in','requirements-complete.lock']
    for name in names:shutil.copy2(destination/name,output/name)
    shutil.copy2(destination/'environment.json',output/'source-environment.json');names.append('source-environment.json')
    data=dict(schema='integration-environment-bundle/1',source_receipt='source-environment.json',host=host(),
              files={n:dict(bytes=(output/n).stat().st_size,sha256=digest(output/n)) for n in names})
    (output/'bundle.json').write_text(json.dumps(data,indent=2))
    validate_bundle(output)
    with tarfile.open(archive,'x:gz') as tar:
        for name in names+['bundle.json']:tar.add(output/name,arcname=output.name+'/'+name,recursive=False)
    archive.with_name(archive.name+'.sha256').write_text(digest(archive)+'  '+archive.name+'\n')
    return archive


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','check','export'))
    parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--python',type=Path)
    parser.add_argument('--bundle',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    if args.command=='prepare':prepare(args.destination,args.python,args.bundle)
    elif args.command=='check':print(json.dumps(preflight(profile='integrator')))
    else:export_bundle(args.destination,args.output)


if __name__=='__main__':main()
