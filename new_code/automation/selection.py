"""Read-only selection/transport of native parser evidence for Colab integration."""
import hashlib
import json
from pathlib import Path, PureWindowsPath, PurePosixPath
import tarfile


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def select_run(run, names, all_papers):
    run=Path(run).resolve(strict=True)
    manifest=json.loads((run/'manifest.json').read_text())
    if manifest.get('schema')!='parsing-hybrid-files/2':raise ValueError('Integration selection requires a current per-file parser manifest')
    inputs=json.loads((run/'inputs.json').read_text())
    ids=[p['id'] for p in inputs]
    if not ids or len(ids)!=len(set(ids)):raise ValueError('Invalid parser input identities')
    chosen=[]
    for token in names or []:
        matches=[p['id'] for p in inputs if token in (p['id'],PureWindowsPath(p['path']).name,PureWindowsPath(p['path']).stem)]
        if len(matches)!=1 or matches[0] in chosen:raise ValueError('Unknown, ambiguous or duplicate paper: '+token)
        chosen.append(matches[0])
    if all_papers:chosen=ids
    if not chosen:raise ValueError('Select papers from this parser run or --all')
    common={'inputs.json','status.json','configuration.json'}
    files={name:sha for name,sha in manifest['outputs'].items()
           if name in common or (len(PurePosixPath(name).parts)>1 and PurePosixPath(name).parts[0] in ('results','renders') and PurePosixPath(name).parts[1] in chosen)}
    if not common.issubset(files):raise ValueError('Missing parser run metadata')
    for name,sha in files.items():
        path=(run/name).resolve(strict=True)
        if not path.is_relative_to(run) or path.is_symlink() or digest(path)!=sha:raise ValueError('Parser source hash differs: '+name)
    status=json.loads((run/'status.json').read_text())
    if status.get('status')!='completed' or status.get('error'):raise ValueError('Only completed parser attempts can be selected')
    selected=[p for p in inputs if p['id'] in chosen]
    # All transferred evidence is covered by the unchanged original manifest.
    return dict(schema='parser-selection/1',source_run=run.name,manifest_sha256=digest(run/'manifest.json'),
                paper_ids=chosen,papers=[dict(id=p['id'],name=PureWindowsPath(p['path']).name,sha256=p['sha256']) for p in selected],files=files)


def package_selection(run, selection, destination):
    run=Path(run).resolve(strict=True)
    if digest(run/'manifest.json')!=selection['manifest_sha256']:raise ValueError('Parser manifest changed')
    with tarfile.open(destination,'x:gz') as archive:
        for name,expected in dict(selection['files'],**{'manifest.json':selection['manifest_sha256']}).items():
            path=(run/name).resolve(strict=True)
            if not path.is_relative_to(run) or path.is_symlink() or digest(path)!=expected:raise ValueError('Parser source changed before transfer')
            archive.add(path,arcname='parser-source/'+name,recursive=False)
