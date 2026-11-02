"""Explicit dependency resolution and installation. Never starts Colab."""
import json
import os
import platform
import subprocess
from pathlib import Path
from .contracts import sha256,write_json
from .layout import resolve_path, wheel_directory


def resolve_lock(uv,source,destination):
    if platform.system()!='Linux' or platform.machine()!='x86_64':raise ValueError('Resolve on Linux x86_64')
    source=Path(source);destination=Path(destination)
    if destination.exists():raise ValueError('Existing lock preserved')
    subprocess.run([str(uv),'pip','compile','--python-version','3.11','--generate-hashes',str(source),'-o',str(destination)],check=True,timeout=600)
    write_json(destination.with_suffix('.receipt.json'),dict(candidate_sha256=sha256(source),lock_sha256=sha256(destination),platform=platform.platform()))


def install_environment(base_python,target,lock):
    target=Path(target);lock=resolve_path(lock)
    if target.exists():raise ValueError('Existing environment is never patched')
    if not lock.is_file() or '--hash=sha256:' not in lock.read_text():raise ValueError('Hashed lock required')
    subprocess.run([str(base_python),'-m','venv',str(target)],check=True,timeout=120)
    python=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    subprocess.run([str(python),'-m','pip','install','--find-links',str(wheel_directory(lock)),'--require-hashes','-r',str(lock)],check=True,timeout=1800)
    return python
