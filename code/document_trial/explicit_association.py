"""Explicit additive association only. No models, inference or discovery."""
import copy
import hashlib
import json
from pathlib import Path


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False)+'\n').encode('utf-8')


def build(result, declaration):
    if declaration.get('identity') != result['identity']:
        raise ValueError('Identity mismatch')
    if declaration.get('conflicts'):
        raise ValueError('Conflicting explicit declarations')
    panels=declaration.get('panels',[])
    caption=declaration.get('caption')
    if len(panels)!=2 or len(set(panels))!=2 or caption in panels:
        raise ValueError('Expected two distinct Fig6 panels and separate caption')
    if not declaration.get('group_id'):
        raise ValueError('Missing group ID')
    items={x['local_id']:x for x in result['segments']}
    if len(items)!=len(result['segments']):
        raise ValueError('Duplicate local IDs')
    def reference(local, role):
        item=items.get(local)
        if item is None or item['type']!=role:
            raise ValueError('Missing reference or incorrect role: '+str(local))
        identity=result['identity']
        prefix=identity['document_sha256']+':'+identity['execution_id']+':p'+str(identity['physical_page'])+':'
        if item['id']!=prefix+local or not item.get('source_pointer'):
            raise ValueError('Invalid full identity or source pointer')
        return {k:copy.deepcopy(item[k]) for k in ('id','local_id','source_pointer')}
    return dict(schema_version='explicit-figure-group/1',group_id=declaration['group_id'],
                identity=copy.deepcopy(result['identity']),method='explicit_declaration',
                panels=[reference(x,'figure') for x in panels],caption=reference(caption,'caption'),
                review_status='agent_reviewed_pending_human_validation',
                evidence=copy.deepcopy(declaration.get('evidence',[])))


def export(source, declaration, destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if source==destination or source in destination.parents:
        raise ValueError('Invalid output destination')
    raw=source.read_bytes()
    try:
        if declaration.get('baseline_sha256')!=digest(raw):
            raise ValueError('Baseline SHA256 mismatch')
        group=build(json.loads(raw),declaration)
        native_path=source.parent/'M0-native.json'
        native_raw=native_path.read_bytes()
        native=json.loads(native_raw)
        for ref in group['panels']+[group['caption']]:
            value=native
            for token in ref['source_pointer'].strip('/').split('/'):
                value=value[int(token)] if isinstance(value,list) else value[token]
            original=next(x for x in json.loads(raw)['segments'] if x['id']==ref['id'])
            if value!=original['native_content']:
                raise ValueError('Native source mismatch')
        group['provenance']=dict(native_path=str(native_path),native_sha256=digest(native_raw),
                                 baseline_sha256=digest(raw))
    except ValueError as exc:
        if not destination.exists():
            destination.mkdir(parents=True)
            (destination/'diagnostic.json').write_bytes(encoded(dict(status='rejected',reason=str(exc))))
        raise
    payload=encoded(group)
    files={'group.json':payload,'declaration.json':encoded(declaration)}
    files['manifest.json']=encoded(dict(schema_version='explicit-group-manifest/1',
        baseline=dict(path=str(source),sha256=digest(raw)),
        outputs={name:digest(data) for name,data in files.items()}))
    if destination.exists():
        if set(x.name for x in destination.iterdir())!=set(files) or any(
                (destination/name).read_bytes()!=data for name,data in files.items()):
            raise ValueError('Existing destination incompatible; not overwritten')
        return group
    destination.mkdir(parents=True)
    for name,data in files.items():
        with (destination/name).open('xb') as stream:
            stream.write(data)
    return group
