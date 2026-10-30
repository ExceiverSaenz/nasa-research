"""Build a local responsive website from classified reconciliation, no new analysis."""
import argparse
import json
from pathlib import Path
import shutil
from .export import digest, write


def build_view(classified_path,destination):
    classified_path=Path(classified_path).resolve();destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError(destination)
    d=json.loads(classified_path.read_text(encoding='utf-8'))
    if d.get('classification_scope')!='reconciled_units_only':raise ValueError('requires reconciled-only classification')
    manifest=classified_path.parents[2]/'manifest.json'
    if manifest.is_file():
        m=json.loads(manifest.read_text(encoding='utf-8'))
        rel=classified_path.relative_to(manifest.parent).as_posix()
        if m.get('outputs',{}).get(rel)!=digest(classified_path):raise ValueError('classification hash mismatch')
    source=Path(d['source']['path'])
    if digest(source)!=d['source']['sha256']:raise ValueError('reconciliation hash mismatch')
    baseline=json.loads(source.read_text(encoding='utf-8'))
    pages=[];originals=[]
    for p in baseline['pages']:
        ident=p['identity'];image=Path(p['render_path']);sha=digest(image)
        if sha!=ident['render_sha256']:raise ValueError('original image hash mismatch')
        n=ident['physical_page'];relative=f'images/{n:04d}.png'
        pages.append(dict(n=n,w=ident['width_px'],h=ident['height_px'],image=relative,status=p.get('status','preserved')))
        originals.append((image,relative,sha))
    rows=[]
    for r in d['regions']:
        original=r['original_record']
        rows.append(dict(id=r['id'],page=r['page'],kind=r['structural_kind'],bbox=r['bbox_xyxy'],
                         text=original.get('text',''),native_type=original['native_type'],
                         retained_category=original.get('category'),classification=r['classification'],member_of=r.get('member_of',[])))
    evidence=[dict(id=r['id'],parser=r['original_record']['parser'],native_type=r['original_record']['native_type'],category=r['original_record'].get('category')) for r in d['evidence_records']]
    data=dict(pages=pages,regions=rows,groups=d['logical_units'],evidence=evidence)
    here=Path(__file__).resolve().parent
    html=(here/'viewer.html').read_text(encoding='utf-8')
    html=html.replace('__CSS__',(here/'viewer.css').read_text(encoding='utf-8')).replace('__JS__',(here/'viewer.js').read_text(encoding='utf-8'))
    html=html.replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
    destination.mkdir(parents=True)
    for image,rel,sha in originals:
        target=destination/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(image,target)
        if digest(target)!=sha:raise ValueError('image copy mismatch')
    with (destination/'index.html').open('x',encoding='utf-8') as stream:stream.write(html)
    verification=dict(pages=len(pages),reconciled_regions=len(rows),logical_groups=len(d['logical_units']),
                      source_sha256=digest(classified_path),source=str(classified_path),
                      original_images={rel:sha for _,rel,sha in originals},
                      image_recompression=False,new_classification=False,default_zoom='fit_width',
                      external_requests=False,html_sha256=digest(destination/'index.html'))
    write(destination/'verification.json',verification)
    return verification


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('classified');parser.add_argument('destination')
    args=parser.parse_args();print(json.dumps(build_view(args.classified,args.destination),indent=2))
