"""Remote installation/import probe. Does not load detector weights or parse PDFs."""
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from urllib.request import urlopen


def extract_archive(archive, destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, 'r:gz') as source:
        for item in source.getmembers():
            target = (destination / item.name).resolve()
            if destination not in target.parents or not (item.isfile() or item.isdir()):
                raise ValueError('Miembro TAR no permitido: ' + item.name)
        source.extractall(destination)


def check_file(path, expected):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
            digest.update(block)
    if path.stat().st_size != expected['bytes'] or digest.hexdigest() != expected['sha256']:
        raise ValueError('Archivo no coincide con el manifiesto: ' + str(path))


def download_model(manifest, destination):
    """Download pinned public files, publishing only after size/hash verification."""
    if manifest['repository'] != 'HYPJUDY/layoutlmv3-base-finetuned-publaynet':
        raise ValueError('Repositorio de modelo no permitido')
    if not re.fullmatch(r'[0-9a-f]{40}', manifest['revision']):
        raise ValueError('Se requiere una revision fija de 40 caracteres')
    for name, expected in manifest['files'].items():
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
            raise ValueError('Nombre de archivo no permitido')
        if not isinstance(expected['bytes'], int) or expected['bytes'] <= 0:
            raise ValueError('Tamano de archivo no valido')
        if not re.fullmatch(r'[0-9a-f]{64}', expected['sha256']):
            raise ValueError('SHA-256 no valido')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for name, expected in manifest['files'].items():
        target = destination / name
        partial = destination / (name + '.part')
        url = ('https://huggingface.co/' + manifest['repository'] + '/resolve/'
               + manifest['revision'] + '/' + name)
        print('Descargando:', name, 'bytes esperados:', expected['bytes'], flush=True)
        try:
            with urlopen(url, timeout=60) as response, partial.open('wb') as output:
                total = 0
                while True:
                    block = response.read(min(4 * 1024 * 1024, expected['bytes'] - total + 1))
                    if not block:
                        break
                    total += len(block)
                    if total > expected['bytes']:
                        raise ValueError('Descarga mayor que el tamano esperado')
                    output.write(block)
            check_file(partial, expected)
            partial.replace(target)
        except Exception:
            # HTTP errors may contain signed redirect URLs; do not archive them.
            raise RuntimeError('Descarga o verificacion fallida: ' + name
                               + '; no se publico el archivo descargado') from None
        finally:
            if partial.exists():
                partial.unlink()
        print('SHA-256 y tamano verificados:', name, flush=True)


def main():
    root = Path('/content/nasa-layoutlm')
    state = Path('/content/nasa-layoutlm-state')
    state.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    for key in ['PYTHONPATH', 'PYTHONHOME']:
        env.pop(key, None)
    env['PYTHONNOUSERSITE'] = '1'

    def run(*args):
        subprocess.run([str(arg) for arg in args], check=True, env=env)

    manifest_path = Path('/content/layoutlmv3-model-manifest.json')
    manifest = json.loads(manifest_path.read_text())
    shutil.copyfile(manifest_path, state / 'model-manifest.json')
    model = root / 'layoutlmv3-publaynet'
    download_model(manifest, model)
    shutil.copyfile(manifest_path, model / 'download-manifest.json')
    (state / 'model-download-check.json').write_text(json.dumps({
        'verified': True, 'repository': manifest['repository'],
        'revision': manifest['revision'], 'files': manifest['files']}, indent=2))
    run(sys.executable, '-u', '/content/nasa_setup_env.py')
    python = Path('/content/layoutlmv3_probe/env/bin/python')
    extract_archive('/content/layoutlmv3-source.tar.gz', root)
    shutil.copyfile('/content/unilm-commit.txt', state / 'unilm-commit.txt')
    requirements = Path('/content/requirements-inference.txt')
    shutil.copyfile(requirements, state / requirements.name)
    constraints = state / 'constraints.txt'
    constraints.write_text('torch==1.10.0+cu111\ntorchvision==0.11.1+cu111\n'
                           'detectron2==0.6+cu111\nnumpy==1.23.5\nPillow==9.5.0\n'
                           'setuptools==80.9.0\n')
    run(python, '-m', 'pip', 'install', '-c', constraints, '-r', requirements)
    run(python, '-m', 'pip', 'install', '--no-deps', '--no-build-isolation', '-e', root / 'layoutlmv3')
    run(python, '-m', 'pip', 'check')
    check = '''
import sys, json
from pathlib import Path
sys.path.insert(0, '/content/nasa-layoutlm/layoutlmv3/examples/object_detection')
import torch, detectron2, layoutlmft
from ditod import add_vit_config
from detectron2.config import get_cfg
from transformers import AutoConfig
cfg=get_cfg()
add_vit_config(cfg)
cfg.merge_from_file('/content/nasa-layoutlm/layoutlmv3/examples/object_detection/cascade_layoutlmv3.yaml')
config=AutoConfig.from_pretrained('/content/nasa-layoutlm/layoutlmv3-publaynet', local_files_only=True)
assert cfg.MODEL.ROI_HEADS.NUM_CLASSES == 5
assert torch.cuda.is_available()
result={'imports_ok': True, 'config_ok': True, 'gpu': torch.cuda.get_device_name(0),
        'scope': 'LayoutLMv3 installed; imports/config only; detector weights NOT loaded; no inference'}
Path('/content/nasa-layoutlm-state/detector-import-check.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
'''
    run(python, '-u', '-c', check)
    with (state / 'requirements-detector-freeze.txt').open('w') as output:
        subprocess.run([str(python), '-m', 'pip', 'freeze'], check=True, env=env, stdout=output)
    print('IMPORTACIONES Y CONFIGURACION VERIFICADAS. Falta cargar pesos y ejecutar inferencia.')


if __name__ == '__main__':
    main()
