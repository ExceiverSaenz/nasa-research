"""Infrastructure test; run with colab exec, without installing packages."""
import hashlib
import json
import platform
import subprocess
from pathlib import Path

import torch

source = Path('/content/nasa_smoke_source.py')
assert source.is_file(), 'Primero transfiere el archivo con colab upload'
assert torch.cuda.is_available(), 'No hay GPU CUDA disponible'
value = torch.tensor([2.0, 3.0], device='cuda').square().sum()
torch.cuda.synchronize()
assert value.item() == 13.0
result = {
    'python': platform.python_version(),
    'torch': torch.__version__,
    'torch_cuda': torch.version.cuda,
    'gpu': torch.cuda.get_device_name(0),
    'vram_bytes': torch.cuda.get_device_properties(0).total_memory,
    'gpu_ok': True,
    'uploaded_source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'nvidia_smi': subprocess.check_output(['nvidia-smi'], text=True),
}
destination = Path('/content/nasa-smoke-result.json')
destination.write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
print('Resultado remoto:', destination)
