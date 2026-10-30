"""Offline inspection site from the exported sidecar; copies original PNG bytes."""
import argparse
import json
import shutil
from pathlib import Path
from integration.reading_order.export import digest,write


def build_view(result_path,baseline_path,destination):
    rp=Path(result_path).resolve();bp=Path(baseline_path).resolve();dest=Path(destination).resolve()
    if dest.exists():raise FileExistsError(dest)
    result=json.loads(rp.read_text(encoding='utf-8'));base=json.loads(bp.read_text(encoding='utf-8'))
    if result['inventory']!=base['inventory'] or result['approved_routes']!=base['routes']:raise ValueError('baseline mismatch')
    m=json.loads((rp.parent/'manifest.json').read_text(encoding='utf-8'))
    if m['outputs'].get(rp.name)!=digest(rp) or m['sources'].get(str(bp))!=digest(bp):raise ValueError('result manifest mismatch')
    source=json.loads(Path(base['reconciliation_source']['path']).read_text(encoding='utf-8'));pages=[];images=[]
    for p in source['pages']:
        i=p['identity'];img=Path(p['render_path']);sha=digest(img)
        if sha!=i['render_sha256']:raise ValueError('render hash mismatch')
        rel=f"images/{i['physical_page']:04d}.png";images.append((img,rel,sha));pages.append(dict(n=i['physical_page'],w=i['width_px'],h=i['height_px'],image=rel))
    links={x['unit_ref']:x for x in result['evidence_links']};proposals={x['unit_ref']:x for x in result['classification_proposals']}
    units=[]
    for i in result['inventory']:
        id=i['unit_ref'];u=i['original_unit'];units.append(dict(id=id,page=u['page'],bbox=u.get('bbox_xyxy'),kind=u['structural_kind'],original=u['classification'],original_text=u.get('original_record',{}).get('text',''),link=links[id],proposal=proposals[id]))
    # Native spans remain in the downloadable JSON; the inspector embeds referenced evidence only once.
    model=dict(pages=pages,units=units,sections=result['document_structure']['sections'],memberships=result['document_structure']['memberships'],continuities=result['document_structure']['continuity_candidates'],evidence={e['id']:e for e in result['native_evidence'] if e['kind']!='text_block'})
    here=Path(__file__).parent;html=(here/'native_view.html').read_text(encoding='utf-8').replace('__DATA__',json.dumps(model,ensure_ascii=False).replace('<','\\u003c')).replace('__CSS__',(here/'native_view.css').read_text(encoding='utf-8')).replace('__JS__',(here/'native_view.js').read_text(encoding='utf-8'))
    dest.mkdir(parents=True)
    for img,rel,sha in images:
        target=dest/rel;target.parent.mkdir(exist_ok=True);shutil.copyfile(img,target)
        if digest(target)!=sha:raise ValueError('image modified')
    (dest/'index.html').write_text(html,encoding='utf-8')
    report=dict(pages=len(pages),images={rel:sha for _,rel,sha in images},image_recompression=False,source_sha256=digest(rp),html_sha256=digest(dest/'index.html'),code={p.name:digest(p) for p in here.glob('native_view.*')},visual_browser_QA='blocked_by_file_URL_security_policy; DOM tests are not visual QA')
    write(dest/'verification.json',report);return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('result');p.add_argument('baseline');p.add_argument('destination');a=p.parse_args();print(json.dumps(build_view(a.result,a.baseline,a.destination),indent=2))
