"""Allowlisted package of the original PNG and new code. Standard library only."""
import hashlib
import json
from pathlib import Path
import zipfile

IMAGE_SHA256 = '6f46d8ff2d05eee785739ec1c34716db14135411c731e7aa6433e27ca06d00b9'
FILES = ('table_transformer/__init__.py', 'table_transformer/detector.py',
         'table_transformer/outputs.py', 'table_transformer/run_image.py',
         'render.png', 'source.json', 'requirements.txt')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(4*1024*1024),b''): digest.update(block)
    return digest.hexdigest()


def prepare_bundle(destination):
    root = Path(__file__).resolve().parents[2]
    previous = root/'code/results/layoutlmv3-page/20261023T153938Z/result.zip'
    if sha256(previous) != previous.with_suffix('.sha256').read_text().strip():
        raise ValueError('Previous result ZIP hash mismatch')
    with zipfile.ZipFile(previous) as source:
        if source.testzip() is not None: raise ValueError('Previous ZIP corrupt')
        image = source.read('page/render.png')
        previous_manifest = json.loads(source.read('page/run-manifest.json'))
    if hashlib.sha256(image).hexdigest() != IMAGE_SHA256:
        raise ValueError('Original render changed')
    contents = {name: (root/'code'/name).read_bytes() for name in FILES if name.startswith('table_transformer/')}
    contents['render.png'] = image
    contents['requirements.txt'] = Path(__file__).with_name('requirements.txt').read_bytes()
    contents['source.json'] = json.dumps({'document': previous_manifest['document'],
        'render': previous_manifest['render'], 'baseline_run_id': previous_manifest['run_id'],
        'baseline_archive_sha256': sha256(previous)}, indent=2).encode()
    manifest = {'image_sha256': IMAGE_SHA256, 'files': {name: {
        'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest()} for name,data in contents.items()}}
    destination = Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as output:
        for name,data in contents.items(): output.writestr(name,data)
        output.writestr('bundle-manifest.json',json.dumps(manifest,indent=2))
    destination.with_suffix('.sha256').write_text(sha256(destination)+'\n',encoding='ascii')
    return manifest


def unpack_bundle(bundle, sidecar, destination):
    if sha256(bundle) != Path(sidecar).read_text(encoding='ascii').strip():
        raise ValueError('Bundle SHA256 mismatch')
    with zipfile.ZipFile(bundle) as source:
        names=source.namelist()
        if set(names) != set(FILES)|{'bundle-manifest.json'} or len(names)!=len(FILES)+1:
            raise ValueError('Unexpected or duplicate bundle entries')
        manifest=json.loads(source.read('bundle-manifest.json'))
        if set(manifest['files'])!=set(FILES) or manifest['image_sha256']!=IMAGE_SHA256:
            raise ValueError('Unexpected bundle manifest')
        for name in FILES:
            data=source.read(name);expected=manifest['files'][name]
            if len(data)!=expected['bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:
                raise ValueError('Bundle member mismatch: '+name)
        if hashlib.sha256(source.read('render.png')).hexdigest()!=IMAGE_SHA256:
            raise ValueError('Input render mismatch')
        destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
        for name in names:
            path=destination/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(source.read(name))
    return manifest


if __name__=='__main__':
    destination=Path(__file__).resolve().parents[1]/'packages/table-transformer-page.zip'
    prepare_bundle(destination)
    print('Paquete preparado:',destination)
