
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

_identity=dict(status='prepared',accelerator='A100',session='order-collection-20261102-r6',
 cuda_verified_by_bootstrap=True,source_data_uploaded=False,automatic_retries=False,
 lock_sha256=hashlib.sha256((root/'requirements.lock').read_bytes()).hexdigest(),
 prepared_identity_sha256=hashlib.sha256((root/'prepared-identity.json').read_bytes()).hexdigest(),
 worker_sha256=hashlib.sha256((root/'xy-worker/target/release/order-memory-worker').read_bytes()).hexdigest(),
 code_archive_sha256=hashlib.sha256(Path('/content/order-code.tar.gz').read_bytes()).hexdigest(),
 code_files={'code/'+str(v.relative_to(delivery)):hashlib.sha256(v.read_bytes()).hexdigest() for v in (delivery/'reading_order').rglob('*') if v.is_file() and '__pycache__' not in v.parts})
Path('/content/order-prepared.json').write_text(json.dumps(_identity,indent=2))
print('ORDER_PREPARATION_COMMITTED',flush=True)
