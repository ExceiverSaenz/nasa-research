"""Update code only in the prepared environment, without dependency changes."""
import hashlib,json,sys,tarfile
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'code'))
from reading_order.preflight import production_fingerprint,require_test_receipt
from reading_order.deployment import ColabController
base=Path(__file__).parent
require_test_receipt(root,base/'offline-comm/test-receipt.json')
controller=ColabController(root.parents[1],base/'code-comm','order-stability-20261102')
files=production_fingerprint(root)
archive=controller.output/'code-only.tar.gz'
with tarfile.open(archive,'w:gz') as bundle:
    for name in files:bundle.add(root/name,arcname=str(Path(name).relative_to('code')))
controller.command(['upload','-s',controller.session,archive,'/content/order-lifecycle.tar.gz'],'upload')
script=controller.output/'verify.py'
script.write_text("import tarfile,hashlib\nfrom pathlib import Path\nwith tarfile.open('/content/order-lifecycle.tar.gz') as a:a.extractall('/content/order-code',filter='data')\nexpected="+repr(files)+"\nassert all(hashlib.sha256((Path('/content/order-code')/Path(k).relative_to('code')).read_bytes()).hexdigest()==v for k,v in expected.items())\nprint('ORDER_CODE_VERIFIED')\n")
text=controller.command(['exec','-s',controller.session,'-f',script,'--timeout','60'],'verify')
assert 'ORDER_CODE_VERIFIED' in text and production_fingerprint(root)==files
receipt=json.loads((base/'environment/environment.json').read_text())
receipt.update(code_files=files,code_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
               previous_environment_receipt='../environment/environment.json',environment_modified=False)
(controller.output/'environment.json').write_text(json.dumps(receipt,indent=2))
print('ORDER_CODE_VERIFIED',flush=True)
