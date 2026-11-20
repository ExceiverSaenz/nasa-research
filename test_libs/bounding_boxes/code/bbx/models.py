"""Metadata-only model discovery; downloads are a separate explicit operation."""
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from .contracts import check
from .environment import classify_artifact
from .contracts import contained


def validate_manifest(manifest):
    if not re.fullmatch('[0-9a-f]{40}',manifest.get('revision','')) or not manifest.get('repo') or not manifest.get('files'):
        raise ValueError('Immutable revision and nonempty file inventory required')
    for name,identity in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts or not re.fullmatch('[0-9a-f]{64}',identity.get('sha256','')) or identity.get('bytes',0)<=0:
            raise ValueError('Invalid model file identity')


def discover_manifest(repo,revision,files):
    if not re.fullmatch(r'[\w.-]+/[\w.-]+',repo):raise ValueError('Invalid repository')
    url='https://huggingface.co/api/models/'+repo+'/revision/'+urllib.parse.quote(revision,safe='')+'?blobs=true'
    with urllib.request.urlopen(url,timeout=30) as r:metadata=json.load(r)
    manifest={'repo':repo,'revision':metadata['sha'],'files':{}}
    siblings={s['rfilename']:s for s in metadata['siblings']}
    for name in files:
        s=siblings[name];lfs=s.get('lfs',{})
        if lfs.get('sha256'):
            identity={'bytes':lfs['size'],'sha256':lfs['sha256']}
        else:
            # Only small configuration files may be fetched during metadata discovery.
            if not name.endswith(('.json','.yml','.yaml','.txt','.jinja')):raise ValueError('Weight hash absent from model metadata')
            url='https://huggingface.co/'+repo+'/resolve/'+manifest['revision']+'/'+urllib.parse.quote(name,safe='/')
            with urllib.request.urlopen(url,timeout=30) as r:data=r.read(8*1024*1024+1)
            if len(data)>8*1024*1024:raise ValueError('Configuration too large')
            identity={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        manifest['files'][name]=identity
    validate_manifest(manifest);return manifest


def verify_models(root,manifest):
    validate_manifest(manifest);checks=[]
    for name,identity in manifest['files'].items():
        state=classify_artifact(contained(root,name),identity)
        checks.append(check('model:'+name,'PASS' if state=='valid' else 'NOT_RUN' if state=='missing' else 'FAIL',state))
    return checks


def fetch_models(root,manifest,*,apply=False):
    validate_manifest(manifest);checks=verify_models(root,manifest)
    if not apply:return checks
    for name,identity in manifest['files'].items():
        path=contained(root,name);state=classify_artifact(path,identity)
        if state=='valid':continue
        if state=='corrupt':raise ValueError('Corrupt artifact preserved; choose separate destination')
        url='https://huggingface.co/'+manifest['repo']+'/resolve/'+manifest['revision']+'/'+urllib.parse.quote(name,safe='/')
        path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.part')
        if temp.exists():raise ValueError('Partial file preserved; explicit recovery required')
        h=hashlib.sha256();size=0
        with urllib.request.urlopen(url,timeout=60) as response,temp.open('xb') as f:
            for chunk in iter(lambda:response.read(1024*1024),b''):
                size+=len(chunk);h.update(chunk);f.write(chunk)
        if size!=identity['bytes'] or h.hexdigest()!=identity['sha256']:raise ValueError('Downloaded model mismatch')
        temp.replace(path)
    return verify_models(root,manifest)
