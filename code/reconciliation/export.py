"""Immutable offline export and minimal comparison; no inference or model imports."""
import argparse
import base64
import html
import json
import math
from pathlib import Path
from .engine import reconcile, VERSION, valid_box
from .inputs import load_evaluation, digest

COLORS={'Texto':'#4678b5','Títulos':'#8758ad','Figuras':'#178078','Tablas':'#b47819',
        'Captions':'#c35572','Ecuaciones':'#62782e','Márgenes':'#7c8590','Otros':'#a1744f'}


def serializable(value):
    if isinstance(value,float) and not math.isfinite(value):return {'$nonfinite':str(value)}
    if isinstance(value,dict):return {k:serializable(v) for k,v in value.items()}
    if isinstance(value,list):return [serializable(v) for v in value]
    return value


def encoded(value):return (json.dumps(serializable(value),ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf-8')


def render_html(document,images):
    esc=html.escape
    chunks=['''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conciliación automática · revisión</title><style>
*{box-sizing:border-box}body{margin:0;background:#f6f7f9;color:#20272d;font:14px system-ui}header{padding:20px 24px;background:white;border-bottom:1px solid #ddd;position:sticky;top:0;z-index:3}h1{font-size:20px;margin:0 0 8px}button,select{font:inherit;border:1px solid #d5d9dd;border-radius:6px;padding:6px;background:white}nav{display:flex;gap:12px;align-items:center;flex-wrap:wrap}small{color:#65717b}.filters{display:flex;gap:12px;flex-wrap:wrap;margin-top:12px}main{padding:18px}.grid{display:grid;grid-template-columns:repeat(4,minmax(240px,1fr));gap:12px;overflow:auto}.card{background:white;border:1px solid #e0e4e7;border-radius:8px;overflow:hidden}.card h2{font-size:14px;padding:12px;margin:0}.sheet{background-image:var(--paper);background-size:100% 100%;position:relative}.sheet svg{display:block;width:100%;height:auto}rect{fill-opacity:.04;stroke-width:2;cursor:pointer}rect:hover,rect:focus{fill-opacity:.2;stroke-width:4}.container{stroke-dasharray:8 6}.hidden{display:none!important}.page[hidden]{display:none}#inspector{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:16px;border-radius:8px;max-height:320px;overflow:auto}summary{cursor:pointer}a{color:#356a9b}p{line-height:1.5}.group{stroke:#128760;stroke-width:4;fill:none;pointer-events:none}details{margin-top:12px}footer{padding:20px;color:#65717b}
</style><header><h1>Conciliación automática</h1><small>Reglas v1 · fuentes intactas · abstención explícita · geometría y OCR sin reparación</small><nav><button id="prev" aria-label="Página anterior">←</button><select id="page" aria-label="Página">''']
    for i,p in enumerate(document['pages']):chunks.append(f'<option value="{i}">Página {p["identity"]["physical_page"]}</option>')
    chunks.append('</select><button id="next" aria-label="Página siguiente">→</button><label><input id="containers" type="checkbox"> Contenedores</label><label><input id="groups" type="checkbox" checked> Grupos automáticos</label></nav><div class="filters">')
    for cat,color in COLORS.items():chunks.append(f'<label style="color:{color}"><input type="checkbox" data-filter="{cat}" checked>{cat}</label>')
    chunks.append('</div></header><main>')
    for index,p in enumerate(document['pages']):
        ident=p['identity'];number=ident['physical_page'];w,h=ident['width_px'],ident['height_px']
        image=images.get(number,'')
        if not image.startswith('data:image/png;base64,'):raise ValueError('Only embedded PNG render permitted')
        chunks.append(f'<section class="page" {"hidden" if index else ""} style="--paper:url({esc(image,quote=True)})"><p>Página {number} · {esc(p["status"])} · {len(p["groups"])} grupos · {sum(d["status"]=="abstained" for d in p["decisions"])} decisiones con abstención</p><div class="grid">')
        for parser,label in [('automatic','Automática'),('mineru','MinerU'),('table_transformer','TATR'),('layoutlmv3','LayoutLMv3')]:
            chunks.append(f'<article class="card"><h2>{label}</h2><div class="sheet"><svg viewBox="0 0 {w} {h}" aria-label="{label}, página {number}">')
            for r in p['records']:
                if r['parser']!=('mineru' if parser=='automatic' else parser):continue
                if parser=='automatic' and r['id'] not in p['objects']+p['containers']:continue
                if not valid_box(r.get('bbox'),w,h):continue
                x,y,x2,y2=r['bbox'];cat=r['category'];container=r.get('role')=='container'
                detail=dict(id=r['id'],category=cat,subtype=r['native_type'],status=r['classification_status'],role=r.get('role'),
                            source=r['source'],text=r.get('text',''),bbox=r['bbox'],geometry=r['geometry_status'])
                encoded_detail=esc(json.dumps(detail,ensure_ascii=False),quote=True)
                chunks.append(f'<rect tabindex="0" data-category="{cat}" data-info="{encoded_detail}" class="{"container hidden" if container else "segment"}" x="{x}" y="{y}" width="{x2-x}" height="{y2-y}" stroke="{COLORS[cat]}" fill="{COLORS[cat]}"><title>{esc(cat+": "+r.get("text","")[:180])}</title></rect>')
            if parser=='automatic':
                byid={r['id']:r for r in p['records']}
                for g in p['groups']:
                    caption=byid[g['caption']]['bbox'];cx=(caption[0]+caption[2])/2;cy=(caption[1]+caption[3])/2
                    for member in g['members']:
                        x,y,x2,y2=byid[member]['bbox']
                        chunks.append(f'<g class="group"><rect x="{x}" y="{y}" width="{x2-x}" height="{y2-y}"/><line x1="{(x+x2)/2}" y1="{(y+y2)/2}" x2="{cx}" y2="{cy}"/></g>')
            chunks.append('</svg></div></article>')
        chunks.append('</div><details><summary>Decisiones, conflictos y procedencia</summary><pre>'+esc(json.dumps(dict(groups=p['groups'],decisions=p['decisions'],incidents=p['incidents']),ensure_ascii=False,indent=2))+'</pre></details></section>')
    chunks.append('''<h2 style="font-size:15px">Objeto seleccionado</h2><pre id="inspector">Selecciona una región para ver su categoría, fuente y contenido.</pre></main><footer>Automática conserva la base MinerU y añade relaciones. TATR y LM permanecen como evidencia. La salida humana anterior se conserva por separado; no se utilizó para generar decisiones.</footer><script>
const selector=document.querySelector('#page'),pages=[...document.querySelectorAll('.page')];
function show(){pages.forEach((p,i)=>p.hidden=i!==Number(selector.value));document.querySelector('#prev').disabled=selector.selectedIndex===0;document.querySelector('#next').disabled=selector.selectedIndex===pages.length-1;}
selector.addEventListener('change',show);for(const [id,delta] of [['prev',-1],['next',1]])document.querySelector('#'+id).addEventListener('click',()=>{selector.selectedIndex=Math.max(0,Math.min(pages.length-1,selector.selectedIndex+delta));show()});
function filters(){const allowed=new Set([...document.querySelectorAll('[data-filter]:checked')].map(x=>x.dataset.filter));document.querySelectorAll('[data-category]').forEach(r=>r.classList.toggle('hidden',!allowed.has(r.dataset.category)||(r.classList.contains('container')&&!document.querySelector('#containers').checked)));document.querySelectorAll('.group').forEach(r=>r.classList.toggle('hidden',!document.querySelector('#groups').checked));}
document.querySelectorAll('input').forEach(x=>x.addEventListener('change',filters));
function inspect(e){const target=e.target.closest('[data-info]');if(target)document.querySelector('#inspector').textContent=JSON.stringify(JSON.parse(target.dataset.info),null,2);}
document.addEventListener('click',inspect);document.addEventListener('keydown',e=>{if(e.key==='Enter')inspect(e)});show();filters();
</script></html>''')
    return ''.join(chunks)


def export(evaluation, destination):
    data=load_evaluation(evaluation)
    result=dict(schema_version='autonomous-document/1',rule_version=VERSION,pages=[reconcile(p) for p in data['pages']],
                parser_configuration=data['parser_configuration'],validation='development_regression_not_cross_paper_validation')
    images={p['identity']['physical_page']:'data:image/png;base64,'+base64.b64encode(Path(p['render_path']).read_bytes() if Path(p['render_path']).is_file() else b'').decode() for p in result['pages']}
    files={'document.json':encoded(result),'review.html':render_html(result,images).encode('utf-8')}
    code={str(p.resolve()):digest(p.read_bytes()) for p in Path(__file__).parent.glob('*.py') if not p.name.startswith('test_')}
    manifest=dict(source_inputs=data['source_inputs'],code=code,outputs={p:digest(raw) for p,raw in files.items()},
                  automated_groups=sum(len(p['groups']) for p in result['pages']),new_inference=False,human_decisions_consumed=False)
    files['manifest.json']=encoded(manifest)
    destination=Path(destination).resolve()
    if destination.exists():
        if any(not (destination/name).is_file() or (destination/name).read_bytes()!=raw for name,raw in files.items()):raise ValueError('Existing destination differs; never overwrite')
    else:
        # Inputs are rechecked after processing, before any publication.
        if any(digest(Path(p).read_bytes())!=sha for p,sha in data['source_inputs'].items()):raise ValueError('Source changed during export')
        destination.mkdir(parents=True,exist_ok=False)
        for name,raw in files.items():
            with (destination/name).open('xb') as stream:stream.write(raw)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evaluation');parser.add_argument('destination')
    args=parser.parse_args();result=export(args.evaluation,args.destination)
    print(json.dumps(dict(pages=len(result['pages']),groups=sum(len(p['groups']) for p in result['pages'])),indent=2))
