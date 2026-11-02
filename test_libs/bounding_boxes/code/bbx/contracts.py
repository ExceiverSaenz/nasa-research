import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from .layout import resolve_path


def check(id, status, reason='', scope='offline', **evidence):
    return dict(id=id, status=status, reason=reason, scope=scope, evidence=evidence,
                timestamp_utc=datetime.now(timezone.utc).isoformat())


def sha256(path):
    h=hashlib.sha256()
    with resolve_path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def load_experiment(path):
    return json.loads(resolve_path(path).read_text(encoding='utf-8-sig'))


def validate_experiment(c):
    tools=c.get('tools',[])
    valid=(len(tools)==4 and [t.get('id') for t in tools]==['heron','heron101','basic','standard']
           and [t.get('environment') for t in tools]==['a','a','a','b']
           and c.get('device')=='cuda' and c.get('gpu')=='A100'
           and tools[-1].get('engine')=='vllm' and c.get('measured_passes')==1)
    result=[check('configuration','PASS' if valid else 'FAIL')]
    if c.get('ready'):
        pinned=all(t.get('revision') for t in tools[:2]) and bool(c.get('locks')) and bool(c.get('model_manifests'))
        result.append(check('pinned_inputs','PASS' if pinned else 'FAIL'))
    return result


def exit_code(checks):
    if any(c['status']=='FAIL' for c in checks): return 1
    return 2 if not checks or any(c['status']!='PASS' for c in checks) else 0


def write_json(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)


def contained(root,path):
    """Validate filesystem boundaries for model and return-archive data."""
    root=Path(root).resolve();p=(root/path).resolve()
    if not p.is_relative_to(root):raise ValueError('Path escapes root')
    return p
