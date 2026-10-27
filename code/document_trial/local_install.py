"""Explicit repair of dependency installation only; never executes parsers."""
import os
from pathlib import Path
import sys
import zipfile
from email.parser import BytesParser
from document_trial.common import MODELS, read, sha, canonical


def verify_wheel(wheel, receipt, expected_packages):
    if sha(wheel) != receipt['sha256']:
        raise ValueError('Transport wheel hash mismatch')
    with zipfile.ZipFile(wheel) as archive:
        names = [n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
        if len(names) != 1:
            raise ValueError('Ambiguous wheel metadata')
        metadata = BytesParser().parsebytes(archive.read(names[0]))
    name = canonical(metadata['Name'])
    if name != canonical(receipt['package']) or metadata['Version'] != expected_packages.get(name):
        raise ValueError('Wheel version differs from frozen baseline')
from document_trial.command_log import run_logged


def install(root, state, models=MODELS):
    import fcntl
    if (root/'ready.json').exists() or (root/'pilot-started.json').exists():
        raise ValueError('Prepared runtime/pilot cannot be modified by the installer')
    inputs = root/'inputs'
    env = os.environ.copy()
    for key in list(env):
        if key.startswith('MINERU_') or key in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'):
            env.pop(key)
    env.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1',
               NASA_DOCUMENT_USER_RUN='LOCAL_WSL_RTX3050', UV_HTTP_TIMEOUT='600',
               UV_CONCURRENT_DOWNLOADS='2', UV_HTTP_RETRIES='3')
    plan = read(inputs/'plan.json')
    runners = {}
    for model in models:
        model_lock = (root/('install-'+model+'.lock')).open('a')
        fcntl.flock(model_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        version = '0.6.14' if model == 'table_transformer' else '0.12.21'
        tools = root/('nasa-sic12-document-v1-tools'+('-tatr' if model == 'table_transformer' else ''))
        if not (tools/'bin/uv').is_file():
            if tools.exists():
                raise ValueError('Incomplete tooling requires inspection')
            run_logged([sys.executable, '-m', 'pip', 'install', '--target', str(tools), 'uv=='+version],
                       state, env=env, stage='repair:bootstrap:'+model)
        toolenv = dict(env, PYTHONPATH=str(tools))
        def uv(*args):
            return run_logged([sys.executable, '-m', 'uv', *map(str, args)], state,
                              env=toolenv, stage='repair:install:'+model)
        venv = root/('nasa-sic12-document-v1-env-'+model)
        if not venv.exists():
            uv('venv', '--python', plan['models'][model]['python'], venv)
        python = venv/'bin/python'
        if model == 'mineru':
            uv('pip', 'sync', '--python', python, '--require-hashes', '--only-binary', ':all:',
               '--no-binary', 'jieba', '--extra-index-url', 'https://download.pytorch.org/whl/cu126',
               '--index-strategy', 'unsafe-best-match', inputs/'mineru/requirements.lock')
        else:
            if model == 'layoutlmv3':
                uv('pip', 'install', '--python', python, 'setuptools==80.9.0', 'pip==25.1.1')
            requirements = inputs/model/'freeze.txt'
            if model == 'layoutlmv3' and (root/'wheels/receipts.json').exists():
                text = requirements.read_text()
                for filename, receipt in read(root/'wheels/receipts.json').items():
                    wheel = root/'wheels'/filename
                    verify_wheel(wheel, receipt, plan['models'][model]['packages'])
                    lines = text.splitlines()
                    replaced = False
                    for i, line in enumerate(lines):
                        if line.startswith(receipt['requirement_prefix']):
                            lines[i] = receipt['package']+' @ '+wheel.as_uri()
                            replaced = True
                    if not replaced:
                        raise ValueError('Frozen wheel requirement missing')
                    text = '\n'.join(lines)+'\n'
                requirements = state/'layoutlmv3-local-transport.txt'
                requirements.write_text(text)
            uv('pip', 'install', '--python', python, '--no-deps', '--no-build-isolation', '-r',
               requirements, '--extra-index-url', 'https://download.pytorch.org/whl/cu121',
               '--index-strategy', 'unsafe-best-match')
        uv('pip', 'check', '--python', python)
        runenv = dict(env, PYTHONPATH=str(inputs), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        if model == 'mineru':
            (state/'config.yaml').write_bytes((inputs/'mineru/config.yaml').read_bytes())
            runenv.update(MINERU_HOME=str(root/'mineru-home'), MINERU_CONFIG=str(state/'config.yaml'),
                          MINERU_DEVICE_MODE='cuda', MINERU_TABLE_DEVICE='cpu')
        runners[model] = (python, runenv)
        model_lock.close()
    return runners
