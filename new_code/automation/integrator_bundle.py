"""Validate integrator bundle metadata before allocating a Colab session."""
import hashlib
from pathlib import PurePosixPath


def validate_source(data, source, raw):
    if source.get('schema')!='integration-environment/1' or source.get('status')!='imports-validated' or source.get('python')!='3.11.16':raise ValueError('Invalid integrator source environment')
    # Kept in the scientific package as the authoritative pin declaration.
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reconciliation_system'))
    from integration.dependencies import PINS
    for name,pin in PINS.items():
        if source.get('versions',{}).get(name.lower().replace('_','-'))!=pin:raise ValueError('Integrator source pin differs: '+name)
    for name,record in source.get('artifacts',{}).items():
        if name not in data['files']:raise ValueError('Unverified integrator source artifact')
        content=raw(name)
        if len(content)!=record['bytes'] or hashlib.sha256(content).hexdigest()!=record['sha256']:raise ValueError('Integrator source artifact differs')
    if not source.get('artifacts'):raise ValueError('Missing integrator source artifacts')
