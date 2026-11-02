"""Integrity and file transport, using only the standard library."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[1]



def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

def file_manifest(root):
    return {p.relative_to(root).as_posix(): {'sha256': digest(p), 'bytes': p.stat().st_size}
            for p in sorted(root.rglob('*')) if p.is_file() and p != root/'files.json'}

class IntegrityService:
    """Verify a specific baseline root without module-global configuration."""

    def __init__(self, root=ROOT):
        self.root = Path(root)

    def verify_lock(self):
        root = self.root
        receipt = json.loads((root / 'lock-verification.json').read_text(encoding='utf-8'))
        for name, field in [('requirements.in', 'input_sha256'), ('requirements.lock', 'lock_sha256')]:
            if digest(root / name) != receipt[field]: raise ValueError('Sealed input changed: ' + name)
        return receipt

    def verify_files(self, root):
        expected = json.loads((root / 'files.json').read_text(encoding='utf-8'))
        if file_manifest(root) != expected: raise ValueError('Result file manifest mismatch')
        return expected

    def extract(self, archive, destination):
        destination = Path(destination).resolve()
        if destination.exists(): raise FileExistsError(destination)
        with tarfile.open(archive) as tar:
            seen = set()
            for member in tar.getmembers():
                p = PurePosixPath(member.name)
                if (not member.isfile() or p.is_absolute() or '..' in p.parts or '\\' in member.name
                        or ':' in member.name or member.name in seen):
                    raise ValueError('Unsafe transport member')
                seen.add(member.name)
            destination.mkdir(parents=True)
            tar.extractall(destination, filter='data')

