"""Provision the frozen CPU integration environment inside a Linux A100 runtime."""
import argparse
from importlib.metadata import version
import inspect
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys

from .common import digest, write_json

PYTHON = '3.13.5'
DOCLING_RB_SHA256 = '688402b548726963fa65c8af3647626ddfb70e42ece07c05893574c15bb05964'


def installation_commands(root, payload):
    root, payload = Path(root), Path(payload)
    env = dict(os.environ, UV_PYTHON_INSTALL_DIR=str(root / 'managed-python'),
               UV_CACHE_DIR=str(root / 'cache'), UV_HTTP_RETRIES='0', PIP_RETRIES='0',
               PYTHONPATH=str(root / 'bootstrap'), PYTHONIOENCODING='utf-8')
    uv = [sys.executable, '-m', 'uv', '--no-config']
    python = root / 'venv' / 'bin' / 'python'
    commands = [
        [sys.executable, '-m', 'pip', 'install', '--target', str(root / 'bootstrap'),
         '--no-deps', '--only-binary=:all:', '--retries', '0', 'uv==0.12.21'],
        uv + ['python', 'install', PYTHON],
        uv + ['venv', '--python', PYTHON, '--managed-python', str(root / 'venv')],
        uv + ['pip', 'install', '--python', str(python), '--no-deps', '--only-binary', ':all:',
              '-r', str(payload / 'requirements-runtime.lock'), '-r', str(payload / 'requirements-docling.txt')],
    ]
    return commands, env, python


def setup(root, payload, log_directory):
    root, payload, log_directory = Path(root).resolve(), Path(payload).resolve(), Path(log_directory).resolve()
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        raise ValueError('Linux x86_64 required')
    root.mkdir(parents=True, exist_ok=False)
    log_directory.mkdir(parents=True, exist_ok=True)
    commands, env, python = installation_commands(root, payload)
    write_json(root / 'commands.json', dict(commands=commands, automatic_retries=False))
    for i, command in enumerate(commands, 1):
        print(f'SETUP {i}/{len(commands)}: ' + ' '.join(command), flush=True)
        with (log_directory / f'setup-{i}.log').open('x', encoding='utf-8') as log:
            child = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            try:
                returncode = child.wait()
            except BaseException:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait()
                raise
        if returncode:
            raise RuntimeError(f'Setup {i} failed; inspect {log_directory / f"setup-{i}.log"}; no retry')
    return python


def probe(lock_directory, receipt):
    if platform.python_version() != PYTHON:
        raise ValueError('Frozen Python version mismatch')
    pins = {}
    for name in ('requirements-runtime.lock', 'requirements-docling.txt'):
        for line in (Path(lock_directory) / name).read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.startswith('#'):
                package, pinned = line.strip().split('==')
                observed = version(package)
                if observed != pinned:
                    raise ValueError(f'Version mismatch: {package}: {observed} != {pinned}')
                pins[package] = observed
    import docling.models.postprocessing.reading_order_rb as rb
    if digest(inspect.getfile(rb)) != DOCLING_RB_SHA256:
        raise ValueError('Frozen Docling source hash mismatch')
    from document_structure.docling_trial import predict
    items = [dict(id='top', bbox=[10, 10, 90, 20], page_size=[100, 100],
                  category='text', text='top', page=1),
             dict(id='bottom', bbox=[10, 40, 90, 50], page_size=[100, 100],
                  category='text', text='bottom', page=1)]
    if predict(items) != ['top', 'bottom']:
        raise ValueError('Real Docling geometric probe failed')
    forbidden = [k for k in sys.modules if k in ('torch', 'transformers', 'mineru')]
    if forbidden:
        raise ValueError('Unexpected model imports: ' + ', '.join(forbidden))
    result = dict(python=platform.python_version(), packages=pins,
                  docling_rb_sha256=DOCLING_RB_SHA256, geometric_probe='passed',
                  neural_modules_imported=False, models_executed=False)
    write_json(receipt, result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('lock_directory', type=Path)
    p.add_argument('receipt', type=Path)
    a = p.parse_args()
    print(probe(a.lock_directory, a.receipt))
