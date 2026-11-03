"""Explicit preparation of a fresh disposable A100 configuration environment.

Invoked by run_config.py with only test code/configuration uploaded, never datasets.
Separate preparation from probes; no installer runs during a check or import.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import urllib.request

ROOT = Path('/content/order-config-20261102')


def command(argv, **kwargs):
    result = subprocess.run(list(map(str, argv)), capture_output=True, text=True, **kwargs)
    print(result.stdout, flush=True)
    print(result.stderr, flush=True)
    result.check_returncode()


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def main():
    gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], text=True)
    if 'A100' not in gpu or (ROOT / 'venv').exists():
        raise ValueError('Requires A100 and a fresh configuration environment')
    sources = json.loads((ROOT / 'sources.json').read_text())
    validated = os.environ.get('ORDER_VALIDATED_LOCK_SHA256')
    if validated:
        lock_input = ROOT/'validated-requirements.lock'
        if not lock_input.is_file() or hashlib.sha256(lock_input.read_bytes()).hexdigest()!=validated:
            raise ValueError('Explicit validated lock is missing or changed')
    command(['uv', 'python', 'install', '3.11.16'])
    command(['uv', 'venv', '--python', '3.11.16', '--seed', ROOT / 'venv'])
    python = ROOT / 'venv/bin/python'
    if validated:
        (ROOT/'requirements.lock').write_bytes(lock_input.read_bytes())
    else:
        command(['uv', 'pip', 'compile', ROOT / 'requirements.in', '--python', python,
                 '--index-url', 'https://pypi.org/simple', '--extra-index-url', 'https://download.pytorch.org/whl/cu128',
                 '--index-strategy', 'unsafe-best-match', '--generate-hashes',
                 '--output-file', ROOT / 'requirements.lock'])
    command(['uv', 'pip', 'sync', '--python', python, '--require-hashes', ROOT / 'requirements.lock',
             '--index-url', 'https://pypi.org/simple', '--extra-index-url', 'https://download.pytorch.org/whl/cu128',
             '--index-strategy', 'unsafe-best-match'])
    # pip is a test tool, installed by uv venv --seed. Sync can remove it as extraneous;
    # use uv pip check for the receipt as well as the Python pip check when available.
    command(['uv', 'pip', 'check', '--python', python])
    helper_urls = {
        'hantian_helpers.py': 'https://raw.githubusercontent.com/FreeOCR-AI/layoutreader/' + sources['repositories']['FreeOCR-AI/layoutreader'] + '/v3/helpers.py',
        'xycut.py': 'https://raw.githubusercontent.com/Sanster/xy-cut/' + sources['repositories']['Sanster/xy-cut'] + '/xycut.py',
    }
    hashes = {}
    for name, url in helper_urls.items():
        content = fetch(url)
        (ROOT / name).write_bytes(content)
        hashes[name] = hashlib.sha256(content).hexdigest()
    rustup = fetch('https://static.rust-lang.org/rustup/archive/1.28.2/x86_64-unknown-linux-gnu/rustup-init')
    expected = fetch('https://static.rust-lang.org/rustup/archive/1.28.2/x86_64-unknown-linux-gnu/rustup-init.sha256').decode().split()[0]
    if hashlib.sha256(rustup).hexdigest() != expected:
        raise ValueError('Rust installer checksum mismatch')
    installer = ROOT / 'rustup-init'
    installer.write_bytes(rustup)
    installer.chmod(0o700)
    env = dict(os.environ, CARGO_HOME=str(ROOT / 'cargo'), RUSTUP_HOME=str(ROOT / 'rustup'))
    command([installer, '-y', '--no-modify-path', '--profile', 'minimal', '--default-toolchain', '1.90.0'], env=env)
    env['PATH'] = str(ROOT / 'cargo/bin') + os.pathsep + env['PATH']
    commit = sources['repositories']['home-still/xycut-plus-plus']
    archive_bytes = fetch('https://codeload.github.com/home-still/xycut-plus-plus/tar.gz/' + commit)
    hashes['xycut_plus_plus_archive'] = hashlib.sha256(archive_bytes).hexdigest()
    with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as archive:
        archive.extractall(ROOT / 'third_party', filter='data')
    dependency = ROOT / 'third_party' / ('xycut-plus-plus-' + commit)
    client = ROOT / 'xy-smoke'
    (client / 'src').mkdir(parents=True)
    (client / 'Cargo.toml').write_text('[package]\nname="order-config-smoke"\nversion="0.1.0"\nedition="2021"\n[dependencies]\nxycut-plus-plus={path="' + str(dependency) + '"}\n')
    (client / 'src/main.rs').write_bytes((ROOT / 'xy_smoke.rs').read_bytes())
    command([ROOT / 'cargo/bin/cargo', 'build', '--release', '--manifest-path', client / 'Cargo.toml'], env=env)
    # Explicit preparation may download checkpoints; the probes load local files only.
    script = """
import json
from pathlib import Path
from huggingface_hub import snapshot_download
root=Path('/content/order-config-20261102')
sources=json.loads((root/'sources.json').read_text())
for model,folder in [('hantian/layoutreader','hantian'),('PaddlePaddle/PP-DocLayoutV2_safetensors','pp_doclayout_v2')]:
    snapshot_download(model,revision=sources['models'][model],local_dir=root/'models'/folder,
                      allow_patterns=['config.json','model.safetensors'])
"""
    command([python, '-B', '-c', script])
    (ROOT / 'source-hashes.json').write_text(json.dumps(hashes, indent=2))
    command([python, '-B', '-c', "import sys; from pathlib import Path; sys.path.insert(0,'" + str(ROOT) + "'); from environment_identity import seal; seal(Path('" + str(ROOT) + "'),'" + hashlib.sha256((ROOT / 'requirements.in').read_bytes()).hexdigest() + "','" + hashlib.sha256((ROOT / 'sources.json').read_bytes()).hexdigest() + "')"])
    print('ORDER_CONFIG_PREPARED', flush=True)


if __name__ == '__main__':
    main()
