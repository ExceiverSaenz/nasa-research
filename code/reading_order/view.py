"""Responsive read-only reading-order site with original PNG bytes."""
import argparse
import json
from pathlib import Path
import shutil
from .export import digest,write


def build_view(path,destination):
    path=Path(path).resolve();destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError(destination)
    reading=json.loads(path.read_text(encoding='utf-8'))
    manifest=path.parents[2]/'manifest.json'
    if manifest.is_file():
        m=json.loads(manifest.read_text(encoding='utf-8'))
        if m['outputs'].get(path.relative_to(manifest.parent).as_posix())!=digest(path):raise ValueError('reading order hash mismatch')
    source=Path(reading['reconciliation_source']['path'])
    if digest(source)!=reading['reconciliation_source']['sha256']:raise ValueError('reconciliation hash mismatch')
    baseline=json.loads(source.read_text(encoding='utf-8'));pages=[];images=[]
    for page in baseline['pages']:
        ident=page['identity'];image=Path(page['render_path']);sha=digest(image)
        if sha!=ident['render_sha256']:raise ValueError('render hash mismatch')
        rel=f"images/{ident['physical_page']:04d}.png";images.append((image,rel,sha));pages.append(dict(n=ident['physical_page'],w=ident['width_px'],h=ident['height_px'],image=rel))
    units=[]
    for u in reading['inventory']:
        original=u['original_unit'];r=original.get('original_record',{})
        units.append(dict(id=u['unit_ref'],page=u['page'],kind=u['kind'],bbox=original.get('bbox_xyxy'),text=r.get('text',''),classification=original['classification'],disposition=u['disposition'],appearance_ref=u['appearance_ref'],parent_step_ref=u.get('parent_step_ref')))
    model=dict(pages=pages,units=units,steps=reading['steps'],routes=reading['routes'],relations=reading['relations'],metrics=reading['metrics'])
    here=Path(__file__).resolve().parent;html=(here/'viewer.html').read_text(encoding='utf-8')
    for key,name in [('__CSS__','viewer.css'),('__JS__','viewer.js')]:html=html.replace(key,(here/name).read_text(encoding='utf-8'))
    html=html.replace('__DATA__',json.dumps(model,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
    destination.mkdir(parents=True)
    for image,relative,sha in images:
        target=destination/relative;target.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(image,target)
        if digest(target)!=sha:raise ValueError('render copy changed')
    with (destination/'index.html').open('x',encoding='utf-8') as stream:stream.write(html)
    v=dict(pages=len(pages),inventory_units=len(units),steps=len(reading['steps']),original_images={rel:sha for _,rel,sha in images},source_sha256=digest(path),html_sha256=digest(destination/'index.html'),image_recompression=False,new_analysis=False)
    write(destination/'verification.json',v);return v


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('destination');a=p.parse_args();print(json.dumps(build_view(a.source,a.destination),indent=2))
