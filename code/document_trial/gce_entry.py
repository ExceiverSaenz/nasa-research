"""Human-only GCE entry and offline receipt. Imports are inert, no models."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import uuid
from urllib.request import Request, build_opener, ProxyHandler
import zipfile
from .common import MODELS, read, save, sha, validate_bundle, verify_terminal


def remote_launch_script(attempt, expected):
    if not re.fullmatch('[0-9a-f]{32}',attempt):raise ValueError('Invalid attempt')
    for key in ('project','instance','zone'):
        if not re.fullmatch('[a-z][a-z0-9-]{0,62}',expected.get(key,'')):raise ValueError('Unsafe GCE identity')
    if not re.fullmatch('[0-9]+',expected.get('instance_id','')):raise ValueError('Numeric instance identity required')
    return '''#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
test -d /content && test -w /content
mkdir /content/gce-claimed
for name in nasa-sic12-document-v1 nasa-sic12-document-v1-inputs nasa-sic12-document-v1.zip nasa-sic12-document-v1.sha256 nasa-sic12-document-v1-upload.zip nasa-sic12-document-v1-upload.sha256 nasa-sic12-document-v1-attempt.json gce-host.json gce-console.log; do
  if [[ -e /content/$name ]]; then echo "Existing evidence: $name; no overwrite/retry" >&2; exit 1; fi
done
expected=$(tr -d '\\r\\n' < upload.sha256)
actual=$(sha256sum upload.zip | cut -d ' ' -f1)
[[ "$actual" == "$expected" ]]
cp upload.zip /content/nasa-sic12-document-v1-upload.zip
cp upload.sha256 /content/nasa-sic12-document-v1-upload.sha256
cp attempt.json /content/nasa-sic12-document-v1-attempt.json
sudo systemd-run --unit=nasa-parsing-ATTEMPT --uid="$(id -u)" --gid="$(id -g)" \\
  --property=Restart=no --property=RemainAfterExit=yes --property=WorkingDirectory=/content \\
  --property=StandardOutput=append:/content/gce-console.log --property=StandardError=inherit \\
  --setenv=PYTHONPATH=/content/nasa-sic12-document-v1-upload.zip --setenv=PYTHONUNBUFFERED=1 \\
  --setenv="HOME=$HOME" /usr/bin/python3 -B -u -m document_trial.gce_entry run --user-run \\
  --project=PROJECT --instance=INSTANCE --zone=ZONE --instance-id=INSTANCEID
echo "Servicio enviado. Esto no confirma parsing ni respaldo terminal."
'''.replace('ATTEMPT',attempt).replace('PROJECT',expected['project']).replace('INSTANCEID',expected['instance_id']).replace('INSTANCE',expected['instance']).replace('ZONE',expected['zone'])


def validate_host(host, expected):
    for name in ('project','instance','zone','instance_id'):
        if not expected.get(name) or host.get(name)!=expected[name]:raise ValueError('GCE identity mismatch: '+name)
    if host.get('gpu') not in ('Tesla T4','NVIDIA Tesla T4'):raise ValueError('Exactly one Tesla T4 required')
    try:driver=tuple(int(n) for n in host['driver'].split('.'))
    except (KeyError,ValueError,TypeError):raise ValueError('Unknown NVIDIA driver')
    if driver<(560,28,3):raise ValueError('Driver >=560.28.03 required for original CUDA12.6')
    if host.get('free_bytes',0)<60*1024**3:raise ValueError('At least 60GiB free space required')


def collect_host():
    opener=build_opener(ProxyHandler({}))
    def metadata(path):
        request=Request('http://metadata.google.internal/computeMetadata/v1/'+path,headers={'Metadata-Flavor':'Google'})
        with opener.open(request,timeout=5) as response:
            if response.headers.get('Metadata-Flavor')!='Google':raise ValueError('Not Google metadata')
            return response.read(4096).decode().strip()
    host=dict(project=metadata('project/project-id'),instance=metadata('instance/name'),
              zone=metadata('instance/zone').split('/')[-1],instance_id=metadata('instance/id'))
    output=subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version','--format=csv,noheader'],text=True,timeout=15)
    lines=output.strip().splitlines()
    if len(lines)!=1:raise ValueError('Exactly one GPU required')
    gpu,driver=lines[0].split(',',1)
    host.update(gpu=gpu.strip(),driver=driver.strip(),free_bytes=shutil.disk_usage('/content').free,
                platform=platform.platform(),python_bootstrap=platform.python_version())
    return host


def verify_gce_terminal(archive, sidecar, plan_bytes, bundle_sha256, attempt_id, expected):
    status=verify_terminal(archive,sidecar,plan_bytes,bundle_sha256,attempt_id)
    plan=json.loads(plan_bytes)
    with zipfile.ZipFile(archive) as z:
        execution=json.loads(z.read('execution.json'));host=json.loads(z.read('gce-host.json'))
        if execution.get('initiator')!='human_gce_ssh':raise ValueError('Backup is not GCE output')
        for key in ('project','instance','zone','instance_id'):
            if not expected.get(key) or host.get(key)!=expected[key]:raise ValueError('Backup host differs: '+key)
        names=set(z.namelist())
        for page in plan['physical_pages']:
            folder='pages/%04d/'%page
            for model in MODELS:
                result=json.loads(z.read(folder+model+'/status.json'))
                if result.get('page')!=page or result.get('model')!=model or result.get('status') not in ('completed','failed','not_run'):
                    raise ValueError('Invalid page/parser accounting')
                if status['status']=='completed' and result['status']!='completed':raise ValueError('Completion contradicts page')
                if result['status']=='completed':
                    identity=json.loads(z.read(folder+'identity.json'))
                    if identity.get('document_sha256')!=plan['document_sha256'] or identity.get('physical_page')!=page:
                        raise ValueError('Page identity differs')
                    render=z.read(folder+'render.png')
                    import hashlib
                    if hashlib.sha256(render).hexdigest()!=identity.get('render_sha256'):raise ValueError('Render hash differs')
                    required={'layoutlmv3':['regions.json','detector.json'],
                        'table_transformer':['regions-raw.json','regions.json','detector.json'],
                        'mineru':['middle-native.json','regions.json']}[model]
                    for member in required:
                        if folder+model+'/'+member not in names:raise ValueError('Missing native output: '+member)
    return status


def user_run(expected, authorized):
    if not authorized or platform.system()!='Linux' or not Path('/content').is_dir():
        raise RuntimeError('Explicit human GCE Linux invocation required')
    from . import remote
    bundle=Path('/content/nasa-sic12-document-v1-upload.zip')
    plan=validate_bundle(bundle,bundle.with_suffix('.sha256'))
    if plan.get('execution_policy')!='USER_ONLY_GCE_SSH_T4' or 'documents' in plan:raise ValueError('GCE single-paper bundle required')
    host=collect_host();validate_host(host,expected)
    hostfile=Path('/content/gce-host.json')
    with hostfile.open('x',encoding='utf-8') as output:json.dump(host,output,indent=2)
    os.environ['NASA_DOCUMENT_USER_RUN']='GCE_SSH_T4'
    return remote.main()


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    run=sub.add_parser('run');run.add_argument('--user-run',action='store_true')
    for name in ('project','instance','zone'):run.add_argument('--'+name,required=True)
    run.add_argument('--instance-id',required=True)
    for command in ('prepare-attempt','bind-instance','write-launch','verify'):
        parser=sub.add_parser(command);parser.add_argument('--package',type=Path,required=True);parser.add_argument('--run',type=Path,required=True)
        if command=='prepare-attempt':
            for name in ('project','instance','zone'):parser.add_argument('--'+name,required=True)
        if command=='bind-instance':parser.add_argument('--instance-id',required=True)
    args=p.parse_args()
    if args.command=='run':return user_run({k:getattr(args,k) for k in ('project','instance','zone','instance_id')},args.user_run)
    package=args.package;plan=validate_bundle(package/'upload.zip',package/'upload.sha256')
    if (package/'plan.json').read_bytes()!=json.dumps(plan,indent=2).encode()+b'\n':raise ValueError('External plan differs')
    if plan.get('execution_policy')!='USER_ONLY_GCE_SSH_T4':raise ValueError('GCE package required')
    if args.command=='prepare-attempt':
        args.run.mkdir(parents=True,exist_ok=False)
        save(args.run/'attempt.json',dict(attempt_id=uuid.uuid4().hex,bundle_sha256=sha(package/'upload.zip'),
            **{k:getattr(args,k) for k in ('project','instance','zone')}))
        return 0
    attempt=read(args.run/'attempt.json')
    if attempt.get('bundle_sha256')!=sha(package/'upload.zip'):raise ValueError('Attempt belongs to another bundle')
    if args.command=='bind-instance':
        if 'instance_id' in attempt or not re.fullmatch('[0-9]+',args.instance_id):raise ValueError('Invalid or already bound VM identity')
        save(args.run/'attempt.json',dict(attempt,instance_id=args.instance_id))
        return 0
    if args.command=='write-launch':
        with (args.run/'launch.sh').open('x',encoding='utf-8',newline='\n') as output:
            output.write(remote_launch_script(attempt['attempt_id'],attempt))
        return 0
    status=verify_gce_terminal(args.run/'result.zip',args.run/'result.sha256',(package/'plan.json').read_bytes(),
        sha(package/'upload.zip'),attempt['attempt_id'],attempt)
    save(args.run/'backup-verified.json',dict(backup_verified=True,status=status['status'],sha256=sha(args.run/'result.zip')))
    print('Respaldo terminal verificado:',status['status'])
    # Receipt validity and parser success are different. A failed terminal run is
    # a valid backup, permits explicit stop, and never permits an automatic retry.
    if status['status']=='failed':print('Parsing fallido: conservar respaldo y revisar, sin retry.')
    return 0


if __name__=='__main__':raise SystemExit(main())
