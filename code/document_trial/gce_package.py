"""Derive a NEW GCE package from a verified Colab bundle, offline only."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import zipfile
from .common import read, save, sha, validate_bundle


def replace_required(data, old, new):
    if old not in data:raise ValueError('Baseline source no longer matches approved transformation: '+old.decode())
    return data.replace(old,new)


def prepare_gce(base, destination):
    base=Path(base);destination=Path(destination)
    if destination.exists():raise FileExistsError('New package required; no overwrite')
    original=validate_bundle(base/'upload.zip',base/'upload.sha256')
    if ('documents' in original or original.get('execution_policy')!='USER_ONLY_COLAB_CLI_T4'
            or original.get('automatic_recovery') is not False or original.get('automatic_retries') is not False):
        raise ValueError('Single original user-only package with no retries required')
    with zipfile.ZipFile(base/'upload.zip') as z:
        blobs={n:z.read(n) for n in z.namelist() if n!='bundle-manifest.json'}
    if blobs['plan.json']!=(base/'plan.json').read_bytes():raise ValueError('External plan differs')
    for name in ('document_trial/remote.py','document_trial/worker.py'):
        data=blobs[name]
        for old,new in [(b'USER_ONLY_COLAB_CLI_T4',b'USER_ONLY_GCE_SSH_T4'),
                        (b'COLAB_CLI_T4',b'GCE_SSH_T4')]:
            # worker only has the runtime flag; remote has both policy and flag.
            if old in data:data=replace_required(data,old,new)
        if b'GCE_SSH_T4' not in data:raise ValueError('Missing original runtime gate')
        if name.endswith('/remote.py'):
            data=replace_required(data,b'human_colab_cli',b'human_gce_ssh')
            data=replace_required(data,b"    status=dict(status='failed',initiator=",
                b"    save(state/'gce-host.json',read('/content/gce-host.json'))\n    status=dict(status='failed',initiator=")
        data=data.replace(b'Colab CLI',b'Compute Engine SSH').replace(b'User Colab',b'User Compute Engine')
        blobs[name]=data
    entry=Path(__file__).with_name('gce_entry.py')
    blobs['document_trial/gce_entry.py']=entry.read_bytes()
    plan=dict(original,execution_policy='USER_ONLY_GCE_SSH_T4',platform_change=dict(
        version='gce-parsing-v1',baseline_bundle_sha256=sha(base/'upload.zip'),
        baseline_plan_sha256=hashlib.sha256(blobs['plan.json']).hexdigest(),
        changed_source_members=['document_trial/remote.py','document_trial/worker.py'],
        retained_paths='/content',inference_adapters_changed=False))
    blobs['plan.json']=(json.dumps(plan,indent=2)+'\n').encode()
    manifest={'files':{n:dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest()) for n,b in sorted(blobs.items())}}
    destination.mkdir(parents=True)
    with zipfile.ZipFile(destination/'upload.zip','x',zipfile.ZIP_DEFLATED) as z:
        for n,b in sorted(blobs.items()):z.writestr(n,b)
        z.writestr('bundle-manifest.json',json.dumps(manifest,indent=2))
    (destination/'upload.sha256').write_text(sha(destination/'upload.zip')+'\n',encoding='ascii')
    (destination/'plan.json').write_bytes(blobs['plan.json'])
    save(destination/'platform-change.json',dict(plan['platform_change'],bundle_sha256=sha(destination/'upload.zip'),
        original_plan=original,source_sha256={n:manifest['files'][n]['sha256'] for n in plan['platform_change']['changed_source_members']}))
    validate_bundle(destination/'upload.zip',destination/'upload.sha256')
    return plan


def release(package, destination):
    """One Cloud Shell upload, with launch/verification code bound to this bundle."""
    package=Path(package);destination=Path(destination)
    if destination.exists():raise FileExistsError('New release archive required')
    validate_bundle(package/'upload.zip',package/'upload.sha256')
    with tarfile.open(destination,'x:gz') as archive:
        for name in ('upload.zip','upload.sha256','plan.json','platform-change.json'):
            archive.add(package/name,arcname='sic-gce-v1/package/'+name)
        for name in ('gce.sh','gce_bootstrap.sh','GCE.md'):
            archive.add(Path(__file__).with_name(name),arcname='sic-gce-v1/'+name)
    destination.with_suffix(destination.suffix+'.sha256').write_text(sha(destination)+'\n',encoding='ascii')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--release')
    args=parser.parse_args();prepare_gce(args.base,args.output)
    if args.release:release(args.output,args.release)
    print('Paquete GCE verificado offline. Sin modelos, red ni VM.')
