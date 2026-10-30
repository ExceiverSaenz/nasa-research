#!/usr/bin/env python3
"""Prepare the shared hybrid environment on the GPU host, without inference.

Run INSIDE the Colab VM (not on the Ubuntu machine controlling Colab CLI).
Python/uv/caches/logs stay under new_code/runtime. APT installs system build
dependencies and CUDA toolkit only; it never requests an NVIDIA driver.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parent
PYTHON_VERSION = '3.11.16'
UV_VERSION = '0.12.21'
CUDA_VERSION = '12.6'


def validate_destination(destination, root=ROOT):
    destination = Path(destination).resolve()
    root = Path(root).resolve()
    if not destination.is_relative_to(root) or destination == root:
        raise ValueError('Environment destination must be inside new_code')
    if destination.exists():
        raise ValueError('Destination exists; use --check or select a new --destination')
    if (destination.parent != root / 'runtime'
            or destination.name in ('python', 'uv-cache', 'pip-cache', '.setup.lock')
            or destination.name.startswith('setup-')):
        raise ValueError('Destination must be a new direct child inside new_code/runtime, excluding setup/cache paths')
    return destination


def validate_apt_transaction(output):
    for line in output.splitlines():
        if line.startswith('Remv '):
            raise RuntimeError('APT proposes a removal; refusing this transaction: ' + line)
        if line.startswith('Inst '):
            name = line.split()[1].split(':')[0]
            if (name.startswith(('nvidia-', 'libnvidia-', 'cuda-drivers', 'linux-modules-nvidia'))
                    or name in ('cuda', 'cuda-12-6', 'cuda-runtime-12-6')):
                raise RuntimeError('APT proposes a driver/runtime installation: ' + line)


def plan(destination, mode='install', profile='both'):
    result = {'python': PYTHON_VERSION, 'cuda_toolkit': CUDA_VERSION, 'mode': mode,
            'uv': UV_VERSION, 'destination': str(destination),
            'requirements': str(ROOT / 'requirements.in'),
            'installs_driver': False, 'runs_inference': False,
            'downloads_model_weights': False,
            'steps': ['Check Ubuntu/x86_64 and an accessible NVIDIA GPU',
                      'Install APT build prerequisites and missing CUDA 12.6 toolkit',
                      'Install isolated uv and managed Python 3.11.16',
                      'Run existing shared installer (locks, Detectron2, imports)',
                      'Check shared environment with CUDA enabled']}
    result['profile']=profile
    if profile=='parser':result['requirements']=str(ROOT/'parse_system/parsing/unified/requirements.in')
    if profile=='integrator':
        result.update(cuda_toolkit=None,requirements=str(ROOT/'reconciliation_system/requirements.in'),
                      steps=['Check Ubuntu/x86_64', 'Prepare Python 3.11.16 and minimal system runtime',
                             'Resolve or reuse integrator hashed lock', 'Validate integrator imports, pins and receipt'])
        return result
    if mode == 'finalize':
        result['steps'] = ['Validate installed attempt and stage shared receipt',
                           'Validate strict integration and publish receipt',
                           'Check shared environment with CUDA enabled']
    elif mode == 'check':
        result['steps'] = ['Check shared environment with CUDA enabled']
    elif mode == 'export':
        result['steps'] = ['Validate installed environment', 'Export locks, wheel, hashes and host compatibility']
    elif mode == 'reuse-build':
        result['steps']=['Validate cached Detectron2 wheel and host ABI', 'Prepare Python and system runtime',
                         'Resolve profile dependencies; reuse verified Detectron2 build', 'Check parser imports and CUDA']
    elif mode == 'reuse':
        result['steps'] = ['Verify bundle hashes, requirements and host compatibility',
                           'Prepare Python and system runtime prerequisites',
                           'Install frozen lock and existing Detectron2 wheel',
                           'Check imports, integration and CUDA']
    return result


class Runner:
    def __init__(self, logfile, env, heartbeat=10):
        self.logfile, self.env = logfile, env
        self.heartbeat = heartbeat

    def run(self, argv, watch_log=None, stage=None):
        argv = list(map(str, argv))
        stage = stage or ' '.join([Path(argv[0]).name] + argv[1:3])
        print('+ ' + shlex.join(argv), flush=True)
        chunks = []
        with self.logfile.open('a', encoding='utf-8') as log:
            log.write('\n+ ' + shlex.join(argv) + '\n')
            log.flush()
            with subprocess.Popen(argv, env=self.env, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True,
                                  encoding='utf-8', errors='replace') as process:
                messages = queue.Queue()
                def read_output():
                    try:
                        for line in process.stdout:
                            messages.put(line)
                    finally:
                        messages.put(None)
                reader = threading.Thread(target=read_output, daemon=True)
                reader.start()
                start = last_output = time.monotonic()
                offset = 0
                eof = False

                def display(text):
                    nonlocal last_output
                    print(text, end='', flush=True)
                    log.write(text)
                    log.flush()
                    last_output = time.monotonic()

                def tail_install_log():
                    nonlocal offset
                    if watch_log is not None and Path(watch_log).is_file():
                        with Path(watch_log).open('r', encoding='utf-8', errors='replace') as nested:
                            nested.seek(offset)
                            text = nested.read()
                            offset = nested.tell()
                        if text:
                            display(text)

                while True:
                    try:
                        line = messages.get(timeout=min(self.heartbeat, .25))
                    except queue.Empty:
                        line = ''
                    tail_install_log()
                    if line is None:
                        eof = True
                    if eof and process.poll() is not None:
                        break
                    if line:
                        display(line)
                        chunks.append(line)
                    if time.monotonic() - last_output >= self.heartbeat:
                        display('[Still running: ' + stage + '; elapsed '
                                + str(int(time.monotonic() - start)) + 's]\n')
                code = process.wait()
                reader.join()
                tail_install_log()
        output = ''.join(chunks)
        if code:
            raise subprocess.CalledProcessError(code, argv, output=output)
        return output


def platform_check(require_gpu=True):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise RuntimeError('Run inside an x86_64 Linux Colab GPU VM')
    release = {}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            release[key] = value.strip('"')
    if release.get('ID') != 'ubuntu' or release.get('VERSION_ID') not in ('22.04', '24.04'):
        raise RuntimeError('Supported GPU hosts: Ubuntu 22.04 or 24.04; found ' + str(release))
    if require_gpu and not shutil.which('nvidia-smi'):
        raise RuntimeError('NVIDIA GPU/driver not accessible. Assign a GPU VM in Colab first.')
    return release['VERSION_ID']


def integrator_command(python, action, destination, *extra):
    argv=[action,'--destination',str(destination)]+list(map(str,extra))
    code='import sys;sys.path.insert(0,'+repr(str(ROOT/'reconciliation_system'))+');from integration.environment import main;main('+repr(argv)+')'
    return [python,'-B','-c',code]


def check_environment(destination, run):
    python = destination / '.venv/bin/python'
    manifest = destination / 'environment.json'
    if run.env.get('NASA_ENV_PROFILE')=='integrator':
        run.run(integrator_command(python,'check',destination));return
    run.run([python, '-B', ROOT / 'parse_system/run.py', 'environment', 'check',
             '--manifest', manifest])


def bootstrap_interpreter(ubuntu):
    versions = {'22.04': '3.10', '24.04': '3.12'}
    if ubuntu not in versions:
        raise ValueError('Unsupported Ubuntu bootstrap: ' + ubuntu)
    return Path('/usr/bin/python' + versions[ubuntu])


def create_bootstrap(attempt, run, ubuntu):
    # Colab may replace /usr/bin/python3 with a newer Python without ensurepip.
    # Use the explicitly versioned interpreter matching the APT venv package.
    python = bootstrap_interpreter(ubuntu)
    run.run([python, '-c', 'import sys,ensurepip;print(sys.version);print("ensurepip:",ensurepip.version())'],
            stage='Check Ubuntu bootstrap Python and ensurepip')
    bootstrap = attempt / 'bootstrap'
    run.run([python, '-m', 'venv', bootstrap], stage='Create bootstrap venv with Ubuntu Python')
    return bootstrap


def ubuntu_apt_options(ubuntu):
    sources={'24.04':'/etc/apt/sources.list.d/ubuntu.sources','22.04':'/etc/apt/sources.list'}
    if ubuntu not in sources:raise ValueError('Unsupported Ubuntu sources')
    # Read the existing signed distro sources without editing any APT settings.
    # Runtime prerequisites do not depend on third-party CUDA/R/CLI repositories.
    return ['-o','Dir::Etc::sourcelist='+sources[ubuntu],'-o','Dir::Etc::sourceparts=-']


def install(destination, attempt, run, ubuntu, reuse_bundle=None, build_bundle=None):
    sudo = [] if os.geteuid() == 0 else ['sudo']
    if sudo:
        run.run(['sudo', '-v'])
    apt = sudo + ['apt-get']
    apt_options=ubuntu_apt_options(ubuntu)

    def apt_install(packages):
        preview = run.run(apt + apt_options + ['--simulate', '--no-remove', '--no-install-recommends',
                                 'install'] + packages)
        validate_apt_transaction(preview)
        run.run(apt + apt_options + ['-y', '--no-remove', '--no-install-recommends', 'install'] + packages)

    run.run(apt + apt_options + ['update'])
    bootstrap_name = bootstrap_interpreter(ubuntu).name
    prerequisites=['ca-certificates',bootstrap_name,bootstrap_name+'-venv','libgl1','libglib2.0-0','libgomp1']
    integration_only=run.env.get('NASA_ENV_PROFILE')=='integrator'
    if reuse_bundle is None and build_bundle is None and not integration_only:prerequisites+=['git','build-essential','ninja-build','pkg-config']
    apt_install(prerequisites)
    cuda = Path('/usr/local/cuda-12.6')
    if not integration_only and reuse_bundle is None and build_bundle is None and not (cuda / 'bin/nvcc').is_file():
        repo = 'ubuntu' + ubuntu.replace('.', '')
        url = ('https://developer.download.nvidia.com/compute/cuda/repos/' + repo
               + '/x86_64/cuda-keyring_1.1-1_all.deb')
        keyring = attempt / 'cuda-keyring_1.1-1_all.deb'
        print('Downloading NVIDIA repository keyring: ' + url, flush=True)
        download_code = ('import urllib.request,shutil,sys;'
                         'source=urllib.request.urlopen(sys.argv[1],timeout=120);'
                         'target=open(sys.argv[2],"xb");shutil.copyfileobj(source,target);'
                         'target.close();source.close();print("NVIDIA keyring downloaded",flush=True)')
        run.run([sys.executable, '-u', '-c', download_code, url, keyring],
                stage='Download NVIDIA CUDA repository keyring')
        run.run(sudo + ['dpkg', '-i', keyring])
        apt_options=[]  # CUDA toolkit is explicitly required only for a fresh build.
        run.run(apt + ['update'])
        apt_install(['cuda-toolkit-12-6'])
    if reuse_bundle is None and build_bundle is None and not integration_only:
        run.env['CUDA_HOME'] = str(cuda)
        run.env['PATH'] = str(cuda / 'bin') + os.pathsep + run.env.get('PATH', '')
        if 'release 12.6' not in run.run([cuda / 'bin/nvcc', '--version']):
            raise RuntimeError('CUDA toolkit 12.6 is required')

    bootstrap = create_bootstrap(attempt, run, ubuntu)
    bootstrap_python = bootstrap / 'bin/python'
    run.run([bootstrap_python, '-m', 'pip', 'install', '--index-url',
             'https://pypi.org/simple', 'uv==' + UV_VERSION])
    uv = bootstrap / 'bin/uv'
    run.env['UV_PYTHON_INSTALL_DIR'] = str(ROOT / 'runtime/python')
    run.env['UV_CACHE_DIR'] = str(ROOT / 'runtime/uv-cache')
    run.env.setdefault('PIP_CACHE_DIR',str(ROOT/'runtime/pip-cache'))
    run.run([uv, '--no-config', 'python', 'install', PYTHON_VERSION])
    # Capture only the executable, not the progress messages emitted by Runner.
    python_output = run.run([uv, '--no-config', 'python', 'find', '--managed-python', PYTHON_VERSION])
    python = Path(python_output.strip())
    if not python.is_file():
        raise RuntimeError('uv did not return a Python executable: ' + python_output)
    if integration_only:
        extra=['--python',python]+(['--bundle',reuse_bundle] if reuse_bundle else [])
        run.run(integrator_command(python,'prepare',destination,*extra),watch_log=destination/'install.log',stage='Prepare integrator-only locked environment')
        check_environment(destination,run);return
    command=[python,'-B',ROOT/'parse_system/run.py','environment',
             'reuse' if reuse_bundle else 'prepare','--destination',destination,'--python',python]
    if reuse_bundle:command+=['--bundle',reuse_bundle]
    if build_bundle:command+=['--build-bundle',build_bundle]
    run.run(command,
            watch_log=destination / 'install.log',
            stage='Install frozen lock / reuse Detectron2' if reuse_bundle else 'Resolve packages / install shared environment / build Detectron2')
    check_environment(destination, run)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',choices=('parser','integrator','both'),default='both')
    parser.add_argument('--plan', action='store_true', help='Print plan without any writes/network/system calls')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='Check an existing installation without installing')
    mode.add_argument('--finalize', action='store_true', help='Validate and seal an installed attempt; no installs or builds')
    mode.add_argument('--export-bundle',type=Path,help='New output directory for validated locks and Detectron2 wheel')
    parser.add_argument('--reuse-build-bundle',type=Path,help='Reuse only a verified Detectron2 wheel, resolve current parser profile')
    parser.add_argument('--reuse-bundle',type=Path,help='Install a verified bundle without resolving or compiling')
    parser.add_argument('--pip-cache-dir',type=Path,default=ROOT/'runtime/pip-cache')
    parser.add_argument('--destination', type=Path, default=ROOT / 'runtime/environment')
    args = parser.parse_args(argv)
    destination = (ROOT / args.destination).resolve()
    if args.reuse_bundle and (args.check or args.finalize or args.export_bundle):
        parser.error('--reuse-bundle is only for a new installation')
    if args.reuse_build_bundle and (args.profile=='integrator' or args.reuse_bundle or args.check or args.finalize or args.export_bundle):
        parser.error('--reuse-build-bundle is only for a fresh parser/both installation')
    build_bundle=(ROOT/args.reuse_build_bundle).resolve() if args.reuse_build_bundle else None
    reuse_bundle=(ROOT/args.reuse_bundle).resolve() if args.reuse_bundle else None
    selected_mode = 'export' if args.export_bundle else 'finalize' if args.finalize else 'check' if args.check else 'reuse' if reuse_bundle else 'reuse-build' if build_bundle else 'install'
    if args.plan:
        print(json.dumps(plan(destination, selected_mode, args.profile), indent=2))
        return 0
    # Reject a reused/unsafe destination before APT, downloads or writes.
    if not (args.check or args.finalize or args.export_bundle):
        validate_destination(destination)
    elif not destination.is_relative_to(ROOT) or destination == ROOT:
        raise ValueError('Environment destination must be inside new_code')
    os.environ['NASA_ENV_PROFILE']=args.profile
    ubuntu = platform_check(require_gpu=args.profile!='integrator')
    if reuse_bundle and args.profile=='integrator':
        sys.path.insert(0,str(ROOT/'reconciliation_system'))
        from integration.environment import validate_bundle
        validate_bundle(reuse_bundle)
    if reuse_bundle and args.profile!='integrator':
        sys.path.insert(0,str(ROOT/'parse_system'))
        from parsing.unified.environment_bundle import validate_bundle,host_fingerprint,require_compatible
        data,_=validate_bundle(reuse_bundle,check_host=False)
        host=host_fingerprint();host['python']=PYTHON_VERSION
        require_compatible(data['host'],host)
    if build_bundle:
        sys.path.insert(0,str(ROOT/'parse_system'))
        from parsing.unified.environment_bundle import validate_bundle,host_fingerprint,require_compatible
        data,_=validate_bundle(build_bundle,check_host=False,check_candidate=False)
        host=host_fingerprint();host['python']=PYTHON_VERSION
        require_compatible(data['host'],host)
    gpu = '' if args.profile=='integrator' else subprocess.check_output(['nvidia-smi', '--query-gpu=name,driver_version,memory.total',
                                   '--format=csv,noheader'], text=True)
    print('GPU host: ' + gpu.strip(), flush=True)
    # No network/package activity until GPU access has succeeded.
    runtime = ROOT / 'runtime'
    runtime.mkdir(exist_ok=True)
    import fcntl
    with (runtime / '.setup.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another environment setup/check is active')
        attempt = runtime / ('setup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                             + '-' + uuid.uuid4().hex[:8])
        attempt.mkdir()
        env = dict(os.environ)
        for key in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'):
            env.pop(key, None)
        env['NASA_ENV_PROFILE']=args.profile
        env.update(PYTHONNOUSERSITE='1', PYTHONUNBUFFERED='1', PIP_VERBOSE='1',
                   PIP_PROGRESS_BAR='off', DEBIAN_FRONTEND='noninteractive', LC_ALL='C.UTF-8')
        env['PIP_CACHE_DIR']=str((ROOT/args.pip_cache_dir).resolve())
        run = Runner(attempt / 'setup.log', env)
        record = dict(plan(destination, selected_mode, args.profile), status='running', gpu=gpu.strip(), host_ubuntu=ubuntu)
        record['pip_cache_dir']=env['PIP_CACHE_DIR']
        if reuse_bundle:record['reuse_bundle']=str(reuse_bundle)
        status = attempt / 'status.json'
        status.write_text(json.dumps(record, indent=2), encoding='utf-8')
        print('Setup log: ' + str(run.logfile), flush=True)
        try:
            if args.export_bundle and args.profile=='integrator':
                run.run(integrator_command(destination/'.venv/bin/python','export',destination,'--output',(ROOT/args.export_bundle).resolve()))
            elif args.export_bundle:
                run.run([destination/'.venv/bin/python','-B',ROOT/'parse_system/run.py','environment','export',
                         '--destination',destination,'--output',(ROOT/args.export_bundle).resolve()],
                        stage='Validate and export reusable environment bundle')
            elif args.check:
                check_environment(destination, run)
            elif args.finalize and args.profile=='integrator':
                raise ValueError('Integrator finalize is unsupported; preserve incomplete attempt for review')
            elif args.finalize:
                run.run([destination / '.venv/bin/python', '-B', ROOT / 'parse_system/run.py',
                         'environment', 'finalize', '--destination', destination],
                        stage='Validate existing installation and publish shared receipt')
                check_environment(destination, run)
            else:
                install(destination, attempt, run, ubuntu,reuse_bundle,build_bundle)
            record['status'] = 'bundle-exported' if args.export_bundle else 'environment-validated'
            record['model_loading'] = 'not-tested'
        except BaseException as exc:
            record.update(status='failed', error=repr(exc))
            raise
        finally:
            status.write_text(json.dumps(record, indent=2), encoding='utf-8')
        print('Environment checked. Model loading/inference remain untested.')
        print('Python: ' + str(destination / '.venv/bin/python'))
        print('Manifest: ' + str(destination / 'environment.json'))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('SETUP FAILED: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
