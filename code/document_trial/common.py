"""Pure manifest and integrity utilities, Python3.9 compatible."""
import hashlib
import json
import math
from pathlib import Path,PurePosixPath
import re
import zipfile

ROOT=Path(__file__).resolve().parents[2]
DOCUMENT='9cea2fa5ad94c6a31031c72a9c3f698d571c85c810af644304c3b9f0d306f660'
PAGE3='6f46d8ff2d05eee785739ec1c34716db14135411c731e7aa6433e27ca06d00b9'
MODELS=('layoutlmv3','table_transformer','mineru')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def canonical(name):return re.sub(r'[-_.]+','-',name).lower()
def read(path):return json.loads(Path(path).read_bytes())
def default(value):
    if hasattr(value,'tolist'):return value.tolist()
    if hasattr(value,'item'):return value.item()
    raise TypeError('Unsupported JSON value: '+type(value).__name__)
def save(path,value):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False,default=default)+'\n',encoding='utf-8')

def freeze_versions(text,known):
    result={}
    for line in text.splitlines():
        line=line.strip()
        if line.startswith('# Editable'):
            name,version=re.search(r'\(([^=]+)==([^\)]+)\)',line).groups();result[canonical(name)]=version
        elif not line or line.startswith(('#','-e ')):continue
        elif ' @ ' in line:
            name=line.split(' @ ')[0];result[canonical(name)]=known[name]
        elif '==' in line:
            name,version=line.split('==',1);result[canonical(name)]=version
        else:raise ValueError('Unsupported frozen requirement: '+line)
    return result

def check_runtime(observed,spec):
    for field in ('python','cuda'):
        if observed.get(field)!=spec[field]:raise ValueError('INCOMPATIBLE '+field+'; no inference authorized')
    if observed.get('gpu')!='Tesla T4':raise ValueError('INCOMPATIBLE hardware; Tesla T4 required')
    actual=observed.get('packages',{})
    if not isinstance(actual,dict):raise ValueError('Invalid runtime package inventory')
    # pip freeze historically omits bootstrap tooling. Every non-tool runtime
    # distribution must match; no unrecorded model dependency may be added.
    actual={canonical(k):v for k,v in actual.items() if canonical(k) not in ('pip','setuptools','wheel') or canonical(k) in spec['packages']}
    if actual!=spec['packages']:raise ValueError('INCOMPATIBLE complete frozen package set; no inference')

def validate_bundle(archive,sidecar,destination=None):
    if sha(archive)!=Path(sidecar).read_text().strip():raise ValueError('Bundle SHA mismatch')
    with zipfile.ZipFile(archive) as z:
        manifest=json.loads(z.read('bundle-manifest.json'));names=z.namelist()
        if set(names)!=set(manifest['files'])|{'bundle-manifest.json'} or len(names)!=len(set(names)):raise ValueError('Unknown/duplicate members')
        blobs={}
        for n,spec in manifest['files'].items():
            p=PurePosixPath(n)
            if p.is_absolute() or '..' in p.parts or '\\' in n or ':' in n:raise ValueError('Unsafe member')
            data=z.read(n)
            if len(data)!=spec['bytes'] or hashlib.sha256(data).hexdigest()!=spec['sha256']:raise ValueError('Member mismatch '+n)
            blobs[n]=data
        if destination:
            destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
            for n,data in blobs.items():
                p=destination/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    return json.loads(blobs['plan.json'])

def box(normalized,width,height):
    if (not isinstance(normalized,(list,tuple)) or len(normalized)!=4 or
        any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in normalized)
        or normalized[2]<=normalized[0] or normalized[3]<=normalized[1]):raise ValueError('Invalid native normalized box')
    return [v*s for v,s in zip(normalized,(width,height,width,height))]

def verify_terminal(archive,sidecar,plan_bytes,bundle_sha256=None,attempt_id=None):
    if sha(archive)!=Path(sidecar).read_text().strip():raise ValueError('Terminal backup hash mismatch')
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None or len(z.namelist())!=len(set(z.namelist())):raise ValueError('Invalid terminal ZIP')
        if z.read('plan.json')!=plan_bytes:raise ValueError('Terminal plan differs')
        if bundle_sha256 is not None or attempt_id is not None:
            execution=json.loads(z.read('execution.json'))
            if bundle_sha256 is not None and execution.get('bundle_sha256')!=bundle_sha256:raise ValueError('Terminal bundle identity differs')
            if attempt_id is not None and execution.get('attempt_id')!=attempt_id:raise ValueError('Terminal attempt identity differs')
        status=json.loads(z.read('execution-status.json'))
        if status.get('status') not in ('completed','failed'):raise ValueError('Backup is not terminal')
        plan=json.loads(plan_bytes)
        for entry in plan.get('documents',[]):
            prefix='documents/'+entry['key']+'/'
            child=json.loads(z.read(prefix+'plan.json'))
            if child!=entry['plan']:raise ValueError('Terminal child plan differs')
            child_status=json.loads(z.read(prefix+'execution-status.json'))['status']
            if child_status not in ('completed','failed'):raise ValueError('Child is not terminal')
            if status['status']=='completed' and child_status!='completed':raise ValueError('Batch completion contradicts child')
            for page in child['physical_pages']:
                folder=prefix+'pages/'+('%04d'%page)+'/'
                for model in MODELS:
                    result=json.loads(z.read(folder+model+'/status.json'))
                    if result.get('page')!=page or result.get('model')!=model or result.get('status') not in ('completed','failed','not_run'):
                        raise ValueError('Invalid page/parser accounting')
                    if child_status=='completed' and result['status']!='completed':raise ValueError('Child completion contradicts page')
                    if result['status']=='completed':
                        identity=json.loads(z.read(folder+'identity.json'))
                        if identity.get('document_sha256')!=entry['key'] or identity.get('physical_page')!=page:
                            raise ValueError('Terminal page identity differs')
                        required={'mineru':['middle-native.json','regions.json'],
                            'table_transformer':['regions-raw.json','regions.json','detector.json'],
                            'layoutlmv3':['regions.json','detector.json']}[model]
                        for name in required:
                            if folder+model+'/'+name not in z.namelist():raise ValueError('Missing native output '+name)
    return status
