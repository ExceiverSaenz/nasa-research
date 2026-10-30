"""Adapt an already saved real response offline. Never invokes the GROBID client."""
import argparse
import json
import shutil
from pathlib import Path
from integration.reading_order.export import digest,write
from .grobid_adapter import parse_tei
from .grobid_align import align_tei
from .grobid_reconcile import integrate_grobid,load_mapping
from .grobid_evaluation import compare_B_C
from .runners.grobid_trial import verify_lock


def export_saved_tei(B_path,raw_path,lock_path,destination):
    bp=Path(B_path).resolve();rp=Path(raw_path).resolve();lp=Path(lock_path).resolve();dest=Path(destination).resolve()
    if dest.exists():raise FileExistsError(dest)
    B=json.loads(bp.read_text(encoding='utf-8'));runpath=rp.parent.parent/'run.json';run=json.loads(runpath.read_text(encoding='utf-8'));lock=json.loads(lp.read_text(encoding='utf-8'))
    verify_lock(lock,run['pdf_path'],bp)
    if run.get('status')!='response_received' or run.get('http_status')!=200 or run.get('attempts')!=1 or run.get('response_sha256')!=digest(rp) or run.get('lock_sha256')!=digest(lp) or run.get('baseline_sha256')!=digest(bp):raise ValueError('response/run provenance mismatch')
    bm=json.loads((bp.parent/'manifest.json').read_text(encoding='utf-8'))
    if bm['outputs'].get(bp.name)!=digest(bp):raise ValueError('B manifest mismatch')
    protected={str(p):digest(p) for p in (bp,rp,lp,runpath,Path(run['pdf_path']))}
    for p,h in bm.get('sources',{}).items():
        if digest(p)!=h:raise ValueError('B source changed')
        protected[p]=h
    ev=parse_tei(rp.read_bytes(),run);links=align_tei(ev,B);mapping=load_mapping();C=integrate_grobid(B,ev,links,mapping);comparison=compare_B_C(B,C)
    dest.mkdir(parents=True,exist_ok=False);(dest/'raw').mkdir();shutil.copyfile(rp,dest/'raw/response.tei.xml')
    review=dict(stage='after_full_mvp',blocking=False,warning='Requiere validación humana',units=C['grobid_proposals'],unaligned_evidence=[l for l in links if l['status'] not in ('aligned_unique','aligned_fragment_set')],structure_candidates=C['grobid_structure'],unmapped_labels=C['grobid_unmapped_labels'])
    for name,data in [('run.json',run),('runtime-lock.json',lock),('grobid-evidence.json',ev),('alignment.json',links),('mapping.json',mapping),('document.json',C),('comparison.json',comparison),('review-queue.json',review)]:write(dest/name,data)
    if any(digest(p)!=h for p,h in protected.items()):raise ValueError('source mutation')
    write(dest/'manifest.json',dict(sources=protected,outputs={p.relative_to(dest).as_posix():digest(p) for p in dest.rglob('*') if p.is_file()},code={p.name:digest(p) for p in Path(__file__).parent.glob('grobid_*.py')},mapping_sha256=digest(Path(__file__).parent/'grobid_mapping.json'),models_executed_by_export=False,quality_validated=False))
    return comparison


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('B');p.add_argument('raw');p.add_argument('lock');p.add_argument('destination');a=p.parse_args();print(json.dumps(export_saved_tei(a.B,a.raw,a.lock,a.destination)['global_counts'],indent=2))
