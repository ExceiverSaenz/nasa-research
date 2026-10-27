"""One retry of the load failure on the existing authorized VM; no installation."""
import json
import os
from pathlib import Path
import subprocess

try:
    from .prepare import unpack_bundle
except ImportError:  # Uploaded as a standalone Colab script.
    import runpy
    unpack_bundle = runpy.run_path('/content/nasa_tatr_prepare.py', run_name='bundle_helper')['unpack_bundle']


def main(root=Path('/content')):
    root = Path(root)
    previous = root/'tatr-state'
    status = json.loads((previous/'page/page-status.json').read_text())
    if status['status'] != 'failed' or status['stage'] != 'load':
        raise ValueError('Retry requires the previous load failure')
    python = root/'tatr-probe/env/bin/python'
    if not python.is_file():
        raise FileNotFoundError('The original TATR environment is no longer available')
    state, inputs = root/'tatr-retry-state', root/'tatr-retry-inputs'
    state.mkdir(parents=True, exist_ok=True)  # Archive helper already creates this directory.
    manifest = unpack_bundle(root/'table-transformer-page.zip', root/'table-transformer-page.sha256', inputs)
    (state/'input-manifest.json').write_text(json.dumps(manifest, indent=2))
    (state/'requirements-freeze.txt').write_bytes((previous/'requirements-freeze.txt').read_bytes())
    (state/'previous-page-status.json').write_text(json.dumps(status, indent=2))
    env = os.environ.copy()
    for key in ('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV'): env.pop(key, None)
    env.update(PYTHONPATH=str(inputs), PYTHONNOUSERSITE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    check = ("import torch,transformers,timm,json; assert torch.cuda.is_available(); "
             "assert 'T4' in torch.cuda.get_device_name(0); assert torch.__version__=='2.5.1+cu121'; "
             "assert transformers.__version__=='4.49.0'; assert timm.__version__=='1.0.14'; "
             "print(json.dumps({'gpu':torch.cuda.get_device_name(0),'torch':torch.__version__}))")
    subprocess.run([str(python), '-u', '-c', check], check=True, env=env)
    subprocess.run([str(python), '-u', '-m', 'table_transformer.run_image',
                    '--image', str(inputs/'render.png'), '--model-dir', str(root/'tatr-model'),
                    '--output', str(state/'page')], check=True, env=env, cwd=inputs)


if __name__ == '__main__': main()
