"""Version-pinned bridge to MinerU's official snapshot completion validator.

All payload bytes come from the pinned manifests. Only the snapshot transport
callback is replaced; the official required-path and completion flow still runs.
No model inference, manual marker creation, or mutation of installed code.
"""
import argparse
import os
import shutil
from pathlib import Path
from .contracts import load_experiment,exit_code
from .models import verify_models
from .remote import manifest_data


def prepare_snapshots(root):
    root=Path(root).resolve();os.environ['MINERU_MODEL_BASE_DIR']=str(root/'runtime/mineru-models')
    os.environ['MINERU_HOME']=str(root/'runtime/mineru-home')
    import importlib.metadata
    if importlib.metadata.version('mineru')!='4.0.12':raise ValueError('Snapshot bridge is pinned to MinerU 4.0.12')
    import mineru.model.download as download
    from mineru.model.registry import MINERU_4_MODELS_TORCH,MINERU_2_5_PRO_2605_1_2B
    pairs=[(MINERU_4_MODELS_TORCH,'mineru-small-preserved'),(MINERU_2_5_PRO_2605_1_2B,'standard-vlm')]
    sources={}
    for repo,name in pairs:
        manifest=manifest_data(root/'model_manifests'/(name+'.json'));source=root/'runtime/model-cache'/name
        if exit_code(verify_models(source,manifest)):raise ValueError('Model snapshot identity failed')
        dest=repo.local_dir();dest.mkdir(parents=True,exist_ok=True)
        from .environment import classify_artifact
        for relative,identity in manifest['files'].items():
            target=dest/relative;state=classify_artifact(target,identity)
            if state=='corrupt':raise ValueError('Existing MinerU snapshot differs')
            if state=='missing':
                target.parent.mkdir(parents=True,exist_ok=True)
                try:os.link(source/relative,target)
                except OSError:shutil.copyfile(source/relative,target)
        sources[repo.name]=(manifest,dest)
    original=download._snapshot_download
    def pinned_transport(model_source,repo,patterns):
        manifest,dest=sources[repo.name]
        if exit_code(verify_models(dest,manifest)):raise ValueError('Pinned snapshot incomplete')
        return str(dest)
    try:
        download._snapshot_download=pinned_transport
        for repo,_ in pairs:
            download.download_model_repo(repo,source='huggingface',reuse_ready=True)
            if not download.verify_model_repo(repo).ready:raise ValueError('Official model readiness failed')
    finally:download._snapshot_download=original


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);args=p.parse_args();prepare_snapshots(args.root)
