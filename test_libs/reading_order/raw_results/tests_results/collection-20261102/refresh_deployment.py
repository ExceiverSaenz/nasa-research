"""Apply the reviewed controller-only update; verify all uploaded code hashes."""
import hashlib,json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'code'))
from reading_order.preflight import production_fingerprint,require_test_receipt
output=Path(__file__).parent
require_test_receipt(root,output/'offline-final/test-receipt.json')
session='order-collection-20261102'
cli=str(Path.home()/'.local/bin/colab')
with (output/'code-update.log').open('w') as log:
    subprocess.run([cli,'upload','-s',session,str(root/'code/reading_order/collection.py'),
        '/content/order-code/reading_order/collection.py'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=45)
script=output/'verify_remote_code.py'
script.write_text("import hashlib,json\nfrom pathlib import Path\nr=Path('/content/order-code')\nf={'code/'+str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (r/'reading_order').rglob('*') if p.is_file() and '__pycache__' not in p.parts}\nprint('ORDER_CODE_HASHES:'+json.dumps(f))\n")
result=subprocess.run([cli,'exec','-s',session,'-f',str(script),'--timeout','45'],capture_output=True,text=True,timeout=60)
(output/'code-verification.log').write_text(result.stdout+result.stderr)
result.check_returncode()
remote=json.loads(next(line.split('ORDER_CODE_HASHES:',1)[1] for line in result.stdout.splitlines() if 'ORDER_CODE_HASHES:' in line))
assert remote==production_fingerprint(root),'Remote code differs from tested source'
path=output/'environment/environment.json';receipt=json.loads(path.read_text())
receipt.update(code_files=remote,code_update=dict(path=str(root/'code/reading_order/collection.py'),
    sha256=remote['code/reading_order/collection.py'],remote_all_files_verified=True,
    original_receipt_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),original_receipt=str(path)))
(output/'environment-current.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(dict(status='PASS',remote_files=len(remote),environment_changed=False)))
