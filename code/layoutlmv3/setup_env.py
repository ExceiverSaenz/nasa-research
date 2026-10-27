"""Restore the verified PyTorch/Detectron2 probe in a disposable Colab VM.

Run as a transferred file in Colab. Does not download model weights.
State is temporary until downloaded. Wheel caching is optional.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
from urllib.parse import unquote, urljoin, urlsplit
import uuid

PYTHON_VERSION = '3.9.25'
TORCH_INDEX = 'https://download.pytorch.org/whl/torch_stable.html'
D2_INDEX = 'https://dl.fbaipublicfiles.com/detectron2/wheels/cu111/torch1.10/index.html'
CORE = {'torch': '1.10.0+cu111', 'torchvision': '0.11.1+cu111', 'detectron2': '0.6+cu111'}
BASE = ['numpy==1.23.5', 'Pillow==9.5.0', 'matplotlib==3.7.5',
        'opencv-python-headless==4.8.1.78', 'pycocotools==2.0.7',
        'setuptools==80.9.0', 'pip==25.1.1']
PROBE_ROOT = Path('/content/layoutlmv3_probe')
PROBE_ENV = PROBE_ROOT / 'env'
PROBE_PYTHON = PROBE_ENV / 'bin' / 'python'
PROJECT_DIR = Path('/content/nasa-layoutlm-state')
UV = None
probe_env = None
ACTIVE_LOG = None


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def atomic_text(path, content):
    path = Path(path)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.part')
    temp.write_text(content, encoding='utf-8')
    os.replace(temp, path)


def run_command(arguments, env=None, log=None):
    """Stream child output into the notebook AND a persistent log."""
    log = log or ACTIVE_LOG
    with subprocess.Popen([str(arg) for arg in arguments], env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding='utf-8', errors='replace', bufsize=1) as child:
        for line in child.stdout:
            print(line, end='', flush=True)
            if log:
                with Path(log).open('a', encoding='utf-8') as stream:
                    stream.write(line)
        code = child.wait()
    if code:
        raise RuntimeError('El subproceso termino con codigo %s. Revisa el error anterior y %s'
                           % (code, log or 'la salida'))


def ejecutar_probe(argumentos):
    run_command(argumentos, env=probe_env)


def select_wheel(source, index, prefix):
    matches = set()
    for link in re.findall(r'href=["\']([^"\']+)', source):
        url = urljoin(index, html.unescape(link))
        name = unquote(urlsplit(url).path.rsplit('/', 1)[-1])
        if (name.startswith(prefix) and '-cp39-cp39-' in name
                and 'linux' in name and 'x86_64' in name and name.endswith('.whl')):
            matches.add(url)
    if len(matches) != 1:
        raise ValueError('No hay un binario inequivoco para %s: %s candidatos' % (prefix, len(matches)))
    return matches.pop()


def read_snapshot(root):
    path = Path(root) / 'snapshot.json'
    if not path.exists():
        return None
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if (manifest.get('schema') != 1 or not manifest.get('requirements')
            or not manifest.get('files')):
        raise ValueError('Snapshot incompleto; no se usara para restaurar.')
    for name, expected_hash in manifest['files'].items():
        if '/' in name or '\\' in name or not name.endswith('.whl'):
            raise ValueError('Nombre de paquete no permitido: ' + name)
        wheel = Path(root) / 'wheelhouse' / name
        if not wheel.is_file() or wheel.is_symlink() or sha256(wheel) != expected_hash:
            raise ValueError('Cache ausente o alterada: ' + name)
    return manifest


def installed_requirements():
    code = ("import importlib.metadata as m,json; "
            "print(json.dumps(sorted(d.metadata['Name']+'=='+d.version for d in m.distributions())))")
    result = subprocess.run([str(PROBE_PYTHON), '-c', code], env=probe_env,
                            text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def verify_gpu():
    code = '''
import sys,torch,torchvision,detectron2
from torchvision.ops import nms
from detectron2.layers import nms_rotated
assert sys.version_info[:2] == (3,9)
assert torch.__version__ == '1.10.0+cu111', torch.__version__
assert torchvision.__version__ == '0.11.1+cu111', torchvision.__version__
assert detectron2.__version__.split('+')[0] == '0.6'
assert torch.cuda.is_available(), 'Se necesita un runtime GPU compatible'
print('Python:',sys.version.split()[0], 'PyTorch:',torch.__version__, 'CUDA:',torch.version.cuda)
print('GPU:',torch.cuda.get_device_name(0))
x=torch.ones((256,256),device='cuda')
assert torch.all(x@x == 256).item()
scores=torch.tensor([.9,.8,.7],device='cuda')
boxes=torch.tensor([[0,0,10,10],[0,0,10,10],[30,30,40,40]],dtype=torch.float32,device='cuda')
assert nms(boxes,scores,.5).tolist() == [0,2]
rotated=torch.tensor([[10,10,8,8,0],[10,10,8,8,0],[50,50,8,8,0]],dtype=torch.float32,device='cuda')
assert nms_rotated(rotated,scores,.5).tolist() == [0,2]
torch.cuda.synchronize()
print('OK: PyTorch, torchvision y Detectron2 comprobados en GPU')
'''
    ejecutar_probe([PROBE_PYTHON, '-u', '-c', code])


def main(save_current=False, cache_wheels=False):
    global UV, probe_env, ACTIVE_LOG
    if sys.platform != 'linux' or platform.machine() != 'x86_64' or not Path('/content').exists():
        raise RuntimeError('Este script esta destinado a Google Colab Linux x86_64.')
    if save_current and not PROBE_PYTHON.exists():
        raise RuntimeError('No hay entorno local para capturar; restaura primero sin --save-current.')
    for folder in ['logs', 'wheelhouse', 'models', 'data', 'outputs']:
        (PROJECT_DIR / folder).mkdir(parents=True, exist_ok=True)
    PROBE_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:6]
    ACTIVE_LOG = PROJECT_DIR / 'logs' / (run_id + '.log')
    ACTIVE_LOG.write_text('Inicio de restauracion ' + run_id + '\n', encoding='utf-8')
    config = {'schema': 1, 'python': PYTHON_VERSION, 'base_requirements': BASE, 'core': CORE}
    config_path = PROJECT_DIR / 'environment-config.json'
    if config_path.exists() and json.loads(config_path.read_text(encoding='utf-8')) != config:
        raise ValueError('La configuracion guardada difiere del script; no se sobrescribira.')
    if not config_path.exists():
        atomic_text(config_path, json.dumps(config, indent=2) + '\n')
    probe_env = os.environ.copy()
    probe_env.update(UV_CACHE_DIR=str(PROBE_ROOT / 'cache'),
                     UV_PYTHON_INSTALL_DIR=str(PROBE_ROOT / 'python'),
                     PYTHONNOUSERSITE='1', PYTHONUNBUFFERED='1',
                     PIP_DISABLE_PIP_VERSION_CHECK='1')
    for name in ['PYTHONPATH', 'PYTHONHOME']:
        probe_env.pop(name, None)
    UV = shutil.which('uv')
    if not UV:
        tools = PROBE_ROOT / 'bootstrap-tools'
        ejecutar_probe([sys.executable, '-m', 'pip', 'install', '--no-deps',
                        '--target', tools, 'uv==0.12.21'])
        UV = str(tools / 'uv' / 'uv')
        if not Path(UV).is_file():
            raise RuntimeError('No se encontro el ejecutable uv instalado localmente.')
    manifest = None if save_current else read_snapshot(PROJECT_DIR)
    if manifest and manifest.get('python') != PYTHON_VERSION:
        raise ValueError('El snapshot usa otra version de Python.')
    if not PROBE_PYTHON.exists():
        ejecutar_probe([UV, 'venv', '--python', PYTHON_VERSION, '--managed-python', PROBE_ENV])
    ejecutar_probe([PROBE_PYTHON, '-c',
                    "import sys; assert sys.version.split()[0] == '" + PYTHON_VERSION + "'"])
    if manifest:
        print('Snapshot encontrado: verificando paquetes locales y cache.', flush=True)
        current = set(installed_requirements())
        if not set(manifest['requirements']).issubset(current):
            local_wheels = PROBE_ROOT / ('restore-' + run_id)
            local_wheels.mkdir()
            for name, expected in manifest['files'].items():
                target = local_wheels / name
                shutil.copyfile(PROJECT_DIR / 'wheelhouse' / name, target)
                if sha256(target) != expected:
                    raise ValueError('La copia local del paquete esta danada: ' + name)
            requirements = PROBE_ROOT / 'restore-requirements.txt'
            requirements.write_text('\n'.join(manifest['requirements']) + '\n', encoding='utf-8')
            ejecutar_probe([UV, 'pip', 'install', '--python', PROBE_PYTHON,
                            '--no-index', '--find-links', local_wheels, '-r', requirements])
        else:
            print('Las versiones guardadas ya estan instaladas; se omite su reinstalacion.', flush=True)
    elif not save_current:
        print('Primera preparacion: consultando los binarios oficiales.', flush=True)
        links = []
        for index, prefix in [(TORCH_INDEX, 'torch-1.10.0+cu111-'),
                              (TORCH_INDEX, 'torchvision-0.11.1+cu111-'),
                              (D2_INDEX, 'detectron2-0.6')]:
            with urllib.request.urlopen(index, timeout=90) as response:
                source = response.read().decode('utf-8')
            links.append(select_wheel(source, index, prefix))
        ejecutar_probe([UV, 'pip', 'install', '--python', PROBE_PYTHON] + BASE + links)
    print('Comprobando dependencias y operaciones GPU.', flush=True)
    ejecutar_probe([UV, 'pip', 'check', '--python', PROBE_PYTHON])
    verify_gpu()
    if manifest is None and (cache_wheels or save_current):
        # pip is needed only to materialize an installable wheelhouse the first time.
        ejecutar_probe([UV, 'pip', 'install', '--python', PROBE_PYTHON, 'pip==25.1.1'])
        requirements_list = installed_requirements()
        requirements = PROBE_ROOT / 'snapshot-requirements.txt'
        requirements.write_text('\n'.join(requirements_list) + '\n', encoding='utf-8')
        staging = PROBE_ROOT / ('wheels-' + run_id)
        staging.mkdir()
        print('Guardando paquetes reutilizables; la primera vez descarga varios GB.', flush=True)
        ejecutar_probe([PROBE_PYTHON, '-m', 'pip', 'wheel', '--no-deps',
                        '--wheel-dir', staging, '-r', requirements,
                        '--find-links', TORCH_INDEX, '--find-links', D2_INDEX,
                        '--only-binary', 'torch,torchvision,detectron2,numpy,pycocotools,opencv-python-headless'])
        files = {}
        for source in sorted(staging.glob('*.whl')):
            expected = sha256(source)
            destination = PROJECT_DIR / 'wheelhouse' / source.name
            if not destination.exists() or sha256(destination) != expected:
                temp = destination.with_name(destination.name + '.' + run_id + '.part')
                shutil.copyfile(source, temp)
                if sha256(temp) != expected:
                    raise ValueError('Fallo al guardar paquete: ' + source.name)
                os.replace(temp, destination)
            files[source.name] = expected
        manifest = {'schema': 1, 'python': PYTHON_VERSION, 'created_utc': run_id,
                    'requirements': requirements_list, 'files': files}
        atomic_text(PROJECT_DIR / 'snapshot.json', json.dumps(manifest, indent=2) + '\n')
        print('Snapshot persistente creado y paquetes comprobados.', flush=True)
    frozen = '\n'.join(manifest['requirements'] if manifest else installed_requirements()) + '\n'
    atomic_text(PROJECT_DIR / 'requirements-verificacion.txt', frozen)
    atomic_text(PROJECT_DIR / 'last-success.json', json.dumps({
        'run': run_id, 'python': PYTHON_VERSION, 'interpreter': str(PROBE_PYTHON),
        'log': str(ACTIVE_LOG), 'scope': 'PyTorch y Detectron2; LayoutLMv3 no instalado'
    }, indent=2) + '\n')
    print('\nLISTO: entorno GPU verificado. Descarga el respaldo antes de cerrar la VM.', flush=True)
    print('Python aislado:', PROBE_PYTHON)
    print('Documentos:', PROJECT_DIR / 'data')
    print('Resultados temporales:', PROJECT_DIR / 'outputs')
    print('Esto no instala todavia LayoutLMv3 ni copia automaticamente archivos de otros directorios.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save-current', action='store_true',
                        help='Actualizar el snapshot desde el entorno local existente.')
    parser.add_argument('--cache-wheels', action='store_true',
                        help='Guardar varios GB de paquetes para restauraciones futuras.')
    args = parser.parse_args()
    main(args.save_current, args.cache_wheels)
