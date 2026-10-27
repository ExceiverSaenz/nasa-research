"""WSL preparation and explicit human run; original bundles remain immutable."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid
import zipfile

from document_trial.common import MODELS, read, save, sha, validate_bundle

GPU = 'NVIDIA GeForce RTX 3050 6GB Laptop GPU'
POLICY = 'LOCAL_WSL_RTX3050'


def derive(base, root):
    """Extract verified baseline, relocate paths and isolate install from inference."""
    if root.exists():
        raise FileExistsError('Existing runtime retained; no automatic reinstall/retry')
    plan = validate_bundle(base/'upload.zip', base/'upload.sha256')
    if 'documents' in plan or plan['execution_policy'] != 'USER_ONLY_COLAB_CLI_T4':
        raise ValueError('Original single-paper baseline required')
    if plan['automatic_retries'] or plan['automatic_recovery']:
        raise ValueError('Retries/recovery prohibited')
    root.mkdir(parents=True)
    inputs = root/'inputs'
    validate_bundle(base/'upload.zip', base/'upload.sha256', inputs)
    originals = {}
    changes = {}
    for path in inputs.rglob('*'):
        if not path.is_file() or path.suffix not in ('.py', '.txt', '.yaml'):
            continue
        old = path.read_bytes()
        data = old.replace(b'/content', root.as_posix().encode())
        if path.relative_to(inputs).as_posix() in ('document_trial/worker.py', 'document_trial/remote.py'):
            data = data.replace(b'COLAB_CLI_T4', POLICY.encode())
            data = data.replace(b'human_colab_cli', b'human_local_wsl')
        if path.relative_to(inputs).as_posix() == 'document_trial/common.py':
            if b"observed.get('gpu')!='Tesla T4'" not in data:
                raise ValueError('GPU guard baseline changed')
            data = data.replace(b"observed.get('gpu')!='Tesla T4'", ("observed.get('gpu')!="+repr(GPU)).encode())
        if path.relative_to(inputs).as_posix() == 'mineru_probe/run_image.py':
            if b"'T4' not in torch.cuda.get_device_name(0)" not in data:
                raise ValueError('MinerU guard baseline changed')
            data = data.replace(b"'T4' not in torch.cuda.get_device_name(0)", ("torch.cuda.get_device_name(0)!="+repr(GPU)).encode())
        if path.relative_to(inputs).as_posix() == 'document_trial/remote.py':
            # Keep original dependency commands verbatim, but discard ALL execution
            # stages after environment construction, and remove the remote entrypoint.
            tree = ast.parse(data.decode())
            setup = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'setup')
            cut = next(i for i, n in enumerate(setup.body) if isinstance(n, ast.FunctionDef) and n.name == 'work')
            setup.body = setup.body[:cut] + [ast.Return(value=ast.Name(id='runners', ctx=ast.Load()))]
            tree.body = [n for n in tree.body if not (isinstance(n, ast.FunctionDef) and n.name == 'main') and not isinstance(n, ast.If)]
            data = (ast.unparse(ast.fix_missing_locations(tree))+'\n').encode()
        if data != old:
            path.write_bytes(data)
            name = path.relative_to(inputs).as_posix()
            originals[name] = hashlib.sha256(old).hexdigest()
            changes[name] = sha(path)
    plan['execution_policy'] = 'USER_ONLY_'+POLICY
    plan['platform_change'] = dict(baseline_bundle_sha256=sha(base/'upload.zip'), gpu=GPU,
                                   version='local-wsl-v1', model_settings_changed=False)
    save(inputs/'plan.json', plan)
    save(root/'derivation.json', dict(baseline=str(base), baseline_sha256=sha(base/'upload.zip'),
        original_hashes=originals, changed_hashes=changes, plan_sha256=sha(inputs/'plan.json')))
    # A baseline bundle manifest would be misleading for the relocated runtime.
    with zipfile.ZipFile(base/'upload.zip') as archive:
        (inputs/'baseline-bundle-manifest.json').write_bytes(archive.read('bundle-manifest.json'))
    save(root/'runtime-manifest.json', {p.relative_to(inputs).as_posix():sha(p)
        for p in inputs.rglob('*') if p.is_file()})
    return inputs


def verify_inputs(root):
    expected = read(root/'runtime-manifest.json')
    actual = {p.relative_to(root/'inputs').as_posix():sha(p)
              for p in (root/'inputs').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if actual != expected:
        raise ValueError('Derived input integrity mismatch')


def verify_vendor(root):
    source = root/'inputs/vendor/layoutlmv3'
    installed = root/'nasa-layoutlm/layoutlmv3'
    for path in source.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            target = installed/path.relative_to(source)
            if not target.is_file() or sha(target) != sha(path):
                raise ValueError('Editable LayoutLMv3 source changed: '+str(path.relative_to(source)))


def child(root, action, repo, output=None):
    # Fresh process: never mix repository modules and relocated modules in sys.modules.
    import subprocess
    env = dict(os.environ, PYTHONPATH=str(root/'inputs'), PYTHONDONTWRITEBYTECODE='1',
               NASA_DOCUMENT_USER_RUN=POLICY)
    if action == 'prepare':
        env.update(UV_HTTP_TIMEOUT='600', UV_CONCURRENT_DOWNLOADS='2')
    command = [sys.executable, '-B', str(Path(__file__).resolve()), '_'+action,
               '--root', str(root), '--repo', str(repo)]
    if output is not None:
        command += ['--output', str(output)]
    subprocess.run(command, env=env, check=True)


def execution_record(root, attempt):
    plan = read(root/'inputs/plan.json')
    return dict(execution_id='local-parsing-'+attempt, initiator='human_local_wsl',
                platform='WSL2', gpu=GPU, baseline=read(root/'derivation.json'),
                document_sha256=plan['document_sha256'], attempt_id=attempt,
                controller_sha256={name:sha(Path(__file__).with_name(name))
                    for name in ('local.py', 'local_install.py', 'local_download.py')})


def import_checks(root, state, runners):
    from document_trial.command_log import run_logged
    checks = {
        'layoutlmv3': "import torch, torchvision, pypdfium2; from detectron2 import _C; "
                     "from detectron2.modeling import build_model; import sys; sys.path.insert(0, "
                     +repr(str(root/'nasa-layoutlm/layoutlmv3/examples/object_detection'))+
                     "); from ditod import add_vit_config; print('LayoutLMv3 imports OK; no model loaded')",
        'table_transformer': "import torch, torchvision; from transformers import DetrImageProcessor, "
                             "TableTransformerForObjectDetection; print('TATR imports OK; no model loaded')",
        'mineru': "import torch; from mineru.parser import parse; print('MinerU imports OK; no model loaded')",
    }
    for model in runners:
        python, env = runners[model]
        run_logged([str(python), '-B', '-c', checks[model]], state, env=env,
                   cwd=root/'inputs', stage='import-smoke:'+model)


def prepare_weights(root, repo, state):
    from document_trial import remote
    from mineru_probe.remote_job import download_models, verify_receipt
    inputs = root/'inputs'
    for model in MODELS:
        print('Verificando pesos: '+model, flush=True)
        if model == 'mineru':
            dest = root/'mineru-models/MinerU-4_models_torch'
            expected = read(inputs/'mineru/model-download-receipt.json')
            if not dest.exists():
                receipt = download_models(read(inputs/'mineru/model-manifest.json'), dest)
                if receipt != expected:
                    raise ValueError('MinerU weights differ')
            verify_receipt(expected, dest)
        else:
            manifest = read(inputs/model/'models.json')
            dest = state/'models'/model
            if not dest.exists():
                if model == 'layoutlmv3':
                    dest.mkdir(parents=True)
                    for name, spec in manifest['files'].items():
                        source = repo/'code/models/layoutlmv3-publaynet'/name
                        if source.stat().st_size != spec['bytes'] or sha(source) != spec['sha256']:
                            raise ValueError('Local LM weight differs: '+name)
                        shutil.copy2(source, dest/name)
                    save(dest/'download-manifest.json', manifest)
                else:
                    remote.download_exact(manifest, dest)
            for name, spec in manifest['files'].items():
                if (dest/name).stat().st_size != spec['bytes'] or sha(dest/name) != spec['sha256']:
                    raise ValueError('Pinned weight differs: '+model+'/'+name)
            if read(dest/'download-manifest.json') != manifest:
                raise ValueError('Model manifest differs')
    save(state/'model-verification.json', dict(all_pinned_models_verified=True))


def runtime(root, repo, output, prepare, repair=False):
    import fcntl
    with (root/'installation.lock').open('a') as install_lock:
        fcntl.flock(install_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _runtime_locked(root, repo, output, prepare, repair)


def _runtime_locked(root, repo, output, prepare, repair=False):
    from document_trial import remote
    from document_trial.command_log import run_logged
    inputs = root/'inputs'
    if prepare:
        if (root/'ready.json').exists() or (root/'pilot-started.json').exists():
            raise ValueError('Already prepared or pilot started; installation changes require a new reviewed runtime')
        state = root/'preparation'
        if repair:
            verify_inputs(root)
            verify_vendor(root)
            # Explicit transport repair, never automatic recovery of inference.
            with (root/('installation-repair-'+uuid.uuid4().hex+'.json')).open('x') as marker:
                json.dump(dict(reason='interrupted downloads', timeout=600, concurrent_downloads=2), marker)
            # Source stays in the workspace, outside the frozen derived inputs.
            import importlib.util
            spec = importlib.util.spec_from_file_location('local_install', Path(__file__).with_name('local_install.py'))
            installer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(installer)
            runners = installer.install(root, state)
        else:
            state.mkdir()
            runners = remote.setup(inputs, state)  # derived install-only function
    else:
        verify_inputs(root)
        verify_vendor(root)
        ready = read(root/'ready.json')
        if ready['status'] != 'prepared_without_inference':
            raise ValueError('Preparation incomplete')
        with (root/'pilot-started.json').open('x') as marker:
            json.dump({'status':'user_started', 'automatic_retry':False}, marker)
        state = output/uuid.uuid4().hex
        state.mkdir(parents=True, exist_ok=False)
        env = os.environ.copy()
        for key in list(env):
            if key.startswith('MINERU_') or key in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'):
                env.pop(key)
        env.update(PYTHONPATH=str(inputs), PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1',
                   NASA_DOCUMENT_USER_RUN=POLICY, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        runners = {m:(root/('nasa-sic12-document-v1-env-'+m)/'bin/python', dict(env)) for m in MODELS}
        (state/'config.yaml').write_bytes((inputs/'mineru/config.yaml').read_bytes())
        runners['mineru'][1].update(MINERU_HOME=str(root/'mineru-home'), MINERU_CONFIG=str(state/'config.yaml'),
                                  MINERU_DEVICE_MODE='cuda', MINERU_TABLE_DEVICE='cpu')
    def work(model, stage):
        python, env = runners[model]
        run_logged([str(python), '-B', '-u', '-m', 'document_trial.worker', '--model', model,
                    '--stage', stage, '--inputs', str(inputs), '--state', str(state)],
                   state, env=env, cwd=inputs, stage=model+':'+stage)
    if prepare:
        for model in MODELS:
            work(model, 'probe')
        import_checks(root, state, runners)
        prepare_weights(root, repo, state)
        verify_inputs(root)
        save(root/'ready.json', dict(status='prepared_without_inference', gpu=GPU,
                                    inference_memory_fit='unverified', models=list(MODELS)))
        return
    import traceback
    status = dict(status='failed', initiator='human_local_wsl', automatic_recovery=False)
    (state/'plan.json').write_bytes((inputs/'plan.json').read_bytes())
    save(state/'execution.json', execution_record(root, state.name))
    print('Salida local: '+str(state), flush=True)
    try:
        for model in MODELS:
            work(model, 'probe')
        from mineru_probe.remote_job import verify_receipt
        verify_receipt(read(inputs/'mineru/model-download-receipt.json'), root/'mineru-models/MinerU-4_models_torch')
        for model in ('layoutlmv3', 'table_transformer'):
            src = root/'preparation/models'/model
            for name, spec in read(inputs/model/'models.json')['files'].items():
                if (src/name).stat().st_size != spec['bytes'] or sha(src/name) != spec['sha256']:
                    raise ValueError('Pinned weights changed')
            (state/'models').mkdir(exist_ok=True)
            (state/'models'/model).symlink_to(src, target_is_directory=True)
        work('layoutlmv3', 'render')
        for model in MODELS:
            work(model, 'infer')
        status['status'] = 'completed'
    except Exception:
        status['error'] = traceback.format_exc()
        raise
    finally:
        from document_trial.batch import account_missing
        account_missing(read(inputs/'plan.json'), state)
        save(state/'execution-status.json', status)
        remote.archive_state(state, state.with_suffix('.zip'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'repair-install', 'run', '_prepare', '_repair', '_run'])
    parser.add_argument('--root', type=Path, default=Path.home()/'.local/share/nasa-parsing/local-v1-ready')
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--paper', default='10')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--user-run', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'linux' or 'microsoft' not in os.uname().release.lower():
        parser.error('WSL2 required')
    if args.action == 'prepare':
        derive(args.repo/'code/packages/sic-parsing-v1'/args.paper, args.root)
        child(args.root, 'prepare', args.repo)
    elif args.action == 'repair-install':
        child(args.root, 'repair', args.repo)
    elif args.action == 'run':
        if not args.user_run:
            parser.error('Explicit --user-run required; preparation never runs inference')
        verify_inputs(args.root)
        if not (args.root/'ready.json').exists() or read(args.root/'ready.json')['status'] != 'prepared_without_inference':
            parser.error('Preparation incomplete')
        child(args.root, 'run', args.repo, args.output or args.repo/'code/results/local-parsing-v1')
    else:
        if os.environ.get('NASA_DOCUMENT_USER_RUN') != POLICY:
            parser.error('Internal entry only')
        runtime(args.root, args.repo, args.output, args.action in ('_prepare', '_repair'), args.action == '_repair')


if __name__ == '__main__':
    main()
