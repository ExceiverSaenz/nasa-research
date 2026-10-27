"""Remote one-page job. Called by cli_job.py, which archives logs even on failure."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import zipfile


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def unpack_bundle(archive, sidecar, destination):
    if sha256(archive) != Path(sidecar).read_text(encoding='ascii').strip():
        raise ValueError('Bundle SHA-256 mismatch')
    destination = Path(destination)
    with zipfile.ZipFile(archive) as source:
        manifest = json.loads(source.read('manifest.json'))
        if manifest['page'] != 3 or manifest['dpi'] != 200:
            raise ValueError('Unexpected first-trial parameters')
        names = source.namelist()
        expected_names = set(manifest['files']) | {'manifest.json'}
        if set(names) != expected_names or len(names) != len(expected_names):
            raise ValueError('Unexpected or duplicate bundle files')
        for name, expected in manifest['files'].items():
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
                raise ValueError('Unsafe bundle filename')
            data = source.read(name)
            if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
                raise ValueError('Bundle member mismatch: ' + name)
        destination.mkdir(parents=True, exist_ok=False)
        # Write validated bytes as ordinary files, never restore ZIP symlinks.
        for name in names:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read(name))
    return manifest


def main():
    inputs = Path('/content/nasa-page-inputs')
    state = Path('/content/nasa-page-state')
    state.mkdir(parents=True, exist_ok=True)
    manifest = unpack_bundle('/content/layoutlmv3-page.zip', '/content/layoutlmv3-page.sha256', inputs)
    (state / 'input-manifest.json').write_text(json.dumps(manifest, indent=2))
    python = '/content/layoutlmv3_probe/env/bin/python'
    env = os.environ.copy()
    env.pop('PYTHONHOME', None)
    env['PYTHONPATH'] = str(inputs)
    env['PYTHONNOUSERSITE'] = '1'
    env['HF_HUB_OFFLINE'] = '1'
    env['TRANSFORMERS_OFFLINE'] = '1'
    def run(*args):
        subprocess.run([python, '-u', *map(str, args)], check=True, env=env, cwd=inputs)
    run('-m', 'pip', 'install', '-c', '/content/nasa-layoutlm-state/constraints.txt',
        '-r', inputs / 'requirements-page.txt')
    run('-m', 'pip', 'check')
    with (state / 'requirements-page-freeze.txt').open('w') as output:
        subprocess.run([python, '-m', 'pip', 'freeze'], check=True, env=env, stdout=output)
    run('-m', 'inference.run_page', '--pdf', inputs / 'SiC-12.pdf', '--page', '3', '--dpi', '200',
        '--config', '/content/nasa-layoutlm/layoutlmv3/examples/object_detection/cascade_layoutlmv3.yaml',
        '--model-config-dir', '/content/nasa-layoutlm/layoutlmv3-publaynet',
        '--checkpoint', '/content/nasa-layoutlm/layoutlmv3-publaynet/model_final.pth',
        '--output', state / 'page')


if __name__ == '__main__':
    main()
