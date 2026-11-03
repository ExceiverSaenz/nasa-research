"""Explicit continuation of interrupted stability conditions, never a pilot."""
import hashlib
import json
from pathlib import Path
from .contracts import identity
from .ingest import portable_reference,resolve_reference


def read_reference(path):
    path=Path(path).resolve()  # Explicit user argument, relative to the caller's cwd.
    raw=path.read_bytes()
    return json.loads(raw),dict(path=portable_reference(path),sha256=hashlib.sha256(raw).hexdigest())


def stability_inputs(primary_path,continuation=None):
    primary,reference=read_reference(primary_path)
    if primary.get('condition')!='canonical_sha256_id_order' or not primary.get('predictions'):
        raise ValueError('Expected the completed canonical pilot')
    if {p['scope']['paper_id'] for p in primary['predictions']}!={'12'} or len(primary['predictions'])!=78:
        raise ValueError('Continuation is restricted to the 12.pdf pilot')
    if any(p['status']!='PASS' for p in primary['predictions']):raise ValueError('Primary pilot is incomplete')
    selected=primary['stability_runs']
    if {v['seed'] for v in selected}!={1729,1730}:raise ValueError('Unexpected stability selection')
    conditions=[]
    for spec in selected:
        name=spec['run_id']
        if Path(name).name!=name:raise ValueError('Unregistered attempt path')
        old,old_reference=read_reference(Path(primary_path).parent.parent/name/'manifest.json')
        if old['input_reference']!=primary['input_reference'] or old['input_profile_id']!=primary['input_profile_id']:
            raise ValueError('Frozen inputs differ')
        reused={}
        keys=set()
        for index,prediction in enumerate(old['predictions']):
            key=(prediction['candidate_id'],prediction['scope']['paper_id'],prediction['scope']['page_idx'])
            if key in keys or prediction['scope']['permutation_seed']!=spec['seed']:
                raise ValueError('Duplicate or mismatched stability case')
            keys.add(key)
            if prediction['status']=='PASS':
                reused[key]=dict(prediction,reused_from=dict(old_reference,json_pointer='/predictions/'+str(index)))
        expected={(p['candidate_id'],p['scope']['paper_id'],p['scope']['page_idx']) for p in primary['predictions']}
        if keys!=expected:raise ValueError('Prior inventory differs')
        extra=[]
        if continuation is not None:
            path=Path(continuation)/('permutation-'+str(spec['seed']))/'manifest.json'
            if path.exists():
                partial,partial_ref=read_reference(path)
                if partial['input_reference']!=primary['input_reference']:raise ValueError('Continuation input differs')
                extra.append(partial_ref)
                for index,p in enumerate(partial['predictions']):
                    key=(p['candidate_id'],p['scope']['paper_id'],p['scope']['page_idx'])
                    if key not in expected or p['scope']['permutation_seed']!=spec['seed']:
                        raise ValueError('Unexpected continuation case')
                    if p['status']=='PASS' and key not in reused:
                        reused[key]=dict(p,reused_from=dict(partial_ref,json_pointer='/predictions/'+str(index)))
        conditions.append(dict(seed=spec['seed'],reuse=reused,reference=old_reference,additional_references=extra))
    return primary,reference,conditions


def verify_unchanged(references):
    for reference in references:
        if hashlib.sha256(resolve_reference(reference['path']).read_bytes()).hexdigest()!=reference['sha256']:
            raise ValueError('Preserved result changed')
