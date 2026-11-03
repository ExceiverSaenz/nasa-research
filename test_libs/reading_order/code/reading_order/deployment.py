"""Explicit Colab lifecycle and code-only delivery. Never transports datasets."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from .preflight import production_fingerprint


BOOTSTRAP = r'''
from pathlib import Path
import hashlib,importlib.util,json,os,subprocess,sys,tarfile
delivery=Path('/content/order-code')
delivery.mkdir(exist_ok=False)
with tarfile.open('/content/order-code.tar.gz') as archive:
    archive.extractall(delivery,filter='data')
config=json.loads((delivery/'support/baseline.json').read_text())
root=Path('/content/order-config-20261102')
root.mkdir(exist_ok=False)
for source in (delivery/'support').iterdir():
    if source.is_file() and source.name!='baseline.json':
        (root/source.name).write_bytes(source.read_bytes())
os.environ['ORDER_VALIDATED_LOCK_SHA256']=config['lock_sha256']
sys.path.insert(0,str(root))
spec=importlib.util.spec_from_file_location('order_prepare',root/'prepare_environment.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.main()
python=root/'venv/bin/python'
script="import sys,json;from pathlib import Path;sys.path.insert(0,'"+str(root)+"');from environment_identity import verify,versions;verify(Path('"+str(root)+"'));expected=json.loads(Path('"+str(delivery/'support/baseline.json')+"').read_text());assert versions()==expected['versions'];from probe_environment import environment,cuda;environment();cuda();print('ORDER_ENV_IDENTITY_VERIFIED')"
p=subprocess.run([str(python),'-B','-c',script],capture_output=True,text=True)
print(p.stdout);print(p.stderr);p.check_returncode()
sources=json.loads((root/'sources.json').read_text())
worker=root/'xy-worker';(worker/'src').mkdir(parents=True)
dependency=root/'third_party'/('xycut-plus-plus-'+sources['repositories']['home-still/xycut-plus-plus'])
(worker/'Cargo.toml').write_text('[package]\nname="order-memory-worker"\nversion="0.1.0"\nedition="2021"\n[dependencies]\nxycut-plus-plus={path="'+str(dependency)+'"}\n')
(worker/'src/main.rs').write_bytes((delivery/'reading_order/adapters/xycut_worker.rs').read_bytes())
env=dict(os.environ,CARGO_HOME=str(root/'cargo'),RUSTUP_HOME=str(root/'rustup'))
env['PATH']=str(root/'cargo/bin')+os.pathsep+env['PATH']
p=subprocess.run([str(root/'cargo/bin/cargo'),'build','--offline','--release','--manifest-path',str(worker/'Cargo.toml')],env=env,capture_output=True,text=True)
print(p.stdout);print(p.stderr);p.check_returncode()
print('ORDER_ENVIRONMENT_READY',flush=True)
'''


class ColabController:
    def __init__(self, project_root, output, session):
        self.project = Path(project_root)
        self.output = Path(output)
        self.output.mkdir(parents=True,exist_ok=False)
        self.session = session
        self.executable = shutil.which('colab') or str(Path.home()/'.local/bin/colab')

    def command(self, args, phase, timeout=2400):
        with (self.output/(phase+'.log')).open('a') as log:
            result = subprocess.run([self.executable,*map(str,args)],stdout=log,stderr=subprocess.STDOUT,
                                    timeout=timeout,env=dict(os.environ,COLAB_CLI_ASSIGN_RETRIES='0'))
        if result.returncode:
            raise RuntimeError('Colab phase failed: '+phase+'; inspect this session, no automatic retry')
        return (self.output/(phase+'.log')).read_text()

    def prepare(self):
        package = self.project/'test_libs/reading_order'
        baseline = package/'raw_results/tests_results/20261102T052716Z-config-7e26b3'
        old = json.loads((baseline/'prepared-identity.json').read_text())
        lock = (baseline/'requirements.lock').read_bytes()
        lock_sha = hashlib.sha256(lock).hexdigest()
        if old['artifacts']['requirements.lock']!=lock_sha:
            raise ValueError('Validated lock identity changed')
        archive = self.output/'code-only.tar.gz'
        with tempfile.TemporaryDirectory(prefix='order-build-') as temp:
            temp = Path(temp)
            baseline_config = temp/'baseline.json'
            baseline_config.write_text(json.dumps(dict(lock_sha256=lock_sha,versions=old['versions'])))
            with tarfile.open(archive,'w:gz') as bundle:
                for source in (package/'code/reading_order').rglob('*'):
                    if source.is_file() and '__pycache__' not in source.parts:
                        bundle.add(source,arcname=str(source.relative_to(package/'code')))
                support = package/'test/test_config'
                for name in ('prepare_environment.py','validation.py','environment_identity.py','probe_environment.py',
                             'sources.json','requirements.in','xy_smoke.rs'):
                    bundle.add(support/name,arcname='support/'+name)
                bundle.add(baseline/'requirements.lock',arcname='support/validated-requirements.lock')
                bundle.add(baseline_config,arcname='support/baseline.json')
            self.command(['sessions'],'sessions-before')
            self.command(['new','-s',self.session,'--gpu','A100'],'create')
            self.command(['upload','-s',self.session,archive,'/content/order-code.tar.gz'],'upload-code')
            script = temp/'bootstrap.py'
            script.write_text(BOOTSTRAP)
            output = self.command(['exec','-s',self.session,'-f',script,'--timeout','2300'],'prepare')
            if 'ORDER_ENVIRONMENT_READY' not in output or 'ORDER_ENV_IDENTITY_VERIFIED' not in output:
                raise RuntimeError('Preparation lacks explicit host/environment confirmation')
        receipt = dict(session=self.session,accelerator='A100',lock_sha256=lock_sha,
                       code_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                       status='prepared',automatic_retries=False,source_data_uploaded=False,
                       code_files=production_fingerprint(package))
        (self.output/'environment.json').write_text(json.dumps(receipt,indent=2))
        return receipt

    def close(self):
        self.command(['stop','-s',self.session],'close',timeout=120)
