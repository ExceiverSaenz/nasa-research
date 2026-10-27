"""Installed distribution inventory in a fresh interpreter; never imports models."""
import argparse
from importlib import metadata
import os
from pathlib import Path
import platform
import sys
from .common import canonical, read, save
from .command_log import run_logged


def collect():
    entries=[]
    for d in metadata.distributions():
        name=d.metadata['Name']
        # Preserve every occurrence, including repeated paths and conflicting versions.
        location=getattr(d,'_path',None)
        entries.append(dict(name=name,canonical_name=canonical(name) if name else None,
            version=d.version,metadata_path=str(Path(location).resolve()) if location is not None else None,
            root_path=str(Path(d.locate_file('')).resolve())))
    return dict(schema='distribution-inventory/1',pid=os.getpid(),python=platform.python_version(),
        executable=sys.executable,prefix=sys.prefix,sys_path=list(sys.path),
        torch_imported='torch' in sys.modules,distributions=entries)


def package_map(snapshot):
    groups={}
    for entry in snapshot['distributions']:
        if not all(isinstance(entry.get(k),str) and entry[k] for k in ('name','version','metadata_path','root_path')):
            raise ValueError('Inventory entry missing name/version/provenance')
        name=canonical(entry['name'])
        groups.setdefault(name,set()).add((entry['version'],entry['metadata_path']))
    ambiguous={name:sorted(values) for name,values in groups.items() if len({v for v,p in values})!=1}
    if ambiguous:raise ValueError('Ambiguous installed distributions: '+repr(ambiguous))
    return {name:next(iter(values))[0] for name,values in groups.items()}


def clean_inventory(state,model,stage="preflight"):
    if stage not in ("preflight","before-infer"):raise ValueError("Unknown inventory stage")
    output=Path(state)/('inventory-'+model+'-'+stage+'-clean.json')
    if output.exists():raise FileExistsError('Existing inventory; no overwrite: '+str(output))
    run_logged([sys.executable,'-B','-m','document_trial.inventory','--output',str(output)],
        state,env=os.environ.copy(),stage=model+':'+stage+':clean-inventory')
    snapshot=read(output)
    if snapshot['pid']==os.getpid() or snapshot['torch_imported']:
        raise ValueError('Inventory was not collected in a clean child interpreter')
    if snapshot['executable']!=sys.executable or snapshot['prefix']!=sys.prefix:
        raise ValueError('Inventory interpreter differs from worker')
    return snapshot


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    if Path(args.output).exists():raise FileExistsError('Existing inventory output')
    snapshot=collect()
    save(args.output,snapshot)
    if snapshot['torch_imported']:raise ValueError('Torch imported during interpreter startup')


if __name__=='__main__':main()
