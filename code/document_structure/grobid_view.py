"""B/C inspection of saved outputs only, with byte-identical source renders."""
import argparse
import json
import shutil
from pathlib import Path
from reading_order.export import digest,write
from .grobid_evaluation import validate_C


def build_model(B,C,pages):
    validate_C(B,C);pmap={p['unit_ref']:p for p in C['grobid_proposals']};units=[]
    for i in B['inventory']:
        u=i['original_unit'];id=i['unit_ref'];units.append(dict(id=id,page=i['page'],route=i.get('route'),bbox=u.get('bbox_xyxy'),kind=u['structural_kind'],text=u.get('original_record',{}).get('text',''),comparison=pmap[id],links=[l for l in C['grobid_alignment'] if any(m['unit_ref']==id for m in l['matches']+l['candidates'])]))
    return dict(paper=B['document'],pages=pages,units=units,evidence={n['id']:n for n in C['grobid_evidence']['nodes']},unlocated=[l for l in C['grobid_alignment'] if l['status'] not in ('aligned_unique','aligned_fragment_set')],structure=C['grobid_structure'],B_structure=B['document_structure'],routes=list(B['approved_routes']))


def build_view(B_path,C_path,catalog_path,destination):
    bp=Path(B_path).resolve();cp=Path(C_path).resolve();cat=Path(catalog_path).resolve();dest=Path(destination).resolve()
    if dest.exists():raise FileExistsError(dest)
    B=json.loads(bp.read_text(encoding='utf-8'));C=json.loads(cp.read_text(encoding='utf-8'));bm=json.loads((bp.parent/'manifest.json').read_text(encoding='utf-8'));cm=json.loads((cp.parent/'manifest.json').read_text(encoding='utf-8'))
    if bm['outputs'].get(bp.name)!=digest(bp) or cm['outputs'].get(cp.name)!=digest(cp) or cm['sources'].get(str(bp))!=digest(bp) or bm['sources'].get(str(cat))!=digest(cat):raise ValueError('view source provenance mismatch')
    catalog=json.loads(cat.read_text(encoding='utf-8'));pages=[];images=[]
    for p in catalog['pages']:
        i=p['identity'];img=Path(p['render_path']);sha=digest(img)
        if sha!=i['render_sha256']:raise ValueError('render mismatch')
        rel=f"images/{i['physical_page']:04d}.png";pages.append(dict(n=i['physical_page'],w=i['width_px'],h=i['height_px'],image=rel));images.append((img,rel,sha))
    model=build_model(B,C,pages);here=Path(__file__).parent
    html=(here/'grobid_view.html').read_text(encoding='utf-8').replace('__DATA__',json.dumps(model,ensure_ascii=False).replace('<','\\u003c')).replace('__CSS__',(here/'native_view.css').read_text(encoding='utf-8')).replace('__JS__',(here/'grobid_view.js').read_text(encoding='utf-8'))
    dest.mkdir(parents=True,exist_ok=False)
    for img,rel,sha in images:
        target=dest/rel;target.parent.mkdir(exist_ok=True);shutil.copyfile(img,target)
        if digest(target)!=sha:raise ValueError('image bytes changed')
    (dest/'index.html').write_text(html,encoding='utf-8')
    verification=dict(images_copied=len(images),image_recompression=False,images={rel:sha for _,rel,sha in images},B_sha256=digest(bp),C_sha256=digest(cp),html_sha256=digest(dest/'index.html'),code={p.name:digest(p) for p in [here/'grobid_view.py',here/'grobid_view.html',here/'grobid_view.js',here/'native_view.css']},visual_QA=False)
    write(dest/'verification.json',verification);return verification


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('B');p.add_argument('C');p.add_argument('render_catalog');p.add_argument('destination');a=p.parse_args();print(json.dumps(build_view(a.B,a.C,a.render_catalog,a.destination),indent=2))
