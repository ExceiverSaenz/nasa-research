"""Build an explicit small inference bundle locally; never contacts Colab."""
import hashlib
import json
from pathlib import Path
import zipfile


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def prepare_bundle(destination):
    root = Path(__file__).resolve().parents[2]
    code = root / 'code/layoutlmv3'
    files = {('inference/' + name): code / 'inference' / name for name in
             ('__init__.py', 'types.py', 'render.py', 'detector.py', 'outputs.py', 'run_page.py')}
    files['requirements-page.txt'] = code / 'requirements-page.txt'
    files['SiC-12.pdf'] = root / 'SiC_papers/12.pdf'
    if sha256(files['SiC-12.pdf']) != '9cea2fa5ad94c6a31031c72a9c3f698d571c85c810af644304c3b9f0d306f660':
        raise ValueError('Selected PDF changed; review before running')
    manifest = {'page': 3, 'dpi': 200, 'files': {
        name: {'bytes': path.stat().st_size, 'sha256': sha256(path)} for name, path in files.items()}}
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as output:
        for name, path in files.items():
            output.write(path, name)
        output.writestr('manifest.json', json.dumps(manifest, indent=2))
    destination.with_suffix('.sha256').write_text(sha256(destination) + '\n', encoding='ascii')
    return manifest


if __name__ == '__main__':
    bundle = Path(__file__).resolve().parents[1] / 'packages/layoutlmv3-page.zip'
    prepare_bundle(bundle)
    print('Paquete local preparado:', bundle)
