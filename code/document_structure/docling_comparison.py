"""Read exported trial only; synchronized standalone HTML with original renders."""
import argparse
import json
import shutil
from pathlib import Path
from reading_order.export import digest,write


HOOK=r'''
 let receiving=false;
 function notify(){if(!receiving&&window.parent!==window)window.parent.postMessage({kind:'trial-state',page,route,step:selected},'*');}
 window.addEventListener('message',e=>{const m=e.data;if(e.source!==window.parent||m?.kind!=='trial-control')return;
 receiving=true;if(data.pages.some(p=>p.n===m.page))page=m.page;if(data.routes[m.route]){route=m.route;$('route').value=route;}
 if(Object.hasOwn(m,'step')){if(steps.has(m.step))selected=m.step;else selected=null;}render();receiving=false;});
 const oldRender=render;render=function(){oldRender();notify();};
 function height(){window.parent.postMessage({kind:'trial-height',height:Math.ceil(document.body.getBoundingClientRect().height)+12},'*');}
 window.addEventListener('load',height);window.addEventListener('resize',height);
 if(typeof ResizeObserver!=='undefined')new ResizeObserver(height).observe(document.body);
'''


def build_comparison(baseline_path,candidate_path,destination):
    bp=Path(baseline_path).resolve();cp=Path(candidate_path).resolve();dest=Path(destination).resolve()
    if dest.exists():raise FileExistsError(dest)
    a=json.loads(bp.read_text(encoding='utf-8'));b=json.loads(cp.read_text(encoding='utf-8'))
    if a['inventory']!=b['inventory']:raise ValueError('comparison inventory mismatch')
    for d in (a,b):
        for key in ('classification_source','reconciliation_source'):
            if digest(d[key]['path'])!=d[key]['sha256']:raise ValueError('source hash mismatch')
    source=json.loads(Path(a['reconciliation_source']['path']).read_text(encoding='utf-8'));pages=[];images=[]
    for p in source['pages']:
        i=p['identity'];img=Path(p['render_path']);sha=digest(img)
        if sha!=i['render_sha256']:raise ValueError('render hash mismatch')
        rel=f"images/{i['physical_page']:04d}.png";images.append((img,rel,sha));pages.append(dict(n=i['physical_page'],w=i['width_px'],h=i['height_px'],image=rel))
    units=[]
    for u in a['inventory']:
        o=u['original_unit'];r=o.get('original_record',{})
        units.append(dict(id=u['unit_ref'],page=u['page'],kind=u['kind'],bbox=o.get('bbox_xyxy'),text=r.get('text',''),classification=o['classification'],disposition=u['disposition'],appearance_ref=u['appearance_ref']))
    here=Path(__file__).parent;old=here.parent/'reading_order'
    css=(old/'viewer.css').read_text(encoding='utf-8')+'\n.layout{display:flex;flex-direction:column}aside{position:static;order:initial}.heading{min-height:48px}body{overflow:hidden}#list-wrap{margin-bottom:8px}'
    js=(old/'viewer.js').read_text(encoding='utf-8');token=' render();\n})();'
    if token not in js:raise ValueError('viewer hook anchor changed')
    js=js.replace(token,HOOK+'\n render();\n})();')
    template=(old/'viewer.html').read_text(encoding='utf-8');dest.mkdir(parents=True)
    for img,rel,sha in images:
        target=dest/rel;target.parent.mkdir(exist_ok=True);shutil.copyfile(img,target)
        if digest(target)!=sha:raise ValueError('image bytes changed')
    for name,d in [('baseline',a),('docling',b)]:
        model=dict(pages=pages,units=units,steps=d['steps'],routes=d['routes'],relations=d['relations'],metrics=d['metrics'])
        title='Baseline v1' if name=='baseline' else 'Docling · reglas geométricas'
        html=template.replace('Orden de lectura · versión conciliada · propuesta sin validar',title+' · sin validación semántica')
        html=html.replace('__CSS__',css).replace('__JS__',js).replace('__DATA__',json.dumps(model,ensure_ascii=False).replace('</','<\\/'))
        (dest/(name+'.html')).write_text(html,encoding='utf-8')
    model=dict(pages=[p['n'] for p in pages],routes=list(a['routes']),comparison=b['trial']['comparison'],metrics=b['metrics'])
    html=(here/'comparison.html').read_text(encoding='utf-8').replace('__CSS__',(here/'comparison.css').read_text(encoding='utf-8')).replace('__JS__',(here/'comparison.js').read_text(encoding='utf-8')).replace('__DATA__',json.dumps(model,ensure_ascii=False).replace('</','<\\/'))
    (dest/'index.html').write_text(html,encoding='utf-8')
    v=dict(pages=len(pages),source_baseline_sha256=digest(bp),source_candidate_sha256=digest(cp),images={rel:sha for _,rel,sha in images},image_recompression=False,analysis_executed=False,html={p.name:digest(p) for p in dest.glob('*.html')})
    write(dest/'verification.json',v);return v


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('baseline');p.add_argument('candidate');p.add_argument('destination');a=p.parse_args();print(json.dumps(build_comparison(a.baseline,a.candidate,a.destination),indent=2))
