"""Explicit code-only repair of the existing prepared session; no installs."""
import hashlib,json,sys,tarfile
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'code'))
from reading_order.deployment import ColabController
from reading_order.preflight import require_test_receipt,production_fingerprint
base=Path(__file__).resolve().parent
require_test_receipt(root,base/sys.argv[1]/'test-receipt.json')
controller=ColabController(root.parents[1],base/sys.argv[2],'order-pilot-20261102')
fingerprint=production_fingerprint(root)
archive=controller.output/'code-only.tar.gz'
with tarfile.open(archive,'w:gz') as bundle:
    for name in fingerprint:
        bundle.add(root/name,arcname=str(Path(name).relative_to('code')))
controller.command(['upload','-s',controller.session,archive,'/content/order-repair.tar.gz'],'upload')
script=controller.output/'verify-code.py'
script.write_text("import tarfile,hashlib\nfrom pathlib import Path\nwith tarfile.open('/content/order-repair.tar.gz') as t:t.extractall('/content/order-code')\nexpected="+repr(fingerprint)+"\nassert all(hashlib.sha256((Path('/content/order-code')/Path(k).relative_to('code')).read_bytes()).hexdigest()==v for k,v in expected.items())\nprint('ORDER_CODE_REPAIR_VERIFIED')\n")
output=controller.command(['exec','-s',controller.session,'-f',script,'--timeout','60'],'verify')
assert 'ORDER_CODE_REPAIR_VERIFIED' in output
assert production_fingerprint(root)==fingerprint
receipt=json.loads((base/'environment/environment.json').read_text())
receipt.update(code_files=fingerprint,code_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
               previous_environment_receipt='../environment/environment.json',repair='stdin callback; code only; no environment changes')
(controller.output/'environment.json').write_text(json.dumps(receipt,indent=2))
print('ORDER_CODE_REPAIR_VERIFIED')
