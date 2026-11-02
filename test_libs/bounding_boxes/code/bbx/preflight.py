import importlib.util
import sys
from pathlib import Path
from .contracts import check, sha256, validate_experiment, load_experiment
from .layout import resolve_path


def inventory(directory):
    papers=[]
    for p in sorted(Path(directory).glob('*.pdf')):
        pages=None
        try:
            import pypdfium2
            with pypdfium2.PdfDocument(str(p)) as doc:pages=len(doc)
        except ImportError:pass
        papers.append(dict(name=p.name,bytes=p.stat().st_size,sha256=sha256(p),pages=pages))
    return papers


def inspect_local(root,papers_dir):
    root=Path(root)
    result=validate_experiment(load_experiment(root/'experiment.json'))
    papers=inventory(papers_dir)
    result.append(check('pdf_inventory','PASS' if papers else 'FAIL',scope='local',papers=papers))
    result.append(check('page_counts','PASS' if papers and all(p['pages'] is not None for p in papers) else 'NOT_RUN',scope='local'))
    for name in ('pytest',):
        result.append(check('dev:'+name,'PASS' if importlib.util.find_spec(name) else 'NOT_RUN',scope='local'))
    for env in ('a','b'):
        lock=resolve_path(root/'requirements'/f'{env}.lock',root=root)
        result.append(check('lock:'+env,'PASS' if lock.is_file() else 'NOT_RUN','Requires resolved Linux CPython 3.11 lock',scope='local'))
    for name in ('remote_gpu','remote_r2','cuda_operation','model_loads','smoke_four_tools'):
        result.append(check(name,'NOT_RUN','No remote session started',scope='remote'))
    return result


def remote_probe():
    from .resources import gpu_snapshot
    import platform
    import shutil
    result=[]
    try:
        gpus=gpu_snapshot()
        result.append(check('a100','PASS' if len(gpus)==1 and gpus[0]['a100'] else 'FAIL',scope='remote',gpus=gpus))
    except Exception as e:result.append(check('a100','FAIL',type(e).__name__,scope='remote'))
    result.append(check('host','PASS' if platform.system()=='Linux' and platform.machine()=='x86_64' else 'FAIL',scope='remote',python=sys.version))
    result.append(check('disk','PASS',scope='remote',free_bytes=shutil.disk_usage('.').free))
    return result
