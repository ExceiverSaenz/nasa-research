import hashlib,json
from pathlib import Path
r=Path('/content/order-code')
f={'code/'+str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (r/'reading_order').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
print('ORDER_CODE_HASHES:'+json.dumps(f))
