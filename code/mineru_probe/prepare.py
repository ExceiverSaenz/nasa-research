"""Allowlisted code + exact baseline PNG, never PDF collection or weights."""
import hashlib
import json
from pathlib import Path
import zipfile

IMAGE_SHA256='6f46d8ff2d05eee785739ec1c34716db14135411c731e7aa6433e27ca06d00b9'
FILES=('mineru_probe/__init__.py','mineru_probe/run_image.py','mineru_probe/outputs.py',
       'render.png','requirements.lock','model-manifest.json')


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(4*1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def prepare_bundle(destination):
    root=Path(__file__).resolve().parents[2]
    image=root/'code/results/layoutlmv3-page/20261023T153938Z/review/render.png'
    if sha256(image)!=IMAGE_SHA256:raise ValueError('Original render changed')
    contents={name:(root/'code'/name).read_bytes() if name.startswith('mineru_probe/')
              else Path(__file__).with_name(name).read_bytes() for name in FILES if name!='render.png'}
    contents['render.png']=image.read_bytes()
    manifest={'image_sha256':IMAGE_SHA256,'files':{
        name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in contents.items()}}
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in contents.items():z.writestr(name,data)
        z.writestr('bundle-manifest.json',json.dumps(manifest,indent=2))
    destination.with_suffix('.sha256').write_text(sha256(destination)+'\n',encoding='ascii')
    return manifest


def unpack_bundle(bundle, sidecar, destination):
    if sha256(bundle)!=Path(sidecar).read_text().strip():raise ValueError('Bundle hash mismatch')
    with zipfile.ZipFile(bundle) as z:
        if set(z.namelist())!=set(FILES)|{'bundle-manifest.json'} or len(z.namelist())!=len(FILES)+1:
            raise ValueError('Unexpected/duplicate ZIP entries')
        manifest=json.loads(z.read('bundle-manifest.json'))
        if set(manifest['files'])!=set(FILES) or manifest['image_sha256']!=IMAGE_SHA256:
            raise ValueError('Invalid manifest')
        for name in FILES:
            data=z.read(name);expected=manifest['files'][name]
            if len(data)!=expected['bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:
                raise ValueError('Member mismatch: '+name)
        if hashlib.sha256(z.read('render.png')).hexdigest()!=IMAGE_SHA256:raise ValueError('Image mismatch')
        destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
        for name in z.namelist():
            target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
    return manifest


if __name__=='__main__':
    destination=Path(__file__).resolve().parents[1]/'packages/mineru-page.zip'
    prepare_bundle(destination);print('Paquete preparado:',destination)
