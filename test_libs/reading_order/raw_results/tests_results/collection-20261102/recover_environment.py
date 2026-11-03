"""Verify already-built artifacts; no installs, rebuilds or model inference."""
import json,hashlib,sys,subprocess
from pathlib import Path
from colab_cli.state import StateStore
from colab_cli.runtime import ColabRuntime
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'code'))
from reading_order.colab_backend import ColabStdinTransport
from reading_order.preflight import production_fingerprint,require_test_receipt
base=Path(__file__).parent;update='--update-transport' in sys.argv
require_test_receipt(root,base/('offline-transport-final-linux/test-receipt.json' if update else 'offline-pdf-reference/test-receipt.json'))
if update:
    with (base/'environment-r4/transport-upload.log').open('w') as stream:
        for name in ('colab_backend.py','collection.py'):
            subprocess.run([str(Path.home()/'.local/bin/colab'),'upload','-s','order-collection-20261102-r4',
                str(root/'code/reading_order'/name),'/content/order-code/reading_order/'+name],
                stdout=stream,stderr=subprocess.STDOUT,timeout=45,check=True)
transport=ColabStdinTransport('order-collection-20261102-r4')
code="""
import json,hashlib,subprocess
from pathlib import Path
r=Path('/content/order-config-20261102');d=Path('/content/order-code')
script="import sys,json;from pathlib import Path;sys.path.insert(0,'/content/order-config-20261102');from environment_identity import verify,versions;verify(Path('/content/order-config-20261102'));b=json.loads(Path('/content/order-code/support/baseline.json').read_text());assert versions()==b['versions'];from probe_environment import environment,cuda;environment();cuda();print('VERIFIED')"
p=subprocess.run([str(r/'venv/bin/python'),'-B','-c',script],capture_output=True,text=True,timeout=90)
p.check_returncode();assert 'VERIFIED' in p.stdout
worker=r/'xy-worker/target/release/order-memory-worker';assert worker.is_file()
files={'code/'+str(v.relative_to(d)):hashlib.sha256(v.read_bytes()).hexdigest() for v in (d/'reading_order').rglob('*') if v.is_file() and '__pycache__' not in v.parts}
print('ORDER_ENV_RECOVERED:'+json.dumps(dict(code_files=files,lock_sha256=hashlib.sha256((r/'requirements.lock').read_bytes()).hexdigest(),worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),prepared_identity_sha256=hashlib.sha256((r/'prepared-identity.json').read_bytes()).hexdigest())))
"""
try:
    transport._register("print('ORDER_COMM_READY')")
    outputs=transport._run_code(code,120)
    lines=''.join(v.get('text','') for v in outputs).splitlines()
    value=json.loads(next(line.split('ORDER_ENV_RECOVERED:',1)[1] for line in lines if line.startswith('ORDER_ENV_RECOVERED:')))
    assert value['code_files']==production_fingerprint(root)
    expected=hashlib.sha256((root/'raw_results/tests_results/20261102T052716Z-config-7e26b3/requirements.lock').read_bytes()).hexdigest()
    assert value['lock_sha256']==expected
    receipt=dict(value,session='order-collection-20261102-r4',accelerator='A100',status='prepared',automatic_retries=False,
        source_data_uploaded=False,code_archive_sha256=hashlib.sha256((base/'environment-r4/code-only.tar.gz').read_bytes()).hexdigest(),
        preparation_recovery='Verified completed artifacts and CUDA through a fresh client; no reinstall or rebuild')
    if update:
        previous=base/'environment-r4/recovered-environment.json'
        receipt['transport_update']=dict(original_receipt=str(previous),original_sha256=hashlib.sha256(previous.read_bytes()).hexdigest(),
            updated_files={name:sha for name,sha in value['code_files'].items() if name.endswith(('/colab_backend.py','/collection.py'))})
    (base/'environment-r4'/('bounded-transport-environment.json' if update else 'recovered-environment.json')).write_text(json.dumps(receipt,indent=2))
    print(json.dumps(dict(status='PASS',code_files=len(value['code_files']),lock_sha256=expected)),flush=True)
except Exception as error:
    print(json.dumps(dict(status='FAIL',error_type=type(error).__name__)),flush=True)
    raise SystemExit(1)
finally:transport._disconnect()
