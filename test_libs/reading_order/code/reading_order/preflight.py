import hashlib
import json
from pathlib import Path


def code_fingerprint(root):
    root = Path(root)
    files = {}
    for name in ('code','analytics','test'):
        for path in (root/name).rglob('*'):
            if (path.is_file() and not {'__pycache__','node_modules','test-results','playwright-report'}.intersection(path.parts)
                    and path.suffix in ('.py','.js','.css','.html','.rs','.in','.json')):
                files[str(path.relative_to(root)).replace('\\','/')] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def require_test_receipt(root,path):
    receipt = json.loads(Path(path).read_text())
    if receipt.get('status')!='PASS' or receipt.get('code_files')!=code_fingerprint(root):
        raise ValueError('Current code/analytics/tests do not match a passing offline test receipt')
    return receipt


def production_fingerprint(root):
    return {name:sha for name,sha in code_fingerprint(root).items() if name.startswith('code/reading_order/')}


def require_deployment_code(root,receipt):
    if receipt.get('code_files')!=production_fingerprint(root):
        raise ValueError('Uploaded production code differs from the current tested source')
    return True
