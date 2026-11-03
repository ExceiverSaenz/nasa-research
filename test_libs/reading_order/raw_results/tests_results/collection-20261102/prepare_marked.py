"""Prepare once with a durable metadata marker after CUDA and worker checks."""
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'code'))
from reading_order.deployment import ColabController
from reading_order.preflight import require_test_receipt
base=Path(__file__).parent
require_test_receipt(root,base/'offline-direct-api-linux/test-receipt.json')
session=sys.argv[1] if len(sys.argv)>1 else 'order-collection-20261102-r5'
folder=base/('environment-'+session.rsplit('-',1)[-1])
class MarkedController(ColabController):
    def command(self,args,phase,timeout=2400):
        if phase=='prepare':
            script=Path(args[args.index('-f')+1])
            marker="""
_identity=dict(status='prepared',accelerator='A100',session=SESSION,
 cuda_verified_by_bootstrap=True,source_data_uploaded=False,automatic_retries=False,
 lock_sha256=hashlib.sha256((root/'requirements.lock').read_bytes()).hexdigest(),
 prepared_identity_sha256=hashlib.sha256((root/'prepared-identity.json').read_bytes()).hexdigest(),
 worker_sha256=hashlib.sha256((root/'xy-worker/target/release/order-memory-worker').read_bytes()).hexdigest(),
 code_archive_sha256=hashlib.sha256(Path('/content/order-code.tar.gz').read_bytes()).hexdigest(),
 code_files={'code/'+str(v.relative_to(delivery)):hashlib.sha256(v.read_bytes()).hexdigest() for v in (delivery/'reading_order').rglob('*') if v.is_file() and '__pycache__' not in v.parts})
Path('/content/order-prepared.json').write_text(json.dumps(_identity,indent=2))
print('ORDER_PREPARATION_COMMITTED',flush=True)
""".replace('SESSION',repr(session))
            script.write_text(script.read_text()+marker)
            (self.output/'bootstrap-source.py').write_bytes(script.read_bytes())
        return super().command(args,phase,timeout)
try:
    receipt=MarkedController(root.parents[1],folder,session).prepare()
    print(json.dumps(dict(status=receipt['status'],session=session)),flush=True)
except Exception as error:
    print(json.dumps(dict(status='FAIL',phase='prepare',error_type=type(error).__name__,session=session)),flush=True)
    raise SystemExit(1)
