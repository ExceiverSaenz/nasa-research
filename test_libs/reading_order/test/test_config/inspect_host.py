"""Explicit Colab host probe; does not install anything."""
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def main():
    gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version,memory.total',
                          '--format=csv,noheader'], capture_output=True, text=True, check=True).stdout.strip()
    if 'A100' not in gpu:
        raise RuntimeError('Requested A100 was not allocated')
    print(json.dumps({'python': sys.version, 'platform': platform.platform(), 'gpu': gpu,
                      'uv': shutil.which('uv'), 'rustc': shutil.which('rustc'),
                      'cargo': shutil.which('cargo'),
                      'disk_free_bytes': shutil.disk_usage('/content').free}), flush=True)
    root = Path('/content/order-config-20261102')
    if root.exists():
        if (root / 'r2-request.json').exists() or list(root.rglob('*.pdf')):
            raise RuntimeError('Configuration workspace still contains a private request or PDF')
        print('ORDER_CONFIG_NO_PERSISTENT_PDF_OR_REQUEST', flush=True)
    print('ORDER_CONFIG_HOST_VERIFIED', flush=True)


if __name__ == '__main__':
    main()
